"""Shared pytest fixtures for Patchy Bot tests.

Provides pre-configured mocks for Config, Store, all clients,
HandlerContext, and common Telegram objects.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from patchy_bot.config import Config
from patchy_bot.rate_limiter import RateLimiter
from patchy_bot.store import Store
from patchy_bot.types import HandlerContext


@pytest.fixture
def mock_config(tmp_path) -> Config:
    """Config with test-safe defaults — temp media paths, dummy token."""
    movies = tmp_path / "Movies"
    tv = tmp_path / "TV"
    spam = tmp_path / "Spam"
    movies.mkdir()
    tv.mkdir()
    spam.mkdir()
    return Config(
        telegram_token="test:token",
        allowed_user_ids={12345},
        allow_group_chats=False,
        access_password="",
        access_session_ttl_s=0,
        vpn_required_for_downloads=False,
        vpn_service_name="",
        vpn_interface_name="tun0",
        qbt_base_url="http://127.0.0.1:8080",
        qbt_username=None,
        qbt_password=None,
        tmdb_api_key=None,
        plex_base_url=None,
        plex_token=None,
        db_path=":memory:",
        page_size=5,
        search_timeout_s=10,
        poll_interval_s=0.6,
        search_early_exit_min_results=5,
        search_early_exit_idle_s=1.0,
        search_early_exit_max_wait_s=3.0,
        default_limit=10,
        default_sort="quality",
        default_order="desc",
        default_min_quality=1080,
        default_min_seeds=5,
        movies_category="Movies",
        tv_category="TV",
        spam_category="Spam",
        movies_path=str(movies),
        tv_path=str(tv),
        spam_path=str(spam),
        nvme_mount_path=str(tmp_path),
        require_nvme_mount=False,
        patchy_chat_enabled=False,
        patchy_chat_name="Patchy",
        patchy_chat_model="test-model",
        patchy_chat_fallback_model="test-fallback",
        patchy_chat_timeout_s=10,
        patchy_chat_max_tokens=200,
        patchy_chat_temperature=0.2,
        patchy_chat_history_turns=4,
        patchy_llm_base_url=None,
        patchy_llm_api_key=None,
        progress_refresh_s=1.0,
        progress_edit_min_s=0.5,
        progress_smoothing_alpha=0.35,
        progress_track_timeout_s=60,
        backup_dir=None,
    )


@pytest.fixture
def mock_store(tmp_path) -> Store:
    """Store backed by a tmp_path SQLite file with full schema initialized."""
    db_file = str(tmp_path / "test_state.sqlite3")
    return Store(db_file)


@pytest.fixture
def mock_qbt() -> MagicMock:
    """Mock QBClient with sensible defaults."""
    qbt = MagicMock()
    qbt.list_categories.return_value = {}
    qbt.get_transfer_info.return_value = {
        "connection_status": "connected",
        "dht_nodes": 100,
        "dl_info_speed": 0,
        "up_info_speed": 0,
        "dl_info_data": 0,
        "up_info_data": 0,
    }
    qbt.get_preferences.return_value = {
        "current_network_interface": "",
        "current_interface_address": "",
        "dl_limit": 0,
        "up_limit": 0,
        "max_active_downloads": 8,
        "max_active_torrents": 15,
        "listen_port": 6881,
    }
    qbt.list_active.return_value = []
    qbt.list_search_plugins.return_value = []
    qbt.ensure_category.return_value = None
    return qbt


@pytest.fixture
def mock_plex() -> MagicMock:
    """Mock PlexInventoryClient. ready() returns True."""
    plex = MagicMock()
    plex.ready.return_value = True
    return plex


@pytest.fixture
def mock_tvmeta() -> MagicMock:
    """Mock TVMetadataClient."""
    return MagicMock()


@pytest.fixture
def mock_llm() -> MagicMock:
    """Mock PatchyLLMClient. ready() returns True."""
    llm = MagicMock()
    llm.ready.return_value = True
    return llm


@pytest.fixture
def mock_ctx(mock_config, mock_store, mock_qbt, mock_plex, mock_tvmeta, mock_llm) -> HandlerContext:
    """Fully assembled HandlerContext with all mocks."""
    return HandlerContext(
        cfg=mock_config,
        store=mock_store,
        qbt=mock_qbt,
        plex=mock_plex,
        tvmeta=mock_tvmeta,
        patchy_llm=mock_llm,
        rate_limiter=RateLimiter(limit=20, window_s=60.0),
    )


@pytest.fixture
def mock_callback_query() -> MagicMock:
    """Mock Telegram CallbackQuery with async answer/edit/reply."""
    query = MagicMock()
    query.answer = AsyncMock()

    reply_msg = MagicMock()
    reply_msg.chat_id = 12345
    reply_msg.message_id = 999

    query.message = MagicMock()
    query.message.edit_text = AsyncMock()
    query.message.reply_text = AsyncMock(return_value=reply_msg)
    query.message.delete = AsyncMock()
    query.message.chat_id = 12345
    query.message.message_id = 100
    return query


@pytest.fixture
def mock_message() -> MagicMock:
    """Mock Telegram Message with async reply_text, edit_text, delete."""
    msg = MagicMock()

    reply_msg = MagicMock()
    reply_msg.chat_id = 12345
    reply_msg.message_id = 999

    msg.reply_text = AsyncMock(return_value=reply_msg)
    msg.edit_text = AsyncMock()
    msg.delete = AsyncMock()
    msg.chat_id = 12345
    msg.message_id = 100
    return msg
