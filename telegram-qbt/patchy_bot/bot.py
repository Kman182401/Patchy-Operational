"""Telegram bot application — command handlers, callback router, and lifecycle."""

from __future__ import annotations

import argparse
import asyncio
import collections
import logging
import math
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.parse
from datetime import time as dt_time
from typing import Any

import requests
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
from .handlers import chat as chat_handler
from .handlers import commands as commands_handler
from .handlers import download as download_handler
from .handlers import remove as remove_handler
from .handlers import schedule as schedule_handler
from .handlers import search as search_handler
from .plex_organizer import organize_download as _organize_download
from .quality import score_torrent
from .rate_limiter import RateLimiter
from .store import Store
from .types import HandlerContext
from .ui import flow as flow_mod
from .ui import keyboards as kb_mod
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

    # ---------- Callback dispatcher registration ----------

    def _register_callbacks(self) -> None:
        d = self._dispatcher
        d.register_exact("nav:home", self._on_cb_nav_home)
        d.register_prefix("a:", self._on_cb_add)
        d.register_prefix("d:", self._on_cb_download)
        d.register_prefix("p:", self._on_cb_page)
        d.register_prefix("rm:", self._on_cb_remove)
        d.register_prefix("sch:", self._on_cb_schedule)
        d.register_prefix("menu:", self._on_cb_menu)
        d.register_prefix("flow:", self._on_cb_flow)
        d.register_prefix("stop:", self._on_cb_stop)

    # ---------- Telegram command discovery ----------

    async def _post_init(self, app: Application) -> None:
        commands = [
            BotCommand("start", "Open command center"),
            BotCommand("search", "Search torrents (with filters)"),
            BotCommand("schedule", "Track a TV show and auto-acquire new episodes"),
            BotCommand("show", "Show a saved search page"),
            BotCommand("add", "Add result to qBittorrent (Movies/TV)"),
            BotCommand("active", "Show active downloads"),
            BotCommand("remove", "Find and delete media from disk/Plex after confirmation"),
            BotCommand("categories", "Show NVMe + category routing status"),
            BotCommand("profile", "Show current defaults"),
            BotCommand("setminseeds", "Set default minimum seeds"),
            BotCommand("setlimit", "Set default result limit"),
            BotCommand("plugins", "List installed search plugins"),
            BotCommand("health", "Quick health check"),
            BotCommand("speed", "Download/upload speed dashboard"),
            BotCommand("unlock", "Unlock bot session with password"),
            BotCommand("logout", "Lock bot session again"),
            BotCommand("help", "Show help/command center"),
        ]
        try:
            await app.bot.set_my_commands(commands)
            LOG.info("Telegram command list registered")
        except Exception:
            LOG.warning("Failed to register Telegram command list", exc_info=True)

        await self._schedule_bootstrap(app)

        # Daily database backup at 3:00 AM local time (if BACKUP_DIR is configured)
        if self.cfg.backup_dir:
            self.app.job_queue.run_daily(
                self._backup_job,
                time=dt_time(3, 0, 0),
                name="daily-db-backup",
            )
            LOG.info("Database backup scheduled daily at 03:00 → %s", self.cfg.backup_dir)

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

        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self.progress_tasks.clear()
        self.pending_tracker_tasks.clear()

        # Close HTTP session pools to release file descriptors cleanly
        for client in (self.qbt, self.patchy_llm, self.tvmeta, self.plex):
            sess = getattr(client, "session", None)
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass

    # ---------- Routing + storage ----------

    def _targets(self) -> dict[str, dict[str, str]]:
        return {
            "movies": {
                "category": self.cfg.movies_category,
                "path": self.cfg.movies_path,
                "label": "Movies",
                "emoji": "🎬",
            },
            "tv": {"category": self.cfg.tv_category, "path": self.cfg.tv_path, "label": "TV", "emoji": "📺"},
        }

    def _normalize_media_choice(self, value: str | None) -> str | None:
        if value is None:
            return None
        raw = value.strip().lower()
        if raw in {"m", "movie", "movies", "film", "films"}:
            return "movies"
        if raw in {"t", "tv", "show", "shows", "series", "episode", "episodes", "tvshow", "tvshows"}:
            return "tv"
        return None

    @staticmethod
    def _norm_path(value: str | None) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        return os.path.normpath(raw.rstrip("/"))

    def _qbt_category_aliases(self, primary_category: str, save_path: str) -> set[str]:
        aliases = {str(primary_category or "").strip()} if primary_category else set()
        want_path = self._norm_path(save_path)
        if not want_path:
            return aliases
        try:
            categories = self.qbt.list_categories()
        except Exception:
            LOG.warning("Failed to inspect qBittorrent category aliases", exc_info=True)
            return aliases
        for name, meta in categories.items():
            current_path = self._norm_path(str((meta or {}).get("savePath") or ""))
            if current_path and current_path == want_path:
                aliases.add(str(name).strip())
        return {name for name in aliases if name}

    def _storage_status(self) -> tuple[bool, str]:
        if self.cfg.require_nvme_mount and not os.path.ismount(self.cfg.nvme_mount_path):
            return False, f"NVMe mount missing at {self.cfg.nvme_mount_path}"

        for key in ("movies", "tv"):
            t = self._targets()[key]
            os.makedirs(t["path"], exist_ok=True)
            if not os.path.isdir(t["path"]):
                return False, f"Library path missing: {t['path']}"

        return True, "ready"

    @staticmethod
    def _check_free_space(
        target_path: str, warn_bytes: int = 10 * 1024**3, block_bytes: int = 5 * 1024**3
    ) -> tuple[bool, str]:
        try:
            st = os.statvfs(target_path)
            free = int(st.f_frsize * st.f_bfree)
        except OSError as e:
            return True, f"disk check skipped ({e})"
        if free < block_bytes:
            return (
                False,
                f"Not enough disk space ({human_size(free)} free). Need at least {human_size(block_bytes)} to start a download.",
            )
        if free < warn_bytes:
            LOG.warning("Low disk space on %s: %s free", target_path, human_size(free))
        return True, "ok"

    def _qbt_transport_status(self) -> tuple[bool, str]:
        info = self.qbt.get_transfer_info()
        prefs = self.qbt.get_preferences()

        status = str(info.get("connection_status") or "unknown").strip().lower()
        dht_nodes = int(info.get("dht_nodes") or 0)
        iface = str(prefs.get("current_network_interface") or "").strip()
        iface_addr = str(prefs.get("current_interface_address") or "").strip()
        bind_label = iface or "any interface"

        if iface:
            iface_dir = f"/sys/class/net/{iface}"
            if not os.path.exists(iface_dir):
                return False, f"bound interface missing: {iface}"
            try:
                with open(f"{iface_dir}/operstate", encoding="utf-8") as f:
                    iface_state = f.read().strip().lower()
            except OSError:
                iface_state = "unknown"
            if iface_state == "down":
                return False, f"bound interface is down: {iface}"
            bind_label = f"{iface} ({iface_state})"

        if iface_addr:
            bind_label = f"{bind_label} @ {iface_addr}"

        summary = f"connection_status={status} via {bind_label}, dht_nodes={dht_nodes}"
        if status == "disconnected":
            return False, summary
        return True, summary

    def _ensure_media_categories(self) -> tuple[bool, str]:
        ok, reason = self._storage_status()
        if not ok:
            return False, reason
        try:
            for t in self._targets().values():
                self.qbt.ensure_category(t["category"], t["path"])
            return True, "ready"
        except Exception as e:
            return False, f"qBittorrent category sync failed: {e}"

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
        chat_id = getattr(message, "chat_id", None)
        message_id = getattr(message, "message_id", None)
        if chat_id is None or message_id is None:
            return
        self.user_nav_ui[user_id] = {
            "chat_id": int(chat_id),
            "message_id": int(message_id),
        }
        # Persist to DB so the CC location survives bot restarts.
        try:
            self.store.save_command_center(user_id, int(chat_id), int(message_id))
        except Exception:
            LOG.warning("Failed to persist CC location to DB", exc_info=True)

    def _track_ephemeral_message(self, user_id: int, message: Any) -> None:
        chat_id = getattr(message, "chat_id", None)
        message_id = getattr(message, "message_id", None)
        if chat_id is None or message_id is None:
            return
        self.user_ephemeral_messages.setdefault(user_id, []).append(
            {"chat_id": int(chat_id), "message_id": int(message_id)}
        )

    def _cancel_pending_trackers_for_user(self, user_id: int) -> None:
        """Cancel pending tracker tasks for this user so they don't create monitor messages after home cleanup."""
        to_cancel = [key for key in list(self.pending_tracker_tasks) if key[0] == user_id]
        for key in to_cancel:
            task = self.pending_tracker_tasks.pop(key, None)
            if task and not task.done():
                task.cancel()

    async def _delete_old_nav_ui(self, user_id: int, bot: Any) -> None:
        """Delete the previous nav-UI message (e.g. old Command Center) so /start shows a clean chat."""
        info = self.user_nav_ui.pop(user_id, None)
        if not info:
            return
        try:
            await bot.delete_message(chat_id=info["chat_id"], message_id=info["message_id"])
        except TelegramError:
            pass

    async def _cleanup_ephemeral_messages(self, user_id: int, bot: Any) -> None:
        msgs = self.user_ephemeral_messages.pop(user_id, [])
        for m in msgs:
            try:
                await bot.delete_message(chat_id=m["chat_id"], message_id=m["message_id"])
            except TelegramError:
                pass

    async def _strip_old_keyboard(self, bot: Any, chat_id: int, message_id: int) -> None:
        """Remove the inline keyboard from an old message so only one interactive bubble exists."""
        if not chat_id or not message_id:
            return
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
        except Exception:
            pass  # Message may be deleted, too old, etc.

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
        bot = anchor_message.get_bot()
        remembered = self.user_nav_ui.get(user_id) or {}
        target_chat_id = int(remembered.get("chat_id") or 0)
        target_message_id = int(remembered.get("message_id") or 0)
        if current_ui_message is not None:
            target_chat_id = int(getattr(current_ui_message, "chat_id", 0) or 0)
            target_message_id = int(getattr(current_ui_message, "message_id", 0) or 0)
        if target_chat_id and target_message_id:
            try:
                rendered = await bot.edit_message_text(
                    chat_id=target_chat_id,
                    message_id=target_message_id,
                    text=text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_web_page_preview,
                    parse_mode=_PM,
                )
                target_message = rendered if hasattr(rendered, "message_id") else current_ui_message
                if target_message is not None:
                    self._remember_nav_ui_message(user_id, target_message)
                    return target_message
            except TelegramError as e:
                if "message is not modified" in str(e).lower():
                    target_message = current_ui_message
                    if target_message is not None:
                        self._remember_nav_ui_message(user_id, target_message)
                        return target_message
        await self._strip_old_keyboard(bot, target_chat_id, target_message_id)
        rendered = await anchor_message.reply_text(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
            parse_mode=_PM,
        )
        self._remember_nav_ui_message(user_id, rendered)
        return rendered

    def _remember_flow_ui_message(self, user_id: int, flow: dict[str, Any] | None, message: Any, flow_key: str) -> None:
        if not isinstance(flow, dict):
            return
        chat_id = getattr(message, "chat_id", None)
        message_id = getattr(message, "message_id", None)
        if chat_id is None or message_id is None:
            return
        flow[f"{flow_key}_ui_chat_id"] = int(chat_id)
        flow[f"{flow_key}_ui_message_id"] = int(message_id)
        if str(flow.get("mode") or "") == flow_key:
            self._set_flow(user_id, flow)

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
        flow = flow if isinstance(flow, dict) else None
        bot = anchor_message.get_bot()
        target_chat_id = int(flow.get(f"{flow_key}_ui_chat_id") or 0) if flow else 0
        target_message_id = int(flow.get(f"{flow_key}_ui_message_id") or 0) if flow else 0
        if current_ui_message is not None:
            target_chat_id = int(getattr(current_ui_message, "chat_id", 0) or 0)
            target_message_id = int(getattr(current_ui_message, "message_id", 0) or 0)
        if target_chat_id and target_message_id:
            try:
                rendered = await bot.edit_message_text(
                    chat_id=target_chat_id,
                    message_id=target_message_id,
                    text=text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_web_page_preview,
                    parse_mode=_PM,
                )
                target_message = rendered if hasattr(rendered, "message_id") else current_ui_message
                if target_message is not None:
                    self._remember_flow_ui_message(user_id, flow, target_message, flow_key)
                    return target_message
            except TelegramError as e:
                if "message is not modified" in str(e).lower():
                    target_message = current_ui_message
                    if target_message is not None:
                        self._remember_flow_ui_message(user_id, flow, target_message, flow_key)
                        return target_message
        await self._strip_old_keyboard(bot, target_chat_id, target_message_id)
        rendered = await anchor_message.reply_text(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
            parse_mode=_PM,
        )
        self._remember_flow_ui_message(user_id, flow, rendered, flow_key)
        return rendered

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
        return await self._render_flow_ui(
            user_id,
            anchor_message,
            flow,
            text,
            flow_key="remove",
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
        return await self._render_flow_ui(
            user_id,
            anchor_message,
            flow,
            text,
            flow_key="schedule",
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
        return await self._render_flow_ui(
            user_id,
            anchor_message,
            flow,
            text,
            flow_key="tv",
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
            current_ui_message=current_ui_message,
        )

    async def _cleanup_private_user_message(self, message: Any) -> None:
        chat = getattr(message, "chat", None)
        chat_type = str(getattr(chat, "type", "") or "").lower()
        if chat_type != "private":
            return
        try:
            await message.delete()
        except TelegramError:
            return
        except Exception:
            return

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
        key = (user_id, torrent_hash.lower())
        existing = self.progress_tasks.get(key)
        if existing and not existing.done():
            existing.cancel()

        self._track_ephemeral_message(user_id, tracker_msg)
        task = asyncio.create_task(self._track_download_progress(user_id, torrent_hash, tracker_msg, title))
        self.progress_tasks[key] = task

    def _start_pending_progress_tracker(self, user_id: int, title: str, category: str, base_msg: Any) -> None:
        key = (user_id, category.lower(), title.strip().lower())
        existing = self.pending_tracker_tasks.get(key)
        if existing and not existing.done():
            return

        task = asyncio.create_task(self._attach_progress_tracker_when_ready(user_id, title, category, base_msg))
        self.pending_tracker_tasks[key] = task

    async def _attach_progress_tracker_when_ready(self, user_id: int, title: str, category: str, base_msg: Any) -> None:
        key = (user_id, category.lower(), title.strip().lower())
        try:
            torrent_hash = await self._resolve_hash_by_name(title, category, wait_s=35)
            if not torrent_hash:
                return

            tracker_msg = await base_msg.reply_text(
                "<b>📡 Live Monitor Attached</b>\n<i>Tracking download progress…</i>",
                reply_markup=self._stop_download_keyboard(torrent_hash),
                parse_mode=_PM,
            )
            self._start_progress_tracker(user_id, torrent_hash, tracker_msg, title)
        except Exception:
            LOG.warning("Deferred live monitor attach failed", exc_info=True)
        finally:
            self.pending_tracker_tasks.pop(key, None)

    def _stop_download_keyboard(self, torrent_hash: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🏠 Home", callback_data="nav:home"),
                    InlineKeyboardButton("🛑 Stop & Delete Download", callback_data=f"stop:{torrent_hash}"),
                ]
            ]
        )

    async def _tracker_send_fallback(self, tracker_msg: Any, text: str) -> None:
        """Send a message directly to the chat when tracker_msg was deleted."""
        chat_id = getattr(tracker_msg, "chat_id", None)
        if not chat_id:
            return
        try:
            bot = tracker_msg.get_bot()
            sent = await bot.send_message(chat_id=chat_id, text=text, parse_mode=_PM)
            self._track_ephemeral_message(int(chat_id), sent)
        except Exception:
            LOG.warning("Tracker fallback send_message also failed", exc_info=True)

    async def _safe_tracker_edit(self, tracker_msg: Any, text: str, reply_markup: Any = None) -> bool:
        try:
            await tracker_msg.edit_text(text, reply_markup=reply_markup, parse_mode=_PM)
            return True
        except Exception as e:
            msg = str(e).lower()
            if "message is not modified" in msg:
                return True
            if "timed out" in msg or "timeout" in msg or "retry after" in msg:
                LOG.warning("Live monitor Telegram edit transient failure: %s", e)
                return False
            LOG.warning("Live monitor Telegram edit failed: %s", e)
            return False

    async def _track_download_progress(self, user_id: int, torrent_hash: str, tracker_msg: Any, title: str) -> None:
        key = (user_id, torrent_hash.lower())
        start = time.time()
        tick = 0
        edit_count = 0
        last_text = ""
        last_edit_at = 0.0
        qbt_error_streak = 0
        edit_error_streak = 0
        stop_kb = self._stop_download_keyboard(torrent_hash)

        smooth_progress_pct: float | None = None
        smooth_dls: float | None = None
        smooth_uls: float | None = None
        alpha = self.cfg.progress_smoothing_alpha

        try:
            while True:
                elapsed = time.time() - start
                if elapsed > self.cfg.progress_track_timeout_s:
                    timeout_text = (
                        (last_text + "\n") if last_text else ""
                    ) + "<b>⏱ Monitor Timed Out</b>\nUse <code>/active</code> for current status."
                    if timeout_text != last_text:
                        edited = await self._safe_tracker_edit(tracker_msg, timeout_text, reply_markup=None)
                        if edited:
                            last_text = timeout_text
                        else:
                            await self._tracker_send_fallback(
                                tracker_msg, "<b>⏱ Monitor Timed Out</b>\nUse <code>/active</code> for current status."
                            )
                    break

                try:
                    info = await asyncio.to_thread(self.qbt.get_torrent, torrent_hash)
                    qbt_error_streak = 0
                except Exception:
                    qbt_error_streak += 1
                    LOG.warning("Live monitor qBittorrent poll failed (%d/5)", qbt_error_streak, exc_info=True)
                    if qbt_error_streak >= 5:
                        await self._tracker_send_fallback(
                            tracker_msg,
                            "<b>⚠️ Monitor Paused</b>\n<i>Repeated qBittorrent errors.</i> Use <code>/active</code> for status.",
                        )
                        break
                    await asyncio.sleep(self.cfg.progress_refresh_s)
                    tick += 1
                    continue

                if not info:
                    if elapsed < 20:
                        await asyncio.sleep(self.cfg.progress_refresh_s)
                        tick += 1
                        continue
                    notice = "<b>⚠️ Torrent Not Found</b>\n<i>Could not locate torrent for tracking.</i> Use <code>/active</code>."
                    edited = await self._safe_tracker_edit(tracker_msg, notice, reply_markup=None)
                    if not edited:
                        await self._tracker_send_fallback(tracker_msg, notice)
                    break

                raw_progress_pct = max(0.0, min(100.0, float(info.get("progress", 0.0) or 0.0) * 100.0))
                raw_dls = max(0.0, float(int(info.get("dlspeed", 0) or 0)))
                raw_uls = max(0.0, float(int(info.get("upspeed", 0) or 0)))

                if smooth_progress_pct is None:
                    smooth_progress_pct = raw_progress_pct
                    smooth_dls = raw_dls
                    smooth_uls = raw_uls
                else:
                    smooth_progress_pct = max(
                        smooth_progress_pct,
                        ((1.0 - alpha) * smooth_progress_pct) + (alpha * raw_progress_pct),
                    )
                    smooth_dls = ((1.0 - alpha) * smooth_dls) + (alpha * raw_dls)
                    smooth_uls = ((1.0 - alpha) * smooth_uls) + (alpha * raw_uls)

                text = self._render_progress_text(
                    title,
                    info,
                    edit_count,
                    progress_pct=smooth_progress_pct,
                    dls_bps=int(smooth_dls),
                    uls_bps=int(smooth_uls),
                )

                now = time.time()
                if text != last_text and (now - last_edit_at) >= self.cfg.progress_edit_min_s:
                    edited = await self._safe_tracker_edit(tracker_msg, text, reply_markup=stop_kb)
                    if edited:
                        last_text = text
                        last_edit_at = now
                        edit_count += 1
                        edit_error_streak = 0
                    else:
                        edit_error_streak += 1
                        if edit_error_streak >= 5:
                            await self._tracker_send_fallback(
                                tracker_msg,
                                "<b>⚠️ Monitor Paused</b>\n<i>Repeated Telegram timeouts.</i> Use <code>/active</code> for status.",
                            )
                            break

                if self._is_complete_torrent(info):
                    done_text = (
                        self._render_progress_text(
                            title,
                            info,
                            edit_count,
                            progress_pct=100.0,
                            dls_bps=int(raw_dls),
                            uls_bps=int(raw_uls),
                        )
                        + "\n<b>✅ Download Complete</b>"
                    )
                    await self._safe_tracker_edit(tracker_msg, done_text, reply_markup=None)
                    # Mark as notified so the background poller won't double-notify.
                    await asyncio.to_thread(self.store.mark_completion_notified, torrent_hash, title)
                    # Organize download into Plex-standard structure.
                    media_path = str(info.get("content_path") or info.get("save_path") or "").strip()
                    category = str(info.get("category") or "")
                    org_result = await asyncio.to_thread(
                        _organize_download,
                        media_path,
                        category,
                        self.cfg.tv_path,
                        self.cfg.movies_path,
                    )
                    if org_result.moved:
                        media_path = org_result.new_path
                    # Trigger a Plex library scan for the (possibly new) download path.
                    plex_added = False
                    if self.plex.ready() and media_path:
                        try:
                            plex_msg = await asyncio.to_thread(self.plex.refresh_for_path, media_path)
                            LOG.info("Post-download Plex refresh: %s", plex_msg)
                            plex_added = True
                        except Exception:
                            LOG.warning("Post-download Plex refresh failed for %s", media_path, exc_info=True)
                    notif_text = f"<b>✅ Download Complete</b>\n<code>{_h(title)}</code>"
                    if org_result.moved:
                        notif_text += f"\n<b>📁 Organized:</b> {_h(org_result.summary)}"
                    if plex_added:
                        notif_text += "\n\n<b>📚 Added to Plex</b>"
                    await self._tracker_send_fallback(tracker_msg, notif_text)
                    break

                tick += 1
                await asyncio.sleep(self.cfg.progress_refresh_s)

        except asyncio.CancelledError:
            return
        except Exception:
            LOG.warning("Live progress tracker failed", exc_info=True)
            await self._tracker_send_fallback(
                tracker_msg, "<b>⚠️ Monitor Error</b>\n<i>Unexpected error.</i> Use <code>/active</code> for status."
            )
        finally:
            self.progress_tasks.pop(key, None)

    # ---------- Background completion poller ----------

    async def _completion_poller_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Periodic job that checks ALL torrents for completions missed by the live monitor."""
        if not self.app:
            return
        try:
            torrents = await asyncio.to_thread(self.qbt.list_torrents, filter_name="completed", limit=200)
        except Exception:
            LOG.warning("Completion poller: failed to list torrents", exc_info=True)
            return

        for info in torrents:
            torrent_hash = str(info.get("hash") or "").strip().lower()
            if not torrent_hash:
                continue

            if not self._is_complete_torrent(info):
                continue

            already = await asyncio.to_thread(self.store.is_completion_notified, torrent_hash)
            if already:
                continue

            name = str(info.get("name") or "Unknown")
            size = int(info.get("size", 0) or info.get("total_size", 0) or 0)
            category = str(info.get("category") or "")

            # Mark notified FIRST to prevent duplicates if sending fails partway.
            await asyncio.to_thread(self.store.mark_completion_notified, torrent_hash, name)

            # Organize download into Plex-standard structure.
            media_path = str(info.get("content_path") or info.get("save_path") or "").strip()
            org_result = await asyncio.to_thread(
                _organize_download,
                media_path,
                category,
                self.cfg.tv_path,
                self.cfg.movies_path,
            )
            if org_result.moved:
                media_path = org_result.new_path

            # Trigger Plex scan.
            plex_added = False
            if self.plex.ready() and media_path:
                try:
                    plex_msg = await asyncio.to_thread(self.plex.refresh_for_path, media_path)
                    LOG.info("Completion poller Plex refresh: %s", plex_msg)
                    plex_added = True
                except Exception:
                    LOG.warning("Completion poller Plex refresh failed for %s", media_path, exc_info=True)

            # Build notification.
            lines = ["<b>✅ Download Complete</b>", f"<code>{_h(name)}</code>"]
            if category:
                lines.append(f"Category: <b>{_h(category)}</b>")
            if size > 0:
                lines.append(f"Size: <b>{human_size(size)}</b>")
            if org_result.moved:
                lines.append(f"<b>📁 Organized:</b> {_h(org_result.summary)}")
            if plex_added:
                lines.append("")
                lines.append("<b>📚 Added to Plex</b>")
            text = "\n".join(lines)

            # Send to all allowed users.
            for uid in self.cfg.allowed_user_ids:
                try:
                    sent = await self.app.bot.send_message(chat_id=uid, text=text, parse_mode=_PM)
                    self._track_ephemeral_message(uid, sent)
                except Exception:
                    LOG.warning("Completion poller: failed to notify user %s for %s", uid, name, exc_info=True)

            LOG.info("Completion poller: notified for '%s' (hash=%s)", name, torrent_hash)

        # Housekeeping: clean up old records once per run.
        try:
            await asyncio.to_thread(self.store.cleanup_old_completion_records)
        except Exception:
            pass

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

    def _command_center_keyboard(self) -> InlineKeyboardMarkup:
        return kb_mod.command_center_keyboard()

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
            return self._extract_show_name(name)
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
                if text == last_text:
                    # Check if there are still active downloads; if not, stop
                    try:
                        items = await asyncio.to_thread(self.qbt.list_torrents, filter_name="all", limit=20)
                        active = [t for t in items if str(t.get("state") or "") in _ACTIVE_DL_STATES]
                    except Exception:
                        active = []
                    if not active:
                        break
                    continue
                last_text = text
                try:
                    bot = self.app.bot if self.app else None
                    if not bot:
                        break
                    await bot.edit_message_text(
                        chat_id=remembered["chat_id"],
                        message_id=remembered["message_id"],
                        text=text,
                        reply_markup=self._command_center_keyboard(),
                        parse_mode=_PM,
                    )
                except TelegramError as e:
                    if "message is not modified" not in str(e).lower():
                        break
                except Exception:
                    break
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

        target_code: str | None = None
        target_air_ts: int | None = None
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
            target_code = code
            target_air_ts = episode_air.get(code)
            if code not in pending_codes:
                tracked_missing.append(code)
                if target_air_ts is None or target_air_ts <= grace_cutoff:
                    target_actionable = [code]
            break

        if target_code:
            auto_state["next_code"] = target_code
            probe["tracking_code"] = target_code
            probe["tracked_missing_codes"] = tracked_missing
            probe["actionable_missing_codes"] = target_actionable
            probe["signature"] = "|".join(sorted(set(target_actionable)))
            if target_air_ts:
                probe["next_air_ts"] = target_air_ts
        else:
            auto_state["next_code"] = None
            probe["tracking_code"] = None
            probe["tracked_missing_codes"] = []
            probe["actionable_missing_codes"] = []
            probe["signature"] = ""

        if target_code in pending_codes:
            # Keep pending target in pending bucket so we do not auto-fire duplicates.
            auto_state["next_code"] = target_code
            probe["tracking_code"] = target_code

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

    def _schedule_should_attempt_auto(self, track: dict[str, Any], probe: dict[str, Any]) -> tuple[bool, str | None]:
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
        return True, candidates[0]

    async def _schedule_attempt_auto_acquire(self, track: dict[str, Any], code: str) -> dict[str, Any] | None:
        try:
            result = await self._schedule_download_episode(track, code)
            LOG.info("Schedule auto-acquire succeeded: %s -> %s", code, result.get("name"))
            return result
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
        should_auto, target_code = self._schedule_should_attempt_auto(track, probe)
        auto_acquired: str | None = None
        if should_auto and target_code:
            result = await self._schedule_attempt_auto_acquire(track, target_code)
            if result:
                auto_acquired = target_code
                pending.add(target_code)
                retry_codes = dict(auto_state.get("retry_codes") or {})
                retry_codes[target_code] = now_ts()
                auto_state["retry_codes"] = retry_codes
                auto_state["last_auto_code"] = target_code
                auto_state["last_auto_at"] = now_ts()
                auto_state["next_auto_retry_at"] = now_ts() + self._schedule_retry_interval_s()
                if allow_notify:
                    await self._schedule_notify_auto_queued(track, target_code, result)
            else:
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
            and not auto_acquired
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
        return (exact_episode, exact_show, ts.resolution_tier, ts.format_score)

    async def _schedule_download_episode(self, track: dict[str, Any], code: str) -> dict[str, Any]:
        m = re.fullmatch(r"S(\d{2})E(\d{2})", code)
        if not m:
            raise RuntimeError(f"Invalid episode code: {code}")
        season = int(m.group(1))
        episode = int(m.group(2))
        show = track.get("show_json") or {}
        query = f"{show.get('name')} {code}"
        defaults = self.store.get_defaults(int(track.get("user_id") or 0), self.cfg)
        raw_rows = await asyncio.to_thread(
            self.qbt.search,
            query,
            plugin="enabled",
            search_cat="tv",
            timeout_s=self.cfg.search_timeout_s,
            poll_interval_s=self.cfg.poll_interval_s,
            early_exit_min_results=max(self.cfg.search_early_exit_min_results, 12),
            early_exit_idle_s=self.cfg.search_early_exit_idle_s,
            early_exit_max_wait_s=self.cfg.search_early_exit_max_wait_s,
        )
        filtered = self._apply_filters(
            raw_rows,
            min_seeds=int(defaults.get("default_min_seeds") or 0),
            min_size=None,
            max_size=None,
            min_quality=self.cfg.default_min_quality,
        )
        filtered = self._deduplicate_results(filtered)
        raw_exact = [
            row
            for row in raw_rows
            if self._schedule_row_matches_episode(str(row.get("fileName") or row.get("name") or ""), season, episode)
        ]
        exact = [
            row
            for row in filtered
            if self._schedule_row_matches_episode(str(row.get("fileName") or row.get("name") or ""), season, episode)
        ]
        if not exact:
            if raw_exact:
                raise RuntimeError(
                    f"Exact episode {code} was found, but every exact match failed the current TV filters"
                )
            raise RuntimeError(f"No exact qBittorrent result matched episode {code}")
        ranked = sorted(
            exact,
            key=lambda row: self._schedule_episode_rank_key(row, str(show.get("name") or ""), season, episode),
            reverse=True,
        )
        search_id = self.store.save_search(
            int(track.get("user_id") or 0),
            query,
            {
                "query": query,
                "plugin": "enabled",
                "search_cat": "tv",
                "media_hint": "tv",
                "sort": "schedule-rank",
                "order": "desc",
                "limit": 10,
            },
            ranked[:10],
        )
        return await self._do_add(int(track.get("user_id") or 0), search_id, 1, "tv")

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
    ) -> list[dict[str, Any]]:
        """Delegation stub -- logic lives in handlers/search.py."""
        return search_handler.apply_filters(
            rows, min_seeds=min_seeds, min_size=min_size, max_size=max_size, min_quality=min_quality
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
            filtered = self._apply_filters(
                raw_rows,
                min_seeds=min_seeds,
                min_size=min_size,
                max_size=max_size,
                min_quality=min_quality,
            )
            filtered = self._deduplicate_results(filtered)
            ranked = self._sort_rows(filtered, key=sort_key, order=order)
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

            sid = self.store.save_search(user_id, query, options, final_rows)
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
        items = await asyncio.to_thread(self.qbt.list_active, limit=max(n * 4, 50))
        active_downloads = [t for t in items if not self._is_complete_torrent(t)][:n]
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
        items = await asyncio.to_thread(self.qbt.list_active, limit=max(n * 4, 50))
        active_downloads = [t for t in items if not self._is_complete_torrent(t)][:n]
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
                await self._send_command_center(msg)
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
                    await self._send_command_center(msg)
                elif flow.get("mode") == "schedule":
                    self._clear_flow(user_id)
                    await self._send_command_center(msg)
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

    @staticmethod
    def _is_direct_torrent_link(url: str) -> bool:
        u = (url or "").strip()
        if not u:
            return False
        low = u.lower()
        if low.startswith("magnet:?"):
            return True
        if not (low.startswith("http://") or low.startswith("https://")):
            return False

        parsed = urllib.parse.urlparse(u)
        path = (parsed.path or "").lower()
        if path.endswith(".torrent"):
            return True

        # Heuristic: known direct download endpoints
        if "download" in path and "torrent" in path:
            return True
        if path.endswith("/dl") or path.endswith("/download"):
            return True

        return False

    def _result_to_url(self, result_row: dict[str, Any]) -> str:
        h = (result_row.get("hash") or "").strip().lower()
        name = (result_row.get("name") or "torrent").strip()
        if re.fullmatch(r"[a-f0-9]{40}", h):
            return f"magnet:?xt=urn:btih:{h}&dn={requests.utils.quote(name)}"

        for k in ("file_url", "url"):
            v = (result_row.get(k) or "").strip()
            if v and self._is_direct_torrent_link(v):
                return v

        # descr_link is usually a webpage, not a torrent payload. Only allow if it is direct.
        d = (result_row.get("descr_link") or "").strip()
        if d and self._is_direct_torrent_link(d):
            return d

        raise RuntimeError(
            "Result source is a webpage, not a direct torrent/magnet link. Pick a different result/source."
        )

    @staticmethod
    def _extract_hash(row: dict[str, Any], url: str) -> str | None:
        h = str(row.get("hash") or "").strip().lower()
        if re.fullmatch(r"[a-f0-9]{40}", h):
            return h

        m = re.search(r"btih:([A-Fa-f0-9]{40})", url)
        if m:
            return m.group(1).lower()

        return None

    async def _resolve_hash_by_name(self, title: str, category: str, wait_s: int = 20) -> str | None:
        deadline = time.time() + wait_s
        want = title.strip().lower()
        while time.time() < deadline:
            try:
                rows = await asyncio.to_thread(
                    self.qbt.list_torrents,
                    category=category,
                    sort="added_on",
                    reverse=True,
                    limit=150,
                )
                for row in rows:
                    name = str(row.get("name") or "").strip().lower()
                    if not name:
                        continue
                    if name == want or want in name or name in want:
                        h = str(row.get("hash") or "").strip().lower()
                        if re.fullmatch(r"[a-f0-9]{40}", h):
                            return h
            except Exception:
                LOG.warning("Hash lookup by name failed", exc_info=True)
            await asyncio.sleep(0.6)
        return None

    def _vpn_ready_for_download(self) -> tuple[bool, str]:
        if not self.cfg.vpn_required_for_downloads:
            return True, "vpn check disabled"

        service = self.cfg.vpn_service_name
        iface = self.cfg.vpn_interface_name

        # Check 1: VPN interface must exist.
        if not os.path.exists(f"/sys/class/net/{iface}"):
            return False, f"VPN interface missing: {iface}"

        # Check 2: Interface must not be down.
        try:
            with open(f"/sys/class/net/{iface}/operstate", encoding="utf-8") as f:
                state = f.read().strip().lower()
        except Exception:
            state = "unknown"
        if state == "down":
            return False, f"VPN interface is down: {iface}"

        # Check 3: Interface must have an IP address assigned.
        try:
            ip_result = subprocess.run(
                ["ip", "-4", "addr", "show", "dev", iface],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if ip_result.returncode != 0 or "inet " not in (ip_result.stdout or ""):
                return False, f"VPN interface {iface} has no IPv4 address"
        except Exception as e:
            return False, f"VPN interface IP check failed: {e}"

        # Check 4 (optional): If a systemd service is configured, verify it's active.
        if service:
            svc = subprocess.run(["systemctl", "is-active", "--quiet", service], capture_output=True)
            if svc.returncode != 0:
                # Not a hard failure — Surfshark Flatpak doesn't use systemd.
                LOG.debug("VPN systemd service %s is not active (may be managed externally)", service)

        return True, f"vpn ready ({iface} up)"

    async def _do_add(self, user_id: int, search_id: str, idx: int, media_choice: str) -> dict[str, Any]:
        payload = self.store.get_search(user_id, search_id)
        if not payload:
            raise RuntimeError("Search result not found")
        _search_meta, _rows = payload

        choice = self._normalize_media_choice(media_choice)
        if choice not in {"movies", "tv"}:
            raise RuntimeError("Media type must be Movies or TV")

        row = self.store.get_result(user_id, search_id, idx)
        if not row:
            raise RuntimeError("Search result not found")

        tasks = [
            asyncio.to_thread(self._ensure_media_categories),
            asyncio.to_thread(self._qbt_transport_status),
            asyncio.to_thread(self._vpn_ready_for_download),
        ]
        results = await asyncio.gather(*tasks)
        ok, reason = results[0]
        transport_ok, transport_reason = results[1]
        vpn_ok, vpn_reason = results[2]
        if not ok:
            raise RuntimeError(f"Storage/category routing not ready: {reason}")
        if not transport_ok:
            raise RuntimeError(f"qBittorrent transport is not ready: {transport_reason}")
        if not vpn_ok:
            raise RuntimeError(f"VPN safety check failed: {vpn_reason}")

        target = self._targets()[choice]
        free_ok, free_reason = self._check_free_space(target["path"])
        if not free_ok:
            raise RuntimeError(free_reason)
        url = self._result_to_url(row)
        torrent_hash = self._extract_hash(row, url)
        resp = await asyncio.to_thread(
            self.qbt.add_url,
            url,
            category=target["category"],
            savepath=target["path"],
        )

        hash_note = ""
        if not torrent_hash:
            hash_note = "\n⏳ Hash is still being assigned by qBittorrent — live monitor will auto-attach shortly."

        summary = (
            f"✅ Added #{idx}: {row['name']}\n"
            f"Library: {target['label']}\n"
            f"Category: {target['category']}\n"
            f"Path: {target['path']}\n"
            f"qBittorrent: {resp}"
            f"{hash_note}"
        )

        return {
            "summary": summary,
            "name": str(row["name"]),
            "category": str(target["category"]),
            "hash": torrent_hash,
            "path": str(target["path"]),
        }

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

        await q.answer()
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

    # ---------- Callback handler methods ----------

    async def _on_cb_nav_home(self, *, data: str, q: Any, user_id: int) -> None:
        self._clear_flow(user_id)
        # Cancel pending trackers so they don't create monitor messages after cleanup
        self._cancel_pending_trackers_for_user(user_id)
        # Recover CC location from DB if lost (e.g. bot restart).
        if not self.user_nav_ui.get(user_id):
            db_cc = await asyncio.to_thread(self.store.get_command_center, user_id)
            if db_cc:
                self.user_nav_ui[user_id] = db_cc
        has_remembered = bool(self.user_nav_ui.get(user_id))
        await self._render_command_center(q.message, user_id=user_id, use_remembered_ui=has_remembered)

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
        if data == "rm:cancel":
            self._clear_flow(user_id)
            await self._render_command_center(q.message, user_id=user_id)
            return

        if data == "rm:browse":
            await self._open_remove_browse_root(user_id, q.message, current_ui_message=q.message)
            return

        if data.startswith("rm:browsecat:"):
            category = data.split(":", 2)[2]
            candidates = await asyncio.to_thread(self._remove_library_items, category)
            if category == "tv":
                candidates = self._remove_group_tv_items(candidates)
            label = "Movies" if category == "movies" else "Shows"
            if not candidates:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    self._get_flow(user_id) or {"mode": "remove", "selected_items": []},
                    f"No {label.lower()} were found in the configured library path.",
                    reply_markup=self._remove_browse_root_keyboard(
                        len(await asyncio.to_thread(self._remove_library_items, "movies")),
                        len(await asyncio.to_thread(self._remove_library_items, "tv")),
                        self._remove_selection_count(self._get_flow(user_id) or {}),
                    ),
                    current_ui_message=q.message,
                )
                return
            flow = self._get_flow(user_id) or {"mode": "remove", "selected_items": []}
            flow["mode"] = "remove"
            flow["stage"] = "choose_item"
            flow["query"] = f"Browse {label}"
            flow["candidates"] = candidates
            flow["browse_category"] = category
            self._set_flow(user_id, flow)
            selected_paths = self._remove_selected_paths(flow)
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_list_text(
                    f"📚 {label} in Plex/library",
                    candidates,
                    0,
                    hint="Tap items to toggle them, or page through the library.",
                    selected_paths=selected_paths,
                ),
                reply_markup=self._remove_paginated_keyboard(
                    candidates,
                    0,
                    item_prefix="rm:pick",
                    nav_prefix="rm:bpage",
                    back_callback="rm:browse",
                    selected_paths=selected_paths,
                ),
                current_ui_message=q.message,
            )
            return

        if data.startswith("rm:bpage:"):
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            candidates = list(flow.get("candidates") or [])
            if not candidates:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "That library browse expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            page = int(data.split(":", 2)[2])
            label = "Movies" if str(flow.get("browse_category") or "") == "movies" else "Shows"
            selected_paths = self._remove_selected_paths(flow)
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_list_text(
                    f"📚 {label} in Plex/library",
                    candidates,
                    page,
                    hint="Tap items to toggle them, or page through the library.",
                    selected_paths=selected_paths,
                ),
                reply_markup=self._remove_paginated_keyboard(
                    candidates,
                    page,
                    item_prefix="rm:pick",
                    nav_prefix="rm:bpage",
                    back_callback="rm:browse",
                    selected_paths=selected_paths,
                ),
                current_ui_message=q.message,
            )
            return

        if data.startswith("rm:pick:"):
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            candidates = list(flow.get("candidates") or [])
            idx = int(data.split(":", 2)[2])
            if idx < 0 or idx >= len(candidates):
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "That item is no longer available. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            selected = self._remove_enrich_candidate(dict(candidates[idx]))
            flow["selected"] = selected
            flow.pop("season_items", None)
            flow.pop("episode_items", None)
            if (
                str(selected.get("root_key") or "") == "tv"
                and str(selected.get("remove_kind") or "") == "show"
                and bool(selected.get("is_dir"))
            ):
                series_selected = self._remove_group_any_selected(flow, selected)
                flow["stage"] = "show_actions"
                self._set_flow(user_id, flow)
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    self._remove_show_actions_text(selected, series_selected),
                    reply_markup=self._remove_show_action_keyboard(series_selected, self._remove_selection_count(flow)),
                    current_ui_message=q.message,
                )
                return
            self._remove_toggle_group(flow, selected)
            flow["stage"] = "choose_item"
            self._set_flow(user_id, flow)
            selected_paths = self._remove_selected_paths(flow)
            if flow.get("browse_category"):
                label = "Movies" if str(flow.get("browse_category") or "") == "movies" else "Shows"
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    self._remove_list_text(
                        f"📚 {label} in Plex/library",
                        candidates,
                        0,
                        hint="Tap items to toggle them, or page through the library.",
                        selected_paths=selected_paths,
                    ),
                    reply_markup=self._remove_paginated_keyboard(
                        candidates,
                        0,
                        item_prefix="rm:pick",
                        nav_prefix="rm:bpage",
                        back_callback="rm:browse",
                        selected_paths=selected_paths,
                    ),
                    current_ui_message=q.message,
                )
            else:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    self._remove_candidates_text(str(flow.get("query") or "Search"), candidates, selected_paths),
                    reply_markup=self._remove_candidate_keyboard(candidates, selected_paths),
                    current_ui_message=q.message,
                )
            return

        if data == "rm:series":
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove" or flow.get("stage") != "show_actions":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            selected = dict(flow.get("selected") or {})
            if not selected:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            self._remove_toggle_group(flow, selected)
            self._set_flow(user_id, flow)
            series_selected = self._remove_group_any_selected(flow, selected)
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_show_actions_text(selected, series_selected),
                reply_markup=self._remove_show_action_keyboard(series_selected, self._remove_selection_count(flow)),
                current_ui_message=q.message,
            )
            return

        if data == "rm:seasons":
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove" or flow.get("stage") != "show_actions":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            selected = dict(flow.get("selected") or {})
            group_items = selected.get("group_items")
            if group_items:
                season_items = await asyncio.to_thread(self._remove_show_group_children, group_items)
            else:
                season_items = await asyncio.to_thread(self._remove_show_children, selected)
            if not season_items:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "No seasons or direct episode files were found inside that show folder.",
                    reply_markup=self._remove_show_action_keyboard(
                        self._remove_group_any_selected(flow, selected), self._remove_selection_count(flow)
                    ),
                    current_ui_message=q.message,
                )
                return
            flow["stage"] = "browse_children"
            flow["season_items"] = season_items
            self._set_flow(user_id, flow)
            selected_paths = self._remove_selected_paths(flow)
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_list_text(
                    f"📂 {selected.get('name')} seasons / episodes",
                    season_items,
                    0,
                    hint="Tap a season to inspect it, or toggle a direct episode file.",
                    selected_paths=selected_paths,
                ),
                reply_markup=self._remove_paginated_keyboard(
                    season_items,
                    0,
                    item_prefix="rm:child",
                    nav_prefix="rm:cpage",
                    back_callback="rm:back:show",
                    selected_paths=selected_paths,
                ),
                current_ui_message=q.message,
            )
            return

        if data.startswith("rm:cpage:"):
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            season_items = list(flow.get("season_items") or [])
            selected = dict(flow.get("selected") or {})
            if not season_items or not selected:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "That season browser expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            page = int(data.split(":", 2)[2])
            selected_paths = self._remove_selected_paths(flow)
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_list_text(
                    f"📂 {selected.get('name')} seasons / episodes",
                    season_items,
                    page,
                    hint="Tap a season to inspect it, or toggle a direct episode file.",
                    selected_paths=selected_paths,
                ),
                reply_markup=self._remove_paginated_keyboard(
                    season_items,
                    page,
                    item_prefix="rm:child",
                    nav_prefix="rm:cpage",
                    back_callback="rm:back:show",
                    selected_paths=selected_paths,
                ),
                current_ui_message=q.message,
            )
            return

        if data.startswith("rm:child:"):
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            season_items = list(flow.get("season_items") or [])
            idx = int(data.split(":", 2)[2])
            if idx < 0 or idx >= len(season_items):
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "That season/episode choice is no longer available. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            selected_child = self._remove_enrich_candidate(dict(season_items[idx]))
            flow["selected_child"] = selected_child
            if str(selected_child.get("remove_kind") or "") == "season" and bool(selected_child.get("is_dir")):
                flow["stage"] = "season_actions"
                self._set_flow(user_id, flow)
                selected_paths = self._remove_selected_paths(flow)
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    self._remove_season_actions_text(selected_child),
                    reply_markup=self._remove_season_action_keyboard(
                        self._remove_selected_path(selected_child) in selected_paths,
                        len(selected_paths),
                    ),
                    current_ui_message=q.message,
                )
                return
            self._remove_toggle_candidate(flow, selected_child)
            flow["stage"] = "browse_children"
            self._set_flow(user_id, flow)
            selected_paths = self._remove_selected_paths(flow)
            parent = dict(flow.get("selected") or {})
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_list_text(
                    f"📂 {parent.get('name')} seasons / episodes",
                    season_items,
                    0,
                    hint="Tap a season to inspect it, or toggle a direct episode file.",
                    selected_paths=selected_paths,
                ),
                reply_markup=self._remove_paginated_keyboard(
                    season_items,
                    0,
                    item_prefix="rm:child",
                    nav_prefix="rm:cpage",
                    back_callback="rm:back:show",
                    selected_paths=selected_paths,
                ),
                current_ui_message=q.message,
            )
            return

        if data == "rm:seasondel":
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove" or flow.get("stage") != "season_actions":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            selected_child = dict(flow.get("selected_child") or {})
            if not selected_child:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            self._remove_toggle_candidate(flow, selected_child)
            self._set_flow(user_id, flow)
            selected_paths = self._remove_selected_paths(flow)
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_season_actions_text(selected_child),
                reply_markup=self._remove_season_action_keyboard(
                    self._remove_selected_path(selected_child) in selected_paths,
                    len(selected_paths),
                ),
                current_ui_message=q.message,
            )
            return

        if data == "rm:episodes":
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove" or flow.get("stage") != "season_actions":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            selected_child = dict(flow.get("selected_child") or {})
            episode_items = await asyncio.to_thread(self._remove_season_children, selected_child)
            if not episode_items:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "No direct episode files were found inside that season folder.",
                    reply_markup=self._remove_season_action_keyboard(
                        self._remove_selected_path(selected_child) in self._remove_selected_paths(flow),
                        self._remove_selection_count(flow),
                    ),
                    current_ui_message=q.message,
                )
                return
            flow["stage"] = "browse_episodes"
            flow["episode_items"] = episode_items
            self._set_flow(user_id, flow)
            selected_paths = self._remove_selected_paths(flow)
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_list_text(
                    f"🎞 {selected_child.get('show_name')} — {selected_child.get('name')}",
                    episode_items,
                    0,
                    hint="Tap episode files to toggle them into the delete batch.",
                    selected_paths=selected_paths,
                ),
                reply_markup=self._remove_paginated_keyboard(
                    episode_items,
                    0,
                    item_prefix="rm:episode",
                    nav_prefix="rm:epage",
                    back_callback="rm:back:season",
                    selected_paths=selected_paths,
                ),
                current_ui_message=q.message,
            )
            return

        if data.startswith("rm:epage:"):
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            episode_items = list(flow.get("episode_items") or [])
            selected_child = dict(flow.get("selected_child") or {})
            if not episode_items or not selected_child:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "That episode browser expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            page = int(data.split(":", 2)[2])
            selected_paths = self._remove_selected_paths(flow)
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_list_text(
                    f"🎞 {selected_child.get('show_name')} — {selected_child.get('name')}",
                    episode_items,
                    page,
                    hint="Tap episode files to toggle them into the delete batch.",
                    selected_paths=selected_paths,
                ),
                reply_markup=self._remove_paginated_keyboard(
                    episode_items,
                    page,
                    item_prefix="rm:episode",
                    nav_prefix="rm:epage",
                    back_callback="rm:back:season",
                    selected_paths=selected_paths,
                ),
                current_ui_message=q.message,
            )
            return

        if data.startswith("rm:episode:"):
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            episode_items = list(flow.get("episode_items") or [])
            idx = int(data.split(":", 2)[2])
            if idx < 0 or idx >= len(episode_items):
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "That episode choice is no longer available. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            selected_episode = self._remove_enrich_candidate(dict(episode_items[idx]))
            self._remove_toggle_candidate(flow, selected_episode)
            flow["stage"] = "browse_episodes"
            self._set_flow(user_id, flow)
            selected_paths = self._remove_selected_paths(flow)
            selected_child = dict(flow.get("selected_child") or {})
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_list_text(
                    f"🎞 {selected_child.get('show_name')} — {selected_child.get('name')}",
                    episode_items,
                    0,
                    hint="Tap episode files to toggle them into the delete batch.",
                    selected_paths=selected_paths,
                ),
                reply_markup=self._remove_paginated_keyboard(
                    episode_items,
                    0,
                    item_prefix="rm:episode",
                    nav_prefix="rm:epage",
                    back_callback="rm:back:season",
                    selected_paths=selected_paths,
                ),
                current_ui_message=q.message,
            )
            return

        if data == "rm:back:show":
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            selected = dict(flow.get("selected") or {})
            if not selected:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            flow["stage"] = "show_actions"
            self._set_flow(user_id, flow)
            selected_paths = self._remove_selected_paths(flow)
            series_selected = self._remove_group_any_selected(flow, selected)
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_show_actions_text(selected, series_selected),
                reply_markup=self._remove_show_action_keyboard(series_selected, len(selected_paths)),
                current_ui_message=q.message,
            )
            return

        if data == "rm:back:season":
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            selected_child = dict(flow.get("selected_child") or {})
            if not selected_child:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            flow["stage"] = "season_actions"
            self._set_flow(user_id, flow)
            selected_paths = self._remove_selected_paths(flow)
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_season_actions_text(selected_child),
                reply_markup=self._remove_season_action_keyboard(
                    self._remove_selected_path(selected_child) in selected_paths,
                    len(selected_paths),
                ),
                current_ui_message=q.message,
            )
            return

        if data == "rm:review":
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            selected_items = self._remove_selection_items(flow)
            effective = self._remove_effective_candidates(selected_items)
            if not effective:
                return
            flow["stage"] = "confirm_delete"
            self._set_flow(user_id, flow)
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                self._remove_confirm_text(effective),
                reply_markup=self._remove_confirm_keyboard(len(effective)),
                current_ui_message=q.message,
            )
            return

        if data == "rm:clear":
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove flow has expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            flow["selected_items"] = []
            flow.pop("selected", None)
            flow.pop("selected_child", None)
            flow.pop("season_items", None)
            flow.pop("episode_items", None)
            self._set_flow(user_id, flow)
            await self._open_remove_browse_root(user_id, q.message, current_ui_message=q.message)
            return

        if data == "rm:confirm":
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "remove" or flow.get("stage") != "confirm_delete":
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    {"mode": "remove", "selected_items": []},
                    "That remove confirmation expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            selected_items = self._remove_selection_items(flow)
            effective = self._remove_effective_candidates(selected_items)
            if not effective:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    "That remove confirmation expired. Start /remove again.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                f"🗑 Deleting {len(effective)} selected item(s) from disk…",
                reply_markup=None,
                current_ui_message=q.message,
            )
            try:
                result_text = await asyncio.to_thread(
                    self._delete_remove_candidates,
                    effective,
                    user_id=user_id,
                    chat_id=getattr(q.message, "chat_id", 0) if q.message else 0,
                )
            except Exception as e:
                await self._render_remove_ui(
                    user_id,
                    q.message,
                    flow,
                    f"Delete failed: {e}",
                    reply_markup=self._home_only_keyboard(),
                    current_ui_message=q.message,
                )
                return
            await self._render_remove_ui(
                user_id,
                q.message,
                flow,
                result_text,
                reply_markup=self._home_only_keyboard(),
                current_ui_message=q.message,
            )
            self._clear_flow(user_id)
            return

    async def _on_cb_schedule(self, *, data: str, q: Any, user_id: int) -> None:
        if data == "sch:cancel":
            self._clear_flow(user_id)
            await self._render_command_center(q.message, user_id=user_id)
            return

        if data.startswith("sch:pick:"):
            idx = int(data.split(":", 2)[2])
            await self._schedule_pick_candidate(q.message, user_id, idx)
            return

        if data == "sch:change":
            self._schedule_start_flow(user_id)
            flow = self._get_flow(user_id) or {"mode": "schedule", "stage": "await_show"}
            await self._render_schedule_ui(
                user_id,
                q.message,
                flow,
                "<b>✏️ Type a show name to search</b>\n━━━━━━━━━━━━━━━━━━━━\n\nMonitors your Plex library and auto-queues missing episodes as they air.\n\n<i>Example: Severance</i>",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return

        if data == "sch:season":
            flow = self._get_flow(user_id)
            if not flow or flow.get("mode") != "schedule" or flow.get("stage") != "confirm":
                await self._render_schedule_ui(
                    user_id,
                    q.message,
                    {"mode": "schedule", "stage": "await_show"},
                    "<b>⏰ Session Expired</b>\nThat schedule setup is no longer active.\n<i>Start /schedule again.</i>",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                return
            available = list(
                (flow.get("probe") or {}).get("available_seasons")
                or flow.get("selected_show", {}).get("available_seasons")
                or []
            )
            flow["stage"] = "await_season_pick"
            self._set_flow(user_id, flow)
            await self._render_schedule_ui(
                user_id,
                q.message,
                flow,
                "Send the season number to track. Available seasons: " + ", ".join(str(x) for x in available),
                reply_markup=None,
                current_ui_message=q.message,
            )
            return

        if data == "sch:confirm:all":
            flow = self._get_flow(user_id)
            if not flow or flow.get("stage") != "confirm":
                await self._schedule_confirm_selection(q.message, user_id, int(q.message.chat_id), post_action="all")
                return
            probe = dict(flow.get("probe") or {})
            codes = list(probe.get("actionable_missing_codes") or probe.get("missing_codes") or [])
            if not codes:
                await self._schedule_confirm_selection(q.message, user_id, int(q.message.chat_id), post_action=None)
                return
            flow["stage"] = "dl_confirm"
            flow["dl_confirm_codes"] = codes
            flow["dl_confirm_post_action"] = "all"
            flow["dl_confirm_from"] = "confirm"
            self._set_flow(user_id, flow)
            await self._render_schedule_ui(
                user_id,
                q.message,
                flow,
                self._schedule_dl_confirm_text(flow),
                reply_markup=self._schedule_dl_confirm_keyboard(),
                current_ui_message=q.message,
            )
            return

        if data == "sch:confirm:series":
            flow = self._get_flow(user_id)
            if not flow or flow.get("stage") != "confirm":
                await self._schedule_confirm_selection(q.message, user_id, int(q.message.chat_id), post_action="series")
                return
            probe = dict(flow.get("probe") or {})
            codes = list(probe.get("series_actionable_all") or probe.get("actionable_missing_codes") or [])
            if not codes:
                await self._schedule_confirm_selection(q.message, user_id, int(q.message.chat_id), post_action=None)
                return
            flow["stage"] = "dl_confirm"
            flow["dl_confirm_codes"] = codes
            flow["dl_confirm_post_action"] = "series"
            flow["dl_confirm_from"] = "confirm"
            self._set_flow(user_id, flow)
            await self._render_schedule_ui(
                user_id,
                q.message,
                flow,
                self._schedule_dl_confirm_text(flow),
                reply_markup=self._schedule_dl_confirm_keyboard(),
                current_ui_message=q.message,
            )
            return

        if data == "sch:confirm:pick":
            await self._schedule_confirm_selection(q.message, user_id, int(q.message.chat_id), post_action="pick")
            return

        if data == "sch:confirm":
            await self._schedule_confirm_selection(q.message, user_id, int(q.message.chat_id))
            return

        if data.startswith("sch:all:"):
            track_id = data.split(":", 2)[2]
            track = await asyncio.to_thread(self.store.get_schedule_track, user_id, track_id)
            if not track:
                await self._render_nav_ui(
                    user_id,
                    q.message,
                    "That schedule entry was not found.",
                    reply_markup=self._home_only_keyboard(),
                    current_ui_message=q.message,
                )
                return
            probe = dict(track.get("last_probe_json") or {})
            codes = list(probe.get("actionable_missing_codes") or probe.get("missing_codes") or [])
            await self._schedule_download_requested(q.message, track, codes)
            return

        if data.startswith("sch:pickeps:"):
            track_id = data.split(":", 2)[2]
            track = await asyncio.to_thread(self.store.get_schedule_track, user_id, track_id)
            if not track:
                await self._render_nav_ui(
                    user_id,
                    q.message,
                    "That schedule entry was not found.",
                    reply_markup=self._home_only_keyboard(),
                    current_ui_message=q.message,
                )
                return
            probe = dict(track.get("last_probe_json") or {})
            current_season = int(track.get("season") or 1)
            current_missing = list(probe.get("actionable_missing_codes") or probe.get("missing_codes") or [])
            all_missing = self._schedule_picker_all_missing(probe, current_season, current_missing)
            if not any(all_missing.values()):
                await self._render_nav_ui(
                    user_id,
                    q.message,
                    "There are no current missing episodes to pick from.",
                    reply_markup=self._home_only_keyboard(),
                    current_ui_message=q.message,
                )
                return
            picker_flow: dict[str, Any] = {
                "mode": "schedule",
                "stage": "picker",
                "picker_selected": [],
                "picker_season": current_season,
                "picker_all_missing": all_missing,
                "picker_has_preview": False,
                "picker_track_id": track_id,
                "picker_show": dict(track.get("show_json") or {}),
            }
            self._set_flow(user_id, picker_flow)
            await self._render_schedule_ui(
                user_id,
                q.message,
                picker_flow,
                self._schedule_picker_text(picker_flow),
                reply_markup=self._schedule_picker_keyboard(picker_flow),
                current_ui_message=q.message,
            )
            return

        if data.startswith("sch:pktog:"):
            code = data[len("sch:pktog:") :]
            flow = self._get_flow(user_id)
            if not flow or flow.get("stage") != "picker":
                await q.answer("Session expired — start over.", show_alert=True)
                return
            selected_list: list[str] = list(flow.get("picker_selected") or [])
            if code in selected_list:
                selected_list.remove(code)
            else:
                selected_list.append(code)
            flow["picker_selected"] = selected_list
            self._set_flow(user_id, flow)
            await self._render_schedule_ui(
                user_id,
                q.message,
                flow,
                self._schedule_picker_text(flow),
                reply_markup=self._schedule_picker_keyboard(flow),
                current_ui_message=q.message,
            )
            return

        if data.startswith("sch:pkseason:"):
            new_season = int(data.split(":", 2)[2])
            flow = self._get_flow(user_id)
            if not flow or flow.get("stage") != "picker":
                await q.answer("Session expired — start over.", show_alert=True)
                return
            flow["picker_season"] = new_season
            self._set_flow(user_id, flow)
            await self._render_schedule_ui(
                user_id,
                q.message,
                flow,
                self._schedule_picker_text(flow),
                reply_markup=self._schedule_picker_keyboard(flow),
                current_ui_message=q.message,
            )
            return

        if data == "sch:pkconfirm":
            flow = self._get_flow(user_id)
            if not flow or flow.get("stage") != "picker":
                await q.answer("Session expired — start over.", show_alert=True)
                return
            selected_codes = list(flow.get("picker_selected") or [])
            if not selected_codes:
                await q.answer("No episodes selected.", show_alert=True)
                return
            flow["stage"] = "dl_confirm"
            flow["dl_confirm_codes"] = selected_codes
            flow["dl_confirm_post_action"] = "pick"
            flow["dl_confirm_from"] = "picker"
            self._set_flow(user_id, flow)
            await self._render_schedule_ui(
                user_id,
                q.message,
                flow,
                self._schedule_dl_confirm_text(flow),
                reply_markup=self._schedule_dl_confirm_keyboard(),
                current_ui_message=q.message,
            )
            return

        if data == "sch:pkback":
            flow = self._get_flow(user_id)
            if not flow or flow.get("stage") != "picker":
                await q.answer("Session expired.", show_alert=True)
                return
            if flow.get("picker_has_preview"):
                probe = dict(flow.get("probe") or {})
                flow["stage"] = "confirm"
                self._set_flow(user_id, flow)
                await self._render_schedule_ui(
                    user_id,
                    q.message,
                    flow,
                    self._schedule_preview_text(probe),
                    reply_markup=self._schedule_preview_keyboard(probe),
                    current_ui_message=q.message,
                )
            else:
                self._clear_flow(user_id)
                await self._render_nav_ui(
                    user_id,
                    q.message,
                    "<b>↩️ Cancelled</b>",
                    reply_markup=self._home_only_keyboard(),
                    current_ui_message=q.message,
                )
            return

        if data == "sch:dlgo":
            flow = self._get_flow(user_id)
            if not flow or flow.get("stage") != "dl_confirm":
                await q.answer("Session expired — start over.", show_alert=True)
                return
            post_action = str(flow.get("dl_confirm_post_action") or "all")
            dl_from = str(flow.get("dl_confirm_from") or "confirm")
            if dl_from == "picker":
                selected_codes = list(flow.get("dl_confirm_codes") or [])
                pk_track_id = str(flow.get("picker_track_id") or "")
                pk_track = await asyncio.to_thread(self.store.get_schedule_track, user_id, pk_track_id)
                if not pk_track:
                    await self._render_schedule_ui(
                        user_id,
                        q.message,
                        flow,
                        "That schedule entry was not found.",
                        reply_markup=None,
                        current_ui_message=q.message,
                    )
                    self._clear_flow(user_id)
                    return
                self._clear_flow(user_id)
                n = len(selected_codes)
                await self._render_schedule_ui(
                    user_id,
                    q.message,
                    flow,
                    f"Queuing {n} episode{'s' if n != 1 else ''}…",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                await self._schedule_download_requested(q.message, pk_track, selected_codes)
            else:
                flow["stage"] = "confirm"
                self._set_flow(user_id, flow)
                await self._schedule_confirm_selection(
                    q.message, user_id, int(q.message.chat_id), post_action=post_action
                )
            return

        if data == "sch:dlback":
            flow = self._get_flow(user_id)
            if not flow or flow.get("stage") != "dl_confirm":
                await q.answer("Session expired.", show_alert=True)
                return
            dl_from = str(flow.get("dl_confirm_from") or "confirm")
            if dl_from == "picker":
                flow["stage"] = "picker"
                self._set_flow(user_id, flow)
                await self._render_schedule_ui(
                    user_id,
                    q.message,
                    flow,
                    self._schedule_picker_text(flow),
                    reply_markup=self._schedule_picker_keyboard(flow),
                    current_ui_message=q.message,
                )
            else:
                probe = dict(flow.get("probe") or {})
                flow["stage"] = "confirm"
                self._set_flow(user_id, flow)
                await self._render_schedule_ui(
                    user_id,
                    q.message,
                    flow,
                    self._schedule_preview_text(probe),
                    reply_markup=self._schedule_preview_keyboard(probe),
                    current_ui_message=q.message,
                )
            return

        if data.startswith("sch:ep:"):
            _, _, track_id, episode_raw = data.split(":", 3)
            track = await asyncio.to_thread(self.store.get_schedule_track, user_id, track_id)
            if not track:
                await self._render_nav_ui(
                    user_id,
                    q.message,
                    "That schedule entry was not found.",
                    reply_markup=self._home_only_keyboard(),
                    current_ui_message=q.message,
                )
                return
            code = episode_code(int(track.get("season") or 1), int(episode_raw))
            await self._schedule_download_requested(q.message, track, [code])
            return

        if data.startswith("sch:skip:"):
            track_id = data.split(":", 2)[2]
            track = await asyncio.to_thread(self.store.get_schedule_track, user_id, track_id)
            if not track:
                await self._render_nav_ui(
                    user_id,
                    q.message,
                    "That schedule entry was not found.",
                    reply_markup=self._home_only_keyboard(),
                    current_ui_message=q.message,
                )
                return
            probe = dict(track.get("last_probe_json") or {})
            signature = str(probe.get("signature") or "") or None
            await asyncio.to_thread(
                self.store.update_schedule_track,
                track_id,
                skipped_signature=signature,
                last_missing_signature=signature,
            )
            await self._render_nav_ui(
                user_id,
                q.message,
                "👍 Got it — I'll skip this notification.\n"
                "<i>I'll alert you again if new episodes air or the missing count changes.</i>",
                reply_markup=self._home_only_keyboard(),
                current_ui_message=q.message,
            )
            return

        if data == "sch:addnew":
            self._schedule_start_flow(user_id)
            text = (
                "<b>✏️ Type a show name to search</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Monitors your Plex library and auto-queues missing episodes as they air.\n\n"
                "<i>Example: Severance</i>"
            )
            kb = InlineKeyboardMarkup(self._nav_footer(back_data="menu:schedule", include_home=False))
            await self._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)
            return

        if data == "sch:myshows":
            tracks = await asyncio.to_thread(self.store.list_schedule_tracks, user_id, False, 50)
            if not tracks:
                await self._render_nav_ui(
                    user_id,
                    q.message,
                    "<b>📋 My Shows</b>\n━━━━━━━━━━━━━━━━━━━━\n\nNo shows tracked yet.\nTap <b>Add New Show</b> to get started.",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("➕ Add New Show", callback_data="sch:addnew")],
                        ]
                        + self._nav_footer(back_data="menu:schedule", include_home=False)
                    ),
                    current_ui_message=q.message,
                )
                return
            lines = [
                "<b>📋 My Shows</b>",
                "━━━━━━━━━━━━━━━━━━━━",
                "<i>⏸ Pause or ▶️ Resume tracking. 🚫 Stop to remove a show.</i>",
            ]
            rows: list[list[InlineKeyboardButton]] = []
            for track in tracks:
                show = dict(track.get("show_json") or {})
                name = str(show.get("name") or track.get("show_name") or "Unknown")
                season = int(track.get("season") or 1)
                tid = track["track_id"]
                enabled = track.get("enabled")
                lines.append("")
                if enabled:
                    lines.append(self._schedule_active_line(track))
                else:
                    lines.append(self._schedule_paused_line(name, season))
                if enabled:
                    rows.append(
                        [
                            InlineKeyboardButton(f"⏸ {name}", callback_data=f"sch:pause:{tid}"),
                            InlineKeyboardButton("🚫 Stop Tracking", callback_data=f"sch:dconf:{tid}"),
                        ]
                    )
                else:
                    rows.append(
                        [
                            InlineKeyboardButton(f"▶️ {name}", callback_data=f"sch:pause:{tid}"),
                            InlineKeyboardButton("🚫 Stop Tracking", callback_data=f"sch:dconf:{tid}"),
                        ]
                    )
            rows.append([InlineKeyboardButton("➕ Add New Show", callback_data="sch:addnew")])
            rows += self._nav_footer(back_data="menu:schedule", include_home=False)
            await self._render_nav_ui(
                user_id,
                q.message,
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(rows),
                current_ui_message=q.message,
            )
            return

        if data.startswith("sch:pause:"):
            tid = data.split(":", 2)[2]
            track = await asyncio.to_thread(self.store.get_schedule_track, user_id, tid)
            if not track:
                await self._render_nav_ui(
                    user_id,
                    q.message,
                    "Track not found.",
                    reply_markup=self._home_only_keyboard(),
                    current_ui_message=q.message,
                )
                return
            new_enabled = not track.get("enabled")
            await asyncio.to_thread(self.store.update_schedule_track, tid, enabled=new_enabled)
            show = dict(track.get("show_json") or {})
            name = str(show.get("name") or track.get("show_name") or "Unknown")
            action = "resumed" if new_enabled else "paused"
            await q.answer(f"{name} {action}")
            # Re-render My Shows list
            tracks = await asyncio.to_thread(self.store.list_schedule_tracks, user_id, False, 50)
            lines = [
                "<b>📋 My Shows</b>",
                "━━━━━━━━━━━━━━━━━━━━",
                "<i>⏸ Pause or ▶️ Resume tracking. 🚫 Stop to remove a show.</i>",
            ]
            rows_list: list[list[InlineKeyboardButton]] = []
            for t in tracks:
                s = dict(t.get("show_json") or {})
                n = str(s.get("name") or t.get("show_name") or "Unknown")
                sn = int(t.get("season") or 1)
                t_id = t["track_id"]
                lines.append("")
                if t.get("enabled"):
                    lines.append(self._schedule_active_line(t))
                    rows_list.append(
                        [
                            InlineKeyboardButton(f"⏸ {n}", callback_data=f"sch:pause:{t_id}"),
                            InlineKeyboardButton("🚫 Stop Tracking", callback_data=f"sch:dconf:{t_id}"),
                        ]
                    )
                else:
                    lines.append(self._schedule_paused_line(n, sn))
                    rows_list.append(
                        [
                            InlineKeyboardButton(f"▶️ {n}", callback_data=f"sch:pause:{t_id}"),
                            InlineKeyboardButton("🚫 Stop Tracking", callback_data=f"sch:dconf:{t_id}"),
                        ]
                    )
            rows_list.append([InlineKeyboardButton("➕ Add New Show", callback_data="sch:addnew")])
            rows_list += self._nav_footer(back_data="menu:schedule", include_home=False)
            await self._render_nav_ui(
                user_id,
                q.message,
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(rows_list),
                current_ui_message=q.message,
            )
            return

        if data.startswith("sch:dconf:"):
            tid = data.split(":", 2)[2]
            track = await asyncio.to_thread(self.store.get_schedule_track, user_id, tid)
            if not track:
                await self._render_nav_ui(
                    user_id,
                    q.message,
                    "Track not found.",
                    reply_markup=self._home_only_keyboard(),
                    current_ui_message=q.message,
                )
                return
            show = dict(track.get("show_json") or {})
            name = str(show.get("name") or track.get("show_name") or "Unknown")
            season = int(track.get("season") or 1)
            text = (
                f"<b>🗑 Delete Tracking?</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Stop tracking <b>{_h(name)}</b> S{season:02d}?\n\n"
                f"<i>This removes the schedule entry. It won't delete any downloaded files.</i>"
            )
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Yes, delete", callback_data=f"sch:del:{tid}"),
                        InlineKeyboardButton("Cancel", callback_data="sch:myshows"),
                    ],
                ]
            )
            await self._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)
            return

        if data.startswith("sch:del:"):
            tid = data.split(":", 2)[2]
            track = await asyncio.to_thread(self.store.get_schedule_track, user_id, tid)
            show_name = "Unknown"
            if track:
                show = dict(track.get("show_json") or {})
                show_name = str(show.get("name") or track.get("show_name") or "Unknown")
            deleted = await asyncio.to_thread(self.store.delete_schedule_track, tid, user_id)
            if deleted:
                await q.answer(f"{show_name} removed")
            # Re-render My Shows list (reuse sch:myshows logic)
            tracks = await asyncio.to_thread(self.store.list_schedule_tracks, user_id, False, 50)
            if not tracks:
                await self._render_nav_ui(
                    user_id,
                    q.message,
                    "<b>📋 My Shows</b>\n━━━━━━━━━━━━━━━━━━━━\n\nNo shows tracked yet.\nTap <b>Add New Show</b> to get started.",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("➕ Add New Show", callback_data="sch:addnew")],
                        ]
                        + self._nav_footer(back_data="menu:schedule", include_home=False)
                    ),
                    current_ui_message=q.message,
                )
                return
            lines = [
                "<b>📋 My Shows</b>",
                "━━━━━━━━━━━━━━━━━━━━",
                "<i>⏸ Pause or ▶️ Resume tracking. 🚫 Stop to remove a show.</i>",
            ]
            rows_del: list[list[InlineKeyboardButton]] = []
            for t in tracks:
                s = dict(t.get("show_json") or {})
                n = str(s.get("name") or t.get("show_name") or "Unknown")
                sn = int(t.get("season") or 1)
                t_id = t["track_id"]
                lines.append("")
                if t.get("enabled"):
                    lines.append(self._schedule_active_line(t))
                    rows_del.append(
                        [
                            InlineKeyboardButton(f"⏸ {n}", callback_data=f"sch:pause:{t_id}"),
                            InlineKeyboardButton("🚫 Stop Tracking", callback_data=f"sch:dconf:{t_id}"),
                        ]
                    )
                else:
                    lines.append(self._schedule_paused_line(n, sn))
                    rows_del.append(
                        [
                            InlineKeyboardButton(f"▶️ {n}", callback_data=f"sch:pause:{t_id}"),
                            InlineKeyboardButton("🚫 Stop Tracking", callback_data=f"sch:dconf:{t_id}"),
                        ]
                    )
            rows_del.append([InlineKeyboardButton("➕ Add New Show", callback_data="sch:addnew")])
            rows_del += self._nav_footer(back_data="menu:schedule", include_home=False)
            await self._render_nav_ui(
                user_id,
                q.message,
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(rows_del),
                current_ui_message=q.message,
            )
            return

        # Command center actions

    async def _on_cb_menu(self, *, data: str, q: Any, user_id: int) -> None:
        if data == "menu:movie":
            self._set_flow(user_id, {"mode": "movie", "stage": "await_title"})
            text = (
                "<b>🎬 Movie Search</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Send the movie title to search.\n\n"
                "<i>Example: Dune Part Two</i>"
            )
            kb = InlineKeyboardMarkup(self._nav_footer(back_data="nav:home", include_home=False))
            await self._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)
            return

        if data == "menu:tv":
            flow = {"mode": "tv", "stage": "await_filter_choice", "season": None, "episode": None}
            self._set_flow(user_id, flow)
            await self._render_tv_ui(
                user_id,
                q.message,
                flow,
                self._tv_filter_choice_text(),
                reply_markup=self._tv_filter_choice_keyboard(),
                current_ui_message=q.message,
            )
            return

        if data == "menu:schedule":
            tracks = await asyncio.to_thread(self.store.list_schedule_tracks, user_id, False, 50)
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
                rows += self._nav_footer(back_data="nav:home", include_home=False)
                kb = InlineKeyboardMarkup(rows)
                await self._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)
            else:
                self._schedule_start_flow(user_id)
                text = (
                    "<b>✏️ Type a show name to search</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    "Monitors your Plex library and auto-queues missing episodes as they air.\n\n"
                    "<i>Example: Severance</i>"
                )
                kb = InlineKeyboardMarkup(self._nav_footer(back_data="nav:home", include_home=False))
                await self._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)
            return

        if data == "menu:remove":
            await self._open_remove_browse_root(user_id, q.message, current_ui_message=q.message)
            return

        if data == "menu:active":
            await self._render_active_ui(user_id, q.message, n=10, current_ui_message=q.message)
            return

        if data == "menu:storage":
            await self._render_categories_ui(user_id, q.message, current_ui_message=q.message)
            return

        if data == "menu:plugins":
            await self._render_plugins_ui(user_id, q.message, current_ui_message=q.message)
            return

        if data == "menu:profile":
            d = self.store.get_defaults(user_id, self.cfg)
            ok, reason = await asyncio.to_thread(self._storage_status)
            transport_ok, transport_reason = await asyncio.to_thread(self._qbt_transport_status)
            vpn_ok, vpn_reason = await asyncio.to_thread(self._vpn_ready_for_download)
            plex_storage_usage = await asyncio.to_thread(self._plex_storage_display)
            lines = [
                "Current profile:",
                f"• min_seeds: {d['default_min_seeds']}",
                f"• sort/order: {d['default_sort']} {d['default_order']}",
                f"• limit: {d['default_limit']}",
                f"• quality default: {self.cfg.default_min_quality}p+",
                f"• movies -> {self.cfg.movies_category} @ {self.cfg.movies_path}",
                f"• tv -> {self.cfg.tv_category} @ {self.cfg.tv_path}",
                f"• storage status: {'ready' if ok else 'not ready'} ({reason})",
                f"• qB transport: {'ready' if transport_ok else 'blocked'} ({transport_reason})",
                f"• plex storage: {plex_storage_usage}",
                f"• vpn gate for downloads: {'ready' if vpn_ok else 'blocked'} ({vpn_reason})",
            ]
            text = "\n".join(lines)
            kb = InlineKeyboardMarkup(self._nav_footer())
            await self._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)
            return

        if data == "menu:help":
            text = self._help_text()
            kb = InlineKeyboardMarkup(self._nav_footer())
            await self._render_nav_ui(
                user_id,
                q.message,
                text,
                reply_markup=kb,
                disable_web_page_preview=True,
                current_ui_message=q.message,
            )
            return

    async def _on_cb_flow(self, *, data: str, q: Any, user_id: int) -> None:
        if data == "flow:tv_filter_set":
            flow = {"mode": "tv", "stage": "await_filter", "season": None, "episode": None}
            self._set_flow(user_id, flow)
            await self._render_tv_ui(
                user_id,
                q.message,
                flow,
                self._tv_filter_prompt_text(),
                reply_markup=InlineKeyboardMarkup(self._nav_footer(back_data="menu:tv")),
                current_ui_message=q.message,
            )
            return

        if data == "flow:tv_filter_skip":
            flow = {"mode": "tv", "stage": "await_title", "season": None, "episode": None}
            self._set_flow(user_id, flow)
            await self._render_tv_ui(
                user_id,
                q.message,
                flow,
                self._tv_title_prompt_text(),
                reply_markup=InlineKeyboardMarkup(self._nav_footer(back_data="menu:tv")),
                current_ui_message=q.message,
            )
            return

        if data == "flow:tv_full_series":
            flow = {"mode": "tv", "stage": "await_title", "season": None, "episode": None, "full_series": True}
            self._set_flow(user_id, flow)
            await self._render_tv_ui(
                user_id,
                q.message,
                flow,
                "<b>📺 TV Search — Full Series</b>\n\n"
                "Send the show title to search.\n"
                "Results will prioritize complete series downloads.\n\n"
                "<i>Example: Severance</i>",
                reply_markup=InlineKeyboardMarkup(self._nav_footer(back_data="menu:tv")),
                current_ui_message=q.message,
            )
            return

    async def _on_cb_stop(self, *, data: str, q: Any, user_id: int) -> None:
        if data.startswith("stop:"):
            torrent_hash = data[5:]
            key = (user_id, torrent_hash.lower())
            task = self.progress_tasks.get(key)
            if task and not task.done():
                task.cancel()
            # Get category before deleting so we can offer the right restart button.
            restart_cb = "menu:movie"
            restart_label = "🎬 Restart Movie Search"
            try:
                torrent_info = await asyncio.to_thread(self.qbt.get_torrent, torrent_hash)
                if torrent_info:
                    cat = str(torrent_info.get("category") or "").strip()
                    if cat.lower() == self.cfg.tv_category.lower():
                        restart_cb = "menu:tv"
                        restart_label = "📺 Restart TV Search"
            except Exception:
                pass
            try:
                await asyncio.to_thread(self.qbt.delete_torrent, torrent_hash, delete_files=True)
                stopped_kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(restart_label, callback_data=restart_cb),
                            InlineKeyboardButton("🏠 Home", callback_data="nav:home"),
                        ]
                    ]
                )
                await q.message.edit_text(
                    "<b>🛑 Download Stopped</b>\n<i>Torrent has been removed.</i>",
                    reply_markup=stopped_kb,
                    parse_mode=_PM,
                )
            except Exception as e:
                await q.message.edit_text(
                    f"<b>⚠️ Stop Failed</b>\n<i>{_h(str(e))}</i>", reply_markup=None, parse_mode=_PM
                )
            await q.answer()
            return

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
