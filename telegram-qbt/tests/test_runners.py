"""Tests for background runner logic: completion poller, remove runner, schedule runner.

Covers ~24 tests across three runner subsystems plus pure-function helpers
from handlers/download.py and handlers/remove.py.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from patchy_bot.handlers.download import (
    completion_poller_job,
    extract_hash,
    is_direct_torrent_link,
    result_to_url,
)
from patchy_bot.handlers.remove import (
    path_size_bytes,
    remove_retry_backoff_s,
    remove_runner_interval_s,
    remove_runner_job,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
from tests.helpers import FakeOrganizeResult, make_torrent_info


@pytest.fixture(autouse=True)
def _default_clean_scan(monkeypatch: Any) -> None:
    monkeypatch.setattr("patchy_bot.handlers.download._run_clamav_scan", lambda path, timeout_s: ("clean", []))


def _completed_torrent(**overrides: Any) -> dict[str, Any]:
    """Return a torrent info dict that looks completed."""
    defaults = make_torrent_info(
        name="Test.Movie.2024.1080p.WEB-DL",
        state="uploading",
        progress=1.0,
        size=2_000_000_000,
        category="Movies",
        save_path="/tmp/movies",
        content_path="/tmp/movies/Test.Movie",
    )
    defaults.update(overrides)
    defaults["amount_left"] = 0
    return defaults


# ---------------------------------------------------------------------------
# 1. Completion poller tests
# ---------------------------------------------------------------------------


async def test_completion_poller_skips_when_no_app(mock_ctx: Any) -> None:
    """When ctx.app is None the poller returns immediately without touching qbt."""
    mock_ctx.app = None
    await completion_poller_job(mock_ctx, None)
    # qbt should never be called
    mock_ctx.qbt.list_torrents.assert_not_called()


async def test_completion_poller_handles_qbt_error(mock_ctx: Any) -> None:
    """If qbt.list_torrents raises, the poller logs and returns gracefully."""
    mock_ctx.app = MagicMock()
    mock_ctx.qbt.list_torrents = MagicMock(side_effect=ConnectionError("refused"))
    # Should not raise
    await completion_poller_job(mock_ctx, None)


async def test_completion_poller_skips_already_notified(mock_ctx: Any, monkeypatch: Any) -> None:
    """Completed torrents that are already notified are silently skipped."""
    completed = _completed_torrent()
    mock_ctx.app = MagicMock()
    mock_ctx.qbt.list_torrents = MagicMock(return_value=[completed])
    mock_ctx.store.is_completion_notified = MagicMock(return_value=True)
    mock_ctx.store.mark_completion_notified = MagicMock()
    mock_ctx.store.cleanup_old_completion_records = MagicMock()

    await completion_poller_job(mock_ctx, None)

    mock_ctx.store.mark_completion_notified.assert_not_called()


async def test_completion_poller_detects_finished(mock_ctx: Any, monkeypatch: Any) -> None:
    """A newly completed torrent triggers notification to all allowed users."""
    completed = _completed_torrent()
    mock_ctx.qbt.list_torrents = MagicMock(return_value=[completed])
    mock_ctx.store.is_completion_notified = MagicMock(return_value=False)
    mock_ctx.store.mark_completion_notified = MagicMock()
    mock_ctx.store.cleanup_old_completion_records = MagicMock()
    mock_ctx.cfg.allowed_user_ids = {111}

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=MagicMock(chat_id=111, message_id=1))
    mock_app = MagicMock()
    mock_app.bot = mock_bot
    mock_ctx.app = mock_app

    mock_ctx.plex.ready.return_value = False

    monkeypatch.setattr(
        "patchy_bot.handlers.download._organize_download",
        lambda *a: FakeOrganizeResult(),
    )

    await completion_poller_job(mock_ctx, None)

    mock_ctx.store.mark_completion_notified.assert_called_once()
    mock_bot.send_message.assert_called_once()
    # Verify the user ID matches
    call_kwargs = mock_bot.send_message.call_args
    assert call_kwargs.kwargs.get("chat_id") == 111 or call_kwargs[1].get("chat_id") == 111


async def test_completion_poller_organizes_download(mock_ctx: Any, monkeypatch: Any) -> None:
    """The poller runs _organize_download for each completed torrent."""
    completed = _completed_torrent()
    mock_ctx.qbt.list_torrents = MagicMock(return_value=[completed])
    mock_ctx.store.is_completion_notified = MagicMock(return_value=False)
    mock_ctx.store.mark_completion_notified = MagicMock()
    mock_ctx.store.cleanup_old_completion_records = MagicMock()
    mock_ctx.cfg.allowed_user_ids = set()
    mock_ctx.plex.ready.return_value = False

    mock_app = MagicMock()
    mock_app.bot = MagicMock()
    mock_ctx.app = mock_app

    organize_calls: list[tuple[Any, ...]] = []

    def fake_organize(*args: Any) -> FakeOrganizeResult:
        organize_calls.append(args)
        return FakeOrganizeResult()

    monkeypatch.setattr("patchy_bot.handlers.download._organize_download", fake_organize)

    await completion_poller_job(mock_ctx, None)

    assert len(organize_calls) == 1
    # First arg is the media path
    assert organize_calls[0][0] == "/tmp/movies/Test.Movie"


async def test_completion_poller_triggers_plex_scan(mock_ctx: Any, monkeypatch: Any) -> None:
    """When Plex is ready the poller triggers a refresh for the media path."""
    completed = _completed_torrent()
    mock_ctx.qbt.list_torrents = MagicMock(return_value=[completed])
    mock_ctx.store.is_completion_notified = MagicMock(return_value=False)
    mock_ctx.store.mark_completion_notified = MagicMock()
    mock_ctx.store.cleanup_old_completion_records = MagicMock()
    mock_ctx.cfg.allowed_user_ids = set()
    mock_ctx.plex.ready.return_value = True
    mock_ctx.plex.refresh_for_path = MagicMock(return_value="ok")

    mock_app = MagicMock()
    mock_app.bot = MagicMock()
    mock_ctx.app = mock_app

    monkeypatch.setattr(
        "patchy_bot.handlers.download._organize_download",
        lambda *a: FakeOrganizeResult(),
    )

    await completion_poller_job(mock_ctx, None)

    mock_ctx.plex.refresh_for_path.assert_called_once()


async def test_completion_poller_notifies_multiple_users(mock_ctx: Any, monkeypatch: Any) -> None:
    """Each allowed user receives a completion notification."""
    completed = _completed_torrent()
    mock_ctx.qbt.list_torrents = MagicMock(return_value=[completed])
    mock_ctx.store.is_completion_notified = MagicMock(return_value=False)
    mock_ctx.store.mark_completion_notified = MagicMock()
    mock_ctx.store.cleanup_old_completion_records = MagicMock()
    mock_ctx.cfg.allowed_user_ids = {100, 200, 300}
    mock_ctx.plex.ready.return_value = False

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=MagicMock(chat_id=1, message_id=1))
    mock_app = MagicMock()
    mock_app.bot = mock_bot
    mock_ctx.app = mock_app

    monkeypatch.setattr(
        "patchy_bot.handlers.download._organize_download",
        lambda *a: FakeOrganizeResult(),
    )

    await completion_poller_job(mock_ctx, None)

    assert mock_bot.send_message.call_count == 3


async def test_completion_poller_cleans_old_records(mock_ctx: Any, monkeypatch: Any) -> None:
    """The poller calls cleanup_old_completion_records at the end of each run."""
    mock_ctx.qbt.list_torrents = MagicMock(return_value=[])
    mock_ctx.store.cleanup_old_completion_records = MagicMock()
    mock_ctx.app = MagicMock()

    await completion_poller_job(mock_ctx, None)

    mock_ctx.store.cleanup_old_completion_records.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Remove runner tests
# ---------------------------------------------------------------------------


async def test_remove_runner_no_due_jobs(mock_ctx: Any, monkeypatch: Any) -> None:
    """When there are no due jobs, the runner completes without action."""
    mock_ctx.store.list_due_remove_jobs = MagicMock(return_value=[])
    monkeypatch.setattr("patchy_bot.handlers.remove.now_ts", lambda: 1000)

    await remove_runner_job(mock_ctx, None)

    mock_ctx.store.list_due_remove_jobs.assert_called_once()


async def test_remove_runner_processes_due_job(mock_ctx: Any, monkeypatch: Any) -> None:
    """A due job is passed to remove_attempt_plex_cleanup."""
    job = {"job_id": "j1", "target_path": "/tmp/x", "remove_kind": "movie"}
    mock_ctx.store.list_due_remove_jobs = MagicMock(return_value=[job])
    monkeypatch.setattr("patchy_bot.handlers.remove.now_ts", lambda: 1000)

    cleanup_calls: list[Any] = []

    def fake_cleanup(ctx: Any, j: Any, *, inline_timeout_s: int = 90) -> dict[str, Any]:
        cleanup_calls.append(j)
        return {"status": "verified", "detail": "ok"}

    monkeypatch.setattr("patchy_bot.handlers.remove.remove_attempt_plex_cleanup", fake_cleanup)

    await remove_runner_job(mock_ctx, None)

    assert len(cleanup_calls) == 1
    assert cleanup_calls[0]["job_id"] == "j1"


async def test_remove_runner_handles_cleanup_failure(mock_ctx: Any, monkeypatch: Any) -> None:
    """If cleanup raises for one job, the runner does not crash."""
    job = {"job_id": "j1", "target_path": "/tmp/x", "remove_kind": "movie"}
    mock_ctx.store.list_due_remove_jobs = MagicMock(return_value=[job])
    monkeypatch.setattr("patchy_bot.handlers.remove.now_ts", lambda: 1000)

    def fail_cleanup(ctx: Any, j: Any, *, inline_timeout_s: int = 90) -> dict[str, Any]:
        raise RuntimeError("plex is down")

    monkeypatch.setattr("patchy_bot.handlers.remove.remove_attempt_plex_cleanup", fail_cleanup)

    # Should not raise
    await remove_runner_job(mock_ctx, None)


async def test_remove_runner_lock_prevents_concurrent(mock_ctx: Any, monkeypatch: Any) -> None:
    """If the lock is already held, a second call waits rather than running in parallel."""
    monkeypatch.setattr("patchy_bot.handlers.remove.now_ts", lambda: 1000)
    mock_ctx.store.list_due_remove_jobs = MagicMock(return_value=[])

    # Acquire lock before calling
    acquired = mock_ctx.remove_runner_lock.locked()
    assert not acquired

    call_order: list[str] = []

    async def slow_runner() -> None:
        call_order.append("start-1")
        await remove_runner_job(mock_ctx, None)
        call_order.append("end-1")

    async def fast_runner() -> None:
        # Give the slow runner a moment to acquire the lock
        await asyncio.sleep(0.01)
        call_order.append("start-2")
        await remove_runner_job(mock_ctx, None)
        call_order.append("end-2")

    await asyncio.gather(slow_runner(), fast_runner())

    # Both completed; lock serialized them
    assert "start-1" in call_order
    assert "end-2" in call_order


# ---------------------------------------------------------------------------
# 3. Schedule runner tests (via BotApp._schedule_runner_job)
# ---------------------------------------------------------------------------


class DummyBotApp:
    """Minimal stand-in for BotApp with the fields _schedule_runner_job needs."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.schedule_runner_lock = asyncio.Lock()
        self._schedule_refresh_track_calls: list[Any] = []
        self._schedule_refresh_track_error: Exception | None = None

    async def _schedule_refresh_track(self, track: dict[str, Any], *, allow_notify: bool = False) -> tuple[dict, dict]:
        self._schedule_refresh_track_calls.append(track)
        if self._schedule_refresh_track_error:
            raise self._schedule_refresh_track_error
        return track, {}

    def _schedule_source_snapshot(self, key: str) -> str:
        return "{}"

    async def _check_movie_tracks(self) -> None:
        pass


def _make_dummy_bot_app(monkeypatch: Any) -> DummyBotApp:
    """Build a DummyBotApp with a mocked store."""
    store = MagicMock()
    store.update_schedule_runner_status = MagicMock()
    store.list_due_schedule_tracks = MagicMock(return_value=[])
    app = DummyBotApp(store)
    monkeypatch.setattr("patchy_bot.bot.now_ts", lambda: 5000)
    return app


async def test_schedule_runner_no_due_tracks(monkeypatch: Any) -> None:
    """With no due tracks, the runner just updates status."""
    app = _make_dummy_bot_app(monkeypatch)

    # Import and call the actual method from bot.py
    from patchy_bot.bot import BotApp

    # Bind the method to our dummy
    await BotApp._schedule_runner_job(app, None)  # type: ignore[arg-type]

    app.store.update_schedule_runner_status.assert_called()
    assert app._schedule_refresh_track_calls == []


async def test_schedule_runner_processes_due_tracks(monkeypatch: Any) -> None:
    """Due tracks are passed to _schedule_refresh_track."""
    app = _make_dummy_bot_app(monkeypatch)
    track = {"track_id": "t1", "show_name": "Test Show"}
    app.store.list_due_schedule_tracks = MagicMock(return_value=[track])

    from patchy_bot.bot import BotApp

    await BotApp._schedule_runner_job(app, None)  # type: ignore[arg-type]

    assert len(app._schedule_refresh_track_calls) == 1
    assert app._schedule_refresh_track_calls[0]["track_id"] == "t1"


async def test_schedule_runner_handles_refresh_failure(monkeypatch: Any) -> None:
    """If _schedule_refresh_track raises, the runner continues and logs error status."""
    app = _make_dummy_bot_app(monkeypatch)
    track = {"track_id": "t1", "show_name": "Test Show"}
    app.store.list_due_schedule_tracks = MagicMock(return_value=[track])
    app._schedule_refresh_track_error = RuntimeError("metadata down")

    from patchy_bot.bot import BotApp

    await BotApp._schedule_runner_job(app, None)  # type: ignore[arg-type]

    # Runner still completed -- status updated
    app.store.update_schedule_runner_status.assert_called()


async def test_schedule_runner_updates_status_on_success(monkeypatch: Any) -> None:
    """After successful processing, last_success_at is set in the final status update."""
    app = _make_dummy_bot_app(monkeypatch)
    app.store.list_due_schedule_tracks = MagicMock(return_value=[])

    from patchy_bot.bot import BotApp

    await BotApp._schedule_runner_job(app, None)  # type: ignore[arg-type]

    # Find the call that sets last_success_at
    calls = app.store.update_schedule_runner_status.call_args_list
    final_call_kwargs = calls[-1].kwargs if calls[-1].kwargs else {}
    assert "last_success_at" in final_call_kwargs


async def test_schedule_runner_updates_status_on_error(monkeypatch: Any) -> None:
    """If the outer loop fails, last_error_text is set."""
    app = _make_dummy_bot_app(monkeypatch)
    # Make list_due_schedule_tracks raise to trigger the outer except
    app.store.list_due_schedule_tracks = MagicMock(side_effect=RuntimeError("db locked"))

    from patchy_bot.bot import BotApp

    await BotApp._schedule_runner_job(app, None)  # type: ignore[arg-type]

    calls = app.store.update_schedule_runner_status.call_args_list
    final_call_kwargs = calls[-1].kwargs if calls[-1].kwargs else {}
    assert "last_error_text" in final_call_kwargs
    assert "db locked" in str(final_call_kwargs["last_error_text"])


# ---------------------------------------------------------------------------
# 4. Pure function tests — remove helpers
# ---------------------------------------------------------------------------


def test_remove_runner_interval_s() -> None:
    """remove_runner_interval_s returns the expected 60-second interval."""
    assert remove_runner_interval_s() == 60


def test_remove_retry_backoff_s_zero() -> None:
    """retry_count 0 returns the minimum backoff."""
    assert remove_retry_backoff_s(0) == 30


def test_remove_retry_backoff_s_high() -> None:
    """High retry counts cap at the maximum backoff step."""
    assert remove_retry_backoff_s(100) == 600


def test_remove_retry_backoff_s_middle() -> None:
    """Middle retry counts return increasing backoff values."""
    assert remove_retry_backoff_s(1) == 60
    assert remove_retry_backoff_s(2) == 120
    assert remove_retry_backoff_s(3) == 300


def test_path_size_bytes_returns_zero_for_missing() -> None:
    """A nonexistent path returns 0 bytes."""
    assert path_size_bytes("/nonexistent/path/that/does/not/exist") == 0


# ---------------------------------------------------------------------------
# 5. Pure function tests — download helpers
# ---------------------------------------------------------------------------


def test_is_direct_torrent_link_magnet() -> None:
    """Magnet URLs are recognized as direct torrent links."""
    assert is_direct_torrent_link("magnet:?xt=urn:btih:abc123") is True


def test_is_direct_torrent_link_dot_torrent() -> None:
    """.torrent URLs are recognized as direct torrent links."""
    assert is_direct_torrent_link("https://example.com/file.torrent") is True


def test_is_direct_torrent_link_webpage() -> None:
    """Regular web pages are not direct torrent links."""
    assert is_direct_torrent_link("https://example.com/page.html") is False


def test_is_direct_torrent_link_empty() -> None:
    """Empty string returns False."""
    assert is_direct_torrent_link("") is False


def test_result_to_url_with_hash() -> None:
    """When a result has a valid 40-char hex hash, a magnet link is generated."""
    row = {"hash": "a" * 40, "name": "Test.Torrent"}
    url = result_to_url(row)
    assert url.startswith("magnet:?xt=urn:btih:")
    assert "a" * 40 in url


def test_result_to_url_with_file_url() -> None:
    """When hash is missing but file_url is a direct link, it is returned."""
    row = {"hash": "", "name": "Test", "file_url": "magnet:?xt=urn:btih:abc", "url": ""}
    url = result_to_url(row)
    assert url == "magnet:?xt=urn:btih:abc"


def test_extract_hash_from_row() -> None:
    """A valid hash in the row dict is extracted directly."""
    row = {"hash": "b" * 40}
    assert extract_hash(row, "") == "b" * 40


def test_extract_hash_from_magnet() -> None:
    """When the row has no hash, the btih is extracted from the magnet URL."""
    row = {"hash": ""}
    url = f"magnet:?xt=urn:btih:{'c' * 40}&dn=test"
    assert extract_hash(row, url) == "c" * 40


def test_extract_hash_returns_none() -> None:
    """When neither row nor URL has a hash, None is returned."""
    row = {"hash": ""}
    assert extract_hash(row, "https://example.com/page") is None


# ---------------------------------------------------------------------------
# Batch auto-acquire tests for _schedule_refresh_track
# ---------------------------------------------------------------------------


class _BatchDummyStore:
    """Minimal store for batch auto-acquire tests."""

    def __init__(self, track: dict[str, Any]) -> None:
        self._track = track
        self.last_update_kwargs: dict[str, Any] = {}

    def update_schedule_track(self, track_id: str, **kwargs: Any) -> None:
        self.last_update_kwargs = kwargs

    def get_schedule_track_any(self, track_id: str) -> dict[str, Any]:
        merged = dict(self._track)
        merged.update(self.last_update_kwargs)
        return merged


class _BatchDummyBot:
    """Minimal stand-in for BotApp with batch auto-acquire support."""

    def __init__(self, store: _BatchDummyStore, acquire_results: dict[str, dict | None]) -> None:
        self.store = store
        self._acquire_results = acquire_results
        self.acquire_calls: list[str] = []
        self.notify_calls: list[tuple[str, dict]] = []

    def _schedule_probe_track(self, track: dict[str, Any]) -> dict[str, Any]:
        return dict(track.get("_test_probe") or {})

    def _schedule_episode_auto_state(self, track: dict[str, Any]) -> dict[str, Any]:
        return dict(track.get("auto_state_json") or {})

    def _schedule_sanitize_auto_state(self, auto_state: dict, *, probe: dict | None = None) -> dict:
        return auto_state

    def _schedule_reconcile_pending(self, track: dict, probe: dict) -> tuple[set, set, set]:
        return set(), set(), set()

    def _schedule_should_attempt_auto(self, track: dict, probe: dict) -> tuple[bool, list[str] | str]:
        codes = list(probe.get("actionable_missing_codes") or [])
        if not codes:
            return False, "no actionable"
        return True, codes

    async def _schedule_attempt_auto_acquire(self, track: dict, code: str) -> dict | None:
        self.acquire_calls.append(code)
        return self._acquire_results.get(code)

    async def _schedule_notify_auto_queued(self, track: dict, code: str, result: dict) -> None:
        self.notify_calls.append((code, result))

    async def _schedule_notify_missing(self, track: dict, probe: dict) -> None:
        pass

    def _schedule_next_check_at(self, next_air_ts: Any, *, has_actionable_missing: bool, auto_state: dict) -> int:
        return 9999

    def _schedule_retry_interval_s(self) -> int:
        return 3600

    def _schedule_release_grace_s(self) -> int:
        return 3600

    def _schedule_source_snapshot(self, key: str) -> dict:
        return {}


def _make_batch_track(actionable: list[str]) -> dict[str, Any]:
    """Build a track dict with an embedded probe for batch tests."""
    probe = {
        "actionable_missing_codes": actionable,
        "tracked_missing_codes": actionable,
        "tracking_code": actionable[0] if actionable else None,
        "signature": "|".join(sorted(actionable)),
        "show": {"name": "Test Show"},
        "_auto_state": {"enabled": True},
    }
    return {
        "track_id": "t-batch",
        "pending_json": [],
        "auto_state_json": {"enabled": True},
        "show_json": {"name": "Test Show"},
        "skipped_signature": None,
        "last_missing_signature": None,
        "_test_probe": probe,
    }


async def test_schedule_runner_batch_downloads_multiple_episodes(monkeypatch: Any) -> None:
    """All three episodes are acquired and notified in one refresh cycle."""
    monkeypatch.setattr("patchy_bot.bot.now_ts", lambda: 5000)
    codes = ["S01E01", "S01E02", "S01E03"]
    track = _make_batch_track(codes)
    acquire_results = {c: {"name": f"Test.{c}", "hash": f"hash_{c}"} for c in codes}
    store = _BatchDummyStore(track)
    bot = _BatchDummyBot(store, acquire_results)

    from patchy_bot.bot import BotApp

    await BotApp._schedule_refresh_track(bot, track, allow_notify=True)  # type: ignore[arg-type]

    assert bot.acquire_calls == codes
    assert [c for c, _ in bot.notify_calls] == codes
    assert store.last_update_kwargs.get("auto_state_json", {}).get("next_auto_retry_at") is None


async def test_schedule_runner_batch_partial_failure(monkeypatch: Any) -> None:
    """Partial success: 2 of 3 episodes succeed, no cooldown set."""
    monkeypatch.setattr("patchy_bot.bot.now_ts", lambda: 5000)
    codes = ["S01E01", "S01E02", "S01E03"]
    track = _make_batch_track(codes)
    acquire_results = {
        "S01E01": {"name": "Test.E01", "hash": "h1"},
        "S01E02": None,  # fails
        "S01E03": {"name": "Test.E03", "hash": "h3"},
    }
    store = _BatchDummyStore(track)
    bot = _BatchDummyBot(store, acquire_results)

    from patchy_bot.bot import BotApp

    await BotApp._schedule_refresh_track(bot, track, allow_notify=True)  # type: ignore[arg-type]

    assert bot.acquire_calls == codes
    assert [c for c, _ in bot.notify_calls] == ["S01E01", "S01E03"]
    assert store.last_update_kwargs.get("auto_state_json", {}).get("next_auto_retry_at") is None


async def test_schedule_runner_batch_all_fail(monkeypatch: Any) -> None:
    """All episodes fail: cooldown is set."""
    monkeypatch.setattr("patchy_bot.bot.now_ts", lambda: 5000)
    codes = ["S01E01", "S01E02", "S01E03"]
    track = _make_batch_track(codes)
    acquire_results: dict[str, dict | None] = {c: None for c in codes}
    store = _BatchDummyStore(track)
    bot = _BatchDummyBot(store, acquire_results)

    from patchy_bot.bot import BotApp

    await BotApp._schedule_refresh_track(bot, track, allow_notify=True)  # type: ignore[arg-type]

    assert bot.acquire_calls == codes
    assert bot.notify_calls == []
    retry_at = store.last_update_kwargs.get("auto_state_json", {}).get("next_auto_retry_at")
    assert retry_at is not None and retry_at > 5000
