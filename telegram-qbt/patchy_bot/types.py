"""Shared types for the handler decomposition."""

from __future__ import annotations

import asyncio
import collections
import threading
from dataclasses import dataclass, field
from typing import Any

from .clients.llm import PatchyLLMClient
from .clients.plex import PlexInventoryClient
from .clients.qbittorrent import QBClient
from .clients.tv_metadata import TVMetadataClient
from .config import Config
from .rate_limiter import RateLimiter
from .store import Store


@dataclass
class HandlerContext:
    """Shared state and client references available to all handler modules.

    BotApp creates a single HandlerContext during __init__ and passes it to
    every handler.  Handlers read/write the shared mutable dicts through
    this object rather than reaching back into BotApp.
    """

    # ---- Clients (immutable after init) ----
    cfg: Config
    store: Store
    qbt: QBClient
    plex: PlexInventoryClient
    tvmeta: TVMetadataClient
    patchy_llm: PatchyLLMClient
    rate_limiter: RateLimiter

    # ---- Shared mutable state ----
    user_flow: dict[int, dict[str, Any]] = field(default_factory=dict)
    user_nav_ui: dict[int, dict[str, int]] = field(default_factory=dict)
    progress_tasks: dict[tuple[int, str], asyncio.Task[Any]] = field(default_factory=dict)
    pending_tracker_tasks: dict[tuple[int, str, str], asyncio.Task[Any]] = field(default_factory=dict)
    batch_monitor_messages: dict[int, Any] = field(default_factory=dict)
    batch_monitor_tasks: dict[int, asyncio.Task[Any]] = field(default_factory=dict)
    batch_monitor_data: dict[tuple[int, str], dict[str, Any]] = field(default_factory=dict)
    user_ephemeral_messages: dict[int, list[dict[str, int]]] = field(default_factory=dict)
    command_center_refresh_tasks: dict[int, asyncio.Task[Any]] = field(default_factory=dict)
    chat_history: collections.OrderedDict[int, list[dict[str, str]]] = field(default_factory=collections.OrderedDict)
    chat_history_max_users: int = 50

    # ---- Schedule source health (protected by schedule_source_state_lock) ----
    schedule_source_state: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
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
    )
    schedule_source_state_lock: threading.Lock = field(default_factory=threading.Lock)

    # ---- Async locks for background runners ----
    schedule_runner_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    remove_runner_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    state_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # ---- Sequential download queue ----
    # Only one torrent downloads at a time; others stay paused until their turn.
    download_queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    active_download_hash: str | None = None  # hash of the currently-downloading torrent
    download_queue_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # ---- Fire-and-forget background tasks (auto-delete notices, etc.) ----
    background_tasks: set[asyncio.Task[Any]] = field(default_factory=set)

    # ---- Application reference (set after build_application) ----
    app: Any = None

    # ---- Callbacks (set after ctx creation) ----
    render_command_center: Any = None
    navigate_to_command_center: Any = None
