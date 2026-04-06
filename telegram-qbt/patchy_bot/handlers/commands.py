"""Slash-command handlers and report generators.

Extracted from BotApp using the Strangler Fig pattern.

Module-level functions that are fully ctx-portable
---------------------------------------------------
- ``health_report(ctx)``  — assembles the /health text, returns (text, ok)
- ``speed_report(ctx)``   — assembles the /speed text, returns str
- ``on_error(update, context)`` — error handler (logging only)

Slash-command functions that still delegate to BotApp helpers
-------------------------------------------------------------
These take ``bot`` (the BotApp instance) plus the Telegram ``update`` and
``context`` objects.  They are thin wrappers so the logic can live here and
the BotApp stubs stay tiny.

Functions
---------
- ``cmd_start``           — clear flow, open Command Center
- ``cmd_search``          — parse flags, call bot._run_search
- ``cmd_schedule``        — open schedule flow or show schedule menu
- ``cmd_remove``          — open remove search prompt
- ``cmd_show``            — display a saved search page
- ``cmd_add``             — add a search result to qBittorrent
- ``cmd_categories``      — show qBittorrent category routing
- ``cmd_mkcat``           — create a new qBittorrent category
- ``cmd_setminseeds``     — update default min-seeds for user
- ``cmd_setlimit``        — update default result limit for user
- ``cmd_profile``         — show current user profile / status
- ``cmd_active``          — show active downloads + tracked shows
- ``cmd_plugins``         — list installed qBittorrent search plugins
- ``cmd_help``            — show help text
- ``cmd_health``          — run health_report, reply to user
- ``cmd_speed``           — run speed_report, reply to user
- ``cmd_unlock``          — password unlock flow
- ``cmd_logout``          — lock session
- ``cmd_text_fallback``   — /start or /help sent as plain text
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import shlex
from typing import TYPE_CHECKING, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from ..types import HandlerContext
from ..utils import (
    _PM,
    _h,
    format_local_ts,
    human_size,
    now_ts,
    parse_size_to_bytes,
)
from . import download as download_handler
from ._shared import (
    ensure_media_categories as _ensure_media_categories,
)
from ._shared import (
    qbt_category_aliases as _qbt_category_aliases,
)
from ._shared import (
    qbt_transport_status as _qbt_transport_status,
)

if TYPE_CHECKING:
    pass  # BotApp is referenced via Any to avoid circular imports

LOG = logging.getLogger("qbtg")


# ---------------------------------------------------------------------------
# health_report — fully ctx-portable
# ---------------------------------------------------------------------------


def health_report(ctx: HandlerContext) -> tuple[str, bool]:
    """Build the /health status report.

    Args:
        ctx: Handler context with all clients and config.

    Returns:
        A ``(html_text, overall_ok)`` tuple.  ``overall_ok`` is False if any
        hard failure is detected (VPN warning is a soft warning, not a hard
        failure).
    """
    hard_failures: list[str] = []
    warnings: list[str] = []
    lines: list[str] = []

    # Storage + category routing
    try:
        routing_ok, routing_reason = _ensure_media_categories(ctx)
    except Exception as e:
        routing_ok, routing_reason = False, str(e)
    if not routing_ok:
        hard_failures.append(f"routing/storage not ready ({routing_reason})")
    lines.append(f"routing/storage: {'ready' if routing_ok else 'blocked'} ({routing_reason})")

    # qBittorrent transport
    try:
        transport_ok, transport_reason = _qbt_transport_status(ctx)
    except Exception as e:
        transport_ok, transport_reason = False, str(e)
    if not transport_ok:
        hard_failures.append(f"qBittorrent transport not ready ({transport_reason})")
    lines.append(f"qBittorrent transport: {'ready' if transport_ok else 'blocked'} ({transport_reason})")

    # qBittorrent search plugins
    try:
        plugins = ctx.qbt.list_search_plugins()
        enabled_plugins = sum(1 for row in plugins if bool(row.get("enabled", True)))
        lines.append(f"qBittorrent search: ready ({enabled_plugins} enabled plugins)")
    except Exception as e:
        hard_failures.append(f"qBittorrent search unavailable ({e})")
        lines.append(f"qBittorrent search: blocked ({e})")

    # VPN gate
    try:
        vpn_ok, vpn_reason = download_handler.vpn_ready_for_download(ctx)
    except Exception as e:
        vpn_ok, vpn_reason = False, str(e)
    if not vpn_ok:
        warnings.append(f"vpn gate not ready ({vpn_reason})")
    lines.append(f"vpn gate: {'ready' if vpn_ok else 'blocked'} ({vpn_reason})")

    # Access controls
    if not ctx.cfg.allowed_user_ids:
        warnings.append("allowlist is empty")
    access_mode = "password" if bool(ctx.cfg.access_password) else "allowlist-only"
    lines.append(
        "access controls: "
        f"{len(ctx.cfg.allowed_user_ids)} allowlisted user(s), "
        f"groups {'allowed' if ctx.cfg.allow_group_chats else 'blocked'}, "
        f"mode={access_mode}"
    )

    # Patchy chat
    patchy_state = "disabled"
    if ctx.cfg.patchy_chat_enabled:
        patchy_state = "ready" if ctx.patchy_llm.ready() else "config missing"
        if patchy_state != "ready":
            warnings.append("Patchy chat is enabled but provider config is incomplete")
    lines.append(f"Patchy chat: {patchy_state}")

    # Category alias warnings
    movie_aliases = sorted(_qbt_category_aliases(ctx, ctx.cfg.movies_category, ctx.cfg.movies_path))
    tv_aliases = sorted(_qbt_category_aliases(ctx, ctx.cfg.tv_category, ctx.cfg.tv_path))
    if len(movie_aliases) > 1:
        warnings.append(f"movie path has multiple qB categories mapped: {', '.join(movie_aliases)}")
    if len(tv_aliases) > 1:
        warnings.append(f"tv path has multiple qB categories mapped: {', '.join(tv_aliases)}")

    # Schedule metadata sources
    lines.append(
        "schedule metadata: "
        f"TVMaze active, TMDb {'configured' if bool(ctx.cfg.tmdb_api_key) else 'not configured'}, "
        f"Plex {'configured' if ctx.plex.ready() else 'not configured'}"
    )

    # Schedule runner + DB diagnostics
    try:
        runner_status = ctx.store.get_schedule_runner_status()
        diagnostics = ctx.store.db_diagnostics()
        due_count = ctx.store.count_due_schedule_tracks(now_ts())
        metadata_health = dict(runner_status.get("metadata_source_health_json") or {})
        inventory_health = dict(runner_status.get("inventory_source_health_json") or {})
        last_success_ts = int(runner_status.get("last_success_at") or 0)
        last_success_label = format_local_ts(last_success_ts) if last_success_ts > 0 else "never"
        lines.append(
            "schedule runner: "
            f"last success <code>{last_success_label}</code>, "
            f"overdue {due_count}, "
            f"metadata {metadata_health.get('status') or 'unknown'}, "
            f"inventory {inventory_health.get('status') or 'unknown'}"
        )
        lines.append(
            "schedule storage: "
            f"sqlite {diagnostics.get('sqlite_runtime')} | "
            f"journal={diagnostics.get('journal_mode')} | "
            f"busy_timeout={diagnostics.get('busy_timeout_ms')}ms"
        )
    except Exception as e:
        warnings.append(f"schedule diagnostics unavailable ({e})")

    overall_ok = not hard_failures
    header = f"<b>{'✅ OK' if overall_ok else '⚠️ DEGRADED'}: Telegram qBittorrent Bot Health</b>"
    lines.insert(0, header)
    lines.insert(1, "━━━━━━━━━━━━━━━━━━━━")
    if hard_failures:
        lines.append("<b>Hard failures:</b> " + "; ".join(_h(f) for f in hard_failures))
    if warnings:
        lines.append("<i>Warnings: " + "; ".join(_h(w) for w in warnings) + "</i>")
    return "\n".join(lines), overall_ok


# ---------------------------------------------------------------------------
# speed_report — fully ctx-portable
# ---------------------------------------------------------------------------


def speed_report(ctx: HandlerContext) -> str:
    """Build the /speed dashboard text.

    Args:
        ctx: Handler context with qbt client.

    Returns:
        HTML-formatted speed dashboard string.
    """
    info = ctx.qbt.get_transfer_info()
    prefs = ctx.qbt.get_preferences()

    dl_speed = int(info.get("dl_info_speed", 0) or 0)
    ul_speed = int(info.get("up_info_speed", 0) or 0)
    dl_total = int(info.get("dl_info_data", 0) or 0)
    ul_total = int(info.get("up_info_data", 0) or 0)
    dht_nodes = int(info.get("dht_nodes", 0) or 0)
    connection_status = str(info.get("connection_status") or "unknown")

    dl_limit = int(prefs.get("dl_limit", 0) or 0)
    ul_limit = int(prefs.get("up_limit", 0) or 0)
    max_dl = int(prefs.get("max_active_downloads", 0) or 0)
    max_torrents = int(prefs.get("max_active_torrents", 0) or 0)
    listen_port = int(prefs.get("listen_port", 0) or 0)

    dl_limit_txt = human_size(dl_limit) + "/s" if dl_limit > 0 else "unlimited"
    ul_limit_txt = human_size(ul_limit) + "/s" if ul_limit > 0 else "unlimited"

    try:
        active = ctx.qbt.list_active(limit=50)
        downloading = sum(1 for t in active if not download_handler.is_complete_torrent(t))
        seeding = sum(1 for t in active if download_handler.is_complete_torrent(t))
    except Exception:
        downloading = -1
        seeding = -1

    connectable = (
        "yes"
        if connection_status == "connected"
        else "no"
        if connection_status == "disconnected"
        else connection_status
    )

    lines = [
        "<b>⚡ Speed Dashboard</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"↓ Download: <code>{human_size(dl_speed)}/s</code> (limit: <code>{dl_limit_txt}</code>)",
        f"↑ Upload: <code>{human_size(ul_speed)}/s</code> (limit: <code>{ul_limit_txt}</code>)",
        f"📊 Session: ↓ <code>{human_size(dl_total)}</code> / ↑ <code>{human_size(ul_total)}</code>",
        "",
        f"🔌 Status: <b>{_h(connection_status)}</b>",
        f"🌐 DHT nodes: <code>{dht_nodes}</code>",
        f"🚪 Port <code>{listen_port}</code>: {'connectable' if connectable == 'yes' else _h(connectable)}",
        "",
        f"📥 Active downloads: <b>{downloading if downloading >= 0 else '?'}</b>",
        f"📤 Active seeding: <b>{seeding if seeding >= 0 else '?'}</b>",
        f"⚙️ Max active DL: <code>{max_dl}</code> / Max active torrents: <code>{max_torrents}</code>",
    ]

    if ul_limit == 0:
        lines.extend(
            [
                "",
                "<i>⚠️ Upload is unlimited — this can slow downloads. Set a limit in qBT WebUI → Options → Speed.</i>",
            ]
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# on_error — logging only, no ctx needed
# ---------------------------------------------------------------------------


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unhandled exceptions from the Telegram dispatcher.

    Args:
        update: The Telegram Update object (may be None for background errors).
        context: Telegram context carrying ``context.error``.
    """
    from telegram.error import Conflict, NetworkError, TelegramError

    from ..utils import exception_tuple

    err = context.error
    if isinstance(err, Conflict):
        LOG.warning("Telegram polling conflict detected: another getUpdates consumer was active")
        return
    if isinstance(err, NetworkError):
        LOG.warning("Transient Telegram network error: %s", err)
        return
    if isinstance(err, TelegramError):
        LOG.warning("Telegram API error: %s", err)
        return
    LOG.error("Unhandled bot error: %s", err, exc_info=exception_tuple(err))


# ---------------------------------------------------------------------------
# Slash-command functions — delegate back to BotApp via the ``bot`` parameter
# ---------------------------------------------------------------------------
# These are thin wrappers.  ``bot`` is a BotApp instance, typed as Any to
# avoid a circular import.  The BotApp stubs become one-liners that call here.
# ---------------------------------------------------------------------------


async def cmd_start(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — clear state and open the Command Center.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return

    try:
        uid = update.effective_user.id if update.effective_user else None
    except Exception:
        uid = None
    LOG.info("Handling /start command for user=%s chat=%s", uid, getattr(update.effective_chat, "id", None))
    if uid is not None:
        bot._clear_flow(uid)
        bot._cancel_pending_trackers_for_user(uid)
        bot._stop_command_center_refresh(uid)
        await bot._cleanup_ephemeral_messages(uid, msg.get_bot())

        # Recover CC location from DB if the in-memory dict was lost (e.g. bot restart).
        existing_nav = bot.user_nav_ui.get(uid)
        if not existing_nav:
            db_cc = await asyncio.to_thread(bot.store.get_command_center, uid)
            if db_cc:
                bot.user_nav_ui[uid] = db_cc
                existing_nav = db_cc

        if existing_nav:
            # Delete the old CC message so there's never a duplicate.
            tg_bot = msg.get_bot()
            try:
                await tg_bot.delete_message(
                    chat_id=existing_nav["chat_id"],
                    message_id=existing_nav["message_id"],
                )
            except TelegramError:
                pass
            bot.user_nav_ui.pop(uid, None)

    await bot._send_command_center(msg=msg)


async def cmd_search(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search — parse flags and run a torrent search.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return

    raw = " ".join(context.args or [])
    if not raw:
        await msg.reply_text(
            "Usage: /search <query> [--min-seeds N] [--min-quality 1080] [--limit N] [--sort ...]",
            parse_mode=_PM,
        )
        return

    parser = bot._build_search_parser()
    try:
        args = parser.parse_args(shlex.split(raw))
    except Exception as e:
        await msg.reply_text(f"Search command parse error: {_h(str(e))}", parse_mode=_PM)
        return

    query = " ".join(args.query).strip()
    await bot._run_search(
        update=update,
        query=query,
        plugin=args.plugin,
        search_cat=args.search_cat,
        min_seeds=args.min_seeds,
        min_size=parse_size_to_bytes(args.min_size),
        max_size=parse_size_to_bytes(args.max_size),
        min_quality=args.min_quality,
        sort_key=args.sort,
        order=args.order,
        limit=args.limit,
        media_hint="any",
    )


async def cmd_schedule(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /schedule — open schedule flow or show schedule menu.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return
    uid = update.effective_user.id
    tracks = await asyncio.to_thread(bot.store.list_schedule_tracks, uid, False, 50)
    if tracks:
        enabled = [t for t in tracks if t.get("enabled")]
        paused = [t for t in tracks if not t.get("enabled")]
        text = (
            "<b>🗓️ Schedule</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Monitors your Plex library and auto-queues missing episodes as they air.\n\n"
            f"<b>{len(enabled)}</b> active"
        )
        if paused:
            text += f" · <b>{len(paused)}</b> paused"
        rows: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton("➕ Add New Show", callback_data="sch:addnew"),
                InlineKeyboardButton(f"📋 My Shows ({len(tracks)})", callback_data="sch:myshows"),
            ],
        ]
        rows += bot._nav_footer(back_data="nav:home", include_home=False)
        kb = InlineKeyboardMarkup(rows)
        await bot._render_schedule_ui(uid, msg, None, text, reply_markup=kb)
    else:
        bot._schedule_start_flow(uid)
        flow = bot._get_flow(uid) or {"mode": "schedule", "stage": "await_show", "tracking_mode": "upcoming"}
        await bot._render_schedule_ui(
            uid,
            msg,
            flow,
            "<b>✏️ Type a show name to search</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Monitors your Plex library and auto-queues missing episodes as they air.\n\n"
            "<i>Example: Severance</i>",
        )


async def cmd_remove(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /remove — open the remove search prompt.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return
    uid = update.effective_user.id
    await bot._open_remove_search_prompt(uid, msg)


async def cmd_show(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /show — display a saved search result page.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return
    if len(context.args) < 1:
        await msg.reply_text("Usage: /show <search_id> [page]", parse_mode=_PM)
        return

    sid = context.args[0].strip()
    page = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 1
    payload = bot.store.get_search(update.effective_user.id, sid)
    if not payload:
        await msg.reply_text(
            "<b>⚠️ Search Expired</b>\nThis search session has expired.\n<i>Run a new search to continue.</i>",
            parse_mode=_PM,
        )
        return
    search_meta, rows = payload
    text, markup = bot._render_page(search_meta, rows, page)
    await msg.reply_text(text, reply_markup=markup, disable_web_page_preview=True, parse_mode=_PM)


async def cmd_add(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /add — add a search result to qBittorrent.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return

    if len(context.args) < 2:
        await msg.reply_text("Usage: /add <search_id> <index> <movies|tv>", parse_mode=_PM)
        return

    sid = context.args[0].strip()
    if not context.args[1].isdigit():
        await msg.reply_text("Index must be numeric.", parse_mode=_PM)
        return

    idx = int(context.args[1])
    payload = bot.store.get_search(update.effective_user.id, sid)
    if not payload:
        await msg.reply_text(
            "<b>⚠️ Search Expired</b>\nThis search session has expired.\n<i>Run a new search to continue.</i>",
            parse_mode=_PM,
        )
        return
    choice = bot._normalize_media_choice(context.args[2]) if len(context.args) >= 3 else None
    if choice is None:
        await msg.reply_text(
            f"Select library for result #{idx}:",
            reply_markup=bot._media_picker_keyboard(sid, idx),
            parse_mode=_PM,
        )
        return

    pending_msg = await msg.reply_text(f"⏳ Adding result #{idx} to {choice.title()}…", parse_mode=_PM)
    try:
        out = await bot._do_add(update.effective_user.id, sid, idx, choice)
        await pending_msg.edit_text(out["summary"], parse_mode=_PM)

        if out.get("hash"):
            tracker_msg = await msg.reply_text(
                "<b>📡 Live Monitor Attached</b>\n<i>Tracking download progress…</i>",
                reply_markup=bot._stop_download_keyboard(out["hash"]),
                parse_mode=_PM,
            )
            bot._start_progress_tracker(update.effective_user.id, out["hash"], tracker_msg, out["name"])
        else:
            bot._start_pending_progress_tracker(update.effective_user.id, out["name"], out["category"], msg)
            await msg.reply_text(
                "⏳ Waiting for qBittorrent to assign hash… live monitor will auto-attach.", parse_mode=_PM
            )
        await msg.reply_text("What's next?", reply_markup=bot._command_center_keyboard(), parse_mode=_PM)
    except Exception as e:
        await pending_msg.edit_text(f"Add failed: {_h(str(e))}", parse_mode=_PM)


async def cmd_categories(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /categories — show qBittorrent category routing status.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return
    try:
        await bot._send_categories(msg)
    except Exception as e:
        await msg.reply_text(f"Failed to read categories: {_h(str(e))}", parse_mode=_PM)


async def cmd_mkcat(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /mkcat — create a new qBittorrent category.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return
    if len(context.args) < 1:
        await msg.reply_text("Usage: /mkcat <name> [savepath]", parse_mode=_PM)
        return
    name = context.args[0].strip()
    save = context.args[1].strip() if len(context.args) > 1 else None
    try:
        resp = await asyncio.to_thread(bot.qbt.create_category, name, save)
        await msg.reply_text(f"Category ready: {_h(name)}\nqBittorrent: {_h(str(resp))}", parse_mode=_PM)
    except Exception as e:
        await msg.reply_text(f"Failed to create category: {_h(str(e))}", parse_mode=_PM)


async def cmd_setminseeds(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /setminseeds — update default minimum seeds for the user.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return
    if len(context.args) != 1 or not context.args[0].isdigit():
        await msg.reply_text("Usage: /setminseeds <number>", parse_mode=_PM)
        return
    value = int(context.args[0])
    bot.store.set_defaults(update.effective_user.id, bot.cfg, default_min_seeds=value)
    await msg.reply_text(f"Default minimum seeds set to {value}", parse_mode=_PM)


async def cmd_setlimit(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /setlimit — update default result limit for the user.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return
    if len(context.args) != 1 or not context.args[0].isdigit():
        await msg.reply_text("Usage: /setlimit <1-50>", parse_mode=_PM)
        return
    value = max(1, min(50, int(context.args[0])))
    bot.store.set_defaults(update.effective_user.id, bot.cfg, default_limit=value)
    await msg.reply_text(f"Default result limit set to {value}", parse_mode=_PM)


async def cmd_profile(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile — show current user profile and system status.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return
    d = bot.store.get_defaults(update.effective_user.id, bot.cfg)
    ok, reason = await asyncio.to_thread(bot._storage_status)
    transport_ok, transport_reason = await asyncio.to_thread(bot._qbt_transport_status)
    vpn_ok, vpn_reason = await asyncio.to_thread(bot._vpn_ready_for_download)
    plex_storage_usage = await asyncio.to_thread(bot._plex_storage_display)
    lines = [
        "<b>⚙️ Current Profile</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"• min_seeds: <code>{d['default_min_seeds']}</code>",
        f"• sort/order: <code>{d['default_sort']} {d['default_order']}</code>",
        f"• limit: <code>{d['default_limit']}</code>",
        f"• quality default: <code>{bot.cfg.default_min_quality}p+</code>",
        f"• movies → <code>{_h(bot.cfg.movies_category)}</code> @ <code>{_h(bot.cfg.movies_path)}</code>",
        f"• tv → <code>{_h(bot.cfg.tv_category)}</code> @ <code>{_h(bot.cfg.tv_path)}</code>",
        f"• storage status: <b>{'ready' if ok else 'not ready'}</b> (<code>{_h(reason)}</code>)",
        f"• qB transport: <b>{'ready' if transport_ok else 'blocked'}</b> (<code>{_h(transport_reason)}</code>)",
        f"• plex storage: {plex_storage_usage}",
        f"• vpn gate for downloads: <b>{'ready' if vpn_ok else 'blocked'}</b> (<code>{_h(vpn_reason)}</code>)",
    ]
    await msg.reply_text("\n".join(lines), parse_mode=_PM)


async def cmd_active(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /active — show active downloads and tracked shows.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return
    n = 10
    if context.args and context.args[0].isdigit():
        n = max(1, min(30, int(context.args[0])))
    try:
        await bot._send_active(msg, n=n, user_id=update.effective_user.id if update.effective_user else None)
    except Exception as e:
        await msg.reply_text(f"<b>⚠️ qBittorrent Error</b>\n<i>{_h(str(e))}</i>", parse_mode=_PM)


async def cmd_plugins(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /plugins — list installed qBittorrent search plugins.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return
    try:
        await bot._send_plugins(msg)
    except Exception as e:
        await msg.reply_text(f"Failed to list plugins: {_h(str(e))}", parse_mode=_PM)


async def cmd_help(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help — send help text with command center keyboard.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return
    await msg.reply_text(
        bot._help_text(),
        reply_markup=bot._command_center_keyboard(),
        disable_web_page_preview=True,
        parse_mode=_PM,
    )


async def cmd_health(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /health — run health_report and reply.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if msg:
        report, _ok = await asyncio.to_thread(health_report, bot._ctx)
        await msg.reply_text(report, parse_mode=_PM)


async def cmd_speed(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /speed — run speed_report and reply.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot.is_allowed(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if msg:
        try:
            report = await asyncio.to_thread(speed_report, bot._ctx)
            await msg.reply_text(report, parse_mode=_PM)
        except Exception as e:
            await msg.reply_text(f"Speed check failed: {_h(str(e))}", parse_mode=_PM)


async def cmd_unlock(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /unlock — password-based session unlock.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    msg = update.effective_message
    if not msg:
        return

    if not bot._is_allowlisted(update):
        await bot.deny(update)
        return

    if bot._requires_password() is False:
        await msg.reply_text("Password access control is disabled (allowlist-only mode).", parse_mode=_PM)
        return

    if len(context.args) < 1:
        await msg.reply_text("Usage: /unlock <password>", parse_mode=_PM)
        return

    uid = update.effective_user.id
    if bot.store.is_auth_locked(uid):
        await msg.reply_text("🔒 Too many failed attempts. Try again in a few minutes.", parse_mode=_PM)
        return

    provided = " ".join(context.args).strip()
    if not secrets.compare_digest(provided, bot.cfg.access_password):
        locked = bot.store.record_auth_failure(uid)
        if locked:
            await msg.reply_text("🔒 Too many failed attempts. Locked for 15 minutes.", parse_mode=_PM)
        else:
            await msg.reply_text(
                "<b>❌ Incorrect Password</b>\n<i>Try again or check your configuration.</i>", parse_mode=_PM
            )
        return

    bot.store.clear_auth_failures(uid)
    bot.store.unlock_user(uid, bot.cfg.access_session_ttl_s)
    # Delete the /unlock message containing the password from chat history
    try:
        await msg.delete()
    except Exception:
        pass
    await bot._send_command_center(msg)


async def cmd_logout(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /logout — lock the user session.

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    if not bot._is_allowlisted(update):
        await bot.deny(update)
        return
    msg = update.effective_message
    if not msg:
        return
    uid = update.effective_user.id
    bot.store.lock_user(uid)
    await msg.reply_text("<b>🔒 Session Locked</b>\n<i>Use /unlock &lt;password&gt; when needed.</i>", parse_mode=_PM)


async def cmd_text_fallback(bot: Any, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start or /help sent as plain text (e.g. in groups).

    Args:
        bot: BotApp instance.
        update: Telegram Update.
        context: Telegram context.
    """
    msg = update.effective_message
    if not msg or not msg.text:
        return
    raw = msg.text.strip().lower()
    LOG.info("Handling text fallback command raw=%s chat=%s", raw, getattr(update.effective_chat, "id", None))
    if raw.startswith("/start"):
        await cmd_start(bot, update, context)
        return
    if raw.startswith("/help"):
        await cmd_help(bot, update, context)
        return


# ---------------------------------------------------------------------------
# Callback handlers: menu and flow
# ---------------------------------------------------------------------------


async def on_cb_menu(bot_app: Any, *, data: str, q: Any, user_id: int) -> None:
    """Handle ``menu:*`` callback queries — Command Center navigation."""
    ctx = getattr(bot_app, "_ctx", bot_app)
    if data == "menu:movie":
        bot_app._set_flow(user_id, {"mode": "movie", "stage": "await_title"})
        text = (
            "<b>\U0001f3ac Movie Search</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send the movie title to search.\n\n"
            "<i>Example: Dune Part Two</i>"
        )
        kb = InlineKeyboardMarkup(bot_app._nav_footer(back_data="nav:home", include_home=False))
        await bot_app._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)
        return

    if data == "menu:tv":
        flow = {"mode": "tv", "stage": "await_filter_choice", "season": None, "episode": None}
        bot_app._set_flow(user_id, flow)
        await bot_app._render_tv_ui(
            user_id,
            q.message,
            flow,
            bot_app._tv_filter_choice_text(),
            reply_markup=bot_app._tv_filter_choice_keyboard(),
            current_ui_message=q.message,
        )
        return

    if data == "menu:schedule":
        tracks = await asyncio.to_thread(ctx.store.list_schedule_tracks, user_id, False, 50)
        if tracks:
            enabled = [t for t in tracks if t.get("enabled")]
            paused = [t for t in tracks if not t.get("enabled")]
            text = (
                "<b>\U0001f5d3\ufe0f Schedule</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Monitors your Plex library and auto-queues missing episodes as they air.\n\n"
                f"<b>{len(enabled)}</b> active"
            )
            if paused:
                text += f" \u00b7 <b>{len(paused)}</b> paused"
            rows: list[list[InlineKeyboardButton]] = [
                [
                    InlineKeyboardButton("\u2795 Add New Show", callback_data="sch:addnew"),
                    InlineKeyboardButton(f"\U0001f4cb My Shows ({len(tracks)})", callback_data="sch:myshows"),
                ],
            ]
            rows += bot_app._nav_footer(back_data="nav:home", include_home=False)
            kb = InlineKeyboardMarkup(rows)
            await bot_app._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)
        else:
            bot_app._schedule_start_flow(user_id)
            text = (
                "<b>\u270f\ufe0f Type a show name to search</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Monitors your Plex library and auto-queues missing episodes as they air.\n\n"
                "<i>Example: Severance</i>"
            )
            kb = InlineKeyboardMarkup(bot_app._nav_footer(back_data="nav:home", include_home=False))
            await bot_app._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)
        return

    if data == "menu:remove":
        await bot_app._open_remove_browse_root(user_id, q.message, current_ui_message=q.message)
        return

    if data == "menu:active":
        await bot_app._render_active_ui(user_id, q.message, n=10, current_ui_message=q.message)
        return

    if data == "menu:storage":
        await bot_app._render_categories_ui(user_id, q.message, current_ui_message=q.message)
        return

    if data == "menu:plugins":
        await bot_app._render_plugins_ui(user_id, q.message, current_ui_message=q.message)
        return

    if data == "menu:profile":
        d = ctx.store.get_defaults(user_id, ctx.cfg)
        ok, reason = await asyncio.to_thread(bot_app._storage_status)
        transport_ok, transport_reason = await asyncio.to_thread(bot_app._qbt_transport_status)
        vpn_ok, vpn_reason = await asyncio.to_thread(bot_app._vpn_ready_for_download)
        plex_storage_usage = await asyncio.to_thread(bot_app._plex_storage_display)
        lines = [
            "Current profile:",
            f"\u2022 min_seeds: {d['default_min_seeds']}",
            f"\u2022 sort/order: {d['default_sort']} {d['default_order']}",
            f"\u2022 limit: {d['default_limit']}",
            f"\u2022 quality default: {ctx.cfg.default_min_quality}p+",
            f"\u2022 movies -> {ctx.cfg.movies_category} @ {ctx.cfg.movies_path}",
            f"\u2022 tv -> {ctx.cfg.tv_category} @ {ctx.cfg.tv_path}",
            f"\u2022 storage status: {'ready' if ok else 'not ready'} ({reason})",
            f"\u2022 qB transport: {'ready' if transport_ok else 'blocked'} ({transport_reason})",
            f"\u2022 plex storage: {plex_storage_usage}",
            f"\u2022 vpn gate for downloads: {'ready' if vpn_ok else 'blocked'} ({vpn_reason})",
        ]
        text = "\n".join(lines)
        kb = InlineKeyboardMarkup(bot_app._nav_footer())
        await bot_app._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)
        return

    if data == "menu:help":
        text = bot_app._help_text()
        kb = InlineKeyboardMarkup(bot_app._nav_footer())
        await bot_app._render_nav_ui(
            user_id,
            q.message,
            text,
            reply_markup=kb,
            disable_web_page_preview=True,
            current_ui_message=q.message,
        )
        return


async def on_cb_flow(bot_app: Any, *, data: str, q: Any, user_id: int) -> None:
    """Handle ``flow:*`` callback queries — TV search flow transitions."""
    if data == "flow:tv_filter_set":
        flow = {"mode": "tv", "stage": "await_filter", "season": None, "episode": None}
        bot_app._set_flow(user_id, flow)
        await bot_app._render_tv_ui(
            user_id,
            q.message,
            flow,
            bot_app._tv_filter_prompt_text(),
            reply_markup=InlineKeyboardMarkup(bot_app._nav_footer(back_data="menu:tv")),
            current_ui_message=q.message,
        )
        return

    if data == "flow:tv_filter_skip":
        flow = {"mode": "tv", "stage": "await_title", "season": None, "episode": None}
        bot_app._set_flow(user_id, flow)
        await bot_app._render_tv_ui(
            user_id,
            q.message,
            flow,
            bot_app._tv_title_prompt_text(),
            reply_markup=InlineKeyboardMarkup(bot_app._nav_footer(back_data="menu:tv")),
            current_ui_message=q.message,
        )
        return

    if data == "flow:tv_full_series":
        flow = {"mode": "tv", "stage": "await_title", "season": None, "episode": None, "full_series": True}
        bot_app._set_flow(user_id, flow)
        await bot_app._render_tv_ui(
            user_id,
            q.message,
            flow,
            "<b>\U0001f4fa TV Search \u2014 Full Series</b>\n\n"
            "Send the show title to search.\n"
            "Results will prioritize complete series downloads.\n\n"
            "<i>Example: Severance</i>",
            reply_markup=InlineKeyboardMarkup(bot_app._nav_footer(back_data="menu:tv")),
            current_ui_message=q.message,
        )
        return
