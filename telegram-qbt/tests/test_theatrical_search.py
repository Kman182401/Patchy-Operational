"""Tests for the theatrical movie search block feature."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from patchy_bot.clients.tv_metadata import MovieReleaseDates, MovieReleaseStatus
from patchy_bot.handlers.schedule import on_cb_movie_schedule
from patchy_bot.utils import now_ts

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta):
    """Build a BotApp with mocked internals, skipping real client init."""
    mock_config.tmdb_api_key = "test-tmdb-key"
    mock_config.tmdb_region = "US"

    with (
        patch("patchy_bot.bot.QBClient", return_value=mock_qbt),
        patch("patchy_bot.bot.Store", return_value=mock_store),
        patch("patchy_bot.bot.PlexInventoryClient", return_value=MagicMock()),
        patch("patchy_bot.bot.PatchyLLMClient", return_value=MagicMock()),
        patch("patchy_bot.bot.TVMetadataClient", return_value=mock_tvmeta),
    ):
        from patchy_bot.bot import BotApp

        app = BotApp(mock_config)

    app.tvmeta = mock_tvmeta
    app.qbt = mock_qbt
    app.store = mock_store
    return app


def _make_update(user_id: int = 12345):
    """Build a mock Telegram Update with effective_message and effective_user."""
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id

    reply_msg = MagicMock()
    reply_msg.edit_text = AsyncMock()
    reply_msg.chat_id = user_id
    reply_msg.message_id = 999

    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock(return_value=reply_msg)
    update.effective_message.chat_id = user_id
    update.effective_message.message_id = 100
    return update


class _FakeScheduleApp:
    def __init__(self, mock_ctx) -> None:
        self._ctx = mock_ctx
        self.store = mock_ctx.store
        self.cfg = mock_ctx.cfg
        self.plex = mock_ctx.plex
        self.qbt = mock_ctx.qbt
        self.flow: dict[int, dict] = {}
        self.render_calls: list[tuple[str, tuple, dict]] = []

    def _set_flow(self, user_id: int, flow: dict) -> None:
        self.flow[user_id] = flow

    def _get_flow(self, user_id: int) -> dict | None:
        return self.flow.get(user_id)

    def _clear_flow(self, user_id: int) -> None:
        self.flow.pop(user_id, None)

    async def _render_schedule_ui(self, *args, **kwargs):
        self.render_calls.append(("schedule_ui", args, kwargs))
        return MagicMock(chat_id=12345, message_id=1)

    async def _render_nav_ui(self, *args, **kwargs):
        self.render_calls.append(("nav_ui", args, kwargs))
        return MagicMock(chat_id=12345, message_id=1)

    def _nav_footer(self, **kwargs):
        return [[]]

    def _home_only_keyboard(self):
        return MagicMock()


# ---------------------------------------------------------------------------
# _detect_movie_release_status tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_status_no_api_key(mock_config, mock_store, mock_qbt, mock_tvmeta):
    bot = _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta)
    bot.cfg.tmdb_api_key = None

    result = await bot._detect_movie_release_status("any query", region="US")

    assert result == (MovieReleaseStatus.UNKNOWN, None, None, None, None)
    mock_tvmeta.search_movies.assert_not_called()


@pytest.mark.asyncio
async def test_detect_status_search_raises(mock_config, mock_store, mock_qbt, mock_tvmeta):
    bot = _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta)
    mock_tvmeta.search_movies.side_effect = RuntimeError("boom")

    result = await bot._detect_movie_release_status("any query", region="US")

    assert result == (MovieReleaseStatus.UNKNOWN, None, None, None, None)


@pytest.mark.asyncio
async def test_detect_status_no_results(mock_config, mock_store, mock_qbt, mock_tvmeta):
    bot = _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta)
    mock_tvmeta.search_movies.return_value = []

    result = await bot._detect_movie_release_status("any query", region="US")

    assert result == (MovieReleaseStatus.UNKNOWN, None, None, None, None)


@pytest.mark.asyncio
async def test_detect_status_in_theaters(mock_config, mock_store, mock_qbt, mock_tvmeta):
    bot = _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta)
    mock_tvmeta.search_movies.return_value = [
        {"tmdb_id": 12345, "title": "Inception", "year": 2024},
    ]
    mock_tvmeta.get_movie_home_release.return_value = MovieReleaseDates(
        tmdb_id=12345,
        theatrical_ts=1700000000,
        status=MovieReleaseStatus.IN_THEATERS,
    )

    result = await bot._detect_movie_release_status("Inception", region="US")

    assert result == (MovieReleaseStatus.IN_THEATERS, 12345, "Inception", 2024, 1700000000)


@pytest.mark.asyncio
async def test_detect_status_home_available(mock_config, mock_store, mock_qbt, mock_tvmeta):
    bot = _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta)
    mock_tvmeta.search_movies.return_value = [
        {"tmdb_id": 12345, "title": "Inception", "year": 2024},
    ]
    mock_tvmeta.get_movie_home_release.return_value = MovieReleaseDates(
        tmdb_id=12345,
        theatrical_ts=1700000000,
        status=MovieReleaseStatus.HOME_AVAILABLE,
    )

    result = await bot._detect_movie_release_status("Inception", region="US")

    assert result == (MovieReleaseStatus.HOME_AVAILABLE, 12345, "Inception", 2024, 1700000000)


# ---------------------------------------------------------------------------
# _show_theatrical_block tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_theatrical_block_message_in_theaters(mock_config, mock_store, mock_qbt, mock_tvmeta):
    bot = _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta)
    mock_msg = MagicMock()
    mock_msg.edit_text = AsyncMock()

    await bot._show_theatrical_block(
        mock_msg,
        MovieReleaseStatus.IN_THEATERS,
        "Inception (2024)",
        12345,
        None,
    )

    mock_msg.edit_text.assert_called_once()
    call_args = mock_msg.edit_text.call_args
    text = call_args[0][0] if call_args[0] else call_args[1].get("text", "")
    assert "Currently In Theaters" in text
    assert "Inception (2024)" in text

    markup = (
        call_args[1].get("reply_markup") or call_args[0][1]
        if len(call_args[0]) > 1
        else call_args[1].get("reply_markup")
    )
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    track_btn = [b for b in buttons if "msch:pick:12345" in (b.callback_data or "")]
    assert len(track_btn) == 1


@pytest.mark.asyncio
async def test_theatrical_block_message_pre_theatrical_with_date(
    mock_config,
    mock_store,
    mock_qbt,
    mock_tvmeta,
):
    bot = _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta)
    mock_msg = MagicMock()
    mock_msg.edit_text = AsyncMock()
    future_ts = now_ts() + 86400 * 30

    await bot._show_theatrical_block(
        mock_msg,
        MovieReleaseStatus.PRE_THEATRICAL,
        "Future Film (2026)",
        99999,
        future_ts,
    )

    mock_msg.edit_text.assert_called_once()
    call_args = mock_msg.edit_text.call_args
    text = call_args[0][0] if call_args[0] else call_args[1].get("text", "")
    assert "Not Yet Released" in text
    # Should contain a date/time reference from _relative_time()
    assert "theatrical release is" in text


# ---------------------------------------------------------------------------
# _run_search integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_search_movies_blocked_when_in_theaters(
    mock_config,
    mock_store,
    mock_qbt,
    mock_tvmeta,
):
    bot = _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta)
    mock_store.get_defaults = MagicMock(
        return_value={
            "default_min_seeds": 5,
            "default_sort": "quality",
            "default_order": "desc",
            "default_limit": 10,
        }
    )

    bot._detect_movie_release_status = AsyncMock(
        return_value=(MovieReleaseStatus.IN_THEATERS, 12345, "Inception", 2024, 1700000000),
    )
    bot._show_theatrical_block = AsyncMock()

    mock_update = _make_update()
    await bot._run_search(update=mock_update, query="Inception", media_hint="movies")

    bot._show_theatrical_block.assert_called_once()
    mock_qbt.search.assert_not_called()


@pytest.mark.asyncio
async def test_run_search_tv_skips_theatrical_check(
    mock_config,
    mock_store,
    mock_qbt,
    mock_tvmeta,
):
    bot = _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta)
    mock_store.get_defaults = MagicMock(
        return_value={
            "default_min_seeds": 5,
            "default_sort": "quality",
            "default_order": "desc",
            "default_limit": 10,
        }
    )

    bot._detect_movie_release_status = AsyncMock()

    # Let qBT search return empty so _run_search hits the "No Results" path
    mock_qbt.search.return_value = []

    mock_update = _make_update()
    await bot._run_search(update=mock_update, query="Breaking Bad S01E01", media_hint="tv")

    bot._detect_movie_release_status.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_ui_no_date_type_selection(mock_ctx, mock_callback_query, monkeypatch):
    app = _FakeScheduleApp(mock_ctx)
    app._set_flow(
        12345,
        {"mode": "msch_add", "stage": "title", "candidates": [{"tmdb_id": 42, "title": "Future Film", "year": 2026}]},
    )

    async def passthrough(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr("patchy_bot.handlers.schedule.asyncio.to_thread", passthrough)
    mock_ctx.tvmeta.get_movie_release_status.return_value = MovieReleaseDates(
        tmdb_id=42,
        theatrical_ts=now_ts() + 86400 * 30,
        digital_ts=now_ts() + 86400 * 75,
        home_release_ts=now_ts() + 86400 * 75,
        home_date_is_inferred=True,
        status=MovieReleaseStatus.PRE_THEATRICAL,
    )

    await on_cb_movie_schedule(app, data="msch:pick:42", q=mock_callback_query, user_id=12345)

    flow = app._get_flow(12345)
    assert flow is not None
    assert flow["stage"] == "confirm_date"
    assert "release_dates" not in flow
    rendered_texts = [args[3] for name, args, kwargs in app.render_calls if name == "schedule_ui" and len(args) > 3]
    assert rendered_texts
    assert all("Choose which release date to track" not in text for text in rendered_texts)


@pytest.mark.asyncio
async def test_schedule_ui_home_available_still_schedules(mock_ctx, mock_callback_query, monkeypatch):
    app = _FakeScheduleApp(mock_ctx)
    app._set_flow(
        12345,
        {
            "mode": "msch_add",
            "stage": "confirm_date",
            "tmdb_id": 77,
            "title": "Available Film",
            "year": 2024,
            "release_status": "home_available",
            "release_date_type": "home_release",
            "release_date_ts": now_ts() - 60,
            "home_release_ts": now_ts() - 60,
            "home_date_is_inferred": False,
        },
    )

    async def passthrough(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr("patchy_bot.handlers.schedule.asyncio.to_thread", passthrough)

    await on_cb_movie_schedule(app, data="msch:confirm:77", q=mock_callback_query, user_id=12345)

    tracks = mock_ctx.store.get_movie_tracks_for_user(12345)
    assert len(tracks) == 1
    assert tracks[0]["tmdb_id"] == 77
    assert tracks[0]["release_status"] == "home_available"
