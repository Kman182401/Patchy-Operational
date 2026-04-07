"""Telegram bot application — command handlers, callback router, and lifecycle."""

from __future__ import annotations

import argparse
import asyncio
import collections
import concurrent.futures
import logging
import math
import os
import re
import secrets
import threading
from datetime import time as dt_time
from typing import Any

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .clients.llm import PatchyLLMClient
from .clients.plex import PlexInventoryClient
from .clients.qbittorrent import QBClient
from .clients.tv_metadata import TVMetadataClient
from .config import Config
from .dispatch import CallbackDispatcher
from .handlers import _shared
from .handlers import chat as chat_handler
from .handlers import commands as commands_handler
from .handlers import download as download_handler
from .handlers import remove as remove_handler
from .handlers import schedule as schedule_handler
from .handlers import search as search_handler
from .quality import score_torrent
from .rate_limiter import RateLimiter
from .store import Store
from .types import HandlerContext
from .ui import flow as flow_mod
from .ui import keyboards as kb_mod
from .ui import rendering as render_mod
from .ui import text as text_mod
from .utils import (
    _ACTIVE_DL_STATES,
    _PM,
    _h,
    _relative_time,
    episode_code,
    episode_number_from_code,
    extract_episode_codes,
    format_local_ts,
    human_size,
    normalize_title,
    now_ts,
)

LOG = logging.getLogger("qbtg")


class BotApp:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.qbt = QBClient(cfg.qbt_base_url, cfg.qbt_username, cfg.qbt_password)
        self.store = Store(cfg.db_path)
        self.user_flow: dict[int, dict[str, Any]] = {}
        self.user_nav_ui: dict[int, dict[str, int]] = {}
        # LRU-bounded chat history: keyed by user_id, max CHAT_HISTORY_MAX_USERS entries.
        # OrderedDict move_to_end on access gives O(1) LRU eviction.
        self.chat_history: collections.OrderedDict[int, list[dict[str, str]]] = collections.OrderedDict()
        _chat_max = max(10, int(os.getenv("CHAT_HISTORY_MAX_USERS", "50")))
        self._chat_history_max_users: int = _chat_max
        self.progress_tasks: dict[tuple[int, str], asyncio.Task] = {}
        self.pending_tracker_tasks: dict[tuple[int, str, str], asyncio.Task] = {}
        self.user_ephemeral_messages: dict[int, list[dict[str, int]]] = {}
        self.command_center_refresh_tasks: dict[int, asyncio.Task] = {}
        if cfg.patchy_chat_enabled:
            self.patchy_llm = PatchyLLMClient(
                cfg.patchy_llm_base_url, cfg.patchy_llm_api_key, timeout_s=cfg.patchy_chat_timeout_s
            )
        else:
            self.patchy_llm = PatchyLLMClient(None, None, timeout_s=cfg.patchy_chat_timeout_s)
        self.tvmeta = TVMetadataClient(cfg.tmdb_api_key)
        self.plex = PlexInventoryClient(cfg.plex_base_url, cfg.plex_token, cfg.tv_path)
        self.schedule_runner_lock = asyncio.Lock()
        self.remove_runner_lock = asyncio.Lock()
        self.schedule_source_state_lock = threading.Lock()
        self.schedule_source_state: dict[str, dict[str, Any]] = {
            "metadata": {
                "status": "unknown",
                "consecutive_failures": 0,
                "backoff_until": 0,
                "last_error": None,
                "last_success_at": None,
            },
            "inventory": {
                "status": "unknown",
                "consecutive_failures": 0,
                "backoff_until": 0,
                "last_error": None,
                "last_success_at": None,
                "effective_source": "unknown",
            },
        }
        self.app: Application | None = None
        # Per-user rate limiter: default 20 commands per 60s, configurable via env
        _rl_limit = max(5, int(os.getenv("RATE_LIMIT_COMMANDS", "20")))
        _rl_window = max(10.0, float(os.getenv("RATE_LIMIT_WINDOW_S", "60.0")))
        self.rate_limiter = RateLimiter(limit=_rl_limit, window_s=_rl_window)
        # Protects shared mutable dicts under concurrent_updates=True
        self._state_lock = asyncio.Lock()
        self._dispatcher = CallbackDispatcher()
        self._register_callbacks()
        self._ctx = HandlerContext(
            cfg=self.cfg,
            store=self.store,
            qbt=self.qbt,
            plex=self.plex,
            tvmeta=self.tvmeta,
            patchy_llm=self.patchy_llm,
            rate_limiter=self.rate_limiter,
            user_flow=self.user_flow,
            user_nav_ui=self.user_nav_ui,
            progress_tasks=self.progress_tasks,
            pending_tracker_tasks=self.pending_tracker_tasks,
            user_ephemeral_messages=self.user_ephemeral_messages,
            command_center_refresh_tasks=self.command_center_refresh_tasks,
            chat_history=self.chat_history,
            chat_history_max_users=self._chat_history_max_users,
            schedule_source_state=self.schedule_source_state,
            schedule_source_state_lock=self.schedule_source_state_lock,
            schedule_runner_lock=self.schedule_runner_lock,
            remove_runner_lock=self.remove_runner_lock,
            state_lock=self._state_lock,
        )
        self._ctx.render_command_center = self._render_command_center
        self._ctx.navigate_to_command_center = self._navigate_to_command_center

    # ---------- Callback dispatcher registration ----------

    def _register_callbacks(self) -> None:
        d = self._dispatcher
        d.register_exact("nav:home", self._on_cb_nav_home)
        d.register_prefix("a:", self._on_cb_add)
        d.register_prefix("d:", self._on_cb_download)
        d.register_prefix("p:", self._on_cb_page)
        d.register_prefix("rm:", self._on_cb_remove)
        d.register_prefix("sch:", self._on_cb_schedule)
        d.register_prefix("msch:", self._on_cb_movie_schedule)
        d.register_prefix("menu:", self._on_cb_menu)
        d.register_prefix("flow:", self._on_cb_flow)
        d.register_exact("dl:manage", self._on_cb_dl_manage)
        d.register_prefix("stop:", self._on_cb_stop)

    # ---------- Telegram command discovery ----------

    async def _post_init(self, app: Application) -> None:
        commands = [
            BotCommand("start", "Open command center"),
        ]
        try:
            await app.bot.delete_my_commands()
            await app.bot.set_my_commands(commands)
            LOG.info("Telegram command list registered")
        except Exception:
            LOG.warning("Failed to register Telegram command list", exc_info=True)

        await self._schedule_bootstrap(app)

        # Explicit thread pool for asyncio.to_thread() calls (search, qBT API, SQLite).
        #
        # Current: 8 workers. Adequate for single-user deployment.
        #
        # Each search blocks a thread for up to 90s (qBT search polling).
        # Progress trackers poll qBT every ~1s via to_thread (brief thread use).
        # SQLite operations are fast but also use to_thread.
        #
        # Saturation scenario: 8 concurrent searches would exhaust the pool,
        # blocking progress trackers and SQLite ops. Unlikely for single user.
        #
        # If concurrent_updates is enabled or multi-user support is added,
        # increase to 16-32 workers. Monitor with asyncio debug logging.
        loop = asyncio.get_running_loop()
        loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=8))

        # Daily database backup at 3:00 AM local time (if BACKUP_DIR is configured)
        if self.cfg.backup_dir:
            self.app.job_queue.run_daily(
                self._backup_job,
                time=dt_time(3, 0, 0),
                name="daily-db-backup",
            )
            LOG.info("Database backup scheduled daily at 03:00 → %s", self.cfg.backup_dir)

        # Daily health event cleanup at 4:00 AM
        self.app.job_queue.run_daily(
            self._health_event_cleanup_job,
            time=dt_time(4, 0, 0),
            name="health-event-cleanup",
        )

        # Periodic qBittorrent connectivity check (every 5 minutes)
        self.app.job_queue.run_repeating(
            self._qbt_health_check_job,
            interval=300,
            first=300,
            name="qbt-health-check",
            job_kwargs={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60},
        )

        # Verify qBittorrent connectivity at startup
        await self._ensure_qbt_connectivity()

        await self._recover_missed_completions()

    async def _recover_missed_completions(self) -> None:
        """Check for downloads that completed while bot was offline."""
        import json as _json

        from .plex_organizer import organize_download

        try:
            torrents = await asyncio.to_thread(self._ctx.qbt.list_torrents, filter_name="completed", limit=200)
            if not torrents:
                return
            recovered = 0
            for torrent in torrents:
                t_hash = str(torrent.get("hash") or "").strip().lower()
                if not t_hash:
                    continue
                # Skip if already notified
                already = await asyncio.to_thread(self._ctx.store.is_completion_notified, t_hash)
                if already:
                    continue
                name = str(torrent.get("name") or "Unknown")
                category = str(torrent.get("category") or "")
                size = int(torrent.get("total_size", 0) or torrent.get("size", 0) or 0)
                completion_on = int(torrent.get("completion_on", 0) or 0)
                # Only recover completions from last 24 hours
                if completion_on > 0 and (now_ts() - completion_on) > 86400:
                    continue
                LOG.info("Recovered missed completion: %s (%s)", name, t_hash[:8])
                # Mark as notified FIRST to prevent duplicates
                await asyncio.to_thread(self._ctx.store.mark_completion_notified, t_hash, name)
                # Organize download
                media_path = str(torrent.get("content_path") or torrent.get("save_path") or "").strip()
                if category and media_path:
                    try:
                        org_result = await asyncio.to_thread(
                            organize_download,
                            media_path,
                            category,
                            self._ctx.cfg.tv_path,
                            self._ctx.cfg.movies_path,
                        )
                        if org_result.moved:
                            media_path = org_result.new_path
                    except Exception as e:
                        LOG.error("Organize failed for recovered torrent %s: %s", name, e)
                # Notify the requesting user, or all allowed users if unknown
                stored_uid = await asyncio.to_thread(self._ctx.store.get_completion_user_id, t_hash)
                notify_uids = {stored_uid} if stored_uid > 0 else set(self._ctx.cfg.allowed_user_ids)
                for uid in notify_uids:
                    try:
                        await self._ctx.app.bot.send_message(
                            chat_id=uid,
                            text=(
                                f"\u2705 <b>Download Complete</b> (recovered)\n\n"
                                f"<code>{_h(name)}</code>\n"
                                f"Size: {human_size(size)}\n"
                                f"Category: {_h(category)}\n\n"
                                f"<i>This download completed while the bot was offline.</i>"
                            ),
                            parse_mode=_PM,
                        )
                    except Exception:
                        pass
                try:
                    self._ctx.store.log_health_event(
                        0,
                        t_hash,
                        "completion_crash_recovered",
                        "info",
                        _json.dumps({"name": name, "category": category}),
                        name,
                    )
                except Exception:
                    pass
                recovered += 1
            if recovered:
                LOG.info("Recovered %d missed completion(s)", recovered)
        except Exception:
            LOG.error("Completion recovery failed", exc_info=True)

    async def _post_stop(self, app: Application) -> None:
        tasks: list[asyncio.Task] = []
        seen: set[int] = set()

        def collect(task: asyncio.Task | None) -> None:
            if task is None or task.done():
                return
            ident = id(task)
            if ident in seen:
                return
            seen.add(ident)
            tasks.append(task)

        for task in self.progress_tasks.values():
            collect(task)
        for task in self.pending_tracker_tasks.values():
            collect(task)
        for task in self.command_center_refresh_tasks.values():
            collect(task)
        for task in self._ctx.background_tasks:
            collect(task)

        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self.progress_tasks.clear()
        self.pending_tracker_tasks.clear()
        self.command_center_refresh_tasks.clear()
        self._ctx.background_tasks.clear()

        # Close HTTP session pools to release file descriptors cleanly
        for client in (self.qbt, self.patchy_llm, self.tvmeta, self.plex):
            sess = getattr(client, "session", None)
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass

        # Close persistent SQLite connection
        try:
            self.store.close()
        except Exception:
            pass

    # ---------- Routing + storage ----------

    def _targets(self) -> dict[str, dict[str, str]]:
        return _shared.targets(getattr(self, "_ctx", self))

    def _normalize_media_choice(self, value: str | None) -> str | None:
        return _shared.normalize_media_choice(value)

    @staticmethod
    def _norm_path(value: str | None) -> str:
        return _shared.norm_path(value)

    def _qbt_category_aliases(self, primary_category: str, save_path: str) -> set[str]:
        return _shared.qbt_category_aliases(getattr(self, "_ctx", self), primary_category, save_path)

    def _storage_status(self) -> tuple[bool, str]:
        return _shared.storage_status(getattr(self, "_ctx", self))

    @staticmethod
    def _check_free_space(
        target_path: str, warn_bytes: int = 10 * 1024**3, block_bytes: int = 5 * 1024**3
    ) -> tuple[bool, str]:
        return _shared.check_free_space(target_path, warn_bytes, block_bytes)

    def _qbt_transport_status(self) -> tuple[bool, str]:
        return _shared.qbt_transport_status(getattr(self, "_ctx", self))

    def _ensure_media_categories(self) -> tuple[bool, str]:
        return _shared.ensure_media_categories(getattr(self, "_ctx", self))

    # ---------- Access + session flow ----------

    def _is_allowlisted(self, update: Update) -> bool:
        uid = update.effective_user.id if update.effective_user else None
        if uid is None:
            return False
        if self.cfg.allowed_user_ids and uid not in self.cfg.allowed_user_ids:
            return False
        if not self.cfg.allow_group_chats:
            chat = update.effective_chat
            if chat and chat.type != "private":
                return False
        return True

    def _requires_password(self) -> bool:
        return bool(self.cfg.access_password)

    def is_allowed(self, update: Update) -> bool:
        if not self._is_allowlisted(update):
            return False
        uid = update.effective_user.id if update.effective_user else None
        if uid is None:
            return False
        # Rate limit allowlisted users to prevent abuse from a compromised account
        if not self.rate_limiter.is_allowed(uid):
            LOG.warning("Rate limit exceeded for user %s", uid)
            return False
        if not self._requires_password():
            return True
        return self.store.is_unlocked(uid)

    async def deny(self, update: Update) -> None:
        uid = update.effective_user.id if update.effective_user else None
        if not self._is_allowlisted(update):
            html_msg = "⛔ Access denied for this Telegram user/chat."
            plain_msg = "Access denied."
        elif uid is not None and not self.rate_limiter._check_within_limit(uid):
            html_msg = "<b>⏱ Slow down</b>\n<i>Too many requests. Wait a moment before trying again.</i>"
            plain_msg = "Too many requests. Please wait."
        elif self._requires_password():
            html_msg = "<b>🔒 Access Locked</b>\nSend the password directly, or use /unlock &lt;password&gt;."
            plain_msg = "🔒 Access locked. Send the password or use /unlock."
        else:
            html_msg = "⛔ Access denied."
            plain_msg = "Access denied."

        if update.effective_message:
            await update.effective_message.reply_text(html_msg, parse_mode=_PM)
        elif update.callback_query:
            await update.callback_query.answer(plain_msg[:200], show_alert=True)

    def _set_flow(self, user_id: int, payload: dict[str, Any]) -> None:
        flow_mod.set_flow(self._ctx, user_id, payload)

    def _get_flow(self, user_id: int) -> dict[str, Any] | None:
        return flow_mod.get_flow(self._ctx, user_id)

    def _clear_flow(self, user_id: int) -> None:
        flow_mod.clear_flow(self._ctx, user_id)

    def _remember_nav_ui_message(self, user_id: int, message: Any) -> None:
        render_mod.remember_nav_ui_message(getattr(self, "_ctx", self), user_id, message)

    def _track_ephemeral_message(self, user_id: int, message: Any) -> None:
        render_mod.track_ephemeral_message(getattr(self, "_ctx", self), user_id, message)

    def _cancel_pending_trackers_for_user(self, user_id: int) -> None:
        """Cancel pending tracker tasks for this user so they don't create monitor messages after home cleanup."""
        render_mod.cancel_pending_trackers_for_user(self._ctx, user_id)

    async def _delete_old_nav_ui(self, user_id: int, bot: Any) -> None:
        """Delete the previous nav-UI message (e.g. old Command Center) so /start shows a clean chat."""
        await render_mod.delete_old_nav_ui(self._ctx, user_id, bot)

    async def _cleanup_ephemeral_messages(self, user_id: int, bot: Any) -> None:
        await render_mod.cleanup_ephemeral_messages(getattr(self, "_ctx", self), user_id, bot)

    async def _strip_old_keyboard(self, bot: Any, chat_id: int, message_id: int) -> None:
        """Remove the inline keyboard from an old message so only one interactive bubble exists.

        Logic lives in ui/rendering.py as ``strip_old_keyboard``; this method is
        kept for backward compatibility with tests that reference BotApp._strip_old_keyboard.
        """
        await render_mod.strip_old_keyboard(bot, chat_id, message_id)

    async def _render_nav_ui(
        self,
        user_id: int,
        anchor_message: Any,
        text: str,
        *,
        reply_markup: InlineKeyboardMarkup | None = None,
        disable_web_page_preview: bool = True,
        current_ui_message: Any | None = None,
    ) -> Any:
        ctx = getattr(self, "_ctx", self)
        return await render_mod.render_nav_ui(
            ctx,
            user_id,
            anchor_message,
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
            current_ui_message=current_ui_message,
        )

    def _remember_flow_ui_message(self, user_id: int, flow: dict[str, Any] | None, message: Any, flow_key: str) -> None:
        render_mod.remember_flow_ui_message(getattr(self, "_ctx", self), user_id, flow, message, flow_key)

    async def _render_flow_ui(
        self,
        user_id: int,
        anchor_message: Any,
        flow: dict[str, Any] | None,
        text: str,
        *,
        flow_key: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        disable_web_page_preview: bool = True,
        current_ui_message: Any | None = None,
    ) -> Any:
        ctx = getattr(self, "_ctx", self)
        return await render_mod.render_flow_ui(
            ctx,
            user_id,
            anchor_message,
            flow,
            text,
            flow_key=flow_key,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
            current_ui_message=current_ui_message,
        )

    async def _render_remove_ui(
        self,
        user_id: int,
        anchor_message: Any,
        flow: dict[str, Any] | None,
        text: str,
        *,
        reply_markup: InlineKeyboardMarkup | None = None,
        disable_web_page_preview: bool = True,
        current_ui_message: Any | None = None,
    ) -> Any:
        ctx = getattr(self, "_ctx", self)
        return await render_mod.render_remove_ui(
            ctx,
            user_id,
            anchor_message,
            flow,
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
            current_ui_message=current_ui_message,
        )

    async def _render_schedule_ui(
        self,
        user_id: int,
        anchor_message: Any,
        flow: dict[str, Any] | None,
        text: str,
        *,
        reply_markup: InlineKeyboardMarkup | None = None,
        disable_web_page_preview: bool = True,
        current_ui_message: Any | None = None,
    ) -> Any:
        ctx = getattr(self, "_ctx", self)
        return await render_mod.render_schedule_ui(
            ctx,
            user_id,
            anchor_message,
            flow,
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
            current_ui_message=current_ui_message,
        )

    async def _render_tv_ui(
        self,
        user_id: int,
        anchor_message: Any,
        flow: dict[str, Any] | None,
        text: str,
        *,
        reply_markup: InlineKeyboardMarkup | None = None,
        disable_web_page_preview: bool = True,
        current_ui_message: Any | None = None,
    ) -> Any:
        ctx = getattr(self, "_ctx", self)
        return await render_mod.render_tv_ui(
            ctx,
            user_id,
            anchor_message,
            flow,
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
            current_ui_message=current_ui_message,
        )

    async def _cleanup_private_user_message(self, message: Any) -> None:
        await render_mod.cleanup_private_user_message(message)

    # ---------- Live progress (delegated to handlers.download) ----------

    @staticmethod
    def _progress_bar(progress_pct: float, width: int = 18) -> str:
        return download_handler.progress_bar(progress_pct, width)

    @staticmethod
    def _completed_bytes(info: dict[str, Any]) -> int:
        return download_handler.completed_bytes(info)

    @staticmethod
    def _is_complete_torrent(info: dict[str, Any]) -> bool:
        return download_handler.is_complete_torrent(info)

    @staticmethod
    def _format_eta(eta_seconds: int) -> str:
        return download_handler.format_eta(eta_seconds)

    @staticmethod
    def _state_label(info: dict[str, Any]) -> str:
        return download_handler.state_label(info)

    @classmethod
    def _eta_label(cls, info: dict[str, Any]) -> str:
        return download_handler.eta_label(info)

    def _render_progress_text(
        self,
        name: str,
        info: dict[str, Any],
        tick: int,
        *,
        progress_pct: float | None = None,
        dls_bps: int | None = None,
        uls_bps: int | None = None,
    ) -> str:
        return download_handler.render_progress_text(
            name, info, tick, progress_pct=progress_pct, dls_bps=dls_bps, uls_bps=uls_bps
        )

    def _start_progress_tracker(self, user_id: int, torrent_hash: str, tracker_msg: Any, title: str) -> None:
        download_handler.start_progress_tracker(self._ctx, user_id, torrent_hash, tracker_msg, title)

    def _start_pending_progress_tracker(self, user_id: int, title: str, category: str, base_msg: Any) -> None:
        download_handler.start_pending_progress_tracker(self._ctx, user_id, title, category, base_msg)

    async def _attach_progress_tracker_when_ready(self, user_id: int, title: str, category: str, base_msg: Any) -> None:
        await download_handler.attach_progress_tracker_when_ready(self._ctx, user_id, title, category, base_msg)

    def _stop_download_keyboard(self, torrent_hash: str) -> InlineKeyboardMarkup:
        return download_handler.stop_download_keyboard(torrent_hash)

    async def _tracker_send_fallback(self, tracker_msg: Any, text: str) -> None:
        await download_handler.tracker_send_fallback(self._ctx, tracker_msg, text)

    async def _safe_tracker_edit(self, tracker_msg: Any, text: str, reply_markup: Any = None) -> bool:
        return await download_handler.safe_tracker_edit(tracker_msg, text, reply_markup)

    async def _track_download_progress(self, user_id: int, torrent_hash: str, tracker_msg: Any, title: str) -> None:
        await download_handler.track_download_progress(self._ctx, user_id, torrent_hash, tracker_msg, title)

    # ---------- Background completion poller ----------

    async def _completion_poller_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        await download_handler.completion_poller_job(self._ctx, context)

    # ---------- UI ----------

    def _nav_footer(self, *, back_data: str = "", include_home: bool = True) -> list[list[InlineKeyboardButton]]:
        return kb_mod.nav_footer(back_data=back_data, include_home=include_home)

    def _home_only_keyboard(self) -> InlineKeyboardMarkup:
        return kb_mod.home_only_keyboard()

    @staticmethod
    def _compact_action_rows(
        rows: list[list[InlineKeyboardButton]], *, max_buttons: int = 5, columns: int = 2
    ) -> list[list[InlineKeyboardButton]]:
        return kb_mod.compact_action_rows(rows, max_buttons=max_buttons, columns=columns)

    def _active_download_tuples(self) -> list[tuple[str, str]]:
        """Return ``(hash, clean_name)`` for each active download (up to 10)."""
        try:
            items = self.qbt.list_torrents(filter_name="all", limit=20)
        except Exception:
            return []
        active = [t for t in items if str(t.get("state") or "") in _ACTIVE_DL_STATES]
        result: list[tuple[str, str]] = []
        for t in active[:10]:
            h = str(t.get("hash") or "")
            raw_name = str(t.get("name") or "Unknown")
            category = str(t.get("category") or "")
            clean_name = self._clean_download_name(raw_name, category)
            if h:
                result.append((h, clean_name))
        return result

    def _command_center_keyboard(self) -> InlineKeyboardMarkup:
        return kb_mod.command_center_keyboard(active_downloads=self._active_download_tuples())

    def _tv_filter_choice_keyboard(self) -> InlineKeyboardMarkup:
        return kb_mod.tv_filter_choice_keyboard()

    def _media_picker_keyboard(self, sid: str, idx: int, *, back_data: str = "") -> InlineKeyboardMarkup:
        return kb_mod.media_picker_keyboard(sid, idx, back_data=back_data)

    def _tv_filter_choice_text(self) -> str:
        return text_mod.tv_filter_choice_text()

    def _tv_filter_prompt_text(self, error: str | None = None) -> str:
        return text_mod.tv_filter_prompt_text(error)

    def _tv_title_prompt_text(self, season: int | None = None, episode: int | None = None) -> str:
        return text_mod.tv_title_prompt_text(season, episode)

    def _storage_probe_paths(self) -> list[str]:
        seen: set[str] = set()
        paths: list[str] = []
        for raw in (self.cfg.movies_path, self.cfg.tv_path, self.cfg.nvme_mount_path):
            path = os.path.realpath(str(raw or "").strip())
            if path and path not in seen:
                seen.add(path)
                paths.append(path)
        return paths

    def _plex_storage_display(self) -> str:
        probe_paths = self._storage_probe_paths()
        if not probe_paths:
            return "⚠️ Plex storage: unavailable"

        target_path = ""
        existing_paths = [path for path in probe_paths if os.path.exists(path)]
        for path in existing_paths:
            if os.path.isdir(path):
                target_path = path
                break
        if not target_path and existing_paths:
            target_path = existing_paths[0]
        if not target_path:
            return f"⚠️ Plex storage: path not found (<code>{_h(probe_paths[0])}</code>)"

        try:
            st = os.statvfs(target_path)
            total = int(st.f_frsize * st.f_blocks)
            free = int(st.f_frsize * st.f_bfree)  # Use bfree, not bavail (avoids counting reserved blocks as "used")
            used = max(0, total - free)
            if total <= 0:
                return "⚠️ Plex storage: unavailable"
            pct = (used / total) * 100.0
            bar = self._progress_bar(pct, width=14)
            warn = " ⚠️" if pct > 85.0 else ""
            free_gb = free / 1_000_000_000
            return (
                f"💾 Plex storage: <code>[{bar}]</code> <code>{pct:.1f}%</code>"
                f" · Free: <code>{free_gb:.0f}GB</code>{warn}"
            )
        except Exception as e:
            return f"⚠️ Plex storage: error (<code>{_h(str(e))}</code>)"

    def _clean_download_name(self, name: str, category: str) -> str:
        tv_cat = self.cfg.tv_category.lower()
        if category.lower() == tv_cat:
            show = self._extract_show_name(name)
            codes = sorted(extract_episode_codes(name))
            if codes:
                return f"{show} {codes[0]}"
            return show
        return self._extract_movie_name(name)

    def _active_downloads_section(self) -> str:
        try:
            items = self.qbt.list_torrents(filter_name="all", limit=20)
        except Exception:
            return ""
        active = [t for t in items if str(t.get("state") or "") in _ACTIVE_DL_STATES]
        if not active:
            return ""
        lines = ["\n<b>Active Downloads</b>"]
        for t in active[:5]:
            raw_name = str(t.get("name") or "Unknown")
            category = str(t.get("category") or "")
            clean_name = self._clean_download_name(raw_name, category)
            pct = max(0.0, min(100.0, float(t.get("progress", 0.0) or 0.0) * 100.0))
            bar = self._progress_bar(pct, width=14)
            lines.append(f"<code>[{bar}] {pct:.0f}%</code>  {_h(clean_name)}")
        return "\n".join(lines) + "\n"

    def _start_text(self, storage_ok: bool, storage_reason: str) -> str:
        vpn_ok, vpn_reason = self._vpn_ready_for_download()
        return text_mod.start_text(
            storage_ok,
            storage_reason,
            storage_usage=self._plex_storage_display(),
            vpn_ok=vpn_ok,
            vpn_reason=vpn_reason,
            downloads=self._active_downloads_section(),
        )

    def _help_text(self) -> str:
        return text_mod.help_text()

    async def _send_command_center(self, msg: Any) -> None:
        ok, reason = await asyncio.to_thread(self._ensure_media_categories)
        text = await asyncio.to_thread(self._start_text, ok, reason)
        rendered = await msg.reply_text(text, reply_markup=self._command_center_keyboard(), parse_mode=_PM)
        user_id = getattr(getattr(msg, "from_user", None), "id", None)
        if user_id is not None:
            self._remember_nav_ui_message(int(user_id), rendered)
            self._start_command_center_refresh(int(user_id))

    async def _render_command_center(
        self, msg: Any, user_id: int | None = None, *, use_remembered_ui: bool = False
    ) -> Any:
        ok, reason = await asyncio.to_thread(self._ensure_media_categories)
        text = await asyncio.to_thread(self._start_text, ok, reason)
        kb = self._command_center_keyboard()
        if user_id is None:
            user_id = getattr(getattr(msg, "from_user", None), "id", None)
        if user_id is None or not hasattr(self, "_render_nav_ui"):
            try:
                result = await msg.edit_text(text, reply_markup=kb, parse_mode=_PM)
            except TelegramError:
                result = await msg.reply_text(text, reply_markup=kb, parse_mode=_PM)
            if user_id is not None:
                self._start_command_center_refresh(int(user_id))
            return result
        # When use_remembered_ui=True, pass current_ui_message=None so _render_nav_ui
        # uses the remembered user_nav_ui entry (the original CC) instead of msg.
        ui_msg = None if use_remembered_ui else msg
        result = await self._render_nav_ui(int(user_id), msg, text, reply_markup=kb, current_ui_message=ui_msg)
        self._start_command_center_refresh(int(user_id))
        return result

    async def _navigate_to_command_center(self, msg: Any, user_id: int) -> Any:
        """Recover CC location from DB if needed, then render the Command Center."""
        if not self.user_nav_ui.get(user_id):
            db_cc = await asyncio.to_thread(self.store.get_command_center, user_id)
            if db_cc:
                self.user_nav_ui[user_id] = db_cc
        has_remembered = bool(self.user_nav_ui.get(user_id))
        return await self._render_command_center(msg, user_id=user_id, use_remembered_ui=has_remembered)

    def _start_command_center_refresh(self, user_id: int) -> None:
        existing = self.command_center_refresh_tasks.get(user_id)
        if existing and not existing.done():
            existing.cancel()
        task = asyncio.create_task(self._command_center_refresh_loop(user_id))
        self.command_center_refresh_tasks[user_id] = task

    def _stop_command_center_refresh(self, user_id: int) -> None:
        task = self.command_center_refresh_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()

    async def _command_center_refresh_loop(self, user_id: int) -> None:
        try:
            last_text = ""
            last_dl_hashes: list[str] = []
            error_streak = 0
            MAX_CONSECUTIVE_ERRORS = 5
            while True:
                await asyncio.sleep(5)
                remembered = self.user_nav_ui.get(user_id)
                if not remembered:
                    break
                # If user navigated away from the command center, stop refreshing
                flow = self._get_flow(user_id)
                if flow:
                    break
                ok, reason = await asyncio.to_thread(self._ensure_media_categories)
                text = await asyncio.to_thread(self._start_text, ok, reason)
                dl_tuples = await asyncio.to_thread(self._active_download_tuples)
                dl_hashes = [h for h, _ in dl_tuples]
                if text == last_text and dl_hashes == last_dl_hashes:
                    if not dl_hashes:
                        break
                    continue
                last_text = text
                last_dl_hashes = dl_hashes
                kb = kb_mod.command_center_keyboard(active_downloads=dl_tuples)
                try:
                    bot = self.app.bot if self.app else None
                    if not bot:
                        break
                    await bot.edit_message_text(
                        chat_id=remembered["chat_id"],
                        message_id=remembered["message_id"],
                        text=text,
                        reply_markup=kb,
                        parse_mode=_PM,
                    )
                    error_streak = 0
                except TelegramError as e:
                    err_msg = str(e).lower()
                    if "message is not modified" in err_msg:
                        error_streak = 0
                        continue
                    if any(hint in err_msg for hint in ("timed out", "timeout", "retry after", "network")):
                        error_streak += 1
                        LOG.warning("CC refresh transient error (%d/%d): %s", error_streak, MAX_CONSECUTIVE_ERRORS, e)
                        if error_streak >= MAX_CONSECUTIVE_ERRORS:
                            LOG.warning(
                                "CC refresh loop stopped after %d consecutive errors for user %d",
                                MAX_CONSECUTIVE_ERRORS,
                                user_id,
                            )
                            break
                        continue
                    LOG.warning("CC refresh loop stopping for user %d: %s", user_id, e)
                    break
                except Exception:
                    error_streak += 1
                    LOG.warning(
                        "CC refresh unexpected error (%d/%d)", error_streak, MAX_CONSECUTIVE_ERRORS, exc_info=True
                    )
                    if error_streak >= MAX_CONSECUTIVE_ERRORS:
                        break
                    continue
        except asyncio.CancelledError:
            return
        finally:
            self.command_center_refresh_tasks.pop(user_id, None)

    def _schedule_runner_interval_s(self) -> int:
        return schedule_handler.schedule_runner_interval_s()

    def _schedule_release_grace_s(self) -> int:
        return schedule_handler.schedule_release_grace_s()

    def _schedule_retry_interval_s(self) -> int:
        return schedule_handler.schedule_retry_interval_s()

    def _schedule_metadata_retry_s(self) -> int:
        return schedule_handler.schedule_metadata_retry_s()

    def _schedule_pending_stale_s(self) -> int:
        return schedule_handler.schedule_pending_stale_s()

    def _schedule_metadata_cache_ttl_s(self, bundle: dict[str, Any]) -> int:
        return schedule_handler.schedule_metadata_cache_ttl_s(bundle)

    def _schedule_metadata_retry_backoff_s(self, failures: int) -> int:
        return schedule_handler.schedule_metadata_retry_backoff_s(failures)

    def _schedule_inventory_backoff_s(self, failures: int) -> int:
        return schedule_handler.schedule_inventory_backoff_s(failures)

    def _schedule_source_snapshot(self, key: str) -> dict[str, Any]:
        return schedule_handler.schedule_source_snapshot(self._ctx, key)

    def _schedule_mark_source_health(
        self,
        key: str,
        *,
        ok: bool,
        detail: str | None = None,
        backoff_until: int = 0,
        effective_source: str | None = None,
    ) -> dict[str, Any]:
        return schedule_handler.schedule_mark_source_health(
            self._ctx, key, ok=ok, detail=detail, backoff_until=backoff_until, effective_source=effective_source
        )

    def _schedule_should_use_plex_inventory(self) -> bool:
        return schedule_handler.schedule_should_use_plex_inventory(self._ctx)

    def _remove_runner_interval_s(self) -> int:
        return remove_handler.remove_runner_interval_s()

    def _remove_retry_backoff_s(self, retry_count: int) -> int:
        return remove_handler.remove_retry_backoff_s(retry_count)

    async def _schedule_bootstrap(self, app: Application) -> None:
        if app.job_queue is None:
            raise RuntimeError(
                'python-telegram-bot job queue support is unavailable. Install via `pip install "python-telegram-bot[job-queue]"`.'
            )
        await asyncio.to_thread(self._schedule_repair_all_tracks)
        await asyncio.to_thread(
            self.store.update_schedule_runner_status,
            metadata_source_health_json=self._schedule_source_snapshot("metadata"),
            inventory_source_health_json=self._schedule_source_snapshot("inventory"),
        )
        for job in app.job_queue.get_jobs_by_name("schedule-runner"):
            job.schedule_removal()
        for job in app.job_queue.get_jobs_by_name("remove-runner"):
            job.schedule_removal()
        app.job_queue.run_once(self._schedule_runner_job, when=3, name="schedule-runner")
        app.job_queue.run_once(self._remove_runner_job, when=5, name="remove-runner")
        app.job_queue.run_repeating(
            self._schedule_runner_job,
            interval=self._schedule_runner_interval_s(),
            first=self._schedule_runner_interval_s(),
            name="schedule-runner",
            job_kwargs={"coalesce": True, "max_instances": 1, "misfire_grace_time": 30},
        )
        app.job_queue.run_repeating(
            self._remove_runner_job,
            interval=self._remove_runner_interval_s(),
            first=self._remove_runner_interval_s(),
            name="remove-runner",
            job_kwargs={"coalesce": True, "max_instances": 1, "misfire_grace_time": 30},
        )
        # Seed notified_completions with already-completed torrents so we don't
        # spam notifications for everything already downloaded on first run.
        try:
            existing = await asyncio.to_thread(self.qbt.list_torrents, filter_name="completed", limit=500)
            seeded = 0
            for t in existing:
                h = str(t.get("hash") or "").strip().lower()
                n = str(t.get("name") or "Unknown")
                if h and self._is_complete_torrent(t):
                    already = await asyncio.to_thread(self.store.is_completion_notified, h)
                    if not already:
                        await asyncio.to_thread(self.store.mark_completion_notified, h, n)
                        seeded += 1
            if seeded:
                LOG.info("Completion poller: seeded %d existing completed torrents", seeded)
        except Exception:
            LOG.warning("Completion poller: failed to seed existing completions", exc_info=True)

        for job in app.job_queue.get_jobs_by_name("completion-poller"):
            job.schedule_removal()
        app.job_queue.run_repeating(
            self._completion_poller_job,
            interval=60,
            first=10,
            name="completion-poller",
            job_kwargs={"coalesce": True, "max_instances": 1, "misfire_grace_time": 30},
        )
        LOG.info("Completion poller registered (60s interval)")

    def _schedule_bundle_from_cache(self, cached: dict[str, Any] | None, *, allow_stale: bool) -> dict[str, Any] | None:
        if not cached:
            return None
        bundle = dict(cached.get("bundle_json") or {})
        if not bundle:
            return None
        now_value = now_ts()
        expires_at = int(cached.get("expires_at") or 0)
        fetched_at = int(cached.get("fetched_at") or 0)
        if expires_at > now_value:
            return bundle
        if allow_stale and fetched_at > 0 and fetched_at >= now_value - 7 * 24 * 3600:
            bundle["_metadata_stale"] = True
            bundle["_metadata_error"] = str(cached.get("last_error_text") or "").strip() or None
            return bundle
        return None

    def _schedule_get_show_bundle(self, show_id: int, allow_stale: bool, lookup_tmdb: bool = False) -> dict[str, Any]:
        cached = self.store.get_schedule_show_cache(int(show_id))
        cached_bundle = self._schedule_bundle_from_cache(cached, allow_stale=False)
        if cached_bundle is not None:
            if lookup_tmdb and not cached_bundle.get("tmdb_id"):
                fetched = self.tvmeta.get_show_bundle(int(show_id), lookup_tmdb=True)
                fetched_at = now_ts()
                self.store.upsert_schedule_show_cache(
                    int(show_id),
                    fetched,
                    fetched_at,
                    fetched_at + self._schedule_metadata_cache_ttl_s(fetched),
                )
                self._schedule_mark_source_health("metadata", ok=True)
                return fetched
            return cached_bundle

        try:
            bundle = self.tvmeta.get_show_bundle(int(show_id), lookup_tmdb=lookup_tmdb)
            cached_tmdb_id = int((cached or {}).get("bundle_json", {}).get("tmdb_id") or 0) or None
            if cached_tmdb_id and not bundle.get("tmdb_id"):
                bundle["tmdb_id"] = cached_tmdb_id
            fetched_at = now_ts()
            self.store.upsert_schedule_show_cache(
                int(show_id),
                bundle,
                fetched_at,
                fetched_at + self._schedule_metadata_cache_ttl_s(bundle),
            )
            self._schedule_mark_source_health("metadata", ok=True)
            return bundle
        except Exception as e:
            state = self._schedule_source_snapshot("metadata")
            failures = int(state.get("consecutive_failures") or 0) + 1
            backoff_s = self._schedule_metadata_retry_backoff_s(failures)
            self._schedule_mark_source_health(
                "metadata",
                ok=False,
                detail=str(e),
                backoff_until=now_ts() + backoff_s,
            )
            stale_bundle = self._schedule_bundle_from_cache(cached, allow_stale=allow_stale)
            if stale_bundle is not None:
                self.store.upsert_schedule_show_cache(
                    int(show_id),
                    dict(cached.get("bundle_json") or {}),
                    int(cached.get("fetched_at") or now_ts()),
                    int(cached.get("expires_at") or now_ts()),
                    last_error_at=now_ts(),
                    last_error_text=str(e),
                )
                stale_bundle["_metadata_stale"] = True
                stale_bundle["_metadata_error"] = str(e)
                return stale_bundle
            raise

    def _schedule_sanitize_auto_state(
        self, auto_state: dict[str, Any] | None, *, probe: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        clean = dict(auto_state or {})
        clean.setdefault("enabled", True)
        clean.setdefault("last_auto_code", None)
        clean.setdefault("last_auto_at", None)
        clean.setdefault("retry_codes", {})
        clean.setdefault("tracking_mode", "upcoming")
        clean.setdefault("next_code", None)
        next_retry = int(clean.get("next_auto_retry_at") or 0)
        has_actionable = bool(probe and probe.get("actionable_missing_codes"))
        if not has_actionable or next_retry <= now_ts():
            clean["next_auto_retry_at"] = None
        else:
            clean["next_auto_retry_at"] = next_retry
        retry_codes = dict(clean.get("retry_codes") or {})
        clean["retry_codes"] = {str(code): int(ts) for code, ts in retry_codes.items() if int(ts or 0) > 0}
        return clean

    def _schedule_repair_track_state(self, track: dict[str, Any]) -> None:
        track_id = str(track.get("track_id") or "")
        last_probe = dict(track.get("last_probe_json") or {})
        clean_auto = self._schedule_sanitize_auto_state(track.get("auto_state_json") or {}, probe=last_probe)
        next_air_ts = int(track.get("next_air_ts") or last_probe.get("next_air_ts") or 0) or None
        if last_probe:
            next_check_at = self._schedule_next_check_at(
                next_air_ts,
                has_actionable_missing=bool(last_probe.get("actionable_missing_codes")),
                auto_state=clean_auto,
            )
        else:
            next_check_at = now_ts() + 300
        update_fields: dict[str, Any] = {}
        if clean_auto != dict(track.get("auto_state_json") or {}):
            update_fields["auto_state_json"] = clean_auto
        if int(track.get("next_check_at") or 0) != next_check_at:
            update_fields["next_check_at"] = next_check_at
        if next_air_ts != (int(track.get("next_air_ts") or 0) or None):
            update_fields["next_air_ts"] = next_air_ts
        if update_fields:
            self.store.update_schedule_track(track_id, **update_fields)

    def _schedule_repair_all_tracks(self) -> None:
        for track in self.store.list_all_schedule_tracks(True):
            self._schedule_repair_track_state(track)

    def _schedule_start_flow(self, user_id: int) -> None:
        self._set_flow(user_id, {"mode": "schedule", "stage": "await_show", "tracking_mode": "upcoming"})

    def _schedule_next_check_at(
        self, next_air_ts: int | None, *, has_actionable_missing: bool, auto_state: dict[str, Any] | None = None
    ) -> int:
        now_value = now_ts()
        auto_state = self._schedule_sanitize_auto_state(
            auto_state or {}, probe={"actionable_missing_codes": [1]} if has_actionable_missing else {}
        )
        next_retry = int(auto_state.get("next_auto_retry_at") or 0)
        if has_actionable_missing:
            if next_retry > now_value:
                return max(now_value + 300, next_retry)
            return now_value + 300
        if next_air_ts:
            release_ready_at = int(next_air_ts) + self._schedule_release_grace_s()
            if release_ready_at <= now_value:
                return now_value + 300
            delta = release_ready_at - now_value
            if delta > 7 * 24 * 3600:
                return now_value + 24 * 3600
            if delta > 24 * 3600:
                return min(now_value + 6 * 3600, release_ready_at)
            return max(now_value + 900, release_ready_at)
        return now_value + 12 * 3600

    @staticmethod
    def _schedule_show_info(show: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": int(show.get("id") or 0),
            "name": str(show.get("name") or "Unknown show").strip(),
            "year": int(show.get("year") or 0) or None,
            "premiered": str(show.get("premiered") or "").strip(),
            "status": str(show.get("status") or "Unknown").strip() or "Unknown",
            "network": str(show.get("network") or "").strip(),
            "country": str(show.get("country") or "").strip(),
            "summary": str(show.get("summary") or "").strip(),
            "genres": list(show.get("genres") or []),
            "language": str(show.get("language") or "").strip(),
            "url": str(show.get("url") or "").strip(),
            "imdb_id": str(show.get("imdb_id") or "").strip() or None,
            "tmdb_id": int(show.get("tmdb_id") or 0) or None,
            "available_seasons": list(show.get("available_seasons") or []),
        }

    def _schedule_select_season(self, bundle: dict[str, Any]) -> int:
        available = [int(x) for x in list(bundle.get("available_seasons") or []) if int(x) > 0]
        if not available:
            return 1
        episodes = list(bundle.get("episodes") or [])
        now_value = now_ts()
        future = [
            int(ep.get("season") or 0)
            for ep in episodes
            if int(ep.get("season") or 0) > 0
            and ep.get("number") is not None
            and ep.get("air_ts")
            and int(ep.get("air_ts") or 0) > now_value
        ]
        if future:
            return max(future)
        aired = [
            int(ep.get("season") or 0)
            for ep in episodes
            if int(ep.get("season") or 0) > 0
            and ep.get("number") is not None
            and ep.get("air_ts")
            and int(ep.get("air_ts") or 0) <= now_value
        ]
        if aired:
            return max(aired)
        return max(available)

    def _schedule_filesystem_inventory(self, show_name: str, year: int | None) -> tuple[set[str], str]:
        root = self.cfg.tv_path
        if not os.path.isdir(root):
            return set(), f"tv folders unavailable ({root})"
        want = normalize_title(show_name)
        candidates: list[tuple[int, str]] = []
        for entry in os.scandir(root):
            if not entry.is_dir():
                continue
            title_norm = normalize_title(entry.name)
            score = 0
            if title_norm == want:
                score += 10
            elif want and want in title_norm:
                score += 6
            elif title_norm and title_norm in want:
                score += 3
            if year and str(year) in entry.name:
                score += 2
            if score > 0:
                candidates.append((score, entry.path))
        if not candidates:
            return set(), "tv folders"
        codes: set[str] = set()
        for _score, base_path in sorted(candidates, reverse=True)[:3]:
            for dirpath, _dirnames, filenames in os.walk(base_path):
                for filename in filenames:
                    codes.update(extract_episode_codes(filename))
        return codes, "tv folders"

    def _schedule_existing_codes(self, show_name: str, year: int | None) -> tuple[set[str], str, bool]:
        inventory_degraded = False
        if self._schedule_should_use_plex_inventory():
            try:
                codes, source = self.plex.episode_inventory(show_name, year)
                if codes or source == "plex":
                    self._schedule_mark_source_health("inventory", ok=True, effective_source="Plex")
                    return codes, "Plex", False
            except Exception as e:
                state = self._schedule_source_snapshot("inventory")
                failures = int(state.get("consecutive_failures") or 0) + 1
                inventory_degraded = True
                self._schedule_mark_source_health(
                    "inventory",
                    ok=False,
                    detail=str(e),
                    backoff_until=now_ts() + self._schedule_inventory_backoff_s(failures),
                    effective_source="tv folders",
                )
        codes, source = self._schedule_filesystem_inventory(show_name, year)
        effective_source = "tv folders"
        if self.plex.ready() and not self._schedule_should_use_plex_inventory():
            inventory_degraded = True
        if not inventory_degraded:
            self._schedule_mark_source_health("inventory", ok=True, effective_source=effective_source)
        return codes, source, inventory_degraded

    def _schedule_probe_bundle(
        self, bundle: dict[str, Any], track: dict[str, Any] | None = None, season: int | None = None
    ) -> dict[str, Any]:
        show_info = self._schedule_show_info(bundle)
        available = [int(x) for x in list(bundle.get("available_seasons") or []) if int(x) > 0]
        chosen_season = int(season) if season and int(season) in available else self._schedule_select_season(bundle)
        present_all, inventory_source, inventory_degraded = self._schedule_existing_codes(
            show_info["name"], show_info.get("year")
        )
        pending_all = set(track.get("pending_json") or []) if track else set()
        pending_all -= present_all
        now_value = now_ts()
        grace_cutoff = now_value - self._schedule_release_grace_s()
        season_eps = [
            ep
            for ep in list(bundle.get("episodes") or [])
            if int(ep.get("season") or 0) == chosen_season and ep.get("number") is not None and ep.get("code")
        ]
        season_eps.sort(key=lambda ep: int(ep.get("number") or 0))

        episode_map: dict[str, str] = {}
        episode_air: dict[str, int | None] = {}
        episode_order: list[str] = []
        present_codes: list[str] = []
        released_codes: list[str] = []
        missing_codes: list[str] = []
        all_missing_codes: list[str] = []
        actionable_missing_codes: list[str] = []
        unreleased_codes: list[str] = []
        pending_codes: list[str] = []
        next_air_ts: int | None = None

        seen: set[str] = set()
        for ep in season_eps:
            code = str(ep.get("code") or "")
            if not code or code in seen:
                continue
            seen.add(code)
            episode_order.append(code)
            episode_map[code] = str(ep.get("name") or "").strip()
            episode_air[code] = int(ep.get("air_ts") or 0) or None
            air_ts = int(ep.get("air_ts") or 0) or None
            if code in present_all:
                present_codes.append(code)
            if code in pending_all:
                pending_codes.append(code)
            if code not in present_all:
                all_missing_codes.append(code)
            if (air_ts is None and not ep.get("airdate")) or (air_ts is not None and air_ts > now_value):
                unreleased_codes.append(code)
                if air_ts and (next_air_ts is None or air_ts < next_air_ts):
                    next_air_ts = air_ts
                continue
            released_codes.append(code)
            if code in present_all:
                continue
            missing_codes.append(code)
            if code not in pending_all and (air_ts is None or air_ts <= grace_cutoff):
                actionable_missing_codes.append(code)

        # Cross-season missing: released episodes not in library, across ALL seasons of this show.
        # Computed here while present_all, pending_all, and grace_cutoff are in scope.
        series_missing_by_season: dict[int, list[str]] = {}  # season_number -> [codes]
        series_actionable_all: list[str] = []  # flat list of actionable across all seasons
        _seen_series: set[str] = set()
        for _ep in sorted(
            list(bundle.get("episodes") or []), key=lambda e: (int(e.get("season") or 0), int(e.get("number") or 0))
        ):
            _ep_season = int(_ep.get("season") or 0)
            _ep_code = str(_ep.get("code") or "")
            if not _ep_code or _ep_season <= 0 or _ep_code in _seen_series:
                continue
            _seen_series.add(_ep_code)
            _air_ts = int(_ep.get("air_ts") or 0) or None
            if (_air_ts is None and not _ep.get("airdate")) or (_air_ts is not None and _air_ts > now_value):
                continue  # not yet released
            if _ep_code in present_all:
                continue  # already in library
            series_missing_by_season.setdefault(_ep_season, []).append(_ep_code)
            if _ep_code not in pending_all and (_air_ts is None or _air_ts <= grace_cutoff):
                series_actionable_all.append(_ep_code)

        return {
            "show": show_info,
            "season": chosen_season,
            "available_seasons": available,
            "inventory_source": inventory_source,
            "inventory_degraded": inventory_degraded,
            "inventory_source_effective": "tv folders" if inventory_source != "Plex" else "Plex",
            "metadata_stale": bool(bundle.get("_metadata_stale")),
            "metadata_error": str(bundle.get("_metadata_error") or "").strip() or None,
            "present_codes": present_codes,
            "pending_codes": pending_codes,
            "released_codes": released_codes,
            "missing_codes": missing_codes,
            "all_missing_codes": all_missing_codes,
            "actionable_missing_codes": actionable_missing_codes,
            "unreleased_codes": unreleased_codes,
            "next_air_ts": next_air_ts,
            "signature": "|".join(sorted(set(actionable_missing_codes))),
            "episode_map": episode_map,
            "episode_air": episode_air,
            "episode_order": episode_order,
            "total_season_episodes": len(season_eps),
            "tracked_missing_codes": list(missing_codes),
            "tracking_mode": "upcoming",
            "tracking_code": None,
            "series_missing_by_season": series_missing_by_season,
            "series_actionable_all": series_actionable_all,
        }

    def _schedule_apply_tracking_mode(self, track: dict[str, Any] | None, probe: dict[str, Any]) -> dict[str, Any]:
        auto_state = self._schedule_episode_auto_state(track or {})
        probe = dict(probe)

        tracking_mode = str(auto_state.get("tracking_mode") or "upcoming")
        probe["tracking_mode"] = tracking_mode

        missing = list(probe.get("all_missing_codes") or probe.get("missing_codes") or [])
        if not missing:
            probe["tracking_code"] = None
            probe["actionable_missing_codes"] = []
            probe["tracked_missing_codes"] = []
            probe["signature"] = ""
            probe["next_air_ts"] = probe.get("next_air_ts")
            return probe

        if tracking_mode == "full_season":
            probe["tracking_code"] = None
            probe["tracked_missing_codes"] = list(missing)
            return probe

        episode_order = list(probe.get("episode_order") or [])
        present_codes = set(probe.get("present_codes") or [])
        pending_codes = set(probe.get("pending_codes") or [])
        episode_air = dict(probe.get("episode_air") or {})

        now_value = now_ts()
        grace_cutoff = now_value - self._schedule_release_grace_s()

        # First, choose a cursor anchored to the first unreleased/missing episode, unless one is already persisted.
        cursor_ep = episode_number_from_code(str(auto_state.get("next_code") or ""))
        if cursor_ep is None:
            cursor_ep = 0
            for code in episode_order:
                if code in present_codes:
                    continue
                try:
                    ep_num = int(episode_number_from_code(code) or 0)
                except Exception:
                    continue
                air_ts = episode_air.get(code)
                if air_ts is None or (air_ts > now_value):
                    cursor_ep = ep_num
                    break
            if cursor_ep <= 0:
                for code in episode_order:
                    if code in present_codes:
                        continue
                    try:
                        ep_num = int(episode_number_from_code(code) or 0)
                    except Exception:
                        continue
                    cursor_ep = ep_num
                    break

        first_target_code: str | None = None
        first_target_air_ts: int | None = None
        target_actionable: list[str] = []
        tracked_missing: list[str] = []
        for code in episode_order:
            ep_num = episode_number_from_code(code)
            if not ep_num:
                continue
            if ep_num < cursor_ep:
                continue
            if code in present_codes:
                continue
            air_ts = episode_air.get(code)
            # Stop collecting when we hit an unreleased episode
            if air_ts is not None and air_ts > now_value:
                if first_target_code is None:
                    first_target_code = code
                    first_target_air_ts = air_ts
                break
            # This episode is released (or air_ts unknown)
            if first_target_code is None:
                first_target_code = code
                first_target_air_ts = air_ts
            if code not in pending_codes:
                tracked_missing.append(code)
                if air_ts is None or air_ts <= grace_cutoff:
                    target_actionable.append(code)

        if first_target_code:
            auto_state["next_code"] = first_target_code
            probe["tracking_code"] = first_target_code
            probe["tracked_missing_codes"] = tracked_missing
            probe["actionable_missing_codes"] = target_actionable
            probe["signature"] = "|".join(sorted(set(target_actionable)))
            if first_target_air_ts:
                probe["next_air_ts"] = first_target_air_ts
        else:
            auto_state["next_code"] = None
            probe["tracking_code"] = None
            probe["tracked_missing_codes"] = []
            probe["actionable_missing_codes"] = []
            probe["signature"] = ""

        if first_target_code in pending_codes:
            # Keep pending target in pending bucket so we do not auto-fire duplicates.
            auto_state["next_code"] = first_target_code
            probe["tracking_code"] = first_target_code

        probe["_auto_state"] = auto_state
        return probe

    def _schedule_probe_track(self, track: dict[str, Any], season: int | None = None) -> dict[str, Any]:
        bundle = self._schedule_get_show_bundle(
            int(track.get("tvmaze_id") or track.get("show_json", {}).get("id") or 0),
            allow_stale=True,
            lookup_tmdb=False,
        )
        target_season = int(season) if season else int(track.get("season") or 1)
        raw_probe = self._schedule_probe_bundle(bundle, track=track, season=target_season)
        return self._schedule_apply_tracking_mode(track, raw_probe)

    def _schedule_candidate_keyboard(self, candidates: list[dict[str, Any]]) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        for idx, candidate in enumerate(candidates[:5]):
            year = candidate.get("year") or "?"
            rows.append([InlineKeyboardButton(f"{candidate['name']} ({year})", callback_data=f"sch:pick:{idx}")])
        rows.append([InlineKeyboardButton("🏠 Home", callback_data="nav:home")])
        rows.extend(self._nav_footer(include_home=False))
        return InlineKeyboardMarkup(rows)

    def _schedule_preview_keyboard(self, probe: dict[str, Any]) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton("✅ Confirm & Track", callback_data="sch:confirm"),
                InlineKeyboardButton("🔄 Different Show", callback_data="sch:change"),
            ]
        ]
        actionable = list(probe.get("actionable_missing_codes") or [])
        missing_current = list(probe.get("missing_codes") or [])
        series_actionable = list(probe.get("series_actionable_all") or [])
        chosen_season = int(probe.get("season") or 0)
        # Actionable missing in seasons OTHER than current
        other_season_actionable = [c for c in series_actionable if not c.startswith(f"S{chosen_season:02d}")]
        has_any_missing = bool(missing_current or series_actionable)
        if actionable:
            rows.append([InlineKeyboardButton(f"⬇️ Download Season {chosen_season}", callback_data="sch:confirm:all")])
        if other_season_actionable or len(series_actionable) > len(actionable):
            rows.append([InlineKeyboardButton("⬇️ Download entire series", callback_data="sch:confirm:series")])
        if has_any_missing:
            rows.append([InlineKeyboardButton("🎯 Choose specific episodes", callback_data="sch:confirm:pick")])
        if len(list(probe.get("available_seasons") or [])) > 1:
            rows.append([InlineKeyboardButton("🔀 Change Season", callback_data="sch:season")])
        rows.append([InlineKeyboardButton("🏠 Home", callback_data="nav:home")])
        rows.extend(self._nav_footer(include_home=False))
        return InlineKeyboardMarkup(rows)

    def _schedule_missing_keyboard(self, track_id: str) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton("⬇️ Download all missing", callback_data=f"sch:all:{track_id}"),
                InlineKeyboardButton("🎯 Pick specific episodes", callback_data=f"sch:pickeps:{track_id}"),
            ],
            [InlineKeyboardButton("⏭ Skip — notify me later", callback_data=f"sch:skip:{track_id}")],
        ]
        rows.extend(self._nav_footer())
        return InlineKeyboardMarkup(rows)

    def _schedule_episode_picker_keyboard(self, track_id: str, codes: list[str]) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        pair: list[InlineKeyboardButton] = []
        for code in codes[:12]:
            episode_num = int(code[-2:])
            pair.append(InlineKeyboardButton(code, callback_data=f"sch:ep:{track_id}:{episode_num}"))
            if len(pair) == 2:
                rows.append(pair)
                pair = []
        if pair:
            rows.append(pair)
        rows.append([InlineKeyboardButton("⏭ Skip — notify me later", callback_data=f"sch:skip:{track_id}")])
        rows.extend(self._nav_footer())
        return InlineKeyboardMarkup(rows)

    def _schedule_picker_all_missing(
        self, probe: dict, current_season: int, current_missing: list[str]
    ) -> dict[str, list[str]]:
        """Normalize series_missing_by_season to string-keyed dict and ensure current season is present."""
        series_raw: dict = probe.get("series_missing_by_season") or {}
        result: dict[str, list[str]] = {}
        for s, codes in series_raw.items():
            if codes:
                result[str(s)] = list(codes)
        if current_missing:
            result[str(current_season)] = current_missing
        return result

    def _schedule_picker_text(self, flow: dict) -> str:
        season = int(flow.get("picker_season") or 1)
        selected: list[str] = list(flow.get("picker_selected") or [])
        all_missing: dict = flow.get("picker_all_missing") or {}
        season_codes = list(all_missing.get(str(season)) or [])
        other_seasons = sorted(int(s) for s in all_missing if int(s) != season and all_missing[s])
        n_selected = len(selected)
        lines = [
            "<b>🎯 Choose Episodes to Download</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"Season <b>{season}</b> · {len(season_codes)} missing",
        ]
        if other_seasons:
            lines.append(f"Other seasons with gaps: {', '.join(f'S{s:02d}' for s in other_seasons)}")
        lines.append(f"Selected: <b>{n_selected}</b>")
        lines.append("<i>Tap to select · ↩️ Back clears your selections</i>")
        return "\n".join(lines)

    def _schedule_picker_keyboard(self, flow: dict) -> InlineKeyboardMarkup:
        selected: set[str] = set(flow.get("picker_selected") or [])
        season = int(flow.get("picker_season") or 1)
        all_missing: dict = flow.get("picker_all_missing") or {}
        season_codes = list(all_missing.get(str(season)) or [])
        rows: list[list[InlineKeyboardButton]] = []
        pair: list[InlineKeyboardButton] = []
        for code in season_codes:
            mark = "✅ " if code in selected else ""
            pair.append(InlineKeyboardButton(f"{mark}{code}", callback_data=f"sch:pktog:{code}"))
            if len(pair) == 2:
                rows.append(pair)
                pair = []
        if pair:
            rows.append(pair)
        # Season switcher tabs
        other_seasons = sorted(int(s) for s in all_missing if int(s) != season and all_missing[s])
        if other_seasons:
            rows.append(
                [InlineKeyboardButton(f"Season {s}", callback_data=f"sch:pkseason:{s}") for s in other_seasons[:4]]
            )
        # Confirm button — always present so keyboard size stays stable
        n = len(selected)
        label = f"⬇️ Download {n} episode{'s' if n != 1 else ''}" if n > 0 else "Select episodes above to download"
        rows.append([InlineKeyboardButton(label, callback_data="sch:pkconfirm")])
        rows.append([InlineKeyboardButton("↩️ Back", callback_data="sch:pkback")])
        return InlineKeyboardMarkup(rows)

    def _schedule_dl_confirm_text(self, flow: dict) -> str:
        codes: list[str] = list(flow.get("dl_confirm_codes") or [])
        probe: dict = flow.get("probe") or {}
        show: dict = probe.get("show") or flow.get("selected_show") or flow.get("picker_show") or {}
        show_name = str(show.get("name") or "this show")
        dl_from = str(flow.get("dl_confirm_from") or "confirm")
        n = len(codes)
        by_season: dict[str, list[str]] = {}
        for c in codes:
            by_season.setdefault(c[:3], []).append(c)
        lines = [
            "<b>📥 Confirm Download</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"<b>{_h(show_name)}</b>",
            f"<b>{n} episode{'s' if n != 1 else ''}</b> will be queued for download:",
        ]
        for prefix in sorted(by_season):
            lines.append(f"  <code>{_h(' · '.join(by_season[prefix]))}</code>")
        lines.append("")
        if dl_from == "picker":
            lines.append("<i>These episodes will be added to your download queue.</i>")
        else:
            lines.append("<i>Tracking will also begin for future episodes of this show.</i>")
        return "\n".join(lines)

    def _schedule_dl_confirm_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Yes, download", callback_data="sch:dlgo"),
                    InlineKeyboardButton("↩️ Back", callback_data="sch:dlback"),
                ],
            ]
        )

    def _schedule_preview_text(self, probe: dict[str, Any]) -> str:
        show = probe.get("show") or {}
        tracking_mode = str(probe.get("tracking_mode") or "upcoming")
        mode_label = "full season" if tracking_mode == "full_season" else "next unreleased"
        released_count = len(probe.get("released_codes") or [])
        total_count = int(probe.get("total_season_episodes") or 0)
        present_count = len(probe.get("present_codes") or [])
        unreleased_count = len(probe.get("unreleased_codes") or [])
        network = show.get("network") or show.get("country") or "Unknown"
        source = probe.get("inventory_source") or "unknown"
        chosen_season = int(probe.get("season") or 0)
        # All released-but-missing for current season (superset of actionable)
        missing_all = list(probe.get("missing_codes") or [])
        pending = set(probe.get("pending_codes") or [])
        # Series-wide gaps from seasons other than the current one
        series_missing: dict = probe.get("series_missing_by_season") or {}
        other_season_gaps = {int(s): codes for s, codes in series_missing.items() if int(s) != chosen_season}

        lines = [
            "<b>📺 Schedule Preview</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"<b>{_h(show.get('name') or '')}</b> ({_h(show.get('year') or '?')})",
            f"Season: <b>{_h(probe.get('season') or '?')}</b> · Status: <code>{_h(show.get('status') or 'Unknown')}</code>",
            f"Network: <code>{_h(network)}</code> · Source: <code>{_h(source)}</code>",
            f"Mode: <b>{_h(mode_label)}</b>",
            "",
            "<b>Inventory</b>",
            f"  ✅ In library: <code>{present_count}/{total_count}</code>",
            f"  📋 Released: <code>{released_count}/{total_count}</code>",
            f"  ⏰ Unreleased: <code>{unreleased_count}</code>",
        ]
        if probe.get("next_air_ts"):
            rel = _relative_time(int(probe["next_air_ts"]))
            lines.append(f"  📅 Next episode: <code>{_h(rel)}</code>")
        if probe.get("metadata_stale"):
            lines.append("<i>⚠️ Metadata: using cached TV data — live source is degraded</i>")
        if probe.get("inventory_degraded"):
            lines.append("<i>⚠️ Inventory: Plex is degraded, using filesystem fallback</i>")

        # Missing episodes — list all released-but-absent episodes for this season explicitly
        not_queued = [c for c in missing_all if c not in pending]
        queued_missing = [c for c in missing_all if c in pending]
        if not_queued or queued_missing:
            lines.append("")
            lines.append(f"<b>Missing (Season {chosen_season}):</b>")
            if not_queued:
                lines.append(f"  ❌ <code>{_h(' · '.join(not_queued))}</code>")
            if queued_missing:
                lines.append(f"  ⬇️ Queued: <code>{_h(' · '.join(queued_missing[:8]))}</code>")

        # Other seasons that have released-but-missing episodes
        if other_season_gaps:
            lines.append("")
            lines.append("<b>Other seasons with gaps:</b>")
            for s in sorted(other_season_gaps):
                codes = other_season_gaps[s]
                sample = codes[:4]
                suffix = f" +{len(codes) - 4} more" if len(codes) > 4 else ""
                lines.append(f"  ❌ Season {s}: <code>{_h(' · '.join(sample))}</code>{_h(suffix)}")

        summary = str(show.get("summary") or "")
        if summary:
            truncated = summary[:320] + ("…" if len(summary) > 320 else "")
            lines.extend(["", f"<blockquote expandable>{_h(truncated)}</blockquote>"])
        lines.extend(["", "<i>Confirm to start background checks for this show/season.</i>"])
        return "\n".join(lines)

    def _schedule_track_ready_text(
        self, track: dict[str, Any], probe: dict[str, Any], *, duplicate: bool = False
    ) -> str:
        show = track.get("show_json") or probe.get("show") or {}
        missing = list(probe.get("tracked_missing_codes") or [])
        header = "<b>📺 Already Tracking</b>" if duplicate else "<b>✅ Schedule Tracking Enabled</b>"
        mode = str(probe.get("tracking_mode") or "upcoming")
        mode_label = "full season" if mode == "full_season" else "next unreleased"
        present_count = len(probe.get("present_codes") or [])
        unreleased_count = len(probe.get("unreleased_codes") or [])
        lines = [
            header,
            "━━━━━━━━━━━━━━━━━━━━",
            f"<b>{_h(show.get('name') or '')}</b> — Season <b>{_h(track.get('season') or '?')}</b>",
            f"Mode: <b>{_h(mode_label)}</b>",
            "",
            f"  ✅ In library: <code>{present_count}</code>",
            f"  🔍 Still needed: <b>{len(missing)}</b>",
            f"  ⏰ Unreleased: <code>{unreleased_count}</code>",
        ]
        if probe.get("next_air_ts"):
            rel = _relative_time(int(probe["next_air_ts"]))
            lines.append(f"  📅 Next episode: <code>{_h(rel)}</code>")
        if probe.get("metadata_stale"):
            lines.append("")
            lines.append("<i>⚠️ TV metadata source degraded: using cached schedule data</i>")
        if probe.get("inventory_degraded"):
            if not probe.get("metadata_stale"):
                lines.append("")
            lines.append("<i>⚠️ Inventory source degraded: using filesystem fallback instead of Plex</i>")
        lines.extend(
            ["", "<i>I'll automatically search and queue missing aired episodes after the release grace window.</i>"]
        )
        return "\n".join(lines)

    def _episode_status_icon(self, probe: dict[str, Any], code: str, *, pending: set[str] | None = None) -> str:
        """Return a single emoji reflecting the episode's current status."""
        present = set(probe.get("present_codes") or [])
        unreleased = set(probe.get("unreleased_codes") or [])
        actionable = set(probe.get("actionable_missing_codes") or [])
        queued = set(probe.get("pending_codes") or [])
        if pending is not None:
            queued = queued | pending
        if code in present:
            return "✅"
        if code in queued:
            return "⬇️"
        if code in unreleased:
            return "⏰"
        if code in actionable:
            return "🔍"
        return "📋"

    def _schedule_episode_label(self, probe: dict[str, Any], code: str, *, pending: set[str] | None = None) -> str:
        name = str((probe.get("episode_map") or {}).get(code) or "").strip()
        air_ts = (probe.get("episode_air") or {}).get(code)
        icon = self._episode_status_icon(probe, code, pending=pending)
        when = _relative_time(int(air_ts)) if air_ts else "released"
        return f"{icon} {code} — {name or 'Episode'} ({when})"

    def _schedule_episode_auto_state(self, track: dict[str, Any]) -> dict[str, Any]:
        return self._schedule_sanitize_auto_state(dict(track.get("auto_state_json") or {}))

    def _schedule_qbt_codes_for_show(self, show_name: str, season: int) -> set[str]:
        codes: set[str] = set()
        tv_categories = self._qbt_category_aliases(self.cfg.tv_category, self.cfg.tv_path)
        try:
            torrents = self.qbt.list_torrents(limit=500)
            want_norm = normalize_title(show_name)
            for t in torrents:
                torrent_category = str(t.get("category") or "").strip()
                if tv_categories and torrent_category not in tv_categories:
                    continue
                name = str(t.get("name") or "")
                if want_norm and want_norm not in normalize_title(name):
                    continue
                t_codes = extract_episode_codes(name)
                if season > 0:
                    t_codes = {c for c in t_codes if c.startswith(f"S{season:02d}")}
                codes.update(t_codes)
        except Exception:
            LOG.warning("Failed to list qBittorrent torrents for schedule reconcile", exc_info=True)
        return codes

    def _schedule_reconcile_pending(
        self, track: dict[str, Any], probe: dict[str, Any]
    ) -> tuple[set[str], set[str], set[str]]:
        show = track.get("show_json") or probe.get("show") or {}
        season = int(track.get("season") or 1)
        pending = set(track.get("pending_json") or [])
        present = set(probe.get("present_codes") or [])
        qbt_codes = self._schedule_qbt_codes_for_show(str(show.get("name") or ""), season)
        stale_threshold = now_ts() - self._schedule_pending_stale_s()
        auto_state = self._schedule_episode_auto_state(track)
        retry_codes = dict(auto_state.get("retry_codes") or {})
        cleared = pending & present
        stale: set[str] = set()
        for code in list(pending - present):
            if code in qbt_codes:
                continue
            added_at = retry_codes.get(code)
            if added_at and int(added_at) < stale_threshold:
                stale.add(code)
        return cleared, stale, qbt_codes

    def _schedule_should_attempt_auto(
        self, track: dict[str, Any], probe: dict[str, Any]
    ) -> tuple[bool, list[str] | str | None]:
        auto_state = self._schedule_episode_auto_state(track)
        if not auto_state.get("enabled"):
            return False, "auto disabled"
        actionable = list(probe.get("actionable_missing_codes") or [])
        if not actionable:
            return False, "no actionable missing"
        pending = set(track.get("pending_json") or [])
        candidates = [c for c in actionable if c not in pending]
        if not candidates:
            return False, "all actionable already pending"
        now_value = now_ts()
        next_retry = auto_state.get("next_auto_retry_at")
        if next_retry and int(next_retry) > now_value:
            return False, f"retry cooldown until <code>{format_local_ts(int(next_retry))}</code>"
        return True, candidates

    async def _schedule_attempt_auto_acquire(self, track: dict[str, Any], code: str) -> dict[str, Any] | None:
        try:
            result = await self._schedule_download_episode(track, code)
            LOG.info("Schedule auto-acquire succeeded: %s -> %s", code, result.get("name"))
            return result
        except schedule_handler.No1080pError:
            raise
        except Exception as e:
            LOG.warning("Schedule auto-acquire failed for %s: %s", code, e)
            return None

    async def _schedule_notify_auto_queued(self, track: dict[str, Any], code: str, result: dict[str, Any]) -> None:
        if not self.app:
            return
        show = track.get("show_json") or {}
        show_name = show.get("name") or "Show"
        torrent_name = result.get("name") or "Torrent added"
        category = result.get("category") or ""
        path = result.get("path") or ""
        lines = [
            "<b>📡 Auto-Queued</b>",
            f"<b>{_h(show_name)}</b> <code>{_h(code)}</code>",
            "",
            f"<code>{_h(torrent_name)}</code>",
        ]
        if category:
            lines.append(f"Category: <code>{_h(category)}</code>")
        if path:
            lines.append(f"Path: <code>{_h(path)}</code>")
        text = "\n".join(lines)
        chat_id = int(track.get("chat_id") or 0)
        user_id = int(track.get("user_id") or 0)
        if not chat_id:
            LOG.warning("Schedule notify_auto_queued skipped: no chat_id for track %s", track.get("track_id"))
            return
        try:
            notif_msg = await self.app.bot.send_message(chat_id=chat_id, text=text, parse_mode=_PM)
            self._track_ephemeral_message(user_id, notif_msg)
            torrent_hash = result.get("hash")
            if torrent_hash:
                tracker_msg = await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=f"<b>📡 Live Monitor Attached</b>\n<i>Tracking {_h(code)} download progress…</i>",
                    reply_markup=self._stop_download_keyboard(torrent_hash),
                    parse_mode=_PM,
                )
                self._start_progress_tracker(user_id, torrent_hash, tracker_msg, torrent_name)
            else:
                self._start_pending_progress_tracker(user_id, torrent_name, category, notif_msg)
        except Exception:
            LOG.warning("Failed to send auto-queue notification", exc_info=True)

    async def _schedule_notify_no_1080p(
        self, track: dict[str, Any], code: str, miss_count: int, lower_res_count: int, backoff_s: int
    ) -> None:
        await schedule_handler.schedule_notify_no_1080p(
            self._ctx,
            track,
            code,
            miss_count,
            lower_res_count,
            backoff_s,
            track_ephemeral_message_fn=self._track_ephemeral_message,
        )

    def _schedule_missing_text(self, track: dict[str, Any], probe: dict[str, Any]) -> str:
        show = track.get("show_json") or probe.get("show") or {}
        codes = list(probe.get("actionable_missing_codes") or [])
        auto_state = self._schedule_episode_auto_state(track)
        next_retry = auto_state.get("next_auto_retry_at")
        inline_codes = codes[:2]
        more_codes = codes[2:10]
        overflow = max(0, len(codes) - 10)
        inline_lines = [f"  {_h(self._schedule_episode_label(probe, c))}" for c in inline_codes]
        more_lines = [f"• {_h(self._schedule_episode_label(probe, c))}" for c in more_codes]
        if overflow > 0:
            more_lines.append(f"• …and {overflow} more")
        ep_count = len(codes)
        lines = [
            "<b>📺 Missing Aired Episodes</b>",
            f"<b>{_h(show.get('name') or '')}</b> · Season <b>{_h(track.get('season') or '?')}</b> · <b>{ep_count}</b> episode{'s' if ep_count != 1 else ''} needed",
            "",
        ]
        lines.extend(inline_lines)
        if more_lines:
            more_block = "\n".join(more_lines)
            lines.append(f"<blockquote expandable>{more_block}</blockquote>")
        lines.append("")
        if next_retry:
            rel = _relative_time(int(next_retry))
            lines.append(f"<i>Auto-search enabled · next attempt {rel}</i>")
        else:
            lines.append("<i>Auto-search enabled · searching now</i>")
        return "\n".join(lines)

    async def _backup_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """APScheduler job: create a daily database backup."""
        if not self.cfg.backup_dir:
            return
        try:
            path = await asyncio.to_thread(self.store.backup, self.cfg.backup_dir)
            size = os.path.getsize(path)
            LOG.info("Database backup created: %s (%d bytes)", path, size)
        except Exception as e:
            LOG.error("Database backup failed: %s", e, exc_info=True)

    async def _health_event_cleanup_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """APScheduler job: remove old health events from the database."""
        try:
            cleaned = await asyncio.to_thread(
                self.store.cleanup_old_health_events, self.cfg.health_event_retention_days
            )
            if cleaned:
                LOG.info("Cleaned up %d old health events", cleaned)
        except Exception as e:
            LOG.error("Health event cleanup failed: %s", e, exc_info=True)

    async def _ensure_qbt_connectivity(self) -> None:
        """Verify qBittorrent is reachable at startup. Attempt service restart if not."""
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                info = await asyncio.to_thread(self.qbt.get_transfer_info)
                status = str(info.get("connection_status") or "unknown")
                LOG.info("qBittorrent connected (status=%s, attempt %d)", status, attempt)
                return
            except Exception as e:
                LOG.warning("qBittorrent unreachable (attempt %d/%d): %s", attempt, max_attempts, e)
                if attempt < max_attempts:
                    try:
                        result = await asyncio.to_thread(
                            subprocess.run,
                            ["sudo", "systemctl", "restart", "qbittorrent.service"],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if result.returncode == 0:
                            LOG.info("qBittorrent service restarted, waiting for startup...")
                            await asyncio.sleep(5)
                        else:
                            LOG.warning("Failed to restart qBittorrent: %s", result.stderr.strip())
                    except Exception as restart_err:
                        LOG.warning("qBittorrent restart failed: %s", restart_err)
        LOG.error(
            "qBittorrent unreachable after %d attempts — downloads will fail until qBT is restored",
            max_attempts,
        )

    async def _qbt_health_check_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Periodic job: verify qBittorrent is reachable every 5 minutes, restart if needed."""
        try:
            info = await asyncio.to_thread(self.qbt.get_transfer_info)
        except Exception as e:
            LOG.warning("qBT health check: unreachable (%s), attempting restart", e)
            await self._qbt_health_restart()
            return

        status = str(info.get("connection_status") or "unknown").strip().lower()
        if status == "firewalled":
            LOG.warning("qBT health check: status=%s — checking for stale interface binding", status)
            try:
                prefs = await asyncio.to_thread(self.qbt.get_preferences)
                iface = str(prefs.get("current_network_interface") or "").strip()
                if iface:
                    LOG.warning(
                        "qBT health check: clearing stale interface binding '%s' (OS kill-switch handles VPN routing)",
                        iface,
                    )
                    await asyncio.to_thread(
                        self.qbt.set_preferences,
                        {"current_network_interface": "", "current_interface_address": ""},
                    )
            except Exception:
                LOG.warning("qBT health check: failed to check/clear interface binding", exc_info=True)
        return

    async def _qbt_health_restart(self) -> None:
        """Restart qbittorrent.service and verify it comes back online."""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["sudo", "systemctl", "restart", "qbittorrent.service"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                LOG.info("qBT health check: service restarted successfully")
                await asyncio.sleep(5)
                try:
                    info = await asyncio.to_thread(self.qbt.get_transfer_info)
                    LOG.info(
                        "qBT health check: confirmed back online (status=%s)",
                        info.get("connection_status", "unknown"),
                    )
                except Exception:
                    LOG.error("qBT health check: still unreachable after restart")
            else:
                LOG.error("qBT health check: restart failed (%s)", result.stderr.strip())
        except Exception as e:
            LOG.error("qBT health check: restart attempt failed: %s", e)

    def _remove_build_job_verification(
        self, candidate: dict[str, Any], target_path: str, identity: dict[str, Any] | None
    ) -> dict[str, Any]:
        return remove_handler.remove_build_job_verification(candidate, target_path, identity)

    def _remove_attempt_plex_cleanup(self, job: dict[str, Any], *, inline_timeout_s: int = 90) -> dict[str, Any]:
        return remove_handler.remove_attempt_plex_cleanup(self._ctx, job, inline_timeout_s=inline_timeout_s)

    async def _remove_runner_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        await remove_handler.remove_runner_job(self._ctx, context)

    async def _schedule_runner_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        async with self.schedule_runner_lock:
            started_at = now_ts()
            due_tracks: list[dict[str, Any]] = []
            processed = 0
            try:
                await asyncio.to_thread(self.store.update_schedule_runner_status, last_started_at=started_at)
                due_tracks = await asyncio.to_thread(self.store.list_due_schedule_tracks, now_ts(), 5)
                for track in due_tracks:
                    try:
                        await self._schedule_refresh_track(track, allow_notify=True)
                        processed += 1
                    except Exception:
                        LOG.warning("Schedule track refresh failed for %s", track.get("track_id"), exc_info=True)
                # Check movie tracks in the same tick
                await self._check_movie_tracks()
                await asyncio.to_thread(
                    self.store.update_schedule_runner_status,
                    last_finished_at=now_ts(),
                    last_success_at=now_ts(),
                    last_error_at=None,
                    last_error_text=None,
                    last_due_count=len(due_tracks),
                    last_processed_count=processed,
                    metadata_source_health_json=self._schedule_source_snapshot("metadata"),
                    inventory_source_health_json=self._schedule_source_snapshot("inventory"),
                )
            except Exception as e:
                LOG.warning("Schedule runner loop failed", exc_info=True)
                await asyncio.to_thread(
                    self.store.update_schedule_runner_status,
                    last_finished_at=now_ts(),
                    last_error_at=now_ts(),
                    last_error_text=str(e),
                    last_due_count=len(due_tracks),
                    last_processed_count=processed,
                    metadata_source_health_json=self._schedule_source_snapshot("metadata"),
                    inventory_source_health_json=self._schedule_source_snapshot("inventory"),
                )

    # ------------------------------------------------------------------
    # Movie track checking (called from _schedule_runner_job)
    # ------------------------------------------------------------------

    async def _check_movie_tracks(self) -> None:
        """Check pending and downloading movie tracks."""
        pending = await asyncio.to_thread(self.store.get_pending_movie_tracks)
        for track in pending:
            try:
                await self._check_pending_movie_track(track)
            except Exception:
                LOG.warning("Movie track check failed for %s", track.get("track_id"), exc_info=True)

        downloading = await asyncio.to_thread(self.store.get_downloading_movie_tracks)
        for track in downloading:
            try:
                await self._check_downloading_movie_track(track)
            except Exception:
                LOG.warning("Movie Plex check failed for %s", track.get("track_id"), exc_info=True)

    async def _check_movie_release_gate(self, track: dict[str, Any]) -> bool:
        """Check if a movie's home release date has passed. Returns True if search should proceed."""
        track_id = str(track.get("track_id") or "")
        tmdb_id = int(track.get("tmdb_id") or 0)
        title = str(track.get("title") or "")
        release_status = str(track.get("release_status") or "unknown")

        # Already confirmed home available — proceed immediately
        if release_status == MovieReleaseStatus.HOME_AVAILABLE:
            return True

        # No TMDB ID — can't check, mark unknown and allow search (fall through to quality gate)
        if not tmdb_id:
            LOG.warning("Movie track %s (%s): no tmdb_id, skipping release gate", track_id, title)
            return True

        # Determine re-check interval based on current status
        if release_status == MovieReleaseStatus.PRE_THEATRICAL:
            recheck_interval = 24 * 3600  # 24 hours
        else:
            recheck_interval = 6 * 3600  # 6 hours for in_theaters, waiting_home, unknown

        # Check if we need to re-fetch from TMDB
        last_check = int(track.get("last_release_check_ts") or 0)
        if last_check > 0 and (now_ts() - last_check) < recheck_interval:
            # Not time to re-check yet. Use cached status to decide.
            if release_status in (
                MovieReleaseStatus.PRE_THEATRICAL,
                MovieReleaseStatus.IN_THEATERS,
                MovieReleaseStatus.WAITING_HOME,
            ):
                return False
            # UNKNOWN — let it through to search (quality.py will filter CAM/TS)
            return True

        # Fetch fresh release dates from TMDB
        try:
            dates = await asyncio.to_thread(self._ctx.tvmeta.get_movie_home_release, tmdb_id, self.cfg.tmdb_region)
        except Exception as e:
            LOG.warning("Movie release gate TMDB check failed for %s: %s", track_id, e)
            # Update last check time so we don't hammer TMDB
            await asyncio.to_thread(
                self.store.update_movie_release_dates,
                track_id,
                track.get("theatrical_ts"),
                track.get("digital_ts"),
                track.get("physical_ts"),
                track.get("home_release_ts"),
                bool(track.get("digital_estimated")),
                release_status,
            )
            return release_status not in (
                MovieReleaseStatus.PRE_THEATRICAL,
                MovieReleaseStatus.IN_THEATERS,
                MovieReleaseStatus.WAITING_HOME,
            )

        # Update DB with fresh dates
        await asyncio.to_thread(
            self.store.update_movie_release_dates,
            track_id,
            dates.theatrical_ts,
            dates.digital_ts,
            dates.physical_ts,
            dates.home_release_ts,
            dates.digital_estimated,
            dates.status.value,
        )

        new_status = dates.status
        LOG.info(
            "Movie track %s (%s): release status = %s, home_release_ts = %s",
            track_id,
            title,
            new_status.value,
            dates.home_release_ts,
        )

        if new_status == MovieReleaseStatus.HOME_AVAILABLE:
            return True

        # Set next_check_ts based on status
        if new_status == MovieReleaseStatus.WAITING_HOME and dates.home_release_ts:
            # Wake up right when home release hits
            next_check = min(dates.home_release_ts, now_ts() + recheck_interval)
        elif new_status == MovieReleaseStatus.PRE_THEATRICAL:
            next_check = now_ts() + 24 * 3600
        else:
            next_check = now_ts() + 6 * 3600

        await asyncio.to_thread(
            self.store.update_movie_track_status,
            track_id,
            next_check_ts=next_check,
        )
        return False

    async def _check_pending_movie_track(self, track: dict[str, Any]) -> None:
        """Search for a torrent for a pending movie track."""
        track_id = str(track.get("track_id") or "")
        search_query = str(track.get("search_query") or "")
        user_id = int(track.get("user_id") or 0)
        title = str(track.get("title") or "")
        year = track.get("year")

        # Release gate: skip torrent search if movie isn't on home video yet
        should_search = await self._check_movie_release_gate(track)
        if not should_search:
            LOG.info(
                "Movie track %s: skipping search (release gate: %s)",
                track_id,
                track.get("release_status", "unknown"),
            )
            return

        LOG.info("Movie track check: searching for '%s'", search_query)

        try:
            raw_rows = await asyncio.to_thread(
                self.qbt.search,
                search_query,
                plugin="enabled",
                search_cat="movies",
                timeout_s=self.cfg.search_timeout_s,
                poll_interval_s=self.cfg.poll_interval_s,
                early_exit_min_results=max(self.cfg.search_early_exit_min_results, 12),
                early_exit_idle_s=self.cfg.search_early_exit_idle_s,
                early_exit_max_wait_s=self.cfg.search_early_exit_max_wait_s,
            )
        except Exception as e:
            LOG.warning("Movie torrent search failed for %s: %s", track_id, e)
            await asyncio.to_thread(
                self.store.update_movie_track_status,
                track_id,
                status="pending",
                next_check_ts=now_ts() + 3600,
                error_text=str(e),
            )
            return

        defaults = await asyncio.to_thread(self.store.get_defaults, user_id, self.cfg)
        filtered = self._apply_filters(
            raw_rows,
            media_type="movie",
            min_seeds=int(defaults.get("default_min_seeds") or 0),
            min_size=None,
            max_size=None,
            min_quality=self.cfg.default_min_quality,
        )
        filtered = search_handler.deduplicate_results(filtered)

        # Pick best result by quality score
        best: dict[str, Any] | None = None
        best_score = (-1, -99999)
        for row in filtered:
            qs = row.get("_quality_score")
            if qs and not qs.is_rejected:
                score_key = (qs.resolution_tier, qs.format_score)
                if score_key > best_score:
                    best_score = score_key
                    best = row

        if best is None:
            LOG.info("Movie track %s: no acceptable torrent found, retrying in 1h", track_id)
            await asyncio.to_thread(
                self.store.update_movie_track_status,
                track_id,
                status="pending",
                next_check_ts=now_ts() + 3600,
            )
            return

        # Build URL and add torrent
        try:
            url = download_handler.result_to_url(best)
        except RuntimeError as e:
            LOG.warning("Movie track %s: no usable URL: %s", track_id, e)
            await asyncio.to_thread(
                self.store.update_movie_track_status,
                track_id,
                status="pending",
                next_check_ts=now_ts() + 3600,
                error_text=str(e),
            )
            return

        torrent_name = str(best.get("fileName") or best.get("name") or "")
        try:
            await asyncio.to_thread(
                self.qbt.add_url,
                url,
                category=self.cfg.movies_category,
                savepath=self.cfg.movies_path,
            )
        except Exception as e:
            LOG.warning("Movie track %s: add torrent failed: %s", track_id, e)
            await asyncio.to_thread(
                self.store.update_movie_track_status,
                track_id,
                status="pending",
                next_check_ts=now_ts() + 3600,
                error_text=str(e),
            )
            return

        torrent_hash = download_handler.extract_hash(best, url) or ""
        LOG.info("Movie track %s: downloading '%s' (hash=%s)", track_id, torrent_name, torrent_hash)
        await asyncio.to_thread(
            self.store.update_movie_track_status,
            track_id,
            status="downloading",
            torrent_hash=torrent_hash,
        )

        # Send notification
        if self.app and user_id:
            qs = best.get("_quality_score")
            qlabel = quality_label(qs.parsed) if qs else ""
            try:
                await self.app.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"⬇️ Found <b>{_h(title)}</b>"
                        f"{f' ({year})' if year else ''}"
                        f" — downloading now!\n\n"
                        f"<code>{_h(torrent_name)}</code>\n"
                        f"Quality: {_h(qlabel)}"
                    ),
                    parse_mode=_PM,
                )
                await asyncio.to_thread(
                    self.store.update_movie_track_status,
                    track_id,
                    notified=True,
                )
            except Exception:
                LOG.warning("Failed to send movie download notification", exc_info=True)

    async def _check_downloading_movie_track(self, track: dict[str, Any]) -> None:
        """Check if a downloading movie has appeared in Plex."""
        track_id = str(track.get("track_id") or "")
        title = str(track.get("title") or "")
        year = track.get("year")

        if not self.plex.ready():
            return

        in_plex = False
        try:
            sections = await asyncio.to_thread(self.plex._sections)
            for section in sections:
                if str(section.get("type") or "").lower() != "movie":
                    continue
                key = str(section.get("key") or "").strip()
                if not key:
                    continue
                root = await asyncio.to_thread(
                    self.plex._get_xml,
                    f"/library/sections/{key}/all",
                    params={"type": 1, "title": title},
                )
                for meta in root.findall(".//*[@ratingKey]"):
                    meta_title = normalize_title(str(meta.attrib.get("title") or ""))
                    want_title = normalize_title(title)
                    meta_year = str(meta.attrib.get("year") or "").strip()
                    if meta_title == want_title:
                        if year and meta_year.isdigit() and int(meta_year) == year:
                            in_plex = True
                            break
                        elif not year:
                            in_plex = True
                            break
                if in_plex:
                    break
        except Exception as e:
            LOG.warning("Movie Plex check failed for %s: %s", track_id, e)
            return

        if in_plex:
            LOG.info("Movie track complete, in Plex: %s (%s)", title, year)
            await asyncio.to_thread(self.store.delete_movie_track, track_id)

    # ------------------------------------------------------------------
    # TV schedule refresh (existing)
    # ------------------------------------------------------------------

    async def _schedule_refresh_track(
        self, track: dict[str, Any], *, allow_notify: bool = False
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        track_id = str(track.get("track_id") or "")
        try:
            probe = await asyncio.to_thread(self._schedule_probe_track, track)
        except Exception as e:
            metadata_state = self._schedule_source_snapshot("metadata")
            retry_at = now_ts() + self._schedule_metadata_retry_backoff_s(
                max(1, int(metadata_state.get("consecutive_failures") or 0))
            )
            LOG.warning("Schedule metadata refresh failed for %s: %s", track_id, e)
            last_probe = dict(track.get("last_probe_json") or {})
            if last_probe:
                last_probe["metadata_error"] = str(e)
                last_probe["last_refresh_error_at"] = now_ts()
                last_probe["metadata_stale"] = bool(last_probe.get("metadata_stale"))
            await asyncio.to_thread(
                self.store.update_schedule_track,
                track_id,
                last_probe_json=last_probe,
                last_probe_at=now_ts(),
                next_check_at=retry_at,
            )
            updated = await asyncio.to_thread(self.store.get_schedule_track_any, track_id)
            if updated is None:
                raise RuntimeError(f"Schedule track {track_id} disappeared after metadata retry update")
            return updated, last_probe
        auto_state = dict(self._schedule_episode_auto_state(track))
        auto_state.update(dict(probe.get("_auto_state") or {}))
        auto_state = self._schedule_sanitize_auto_state(auto_state, probe=probe)
        pending = set(track.get("pending_json") or [])
        cleared, stale, qbt_codes = self._schedule_reconcile_pending(track, probe)
        if cleared:
            pending -= cleared
            LOG.info(
                "Schedule cleared %d pending episodes now present locally: %s", len(cleared), ", ".join(sorted(cleared))
            )
        if stale:
            pending -= stale
            retry_codes = dict(auto_state.get("retry_codes") or {})
            for code in stale:
                retry_codes.pop(code, None)
            auto_state["retry_codes"] = retry_codes
            LOG.info("Schedule recovered %d stale pending episodes: %s", len(stale), ", ".join(sorted(stale)))
        should_auto, target_codes_or_reason = self._schedule_should_attempt_auto(track, probe)
        auto_acquired_codes: list[str] = []
        if should_auto and isinstance(target_codes_or_reason, list) and target_codes_or_reason:
            for target_code in target_codes_or_reason:
                try:
                    result = await self._schedule_attempt_auto_acquire(track, target_code)
                except schedule_handler.No1080pError as _e:
                    no_1080p_miss = dict(auto_state.get("no_1080p_miss") or {})
                    miss_count = int(no_1080p_miss.get(target_code) or 0) + 1
                    no_1080p_miss[target_code] = miss_count
                    auto_state["no_1080p_miss"] = no_1080p_miss
                    backoff_s = schedule_handler.schedule_no_1080p_backoff_s(miss_count)
                    auto_state["next_auto_retry_at"] = now_ts() + backoff_s
                    LOG.info(
                        "Schedule no-1080p miss %d for %s, backing off %ds",
                        miss_count,
                        target_code,
                        backoff_s,
                    )
                    if miss_count == 3 and allow_notify:
                        await self._schedule_notify_no_1080p(
                            track, target_code, miss_count, _e.lower_res_count, backoff_s
                        )
                    continue
                if result:
                    auto_acquired_codes.append(target_code)
                    pending.add(target_code)
                    retry_codes = dict(auto_state.get("retry_codes") or {})
                    retry_codes[target_code] = now_ts()
                    auto_state["retry_codes"] = retry_codes
                    auto_state["last_auto_code"] = target_code
                    auto_state["last_auto_at"] = now_ts()
                    # Clear no-1080p miss counter on success
                    no_1080p_miss = dict(auto_state.get("no_1080p_miss") or {})
                    no_1080p_miss.pop(target_code, None)
                    auto_state["no_1080p_miss"] = no_1080p_miss
                    if allow_notify:
                        await self._schedule_notify_auto_queued(track, target_code, result)
            if auto_acquired_codes:
                auto_state["next_auto_retry_at"] = None
            elif auto_state.get("next_auto_retry_at") is None:
                # Only set generic retry if No1080pError handler didn't already set a backoff
                auto_state["next_auto_retry_at"] = now_ts() + self._schedule_retry_interval_s()
        elif not probe.get("actionable_missing_codes"):
            auto_state["next_auto_retry_at"] = None
        auto_state = self._schedule_sanitize_auto_state(auto_state, probe=probe)
        next_check_at = self._schedule_next_check_at(
            probe.get("next_air_ts"),
            has_actionable_missing=bool(probe.get("actionable_missing_codes")),
            auto_state=auto_state,
        )

        store_probe = dict(probe)
        store_probe.pop("_auto_state", None)

        update_fields: dict[str, Any] = {
            "pending_json": sorted(pending),
            "auto_state_json": auto_state,
            "last_probe_json": store_probe,
            "last_probe_at": now_ts(),
            "next_check_at": next_check_at,
            "next_air_ts": store_probe.get("next_air_ts"),
            "show_json": probe.get("show") or track.get("show_json") or {},
        }
        if not probe.get("signature"):
            update_fields["last_missing_signature"] = None
            update_fields["skipped_signature"] = None
        await asyncio.to_thread(self.store.update_schedule_track, track_id, **update_fields)
        updated = await asyncio.to_thread(self.store.get_schedule_track_any, track_id)
        if updated is None:
            raise RuntimeError(f"Schedule track {track_id} disappeared after refresh update")
        if (
            allow_notify
            and not auto_acquired_codes
            and probe.get("signature")
            and probe.get("signature") != updated.get("skipped_signature")
            and probe.get("signature") != updated.get("last_missing_signature")
        ):
            await self._schedule_notify_missing(updated, probe)
        return updated, probe

    async def _schedule_notify_missing(self, track: dict[str, Any], probe: dict[str, Any]) -> None:
        if not self.app:
            return
        chat_id = int(track.get("chat_id") or 0)
        if not chat_id:
            LOG.warning("Schedule notify_missing skipped: no chat_id for track %s", track.get("track_id"))
            return
        text = self._schedule_missing_text(track, probe)
        try:
            sent = await self.app.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=self._schedule_missing_keyboard(str(track.get("track_id") or "")),
                parse_mode=_PM,
            )
            user_id = int(track.get("user_id") or chat_id)
            self._track_ephemeral_message(user_id, sent)
        except TelegramError as e:
            LOG.warning("Schedule notify_missing failed for track %s: %s", track.get("track_id"), e)
        # Always update signature so we don't re-send the same notification
        store_probe = dict(probe)
        store_probe.pop("_auto_state", None)
        await asyncio.to_thread(
            self.store.update_schedule_track,
            str(track.get("track_id") or ""),
            last_missing_signature=str(probe.get("signature") or "") or None,
            last_probe_json=store_probe,
            last_probe_at=now_ts(),
        )

    def _schedule_row_matches_episode(self, name: str, season: int, episode: int) -> bool:
        return episode_code(season, episode) in extract_episode_codes(name)

    def _schedule_episode_rank_key(
        self, row: dict[str, Any], show_name: str, season: int, episode: int
    ) -> tuple[int, ...]:
        name = str(row.get("fileName") or row.get("name") or "")
        seeds = int(row.get("nbSeeders") or row.get("seeders") or 0)
        size = int(row.get("fileSize") or row.get("size") or 0)
        exact_episode = 1 if self._schedule_row_matches_episode(name, season, episode) else 0
        exact_show = 1 if normalize_title(show_name) in normalize_title(name) else 0
        ts = score_torrent(name, size, seeds, media_type="episode")
        return (exact_episode, exact_show, seeds, ts.format_score)

    async def _schedule_download_episode(self, track: dict[str, Any], code: str) -> dict[str, Any]:
        return await schedule_handler.schedule_download_episode(
            self._ctx,
            track,
            code,
            apply_filters_fn=lambda rows, **kw: self._apply_filters(rows, media_type="episode", **kw),
            do_add_fn=self._do_add,
        )

    async def _schedule_download_requested(self, msg: Any, track: dict[str, Any], codes: list[str]) -> None:
        probe = track.get("last_probe_json") or {}
        available = set(probe.get("actionable_missing_codes") or probe.get("missing_codes") or [])
        pending = set(track.get("pending_json") or [])
        wanted = [code for code in codes if code in available and code not in pending]
        edit_text = getattr(msg, "edit_text", None)
        can_edit = callable(edit_text) and asyncio.iscoroutinefunction(edit_text)
        if not wanted:
            if can_edit:
                await msg.edit_text(
                    "Those episodes are no longer pending for this schedule.",
                    reply_markup=self._home_only_keyboard(),
                    parse_mode=_PM,
                )
            else:
                await msg.reply_text("Those episodes are no longer pending for this schedule.", parse_mode=_PM)
            return
        updated_pending = sorted(pending | set(wanted))
        await asyncio.to_thread(
            self.store.update_schedule_track,
            str(track.get("track_id") or ""),
            pending_json=updated_pending,
            skipped_signature=None,
        )
        show = track.get("show_json") or {}
        show_name = show.get("name") or "Show"
        ep_word = "episode" if len(wanted) == 1 else "episodes"
        status_lines = [
            "<b>⬇️ Queuing Episodes</b>",
            f"<b>{_h(show_name)}</b> · {len(wanted)} {ep_word}",
            "",
            "<i>Searching qBittorrent…</i>",
        ]
        if can_edit:
            await msg.edit_text("\n".join(status_lines), reply_markup=None, parse_mode=_PM)
            status_msg = msg
        else:
            status_msg = await msg.reply_text("\n".join(status_lines), parse_mode=_PM)
        failures: list[tuple[str, str]] = []
        success_lines: list[str] = []
        for code in wanted:
            try:
                out = await self._schedule_download_episode(track, code)
                success_lines.append(f"✅ <code>{_h(code)}</code>: {_h(out['name'])}")
                if out.get("hash"):
                    tracker_msg = await msg.reply_text(
                        f"<b>📡 Live Monitor</b> · <code>{_h(code)}</code>\n<i>Tracking download progress…</i>",
                        reply_markup=self._stop_download_keyboard(out["hash"]),
                        parse_mode=_PM,
                    )
                    self._start_progress_tracker(int(track.get("user_id") or 0), out["hash"], tracker_msg, out["name"])
                else:
                    self._start_pending_progress_tracker(
                        int(track.get("user_id") or 0), out["name"], out["category"], msg
                    )
            except Exception as e:
                failures.append((code, str(e)))
        if failures:
            remaining_pending = sorted(set(updated_pending) - {code for code, _detail in failures})
            await asyncio.to_thread(
                self.store.update_schedule_track, str(track.get("track_id") or ""), pending_json=remaining_pending
            )
        result_lines = [
            "<b>⬇️ Queue Results</b>",
            f"<b>{_h(show_name)}</b>",
            "",
        ]
        result_lines.extend(success_lines or ["• No episodes were queued."])
        for code, detail in failures:
            result_lines.append(f"❌ <code>{_h(code)}</code>: <i>{_h(detail)}</i>")
        result_lines.extend(["", "<i>Background monitoring is now active for queued episodes.</i>"])
        await status_msg.edit_text(
            "\n".join(result_lines), reply_markup=self._command_center_keyboard(), parse_mode=_PM
        )
        refreshed = await asyncio.to_thread(
            self.store.get_schedule_track, int(track.get("user_id") or 0), str(track.get("track_id") or "")
        )
        if refreshed:
            await self._schedule_refresh_track(refreshed, allow_notify=False)

    async def _schedule_pick_candidate(self, msg: Any, user_id: int, idx: int) -> None:
        flow = self._get_flow(user_id)
        if not flow or flow.get("mode") != "schedule":
            await self._render_schedule_ui(
                user_id,
                msg,
                {"mode": "schedule", "stage": "await_show"},
                "<b>⏰ Session Expired</b>\nThat schedule setup has expired.\n<i>Start /schedule again.</i>",
                reply_markup=None,
            )
            return
        candidates = list(flow.get("candidates") or [])
        if idx < 0 or idx >= len(candidates):
            await self._render_schedule_ui(
                user_id,
                msg,
                flow,
                "<b>⚠️ Show Not Found</b>\nThat show choice is no longer available.\n<i>Search again with /schedule.</i>",
                reply_markup=None,
            )
            return
        await self._render_schedule_ui(
            user_id,
            msg,
            flow,
            "<b>🔎 Looking Up Show</b>\n<i>Researching the show and comparing Plex/library episodes…</i>",
            reply_markup=None,
        )
        candidate = candidates[idx]
        try:
            bundle = await asyncio.to_thread(
                self._schedule_get_show_bundle,
                int(candidate.get("id") or 0),
                False,
                True,
            )
            raw_probe = await asyncio.to_thread(self._schedule_probe_bundle, bundle, None, None)
            probe = self._schedule_apply_tracking_mode(
                {"auto_state_json": {"tracking_mode": str(flow.get("tracking_mode") or "upcoming")}},
                raw_probe,
            )
        except Exception as e:
            await self._render_schedule_ui(
                user_id, msg, flow, f"<b>⚠️ Lookup Failed</b>\n<i>{_h(str(e))}</i>", reply_markup=None
            )
            return
        flow["stage"] = "confirm"
        flow["selected_show"] = self._schedule_show_info(bundle)
        flow["season"] = int(probe.get("season") or 1)
        flow["probe"] = probe
        flow["tracking_mode"] = str(flow.get("tracking_mode") or "upcoming")
        self._set_flow(user_id, flow)
        await self._render_schedule_ui(
            user_id,
            msg,
            flow,
            self._schedule_preview_text(probe),
            reply_markup=self._schedule_preview_keyboard(probe),
        )

    async def _schedule_confirm_selection(
        self, msg: Any, user_id: int, chat_id: int, post_action: str | None = None
    ) -> None:
        flow = self._get_flow(user_id)
        if not flow or flow.get("mode") != "schedule" or flow.get("stage") != "confirm":
            await self._render_schedule_ui(
                user_id,
                msg,
                {"mode": "schedule", "stage": "await_show"},
                "<b>⏰ Session Expired</b>\nThat schedule setup is no longer active.\n<i>Start /schedule again.</i>",
                reply_markup=None,
            )
            return
        probe = dict(flow.get("probe") or {})
        show = dict(flow.get("selected_show") or {})
        season = int(flow.get("season") or probe.get("season") or 1)
        track_auto_state = self._schedule_apply_tracking_mode(
            {"auto_state_json": {"tracking_mode": str(flow.get("tracking_mode") or "upcoming")}},
            probe,
        ).get("_auto_state")

        store_probe = dict(probe)
        store_probe.pop("_auto_state", None)

        next_check_at = self._schedule_next_check_at(
            store_probe.get("next_air_ts"),
            has_actionable_missing=bool(store_probe.get("actionable_missing_codes")),
            auto_state=track_auto_state,
        )
        created, track = await asyncio.to_thread(
            self.store.create_schedule_track,
            user_id=int(user_id),
            chat_id=int(chat_id),
            show=show,
            season=season,
            probe=store_probe,
            next_check_at=next_check_at,
            initial_auto_state=track_auto_state,
        )
        effective_probe = track.get("last_probe_json") or probe
        final_text = self._schedule_track_ready_text(track, effective_probe, duplicate=not created)
        track_id = str(track.get("track_id") or "")

        if post_action == "all":
            codes = list(effective_probe.get("actionable_missing_codes") or effective_probe.get("missing_codes") or [])
            await self._render_schedule_ui(user_id, msg, flow, final_text, reply_markup=None)
            self._clear_flow(user_id)
            await self._schedule_download_requested(msg, track, codes)
            return

        if post_action == "series":
            # Download all actionable missing across every season of this show
            codes = list(
                effective_probe.get("series_actionable_all") or effective_probe.get("actionable_missing_codes") or []
            )
            await self._render_schedule_ui(user_id, msg, flow, final_text, reply_markup=None)
            self._clear_flow(user_id)
            await self._schedule_download_requested(msg, track, codes)
            return

        if post_action == "pick":
            current_missing = list(
                effective_probe.get("actionable_missing_codes") or effective_probe.get("missing_codes") or []
            )
            all_missing = self._schedule_picker_all_missing(effective_probe, season, current_missing)
            if not any(all_missing.values()):
                await self._render_schedule_ui(user_id, msg, flow, final_text, reply_markup=None)
                self._clear_flow(user_id)
                return
            flow["stage"] = "picker"
            flow["picker_selected"] = []
            flow["picker_season"] = season
            flow["picker_all_missing"] = all_missing
            flow["picker_has_preview"] = True
            flow["picker_track_id"] = track_id
            self._set_flow(user_id, flow)
            await self._render_schedule_ui(
                user_id,
                msg,
                flow,
                self._schedule_picker_text(flow),
                reply_markup=self._schedule_picker_keyboard(flow),
            )
            return

        final_markup: InlineKeyboardMarkup | None = None
        if effective_probe.get("signature"):
            final_text += "\n\n" + self._schedule_missing_text(track, effective_probe)
            final_markup = self._schedule_missing_keyboard(track_id)
            await asyncio.to_thread(
                self.store.update_schedule_track,
                track_id,
                last_missing_signature=str(effective_probe.get("signature") or "") or None,
                last_probe_json=effective_probe,
                last_probe_at=now_ts(),
            )
        await self._render_schedule_ui(user_id, msg, flow, final_text, reply_markup=final_markup)
        self._clear_flow(user_id)

    # ---------- Parsing helpers ----------

    def _build_search_parser(self) -> argparse.ArgumentParser:
        """Delegation stub -- logic lives in handlers/search.py."""
        return search_handler.build_search_parser()

    def _apply_filters(
        self,
        rows: list[dict[str, Any]],
        *,
        min_seeds: int,
        min_size: int | None,
        max_size: int | None,
        min_quality: int,
        media_type: str = "movie",
    ) -> list[dict[str, Any]]:
        """Delegation stub -- logic lives in handlers/search.py."""
        return search_handler.apply_filters(
            rows,
            min_seeds=min_seeds,
            min_size=min_size,
            max_size=max_size,
            min_quality=min_quality,
            media_type=media_type,
        )

    @staticmethod
    def _deduplicate_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Delegation stub -- logic lives in handlers/search.py."""
        return search_handler.deduplicate_results(rows)

    @staticmethod
    def _sort_rows(rows: list[dict[str, Any]], key: str, order: str) -> list[dict[str, Any]]:
        """Delegation stub -- logic lives in handlers/search.py."""
        return search_handler.sort_rows(rows, key, order)

    def _parse_tv_filter(self, text: str) -> tuple[int | None, int | None] | None:
        """Delegation stub -- logic lives in handlers/search.py."""
        return search_handler.parse_tv_filter(text)

    @staticmethod
    def _build_tv_query(title: str, season: int | None, episode: int | None) -> str:
        """Delegation stub -- logic lives in handlers/search.py."""
        return search_handler.build_tv_query(title, season, episode)

    def _strip_patchy_name(self, text: str) -> str:
        """Delegation stub -- logic lives in handlers/search.py."""
        return search_handler.strip_patchy_name(text, self.cfg.patchy_chat_name)

    def _extract_search_intent(self, text: str) -> tuple[str | None, str]:
        """Delegation stub -- logic lives in handlers/search.py."""
        return search_handler.extract_search_intent(text, self.cfg.patchy_chat_name)

    @staticmethod
    def _chat_needs_qbt_snapshot(text: str) -> bool:
        """Delegation stub — logic lives in handlers/chat.py."""
        return chat_handler.chat_needs_qbt_snapshot(text)

    def _build_qbt_snapshot(self) -> str:
        """Delegation stub — logic lives in handlers/chat.py."""
        return chat_handler.build_qbt_snapshot(self._ctx)

    def _patchy_system_prompt(self) -> str:
        """Delegation stub — logic lives in handlers/chat.py."""
        return chat_handler.patchy_system_prompt(self._ctx)

    async def _reply_patchy_chat(self, msg: Any, user_id: int, text: str) -> None:
        """Delegation stub — logic lives in handlers/chat.py."""
        await chat_handler.reply_patchy_chat(self._ctx, msg, user_id, text)

    def _render_page(
        self, search_meta: dict[str, Any], rows: list[dict[str, Any]], page: int
    ) -> tuple[str, InlineKeyboardMarkup | None]:
        """Delegation stub -- logic lives in handlers/search.py."""
        return search_handler.render_page(
            search_meta, rows, page, page_size=self.cfg.page_size, nav_footer_fn=self._nav_footer
        )

    # ---------- Theatrical release detection ----------

    async def _detect_movie_release_status(
        self,
        query: str,
        *,
        region: str,
    ) -> tuple:
        """Classify a movie query's release status via TMDB.

        Returns (status, tmdb_id, raw_title, year, theatrical_ts).
        Returns (UNKNOWN, None, None, None, None) on any failure or no TMDB key.
        Never raises.
        """
        from .clients.tv_metadata import MovieReleaseStatus

        if not self.cfg.tmdb_api_key:
            return MovieReleaseStatus.UNKNOWN, None, None, None, None

        try:
            movies = await asyncio.to_thread(self.tvmeta.search_movies, query, 1)
        except Exception as exc:
            LOG.warning("theatrical check search_movies(%r) failed: %s", query, exc)
            return MovieReleaseStatus.UNKNOWN, None, None, None, None

        if not movies:
            return MovieReleaseStatus.UNKNOWN, None, None, None, None

        top = movies[0]
        tmdb_id: int = int(top["tmdb_id"])
        title: str = str(top.get("title") or query)
        year: int | None = top.get("year")

        try:
            dates = await asyncio.to_thread(self.tvmeta.get_movie_home_release, tmdb_id, region)
        except Exception as exc:
            LOG.warning("theatrical check get_movie_home_release(tmdb_id=%r) failed: %s", tmdb_id, exc)
            return MovieReleaseStatus.UNKNOWN, tmdb_id, title, year, None

        return dates.status, tmdb_id, title, year, dates.theatrical_ts

    async def _show_theatrical_block(
        self,
        status_msg,
        release_status,
        movie_title: str,
        tmdb_id: int,
        theatrical_ts: int | None,
    ) -> None:
        """Edit status_msg into a theatrical-block notice with a Track button."""
        from .clients.tv_metadata import MovieReleaseStatus

        title_safe = _h(movie_title)

        if release_status == MovieReleaseStatus.PRE_THEATRICAL:
            if theatrical_ts and theatrical_ts > now_ts():
                when = _relative_time(theatrical_ts)
                body = (
                    f"<b>🎬 Not Yet Released</b>\n\n"
                    f"<b>{title_safe}</b> hasn't reached theaters yet — "
                    f"theatrical release is {when}.\n\n"
                    f"<i>No copies exist yet. Track it to auto-download when a quality release becomes available.</i>"
                )
            else:
                body = (
                    f"<b>🎬 Not Yet Released</b>\n\n"
                    f"<b>{title_safe}</b> hasn't been released yet.\n\n"
                    f"<i>No copies exist yet. Track it to auto-download when a quality release becomes available.</i>"
                )
        else:  # IN_THEATERS
            body = (
                f"<b>🎬 Currently In Theaters</b>\n\n"
                f"<b>{title_safe}</b> is only available in theaters — "
                f"no home release has been announced yet.\n\n"
                f"<i>Only theater-recorded sources (TeleSync/CAM) exist right now. "
                f"No WEB-DL, streaming, or Blu-ray rips are available.</i>"
            )

        track_btn = InlineKeyboardButton("🎬 Track this movie", callback_data=f"msch:pick:{tmdb_id}")
        cancel_btn = InlineKeyboardButton("✖ Dismiss", callback_data="msch:cancel")
        kb = InlineKeyboardMarkup([[track_btn], [cancel_btn]])

        await status_msg.edit_text(body, reply_markup=kb, parse_mode=_PM)

    # ---------- Core actions ----------

    async def _run_search(
        self,
        *,
        update: Update,
        query: str,
        plugin: str = "enabled",
        search_cat: str = "all",
        min_seeds: int | None = None,
        min_size: int | None = None,
        max_size: int | None = None,
        min_quality: int | None = None,
        sort_key: str | None = None,
        order: str | None = None,
        limit: int | None = None,
        media_hint: str = "any",
        tv_flow: dict[str, Any] | None = None,
        current_tv_ui_message: Any | None = None,
        nav_user_id: int | None = None,
        current_nav_ui_message: Any | None = None,
    ) -> None:
        msg = update.effective_message
        if not msg:
            return

        # Cap query length to prevent abuse via Telegram's 4096-char message limit
        if len(query) > 200:
            await msg.reply_text("Search query is too long (max 200 characters).", parse_mode=_PM)
            return

        user_id = update.effective_user.id
        defaults = self.store.get_defaults(user_id, self.cfg)
        min_seeds = int(min_seeds if min_seeds is not None else defaults["default_min_seeds"])
        min_quality = int(min_quality if min_quality is not None else self.cfg.default_min_quality)
        sort_key = (sort_key or defaults["default_sort"] or "seeds").lower()
        order = (order or defaults["default_order"] or "desc").lower()
        limit = int(limit if limit is not None else defaults["default_limit"])
        limit = max(1, min(50, limit))

        searching_text = f"<b>🔎 Searching for {_h(query)}…</b>\n<i>Querying qBittorrent search plugins…</i>"
        if isinstance(tv_flow, dict):
            status_msg = await self._render_tv_ui(
                user_id,
                current_tv_ui_message or msg,
                tv_flow,
                searching_text,
                reply_markup=None,
                current_ui_message=current_tv_ui_message,
            )
        elif nav_user_id is not None:
            status_msg = await self._render_nav_ui(
                nav_user_id,
                current_nav_ui_message or msg,
                searching_text,
                reply_markup=None,
                current_ui_message=current_nav_ui_message,
            )
        else:
            status_msg = await msg.reply_text(searching_text, parse_mode=_PM)

        # --- Theatrical detection (movies only) ---
        # WAITING_HOME / HOME_AVAILABLE intentionally allow search — WEB-DL/screener
        # rips often appear before official digital release date.
        if media_hint == "movies":
            from .clients.tv_metadata import MovieReleaseStatus

            (
                release_status,
                det_tmdb_id,
                det_title,
                det_year,
                det_theatrical_ts,
            ) = await self._detect_movie_release_status(query, region=self.cfg.tmdb_region)

            if release_status in (MovieReleaseStatus.IN_THEATERS, MovieReleaseStatus.PRE_THEATRICAL):
                # Set up flow so msch:pick handler can find the candidate
                self._set_flow(
                    user_id,
                    {
                        "mode": "msch_add",
                        "stage": "title",
                        "candidates": [
                            {
                                "tmdb_id": det_tmdb_id,
                                "title": det_title or query,
                                "year": det_year,
                            }
                        ],
                    },
                )
                display = f"{det_title} ({det_year})" if det_year else (det_title or query)
                await self._show_theatrical_block(
                    status_msg,
                    release_status,
                    display,
                    det_tmdb_id or 0,
                    det_theatrical_ts,
                )
                return

            if release_status == MovieReleaseStatus.UNKNOWN and self.cfg.tmdb_api_key:
                try:
                    await status_msg.edit_text(
                        f"<b>🔎 Searching for {_h(query)}…</b>\n"
                        f"<i>⚠️ Could not verify release status — showing all available results.</i>",
                        parse_mode=_PM,
                    )
                except Exception:
                    pass  # non-critical — search continues regardless
        # --- End theatrical detection ---

        try:
            plugin_scope = (plugin or "").strip() or "enabled"
            early_min_results = max(self.cfg.search_early_exit_min_results, limit * 3)
            raw_rows = await asyncio.to_thread(
                self.qbt.search,
                query,
                plugin=plugin_scope,
                search_cat=search_cat,
                timeout_s=self.cfg.search_timeout_s,
                poll_interval_s=self.cfg.poll_interval_s,
                early_exit_min_results=early_min_results,
                early_exit_idle_s=self.cfg.search_early_exit_idle_s,
                early_exit_max_wait_s=self.cfg.search_early_exit_max_wait_s,
            )
            _mt = "episode" if media_hint == "tv" else "movie"
            filtered = self._apply_filters(
                raw_rows,
                min_seeds=min_seeds,
                min_size=min_size,
                max_size=max_size,
                min_quality=min_quality,
                media_type=_mt,
            )
            filtered = self._deduplicate_results(filtered)
            ranked = self._sort_rows(filtered, key=sort_key, order=order)
            ranked = search_handler.prioritize_results(ranked)
            final_rows = ranked[:limit]

            if not final_rows:
                kwargs: dict[str, Any] = {"parse_mode": _PM}
                if isinstance(tv_flow, dict):
                    kwargs["reply_markup"] = InlineKeyboardMarkup(self._nav_footer(back_data="menu:tv"))
                await status_msg.edit_text(
                    "<b>📭 No Results</b>\n<i>No matches found. Try a broader title or lower quality filter.</i>",
                    **kwargs,
                )
                return

            options = {
                "query": query,
                "plugin": plugin_scope,
                "search_cat": search_cat,
                "min_seeds": min_seeds,
                "min_size": min_size,
                "max_size": max_size,
                "min_quality": min_quality,
                "sort": sort_key,
                "order": order,
                "limit": limit,
                "media_hint": media_hint,
            }

            # Map media_hint to score_torrent media_type for correct size ranges
            mt = "episode" if media_hint == "tv" else "movie"
            sid = self.store.save_search(user_id, query, options, final_rows, media_type=mt)
            payload = self.store.get_search(user_id, sid)
            if payload is None:
                raise RuntimeError(f"Search {sid} was saved but could not be read back")
            search_meta, rows = payload
            text, markup = self._render_page(search_meta, rows, page=1)
            await status_msg.edit_text(text, reply_markup=markup, disable_web_page_preview=True, parse_mode=_PM)
            if nav_user_id is not None:
                self._remember_nav_ui_message(nav_user_id, status_msg)
        except Exception as e:
            LOG.exception("Search failed")
            kwargs = {"parse_mode": _PM}
            if isinstance(tv_flow, dict):
                kwargs["reply_markup"] = InlineKeyboardMarkup(self._nav_footer(back_data="menu:tv"))
            elif nav_user_id is not None:
                kwargs["reply_markup"] = InlineKeyboardMarkup(self._nav_footer())
            await status_msg.edit_text(f"Search failed: {_h(str(e))}", **kwargs)

    # ---------- Remove system (delegated to handlers.remove) ----------

    def _remove_roots(self) -> list[dict[str, str]]:
        return remove_handler.remove_roots(self._ctx)

    @staticmethod
    def _path_size_bytes(path: str) -> int:
        return remove_handler.path_size_bytes(path)

    @staticmethod
    def _remove_match_score(query_norm: str, candidate_norm: str) -> int:
        return remove_handler.remove_match_score(query_norm, candidate_norm)

    def _find_remove_candidates(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        return remove_handler.find_remove_candidates(self._ctx, query, limit)

    def _remove_prompt_keyboard(self, selected_count: int = 0) -> InlineKeyboardMarkup:
        return remove_handler.remove_prompt_keyboard(selected_count)

    def _remove_browse_root_keyboard(
        self, movie_count: int, show_count: int, selected_count: int = 0
    ) -> InlineKeyboardMarkup:
        return remove_handler.remove_browse_root_keyboard(movie_count, show_count, selected_count)

    @staticmethod
    def _remove_selected_path(candidate: dict[str, Any]) -> str:
        return remove_handler.remove_selected_path(candidate)

    def _remove_selection_items(self, flow: dict[str, Any] | None) -> list[dict[str, Any]]:
        return remove_handler.remove_selection_items(flow)

    def _remove_selected_paths(self, flow: dict[str, Any] | None) -> set[str]:
        return remove_handler.remove_selected_paths(flow)

    def _remove_selection_count(self, flow: dict[str, Any] | None) -> int:
        return remove_handler.remove_selection_count(flow)

    def _remove_toggle_candidate(self, flow: dict[str, Any], candidate: dict[str, Any]) -> bool:
        return remove_handler.remove_toggle_candidate(flow, candidate)

    def _remove_selection_total_size(self, candidates: list[dict[str, Any]]) -> int:
        return remove_handler.remove_selection_total_size(candidates)

    def _remove_effective_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return remove_handler.remove_effective_candidates(candidates)

    def _remove_toggle_label(self, candidate: dict[str, Any], selected_paths: set[str]) -> str:
        return remove_handler.remove_toggle_label(candidate, selected_paths)

    def _remove_candidate_keyboard(
        self, candidates: list[dict[str, Any]], selected_paths: set[str] | None = None
    ) -> InlineKeyboardMarkup:
        return remove_handler.remove_candidate_keyboard(candidates, selected_paths)

    def _remove_confirm_keyboard(self, selected_count: int) -> InlineKeyboardMarkup:
        return remove_handler.remove_confirm_keyboard(selected_count)

    @staticmethod
    def _remove_kind_label(kind: str, is_dir: bool) -> str:
        return remove_handler.remove_kind_label(kind, is_dir)

    def _remove_enrich_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        return remove_handler.remove_enrich_candidate(candidate)

    def _remove_candidate_text(self, candidate: dict[str, Any]) -> str:
        return remove_handler.remove_candidate_text(candidate)

    def _remove_candidates_text(
        self, query: str, candidates: list[dict[str, Any]], selected_paths: set[str] | None = None
    ) -> str:
        return remove_handler.remove_candidates_text(query, candidates, selected_paths)

    def _remove_confirm_text(self, candidates: list[dict[str, Any]]) -> str:
        return remove_handler.remove_confirm_text(candidates)

    def _remove_show_action_keyboard(self, series_selected: bool, selected_count: int) -> InlineKeyboardMarkup:
        return remove_handler.remove_show_action_keyboard(series_selected, selected_count)

    def _remove_season_action_keyboard(self, selected: bool, selected_count: int) -> InlineKeyboardMarkup:
        return remove_handler.remove_season_action_keyboard(selected, selected_count)

    @staticmethod
    def _remove_page_bounds(items: list[dict[str, Any]], page: int, per_page: int = 8) -> tuple[int, int, int, int]:
        return remove_handler.remove_page_bounds(items, page, per_page)

    def _remove_paginated_keyboard(
        self,
        items: list[dict[str, Any]],
        page: int,
        *,
        item_prefix: str,
        nav_prefix: str,
        back_callback: str | None = None,
        selected_paths: set[str] | None = None,
    ) -> InlineKeyboardMarkup:
        return remove_handler.remove_paginated_keyboard(
            items,
            page,
            item_prefix=item_prefix,
            nav_prefix=nav_prefix,
            back_callback=back_callback,
            selected_paths=selected_paths,
        )

    def _remove_list_text(
        self, title: str, items: list[dict[str, Any]], page: int, *, hint: str, selected_paths: set[str] | None = None
    ) -> str:
        return remove_handler.remove_list_text(title, items, page, hint=hint, selected_paths=selected_paths)

    def _remove_library_items(self, root_key: str) -> list[dict[str, Any]]:
        return remove_handler.remove_library_items(self._ctx, root_key)

    def _remove_show_children(self, show_candidate: dict[str, Any]) -> list[dict[str, Any]]:
        return remove_handler.remove_show_children(show_candidate)

    def _remove_season_children(self, season_candidate: dict[str, Any]) -> list[dict[str, Any]]:
        return remove_handler.remove_season_children(season_candidate)

    @staticmethod
    def _extract_movie_name(folder_name: str) -> str:
        return remove_handler.extract_movie_name(folder_name)

    @staticmethod
    def _extract_show_name(folder_name: str) -> str:
        return remove_handler.extract_show_name(folder_name)

    def _remove_group_tv_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return remove_handler.remove_group_tv_items(items)

    def _remove_show_group_children(self, group_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return remove_handler.remove_show_group_children(group_items)

    def _remove_group_any_selected(self, flow: dict[str, Any], group_item: dict[str, Any]) -> bool:
        return remove_handler.remove_group_any_selected(flow, group_item)

    def _remove_toggle_group(self, flow: dict[str, Any], group_item: dict[str, Any]) -> bool:
        return remove_handler.remove_toggle_group(flow, group_item)

    def _remove_show_actions_text(self, show_candidate: dict[str, Any], series_selected: bool) -> str:
        return remove_handler.remove_show_actions_text(show_candidate, series_selected)

    def _remove_season_actions_text(self, season_candidate: dict[str, Any]) -> str:
        return remove_handler.remove_season_actions_text(season_candidate)

    def _cleanup_qbt_for_path(self, target_path: str) -> list[str]:
        return remove_handler.cleanup_qbt_for_path(self._ctx, target_path)

    def _delete_remove_candidate(
        self, candidate: dict[str, Any], *, user_id: int | None = None, chat_id: int | None = None
    ) -> dict[str, Any]:
        return remove_handler.delete_remove_candidate(self._ctx, candidate, user_id=user_id, chat_id=chat_id)

    def _delete_remove_candidates(
        self, candidates: list[dict[str, Any]], *, user_id: int | None = None, chat_id: int | None = None
    ) -> str:
        return remove_handler.delete_remove_candidates(self._ctx, candidates, user_id=user_id, chat_id=chat_id)

    def _schedule_active_line(self, track: dict[str, Any]) -> str:
        probe = dict(track.get("last_probe_json") or {})
        show = dict(track.get("show_json") or probe.get("show") or {})
        name = str(show.get("name") or track.get("show_name") or "Unknown show")
        season = int(track.get("season") or probe.get("season") or 1)
        actionable = len(probe.get("actionable_missing_codes") or [])
        pending = len(track.get("pending_json") or probe.get("pending_codes") or [])
        unreleased = len(probe.get("unreleased_codes") or [])
        if actionable > 0:
            lead = "🔍"
            status = f"<b>{actionable} missing</b>"
        elif pending > 0:
            lead = "⬇️"
            status = f"<b>{pending} downloading</b>"
        elif unreleased > 0:
            lead = "⏰"
            status = "waiting on release"
        else:
            lead = "✅"
            status = "up to date"
        details: list[str] = [status]
        if unreleased > 0:
            details.append(f"{unreleased} unreleased")
        next_air_ts = int(track.get("next_air_ts") or probe.get("next_air_ts") or 0)
        if next_air_ts > 0:
            details.append(f"next {_relative_time(next_air_ts)}")
        next_check_at = int(track.get("next_check_at") or 0)
        if next_check_at > 0:
            details.append(f"check {_relative_time(next_check_at)}")
        if probe.get("metadata_stale"):
            details.append("⚠️ stale data")
        detail_line = " · ".join(details[:3])
        return f"{lead} <b>{_h(name)}</b>\n   Season {season} · {detail_line}"

    def _schedule_paused_line(self, name: str, season: int) -> str:
        return f"⏸ <b>{_h(name)}</b>\n   Season {season} · <i>paused</i>"

    async def _send_active(self, msg: Any, n: int = 10, user_id: int | None = None) -> None:
        all_items = await asyncio.to_thread(self.qbt.list_torrents, filter_name="all", limit=50)
        active_downloads = [t for t in all_items if str(t.get("state") or "") in _ACTIVE_DL_STATES][:n]
        schedule_tracks: list[dict[str, Any]] = []
        if user_id is not None:
            schedule_tracks = await asyncio.to_thread(
                self.store.list_schedule_tracks, int(user_id), True, max(5, min(20, n))
            )

        lines: list[str] = []
        if not active_downloads and not schedule_tracks:
            lines.append("<b>📭 Nothing Active</b>\n<i>No downloads or tracking jobs running.</i>")
        elif active_downloads:
            lines.append("<b>📥 Current Active Downloads</b>")
            for t in active_downloads:
                name = t.get("name", "?")
                progress = float(t.get("progress", 0.0)) * 100
                ds = human_size(int(t.get("dlspeed", 0))) + "/s"
                us = human_size(int(t.get("upspeed", 0))) + "/s"
                state_txt = self._state_label(t)
                eta_txt = self._eta_label(t)
                lines.append(
                    f"• <code>{_h(name)}</code>\n  {progress:.1f}% | <b>{state_txt}</b> | ↓ <code>{ds}</code> ↑ <code>{us}</code> | ETA <code>{eta_txt}</code>"
                )
        else:
            lines.append("<b>📥 Current Active Downloads</b>")
            lines.append("• none")

        lines.append("")
        lines.append("<b>📺 Scheduled Tracking</b>")
        if schedule_tracks:
            for track in schedule_tracks:
                lines.append(self._schedule_active_line(track))
        else:
            lines.append("• none")

        await msg.reply_text("\n".join(lines), parse_mode=_PM)

    async def _render_active_ui(
        self, user_id: int, msg: Any, n: int = 10, current_ui_message: Any | None = None
    ) -> Any:
        all_items = await asyncio.to_thread(self.qbt.list_torrents, filter_name="all", limit=50)
        active_downloads = [t for t in all_items if str(t.get("state") or "") in _ACTIVE_DL_STATES][:n]
        schedule_tracks = await asyncio.to_thread(
            self.store.list_schedule_tracks, int(user_id), True, max(5, min(20, n))
        )

        if not active_downloads and not schedule_tracks:
            text = "<b>📭 Nothing Active</b>\n<i>No downloads or tracking jobs running.</i>"
        else:
            lines: list[str] = []
            if active_downloads:
                lines.append("<b>📥 Current Active Downloads</b>")
                for t in active_downloads:
                    name = t.get("name", "?")
                    progress = float(t.get("progress", 0.0)) * 100
                    ds = human_size(int(t.get("dlspeed", 0))) + "/s"
                    us = human_size(int(t.get("upspeed", 0))) + "/s"
                    state_txt = self._state_label(t)
                    eta_txt = self._eta_label(t)
                    lines.append(
                        f"• <code>{_h(name)}</code>\n  {progress:.1f}% | <b>{state_txt}</b> | ↓ <code>{ds}</code> ↑ <code>{us}</code> | ETA <code>{eta_txt}</code>"
                    )
            else:
                lines.append("<b>📥 Current Active Downloads</b>")
                lines.append("• none")

            lines.append("")
            lines.append("<b>📺 Scheduled Tracking</b>")
            if schedule_tracks:
                for track in schedule_tracks:
                    lines.append(self._schedule_active_line(track))
            else:
                lines.append("• none")
            text = "\n".join(lines)
        return await self._render_nav_ui(user_id, msg, text, current_ui_message=current_ui_message)

    async def _send_categories(self, msg: Any) -> None:
        ok, reason = self._storage_status()
        cats = await asyncio.to_thread(self.qbt.list_categories)
        lines = ["<b>⚙️ Categories</b>"]
        lines.append(f"• status: <b>{'ready' if ok else 'not ready'}</b> (<code>{_h(reason)}</code>)")
        lines.append(
            f"• NVMe mount policy: <b>{'required' if self.cfg.require_nvme_mount else 'optional'}</b> @ <code>{_h(self.cfg.nvme_mount_path)}</code>"
        )
        lines.append(f"• Movies path: <code>{_h(self.cfg.movies_path)}</code>")
        lines.append(f"• TV path: <code>{_h(self.cfg.tv_path)}</code>")
        lines.append(f"• Spam path: <code>{_h(self.cfg.spam_path)}</code>")
        lines.append("")
        lines.append("<b>qBittorrent categories:</b>")
        if not cats:
            lines.append("• (none)")
        else:
            for name, meta in sorted(cats.items()):
                save_path = meta.get("savePath", "") if isinstance(meta, dict) else ""
                lines.append(f"• <code>{_h(name)}</code> → <code>{_h(save_path)}</code>")
        await msg.reply_text("\n".join(lines), parse_mode=_PM)

    async def _render_categories_ui(self, user_id: int, msg: Any, current_ui_message: Any | None = None) -> Any:
        ok, reason = self._storage_status()
        cats = await asyncio.to_thread(self.qbt.list_categories)
        lines = ["<b>⚙️ Categories</b>"]
        lines.append(f"• status: <b>{'ready' if ok else 'not ready'}</b> (<code>{_h(reason)}</code>)")
        lines.append(
            f"• NVMe mount policy: <b>{'required' if self.cfg.require_nvme_mount else 'optional'}</b> @ <code>{_h(self.cfg.nvme_mount_path)}</code>"
        )
        lines.append(f"• Movies path: <code>{_h(self.cfg.movies_path)}</code>")
        lines.append(f"• TV path: <code>{_h(self.cfg.tv_path)}</code>")
        lines.append(f"• Spam path: <code>{_h(self.cfg.spam_path)}</code>")
        lines.append("")
        lines.append("<b>qBittorrent categories:</b>")
        if not cats:
            lines.append("• (none)")
        else:
            for name, meta in sorted(cats.items()):
                save_path = meta.get("savePath", "") if isinstance(meta, dict) else ""
                lines.append(f"• <code>{_h(name)}</code> → <code>{_h(save_path)}</code>")
        return await self._render_nav_ui(user_id, msg, "\n".join(lines), current_ui_message=current_ui_message)

    async def _send_plugins(self, msg: Any) -> None:
        plugins = await asyncio.to_thread(self.qbt.list_search_plugins)
        if not plugins:
            await msg.reply_text(
                "<b>🔌 Plugins</b>\n<i>No search plugins installed in qBittorrent.</i>", parse_mode=_PM
            )
            return
        lines = ["<b>🔌 Plugins</b>"]
        for p in plugins:
            pname = _h(str(p.get("fullName") or p.get("name") or "?"))
            lines.append(
                f"• <code>{pname}</code> | enabled=<b>{p.get('enabled')}</b> | version=<code>{_h(str(p.get('version') or '?'))}</code>"
            )
        await msg.reply_text("\n".join(lines), parse_mode=_PM)

    async def _render_plugins_ui(self, user_id: int, msg: Any, current_ui_message: Any | None = None) -> Any:
        plugins = await asyncio.to_thread(self.qbt.list_search_plugins)
        if not plugins:
            text = "<b>🔌 Plugins</b>\n<i>No search plugins installed in qBittorrent.</i>"
        else:
            lines = ["<b>🔌 Plugins</b>"]
            for p in plugins:
                pname = _h(str(p.get("fullName") or p.get("name") or "?"))
                lines.append(
                    f"• <code>{pname}</code> | enabled=<b>{p.get('enabled')}</b> | version=<code>{_h(str(p.get('version') or '?'))}</code>"
                )
            text = "\n".join(lines)
        return await self._render_nav_ui(user_id, msg, text, current_ui_message=current_ui_message)

    # ---------- Commands ----------

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_start(self, update, context)

    async def cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_search(self, update, context)

    async def cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_schedule(self, update, context)

    async def cmd_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_remove(self, update, context)

    async def _open_remove_search_prompt(
        self, user_id: int, msg: Any, *, current_ui_message: Any | None = None
    ) -> None:
        flow = self._get_flow(user_id) or {"mode": "remove", "selected_items": []}
        flow["mode"] = "remove"
        flow["stage"] = "await_query"
        self._set_flow(user_id, flow)
        selected_count = self._remove_selection_count(flow)
        await self._render_remove_ui(
            user_id,
            msg,
            flow,
            "🗑️ <b>Remove from Library</b>\n\nType the name of a movie or show to find it directly.\n\nOr tap <b>Browse Plex Library</b> to scroll through everything.",
            reply_markup=self._remove_prompt_keyboard(selected_count),
            current_ui_message=current_ui_message,
        )

    async def _open_remove_browse_root(self, user_id: int, msg: Any, *, current_ui_message: Any | None = None) -> None:
        movie_items = await asyncio.to_thread(self._remove_library_items, "movies")
        show_items = await asyncio.to_thread(self._remove_library_items, "tv")
        flow = self._get_flow(user_id) or {"mode": "remove", "selected_items": []}
        flow["mode"] = "remove"
        flow["stage"] = "browse_root"
        self._set_flow(user_id, flow)
        await self._render_remove_ui(
            user_id,
            msg,
            flow,
            "📚 <b>Browse Plex/library items</b>\n\nChoose a library to browse, or <b>type any movie or show name</b> and the bot will find it for you directly.",
            reply_markup=self._remove_browse_root_keyboard(
                len(movie_items), len(show_items), self._remove_selection_count(flow)
            ),
            current_ui_message=current_ui_message,
        )

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if not msg or not msg.text:
            return

        user_id = update.effective_user.id
        text = msg.text.strip()
        low = text.lower().strip()

        # Allow plain password unlock without requiring /unlock
        if not self._is_allowlisted(update):
            await self.deny(update)
            return
        if self._requires_password() and not self.store.is_unlocked(user_id):
            if self.store.is_auth_locked(user_id):
                await msg.reply_text("🔒 Too many failed attempts. Try again in a few minutes.", parse_mode=_PM)
                return
            if secrets.compare_digest(text, self.cfg.access_password):
                self.store.clear_auth_failures(user_id)
                self.store.unlock_user(user_id, self.cfg.access_session_ttl_s)
                # Delete the message containing the password from chat history
                try:
                    await msg.delete()
                except Exception:
                    pass
                await self._navigate_to_command_center(msg, user_id)
                return
            locked = self.store.record_auth_failure(user_id)
            if locked:
                await msg.reply_text("🔒 Too many failed attempts. Locked for 15 minutes.", parse_mode=_PM)
            else:
                await msg.reply_text("<b>❌ Wrong Password</b>\n<i>Try again.</i>", parse_mode=_PM)
            return

        # Guided flow handling first.
        flow = self._get_flow(user_id)
        if flow:
            if low in {"cancel", "/cancel", "stop", "exit", "abort"}:
                if flow.get("mode") == "remove":
                    self._clear_flow(user_id)
                    await self._navigate_to_command_center(msg, user_id)
                elif flow.get("mode") == "schedule":
                    self._clear_flow(user_id)
                    await self._navigate_to_command_center(msg, user_id)
                elif flow.get("mode") == "msch_add":
                    self._clear_flow(user_id)
                    await self._navigate_to_command_center(msg, user_id)
                elif flow.get("mode") == "tv":
                    await self._cleanup_private_user_message(msg)
                    await self._render_tv_ui(
                        user_id,
                        msg,
                        flow,
                        "<b>📺 TV Search Cancelled</b>\n\nTap TV Search to start again.",
                        reply_markup=InlineKeyboardMarkup(self._nav_footer()),
                    )
                    self._clear_flow(user_id)
                else:
                    self._clear_flow(user_id)
                    await msg.reply_text("Setup cancelled.", parse_mode=_PM)
                return

            mode = flow.get("mode")
            stage = flow.get("stage")

            if mode == "movie" and stage == "await_title":
                await self._cleanup_private_user_message(msg)
                self._clear_flow(user_id)
                await self._run_search(
                    update=update,
                    query=text,
                    media_hint="movies",
                    nav_user_id=user_id,
                )
                return

            if mode == "tv" and stage == "await_filter":
                await self._cleanup_private_user_message(msg)
                parsed = self._parse_tv_filter(text)
                if parsed is None:
                    await self._render_tv_ui(
                        user_id,
                        msg,
                        flow,
                        self._tv_filter_prompt_text(
                            "<b>⚠️ Invalid Filter Format</b>\n<i>Use one of: S1E2 · season 1 episode 2 · season 1 · episode 2</i>"
                        ),
                        reply_markup=InlineKeyboardMarkup(self._nav_footer(back_data="menu:tv")),
                    )
                    return
                season, episode = parsed
                flow["season"] = season
                flow["episode"] = episode
                flow["stage"] = "await_title"
                self._set_flow(user_id, flow)
                await self._render_tv_ui(
                    user_id,
                    msg,
                    flow,
                    self._tv_title_prompt_text(season, episode),
                    reply_markup=InlineKeyboardMarkup(self._nav_footer(back_data="menu:tv")),
                )
                return

            if mode == "tv" and stage == "await_title":
                await self._cleanup_private_user_message(msg)
                query = self._build_tv_query(text, flow.get("season"), flow.get("episode"))
                if flow.get("full_series"):
                    query = f"{query} COMPLETE SERIES"
                tv_flow = dict(flow)
                self._clear_flow(user_id)
                await self._run_search(update=update, query=query, media_hint="tv", tv_flow=tv_flow)
                return

            if mode == "schedule" and stage == "await_show":
                await self._render_schedule_ui(
                    user_id,
                    msg,
                    flow,
                    "<b>🔎 Looking Up Show</b>\n<i>Checking TVMaze for matches…</i>",
                    reply_markup=None,
                )
                try:
                    candidates = await asyncio.to_thread(self.tvmeta.search_shows, text, 5)
                except Exception as e:
                    await self._render_schedule_ui(
                        user_id, msg, flow, f"<b>⚠️ Lookup Failed</b>\n<i>{_h(str(e))}</i>", reply_markup=None
                    )
                    return
                if not candidates:
                    await self._render_schedule_ui(
                        user_id, msg, flow, "No matching shows found. Try a more specific title.", reply_markup=None
                    )
                    return
                flow["stage"] = "choose_show"
                flow["candidates"] = candidates
                self._set_flow(user_id, flow)
                lines = ["<b>📺 Pick the Correct Show</b>", ""]
                for idx, candidate in enumerate(candidates, start=1):
                    net = candidate.get("network") or candidate.get("country") or "Unknown network"
                    lines.append(
                        f"<b>{idx}.</b> {_h(candidate['name'])} (<code>{_h(candidate.get('year') or '?')}</code>) • <code>{_h(candidate.get('status') or 'Unknown')}</code> • <i>{_h(net)}</i>"
                    )
                lines.append("")
                lines.append("<i>Tap a show below, or send another title if you want to search again.</i>")
                await self._render_schedule_ui(
                    user_id,
                    msg,
                    flow,
                    "\n".join(lines),
                    reply_markup=self._schedule_candidate_keyboard(candidates),
                )
                return

            if mode == "schedule" and stage in {"choose_show", "confirm"}:
                self._schedule_start_flow(user_id)
                flow = self._get_flow(user_id) or {"mode": "schedule", "stage": "await_show"}
                await self._render_schedule_ui(
                    user_id,
                    msg,
                    flow,
                    "<b>🔎 Looking Up Show</b>\n<i>Checking TVMaze for matches…</i>",
                    reply_markup=None,
                )
                try:
                    candidates = await asyncio.to_thread(self.tvmeta.search_shows, text, 5)
                except Exception as e:
                    await self._render_schedule_ui(
                        user_id, msg, flow, f"<b>⚠️ Lookup Failed</b>\n<i>{_h(str(e))}</i>", reply_markup=None
                    )
                    return
                if not candidates:
                    await self._render_schedule_ui(
                        user_id, msg, flow, "No matching shows found. Try a more specific title.", reply_markup=None
                    )
                    return
                flow["stage"] = "choose_show"
                flow["candidates"] = candidates
                self._set_flow(user_id, flow)
                lines = ["<b>📺 Pick the Correct Show</b>", ""]
                for idx, candidate in enumerate(candidates, start=1):
                    net = candidate.get("network") or candidate.get("country") or "Unknown network"
                    lines.append(
                        f"<b>{idx}.</b> {_h(candidate['name'])} (<code>{_h(candidate.get('year') or '?')}</code>) • <code>{_h(candidate.get('status') or 'Unknown')}</code> • <i>{_h(net)}</i>"
                    )
                lines.append("")
                lines.append("<i>Tap a show below, or send another title if you want to search again.</i>")
                await self._render_schedule_ui(
                    user_id,
                    msg,
                    flow,
                    "\n".join(lines),
                    reply_markup=self._schedule_candidate_keyboard(candidates),
                )
                return

            if mode == "schedule" and stage == "await_season_pick":
                if not text.isdigit():
                    await self._render_schedule_ui(
                        user_id,
                        msg,
                        flow,
                        "Send a season number from the available season list shown above.",
                        reply_markup=None,
                    )
                    return
                wanted_season = int(text)
                available = [int(x) for x in list(flow.get("selected_show", {}).get("available_seasons") or [])]
                if available and wanted_season not in available:
                    await self._render_schedule_ui(
                        user_id,
                        msg,
                        flow,
                        "That season is not available for this show. Send one of: "
                        + ", ".join(str(x) for x in available),
                        reply_markup=None,
                    )
                    return
                await self._render_schedule_ui(
                    user_id, msg, flow, "🔄 Re-checking that season against Plex/library inventory…", reply_markup=None
                )
                try:
                    bundle = await asyncio.to_thread(
                        self._schedule_get_show_bundle,
                        int(flow.get("selected_show", {}).get("id") or 0),
                        False,
                        False,
                    )
                    raw_probe = await asyncio.to_thread(self._schedule_probe_bundle, bundle, None, wanted_season)
                    probe = self._schedule_apply_tracking_mode(
                        {"auto_state_json": {"tracking_mode": str(flow.get("tracking_mode") or "upcoming")}},
                        raw_probe,
                    )
                except Exception as e:
                    await self._render_schedule_ui(user_id, msg, flow, f"Season check failed: {e}", reply_markup=None)
                    return
                flow["stage"] = "confirm"
                flow["season"] = wanted_season
                flow["selected_show"] = self._schedule_show_info(bundle)
                flow["probe"] = probe
                self._set_flow(user_id, flow)
                await self._render_schedule_ui(
                    user_id,
                    msg,
                    flow,
                    self._schedule_preview_text(probe),
                    reply_markup=self._schedule_preview_keyboard(probe),
                )
                return

            if mode == "msch_add" and stage == "title":
                await schedule_handler.on_text_movie_schedule(self, user_id, text, msg, update)
                return

            if mode == "remove" and stage == "await_query":
                await self._cleanup_private_user_message(msg)
                await self._render_remove_ui(
                    user_id,
                    msg,
                    flow,
                    "<b>🔎 Scanning Library</b>\n<i>Searching Plex for matching items…</i>",
                    reply_markup=None,
                )
                try:
                    candidates = await asyncio.to_thread(self._find_remove_candidates, text, 8)
                except Exception as e:
                    await self._render_remove_ui(
                        user_id, msg, flow, f"<b>⚠️ Search Failed</b>\n<i>{_h(str(e))}</i>", reply_markup=None
                    )
                    return
                if not candidates:
                    await self._render_remove_ui(
                        user_id,
                        msg,
                        flow,
                        "No matching removable items were found in Movies or TV. Try a different name.",
                        reply_markup=self._remove_prompt_keyboard(),
                    )
                    return
                flow["stage"] = "choose_item"
                flow["query"] = text
                flow["candidates"] = candidates
                self._set_flow(user_id, flow)
                selected_paths = self._remove_selected_paths(flow)
                await self._render_remove_ui(
                    user_id,
                    msg,
                    flow,
                    self._remove_candidates_text(text, candidates, selected_paths),
                    reply_markup=self._remove_candidate_keyboard(candidates, selected_paths),
                )
                return

            if mode == "remove" and stage in {
                "choose_item",
                "confirm_delete",
                "browse_root",
                "show_actions",
                "browse_children",
                "season_actions",
                "browse_episodes",
            }:
                await self._cleanup_private_user_message(msg)
                preserved_selected = list(flow.get("selected_items") or [])
                new_flow: dict[str, Any] = {
                    "mode": "remove",
                    "stage": "await_query",
                    "selected_items": preserved_selected,
                }
                # Preserve UI message reference so the next render edits the existing message
                for key in ("remove_ui_chat_id", "remove_ui_message_id"):
                    if flow.get(key):
                        new_flow[key] = flow[key]
                self._set_flow(user_id, new_flow)
                flow = self._get_flow(user_id) or new_flow
                await self._render_remove_ui(
                    user_id,
                    msg,
                    flow,
                    "<b>🔎 Scanning Library</b>\n<i>Searching Plex for matching items…</i>",
                    reply_markup=None,
                )
                try:
                    candidates = await asyncio.to_thread(self._find_remove_candidates, text, 8)
                except Exception as e:
                    await self._render_remove_ui(
                        user_id, msg, flow, f"<b>⚠️ Search Failed</b>\n<i>{_h(str(e))}</i>", reply_markup=None
                    )
                    return
                if not candidates:
                    await self._render_remove_ui(
                        user_id,
                        msg,
                        flow,
                        "No matching removable items were found in Movies or TV. Try a different name.",
                        reply_markup=self._remove_prompt_keyboard(),
                    )
                    return
                flow["stage"] = "choose_item"
                flow["query"] = text
                flow["candidates"] = candidates
                flow.pop("selected", None)
                flow.pop("selected_child", None)
                flow.pop("season_items", None)
                flow.pop("episode_items", None)
                self._set_flow(user_id, flow)
                selected_paths = self._remove_selected_paths(flow)
                await self._render_remove_ui(
                    user_id,
                    msg,
                    flow,
                    self._remove_candidates_text(text, candidates, selected_paths),
                    reply_markup=self._remove_candidate_keyboard(candidates, selected_paths),
                )
                return

        # Quick plain-English actions
        if low in {"start", "menu", "help", "command center", "home"}:
            await self.cmd_start(update, context)
            return
        if low in {"active", "active downloads", "downloads", "show active"}:
            await self.cmd_active(update, context)
            return
        if low in {"categories", "show categories", "storage", "storage status"}:
            await self.cmd_categories(update, context)
            return
        if low in {"schedule", "create schedule", "new schedule", "track show"}:
            await self.cmd_schedule(update, context)
            return
        if low in {"remove", "delete", "remove media", "clear space"}:
            await self.cmd_remove(update, context)
            return

        # Explicit mode shortcuts
        if low in {"movie", "movies", "movie search"}:
            self._set_flow(user_id, {"mode": "movie", "stage": "await_title"})
            await msg.reply_text("Send the movie title to search (1080p+ default).", parse_mode=_PM)
            return

        if low in {"tv", "show", "tv search", "show search", "tv show"}:
            flow = {"mode": "tv", "stage": "await_filter_choice", "season": None, "episode": None}
            self._set_flow(user_id, flow)
            await self._render_tv_ui(
                user_id, msg, flow, self._tv_filter_choice_text(), reply_markup=self._tv_filter_choice_keyboard()
            )
            return

        if low.startswith("movie "):
            await self._run_search(update=update, query=text[6:].strip(), media_hint="movies")
            return

        if low.startswith("tv ") or low.startswith("show "):
            query = re.sub(r"^(tv|show)\s+", "", text, flags=re.I)
            await self._run_search(update=update, query=query.strip(), media_hint="tv")
            return

        # Intent-based search so regular conversation can stay conversational.
        query, media_hint = self._extract_search_intent(text)
        if query:
            await self._run_search(update=update, query=query, media_hint=media_hint)
            return

        # Default fallback: chat with Patchy (read-only mode).
        await self._reply_patchy_chat(msg, user_id, text)

    async def cmd_show(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_show(self, update, context)

    async def _resolve_hash_by_name(self, title: str, category: str, wait_s: int = 20) -> str | None:
        return await download_handler.resolve_hash_by_name(self._ctx, title, category, wait_s)

    def _vpn_ready_for_download(self) -> tuple[bool, str]:
        return _shared.vpn_ready_for_download(getattr(self, "_ctx", self))

    async def _do_add(self, user_id: int, search_id: str, idx: int, media_choice: str) -> dict[str, Any]:
        return await download_handler.do_add(self._ctx, user_id, search_id, idx, media_choice)

    async def cmd_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_add(self, update, context)

    async def cmd_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_categories(self, update, context)

    async def cmd_mkcat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_mkcat(self, update, context)

    async def cmd_setminseeds(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_setminseeds(self, update, context)

    async def cmd_setlimit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_setlimit(self, update, context)

    async def cmd_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_profile(self, update, context)

    async def cmd_active(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_active(self, update, context)

    async def cmd_plugins(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_plugins(self, update, context)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_help(self, update, context)

    async def _cmd_text_fallback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_text_fallback(self, update, context)

    def _health_report(self) -> tuple[str, bool]:
        return commands_handler.health_report(self._ctx)

    async def cmd_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_health(self, update, context)

    def _speed_report(self) -> str:
        return commands_handler.speed_report(self._ctx)

    async def cmd_speed(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_speed(self, update, context)

    async def cmd_unlock(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_unlock(self, update, context)

    async def cmd_logout(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.cmd_logout(self, update, context)

    async def on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        await commands_handler.on_error(update, context)

    # ---------- Callbacks ----------

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_allowed(update):
            await self.deny(update)
            return

        q = update.callback_query
        if not q or not q.message:
            return

        data = q.data or ""
        user_id = update.effective_user.id

        await self._cleanup_ephemeral_messages(user_id, q.get_bot())

        # Stop Command Center refresh when navigating away (nav:home handler restarts it)
        if data != "nav:home":
            self._stop_command_center_refresh(user_id)

        try:
            await self._dispatcher.dispatch(data, q=q, user_id=user_id)
        except Exception as e:
            await self._render_nav_ui(
                user_id,
                q.message,
                f"Action failed: {_h(str(e))}",
                reply_markup=self._home_only_keyboard(),
                current_ui_message=q.message,
            )
        finally:
            # Default acknowledgment — handlers that called q.answer(show_alert=True) will have
            # already answered; this silently no-ops for those cases (BadRequest caught below).
            try:
                await q.answer()
            except Exception:
                pass

    # ---------- Callback handler methods ----------

    async def _on_cb_nav_home(self, *, data: str, q: Any, user_id: int) -> None:
        self._clear_flow(user_id)
        # Cancel pending trackers so they don't create monitor messages after cleanup
        self._cancel_pending_trackers_for_user(user_id)
        # Delete the message that hosted this button press (may be a Live Monitor tracker_msg)
        try:
            await q.message.delete()
        except Exception:
            pass
        await self._navigate_to_command_center(q.message, user_id)

    async def _on_cb_add(self, *, data: str, q: Any, user_id: int) -> None:
        _, sid, idx_raw = data.split(":", 2)
        idx = int(idx_raw)
        payload = self.store.get_search(user_id, sid)
        if not payload:
            await q.answer("Search expired", show_alert=True)
            return
        search_meta, _ = payload
        media_hint = str((search_meta.get("options") or {}).get("media_hint") or "any")
        # Auto-route to the correct library when search type is known
        if media_hint in ("tv", "movies"):
            # Synthesize a d: callback to skip the library picker and fall through to download
            await self._on_cb_download(data=f"d:{sid}:{idx_raw}:{media_hint}", q=q, user_id=user_id)
        else:
            result = self.store.get_result(user_id, sid, idx)
            page = max(1, math.ceil(max(1, idx) / self.cfg.page_size))
            result_name = _h(str((result or {}).get("name") or f"Result #{idx}"))
            text = f"<b>⬇️ Add Result #{idx}</b>\n<code>{result_name}</code>\n\nChoose the destination library:"
            await self._render_nav_ui(
                user_id,
                q.message,
                text,
                reply_markup=self._media_picker_keyboard(sid, idx, back_data=f"p:{sid}:{page}"),
                current_ui_message=q.message,
            )

    async def _on_cb_download(self, *, data: str, q: Any, user_id: int) -> None:
        _, sid, idx_raw, choice = data.split(":", 3)
        idx = int(idx_raw)
        page = max(1, math.ceil(max(1, idx) / self.cfg.page_size))
        choice_label = "Movies" if self._normalize_media_choice(choice) == "movies" else "TV"
        rendered = await self._render_nav_ui(
            user_id,
            q.message,
            f"⏳ Adding result #{idx} to {choice_label}…",
            reply_markup=InlineKeyboardMarkup(self._nav_footer(back_data=f"p:{sid}:{page}")),
            current_ui_message=q.message,
        )
        try:
            out = await self._do_add(user_id, sid, idx, choice)
        except Exception as e:
            await self._render_nav_ui(
                user_id,
                rendered,
                f"<b>⚠️ Add Failed</b>\n<i>{_h(str(e))}</i>",
                reply_markup=InlineKeyboardMarkup(self._nav_footer(back_data=f"p:{sid}:{page}")),
                current_ui_message=rendered,
            )
            return
        summary = str(out["summary"])
        if not out.get("hash"):
            summary += "\n\n<i>Waiting for qBittorrent to assign a hash. A live monitor will attach automatically.</i>"
        rendered = await self._render_nav_ui(
            user_id,
            rendered,
            summary,
            reply_markup=None,
            current_ui_message=rendered,
        )

        if out.get("hash"):
            tracker_msg = await rendered.reply_text(
                "<b>📡 Live Monitor Attached</b>\n<i>Tracking download progress…</i>",
                reply_markup=self._stop_download_keyboard(out["hash"]),
                parse_mode=_PM,
            )
            self._start_progress_tracker(user_id, out["hash"], tracker_msg, out["name"])
        else:
            self._start_pending_progress_tracker(user_id, out["name"], out["category"], rendered)

    async def _on_cb_page(self, *, data: str, q: Any, user_id: int) -> None:
        _, sid, page_raw = data.split(":", 2)
        page = int(page_raw)
        payload = self.store.get_search(user_id, sid)
        if not payload:
            await q.answer("Search expired", show_alert=True)
            return
        search_meta, rows = payload
        text, markup = self._render_page(search_meta, rows, page)
        await self._render_nav_ui(
            user_id,
            q.message,
            text,
            reply_markup=markup,
            disable_web_page_preview=True,
            current_ui_message=q.message,
        )

    async def _on_cb_remove(self, *, data: str, q: Any, user_id: int) -> None:
        await remove_handler.on_cb_remove(self, data=data, q=q, user_id=user_id)

    async def _on_cb_schedule(self, *, data: str, q: Any, user_id: int) -> None:
        await schedule_handler.on_cb_schedule(self, data=data, q=q, user_id=user_id)

    async def _on_cb_movie_schedule(self, *, data: str, q: Any, user_id: int) -> None:
        await schedule_handler.on_cb_movie_schedule(self, data=data, q=q, user_id=user_id)

    async def _on_cb_menu(self, *, data: str, q: Any, user_id: int) -> None:
        await commands_handler.on_cb_menu(self, data=data, q=q, user_id=user_id)

    async def _on_cb_flow(self, *, data: str, q: Any, user_id: int) -> None:
        await commands_handler.on_cb_flow(self, data=data, q=q, user_id=user_id)

    async def _on_cb_dl_manage(self, *, data: str, q: Any, user_id: int) -> None:
        """Show the Manage Downloads sub-page with individual stop buttons."""
        self._stop_command_center_refresh(user_id)
        dl_tuples = await asyncio.to_thread(self._active_download_tuples)
        lines: list[str] = ["<b>🛑 Manage Downloads</b>", ""]
        if dl_tuples:
            lines.append(f"<i>{len(dl_tuples)} active download{'s' if len(dl_tuples) != 1 else ''} — tap to cancel</i>")
        else:
            lines.append("<i>No active downloads right now.</i>")
        text = "\n".join(lines)
        kb = kb_mod.manage_downloads_keyboard(dl_tuples)
        await self._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)

    async def _on_cb_stop(self, *, data: str, q: Any, user_id: int) -> None:
        await download_handler.on_cb_stop(self._ctx, data=data, q=q, user_id=user_id)

    def build_application(self) -> Application:
        app = (
            Application.builder()
            .token(self.cfg.telegram_token)
            .connection_pool_size(16)
            .pool_timeout(15.0)
            .connect_timeout(10.0)
            .read_timeout(30.0)
            .write_timeout(30.0)
            .get_updates_connection_pool_size(2)
            .get_updates_pool_timeout(15.0)
            .get_updates_connect_timeout(10.0)
            .get_updates_read_timeout(35.0)
            .get_updates_write_timeout(30.0)
            .post_init(self._post_init)
            .post_stop(self._post_stop)
            .concurrent_updates(False)
            .build()
        )
        self.app = app

        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(MessageHandler(filters.Regex(r"^/(start|help)(?:@\w+)?$"), self._cmd_text_fallback))
        app.add_handler(CommandHandler("health", self.cmd_health))
        app.add_handler(CommandHandler("speed", self.cmd_speed))
        app.add_handler(CommandHandler("search", self.cmd_search))
        app.add_handler(CommandHandler("schedule", self.cmd_schedule))
        app.add_handler(CommandHandler("remove", self.cmd_remove))
        app.add_handler(CommandHandler("show", self.cmd_show))
        app.add_handler(CommandHandler("add", self.cmd_add))
        app.add_handler(CommandHandler("categories", self.cmd_categories))
        app.add_handler(CommandHandler("mkcat", self.cmd_mkcat))
        app.add_handler(CommandHandler("setminseeds", self.cmd_setminseeds))
        app.add_handler(CommandHandler("setlimit", self.cmd_setlimit))
        app.add_handler(CommandHandler("profile", self.cmd_profile))
        app.add_handler(CommandHandler("active", self.cmd_active))
        app.add_handler(CommandHandler("plugins", self.cmd_plugins))
        app.add_handler(CommandHandler("unlock", self.cmd_unlock))
        app.add_handler(CommandHandler("logout", self.cmd_logout))

        app.add_handler(CallbackQueryHandler(self.on_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_text))
        app.add_error_handler(self.on_error)

        return app
