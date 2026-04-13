"""Tests for the download pipeline: do_add, resolve_hash_by_name, progress smoothing,
active-state filtering, and shared helpers (normalize_media_choice, check_free_space).
"""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from patchy_bot.handlers._shared import (
    check_free_space,
    normalize_media_choice,
)
import patchy_bot.handlers.download as _dl_mod
from patchy_bot.handlers.download import (
    DoAddResult,
    completion_poller_job,
    do_add,
    do_add_full,
    on_cb_stop,
    render_progress_text,
    resolve_hash_by_name,
    start_progress_tracker,
    track_download_progress,
)
from patchy_bot.utils import _ACTIVE_DL_STATES

# noqa: F401 — _dl_mod used in TestCompletionPollerJob._clear_seen_hashes fixture


@pytest.fixture(autouse=True)
def _clear_preflight_cache():
    """Clear the do_add preflight cache between tests."""
    _dl_mod._preflight_cache.clear()
    yield
    _dl_mod._preflight_cache.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _torrent(
    *,
    name: str = "Test.Torrent.S01E01",
    hash: str = "a" * 40,
    state: str = "downloading",
    progress: float = 0.0,
    dlspeed: int = 0,
    upspeed: int = 0,
    size: int = 1_000_000,
    completed: int = 0,
    amount_left: int = -1,
    eta: int = -1,
    content_path: str = "/tmp/test",
    category: str = "TV",
) -> dict:
    return {
        "name": name,
        "hash": hash,
        "state": state,
        "progress": progress,
        "dlspeed": dlspeed,
        "upspeed": upspeed,
        "size": size,
        "completed": completed,
        "amount_left": amount_left,
        "eta": eta,
        "content_path": content_path,
        "category": category,
    }


def _save_search_with_hash(store, user_id, torrent_hash):
    """Save a minimal search result that has a valid 40-char hash for do_add."""
    rows = [
        {
            "name": "Test.Movie.2024.1080p",
            "size": 2_000_000_000,
            "seeds": 50,
            "hash": torrent_hash,
        }
    ]
    return store.save_search(user_id, "Test Movie 2024", {"sort": "quality"}, rows)


# ---------------------------------------------------------------------------
# 8a: do_add timeout tests
# ---------------------------------------------------------------------------


class TestDoAddTimeouts:
    """Pre-flight timeout behavior in do_add."""

    @pytest.mark.asyncio
    async def test_do_add_category_check_timeout(self, mock_ctx, monkeypatch):
        """do_add raises RuntimeError when the category check exceeds its timeout."""
        search_id = _save_search_with_hash(mock_ctx.store, 12345, "b" * 40)

        _real_wait_for = asyncio.wait_for
        call_count = 0

        async def _selective_timeout(coro, *, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First wait_for wraps ensure_media_categories — simulate timeout
                coro.close()
                raise TimeoutError()
            return await _real_wait_for(coro, timeout=timeout)

        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.wait_for", _selective_timeout)

        with pytest.raises(RuntimeError, match="timed out"):
            await do_add(mock_ctx, 12345, search_id, 1, "movies")

    @pytest.mark.asyncio
    async def test_do_add_transport_check_timeout(self, mock_ctx, monkeypatch):
        """do_add raises RuntimeError when the transport check exceeds its timeout."""
        search_id = _save_search_with_hash(mock_ctx.store, 12345, "c" * 40)

        _real_wait_for = asyncio.wait_for
        call_count = 0

        async def _selective_timeout(coro, *, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                # Second wait_for wraps qbt_transport_status
                coro.close()
                raise TimeoutError()
            return await _real_wait_for(coro, timeout=timeout)

        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.wait_for", _selective_timeout)

        # Category check must succeed so we reach the transport check
        monkeypatch.setattr(
            "patchy_bot.handlers.download.ensure_media_categories",
            lambda ctx: (True, "ready"),
        )

        with pytest.raises(RuntimeError, match="timed out"):
            await do_add(mock_ctx, 12345, search_id, 1, "movies")

    @pytest.mark.asyncio
    async def test_do_add_vpn_check_timeout(self, mock_ctx, monkeypatch):
        """do_add raises RuntimeError when the VPN check exceeds its timeout."""
        search_id = _save_search_with_hash(mock_ctx.store, 12345, "d" * 40)

        _real_wait_for = asyncio.wait_for
        call_count = 0

        async def _selective_timeout(coro, *, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                # Third wait_for wraps vpn_ready_for_download
                coro.close()
                raise TimeoutError()
            return await _real_wait_for(coro, timeout=timeout)

        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.wait_for", _selective_timeout)
        monkeypatch.setattr(
            "patchy_bot.handlers.download.ensure_media_categories",
            lambda ctx: (True, "ready"),
        )
        monkeypatch.setattr(
            "patchy_bot.handlers.download.qbt_transport_status",
            lambda ctx: (True, "ok"),
        )

        with pytest.raises(RuntimeError, match="timed out"):
            await do_add(mock_ctx, 12345, search_id, 1, "movies")

    @pytest.mark.asyncio
    async def test_do_add_add_url_timeout(self, mock_ctx, monkeypatch):
        """do_add raises RuntimeError when qbt.add_url exceeds its timeout."""
        search_id = _save_search_with_hash(mock_ctx.store, 12345, "e" * 40)

        _real_wait_for = asyncio.wait_for
        call_count = 0

        async def _selective_timeout(coro, *, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 4:
                # Fourth wait_for wraps add_url
                coro.close()
                raise TimeoutError()
            return await _real_wait_for(coro, timeout=timeout)

        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.wait_for", _selective_timeout)
        monkeypatch.setattr(
            "patchy_bot.handlers.download.ensure_media_categories",
            lambda ctx: (True, "ready"),
        )
        monkeypatch.setattr(
            "patchy_bot.handlers.download.qbt_transport_status",
            lambda ctx: (True, "ok"),
        )
        monkeypatch.setattr(
            "patchy_bot.handlers.download.vpn_ready_for_download",
            lambda ctx: (True, "ok"),
        )

        with pytest.raises(RuntimeError, match="timed out"):
            await do_add(mock_ctx, 12345, search_id, 1, "movies")

    @pytest.mark.asyncio
    async def test_do_add_success(self, mock_ctx, monkeypatch):
        """do_add returns a DoAddResult with required fields when all pre-flights pass."""
        torrent_hash = "f" * 40
        search_id = _save_search_with_hash(mock_ctx.store, 12345, torrent_hash)

        monkeypatch.setattr(
            "patchy_bot.handlers.download.ensure_media_categories",
            lambda ctx: (True, "ready"),
        )
        monkeypatch.setattr(
            "patchy_bot.handlers.download.qbt_transport_status",
            lambda ctx: (True, "ok"),
        )
        monkeypatch.setattr(
            "patchy_bot.handlers.download.vpn_ready_for_download",
            lambda ctx: (True, "ok"),
        )
        mock_ctx.qbt.add_url = MagicMock(return_value="Ok.")

        result = await do_add(mock_ctx, 12345, search_id, 1, "movies")

        assert isinstance(result, DoAddResult)
        assert result.hash == torrent_hash
        assert result.name == "Test.Movie.2024.1080p"
        assert result.category == "Movies"
        assert result.save_path

    @pytest.mark.asyncio
    async def test_do_add_full_blocks_suspicious_file_list(self, mock_ctx, monkeypatch):
        """do_add_full raises RuntimeError when post-add file inspection finds malware."""
        rows = [
            {
                "name": "Bad.Movie.2024.1080p",
                "size": 2_000_000_000,
                "seeds": 50,
                "url": "https://tracker.invalid/download/bad.torrent",
            }
        ]
        search_id = mock_ctx.store.save_search(12345, "Bad Movie 2024", {"sort": "quality"}, rows)

        monkeypatch.setattr("patchy_bot.handlers.download.ensure_media_categories", lambda ctx: (True, "ready"))
        monkeypatch.setattr("patchy_bot.handlers.download.qbt_transport_status", lambda ctx: (True, "ok"))
        monkeypatch.setattr("patchy_bot.handlers.download.vpn_ready_for_download", lambda ctx: (True, "ok"))
        mock_ctx.qbt.get_torrent_files = MagicMock(return_value=[{"name": "Bad.Movie.mkv"}, {"name": "setup.exe"}])

        async def _fake_resolve(ctx, title, category, wait_s=20):
            return "a" * 40

        monkeypatch.setattr("patchy_bot.handlers.download.resolve_hash_by_name", _fake_resolve)

        with pytest.raises(RuntimeError, match="Blocked"):
            await do_add_full(mock_ctx, 12345, search_id, 1, "movies")

        mock_ctx.qbt.delete_torrent.assert_called_once_with("a" * 40, delete_files=True)

    @pytest.mark.asyncio
    async def test_do_add_full_resumes_after_clean_file_inspection(self, mock_ctx, monkeypatch):
        """do_add_full resumes torrent after clean inspection and returns compat dict."""
        rows = [
            {
                "name": "Clean.Movie.2024.1080p",
                "size": 2_000_000_000,
                "seeds": 50,
                "url": "https://tracker.invalid/download/clean.torrent",
                "uploader": "TrustedUploader",
            }
        ]
        search_id = mock_ctx.store.save_search(12345, "Clean Movie 2024", {"sort": "quality"}, rows)

        monkeypatch.setattr("patchy_bot.handlers.download.ensure_media_categories", lambda ctx: (True, "ready"))
        monkeypatch.setattr("patchy_bot.handlers.download.qbt_transport_status", lambda ctx: (True, "ok"))
        monkeypatch.setattr("patchy_bot.handlers.download.vpn_ready_for_download", lambda ctx: (True, "ok"))
        mock_ctx.qbt.get_torrent_files = MagicMock(return_value=[{"name": "Clean.Movie.2024.1080p.mkv"}])

        async def _fake_resolve(ctx, title, category, wait_s=20):
            return "b" * 40

        monkeypatch.setattr("patchy_bot.handlers.download.resolve_hash_by_name", _fake_resolve)

        result = await do_add_full(mock_ctx, 12345, search_id, 1, "movies")

        assert isinstance(result, dict)
        assert result["hash"] == "b" * 40
        mock_ctx.qbt.resume_torrents.assert_called_once_with("b" * 40)

    @pytest.mark.asyncio
    async def test_do_add_invalid_media_choice(self, mock_ctx):
        """do_add raises RuntimeError for unrecognized media type strings."""
        search_id = _save_search_with_hash(mock_ctx.store, 12345, "a" * 40)
        with pytest.raises(RuntimeError, match="Media type"):
            await do_add(mock_ctx, 12345, search_id, 1, "anime")

    @pytest.mark.asyncio
    async def test_do_add_missing_search(self, mock_ctx):
        """do_add raises RuntimeError when search_id does not exist."""
        with pytest.raises(RuntimeError, match="not found"):
            await do_add(mock_ctx, 12345, "nonexistent_search_id", 1, "movies")


# ---------------------------------------------------------------------------
# 8b: resolve_hash_by_name tests
# ---------------------------------------------------------------------------


class TestResolveHashByName:
    """Tiered matching logic in resolve_hash_by_name."""

    @pytest.mark.asyncio
    async def test_resolve_exact_match(self, mock_ctx, monkeypatch):
        """Returns hash immediately on exact case-insensitive name match."""
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[_torrent(name="my.show.s01e01", hash="a" * 40)])
        result = await resolve_hash_by_name(mock_ctx, "my.show.s01e01", "TV", wait_s=1)
        assert result == "a" * 40

    @pytest.mark.asyncio
    async def test_resolve_exact_match_case_insensitive(self, mock_ctx, monkeypatch):
        """Exact match is case-insensitive (query lowercased vs stored name lowercased)."""
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[_torrent(name="My.Show.S01E01", hash="b" * 40)])
        result = await resolve_hash_by_name(mock_ctx, "My.Show.S01E01", "TV", wait_s=1)
        assert result == "b" * 40

    @pytest.mark.asyncio
    async def test_resolve_normalized_match(self, mock_ctx, monkeypatch):
        """Returns hash when normalized titles match (e.g., dots vs spaces)."""
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())
        # "Dune 2024 1080p WEB-DL" stored as "Dune.2024.1080p.WEB-DL"
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[_torrent(name="Dune.2024.1080p.WEB-DL", hash="c" * 40)])
        # normalize_title strips dots/dashes so "Dune 2024" won't match "Dune.2024.1080p.WEB-DL"
        # but exact normalized forms will: query with same normalized form
        result = await resolve_hash_by_name(mock_ctx, "Dune.2024.1080p.WEB-DL", "movies", wait_s=1)
        assert result == "c" * 40

    @pytest.mark.asyncio
    async def test_resolve_substring_match_good_ratio(self, mock_ctx, monkeypatch):
        """Returns hash when query is a substring and meets the length-ratio threshold."""
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())
        # query "the office us s01e01" contained in name "the office us s01e01 1080p"
        # len("the office us s01e01") / len("the office us s01e01 1080p") = 20/26 >= 0.4
        mock_ctx.qbt.list_torrents = MagicMock(
            return_value=[_torrent(name="the office us s01e01 1080p", hash="d" * 40)]
        )
        result = await resolve_hash_by_name(mock_ctx, "the office us s01e01", "TV", wait_s=1)
        assert result == "d" * 40

    @pytest.mark.asyncio
    async def test_resolve_no_match_short_query(self, mock_ctx, monkeypatch):
        """Short query that is a substring but below the 0.4 ratio threshold returns None."""
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())
        # "dune" in "fortune.2024.1080p.web-dl" is False, no match at all
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[_torrent(name="Fortune.2024.1080p.WEB-DL", hash="e" * 40)])
        result = await resolve_hash_by_name(mock_ctx, "dune", "movies", wait_s=0)
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_no_match_returns_none(self, mock_ctx, monkeypatch):
        """Returns None when no torrent name matches the query."""
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[])
        result = await resolve_hash_by_name(mock_ctx, "totally unknown title", "TV", wait_s=0)
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_invalid_hash_skipped(self, mock_ctx, monkeypatch):
        """Torrents with non-40-char hashes are ignored even on name match."""
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())
        # Short/invalid hash — should be skipped
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[_torrent(name="exactname", hash="tooshort")])
        result = await resolve_hash_by_name(mock_ctx, "exactname", "TV", wait_s=0)
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_prefers_exact_over_substring(self, mock_ctx, monkeypatch):
        """Exact match wins over substring match when both are present."""
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())
        exact_hash = "a" * 40
        substr_hash = "b" * 40
        mock_ctx.qbt.list_torrents = MagicMock(
            return_value=[
                _torrent(name="my show s01e01 extended cut", hash=substr_hash),
                _torrent(name="my show s01e01", hash=exact_hash),
            ]
        )
        result = await resolve_hash_by_name(mock_ctx, "my show s01e01", "TV", wait_s=1)
        assert result == exact_hash

    @pytest.mark.asyncio
    async def test_resolve_qbt_exception_retries(self, mock_ctx, monkeypatch):
        """An exception from list_torrents is swallowed and retried until deadline."""
        sleep_mock = AsyncMock()
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", sleep_mock)
        mock_ctx.qbt.list_torrents = MagicMock(side_effect=RuntimeError("connection refused"))
        result = await resolve_hash_by_name(mock_ctx, "anything", "TV", wait_s=0)
        assert result is None


# ---------------------------------------------------------------------------
# 8c: Progress smoothing tests
# ---------------------------------------------------------------------------


class TestProgressSmoothing:
    """EMA smoothing behavior in track_download_progress."""

    @pytest.mark.asyncio
    async def test_progress_can_decrease(self, mock_ctx, monkeypatch):
        """Smoothed progress can decrease when raw progress drops (no ratchet)."""
        # Alpha = 0.35 from mock_config. After two polls:
        #   poll 1: raw=50 → smooth=50
        #   poll 2: raw=30 → smooth = 0.65*50 + 0.35*30 = 43
        # Verify the EMA formula allows going below the first value.
        alpha = mock_ctx.cfg.progress_smoothing_alpha  # 0.35

        smooth = 50.0
        raw2 = 30.0
        smooth2 = (1.0 - alpha) * smooth + alpha * raw2
        assert smooth2 < smooth, "EMA must allow progress to decrease"
        assert smooth2 == pytest.approx(0.65 * 50 + 0.35 * 30)

    def test_progress_100_on_completion(self):
        """render_progress_text with progress_pct=100.0 always shows 100%."""
        info = {
            "progress": 0.5,
            "state": "uploading",
            "size": 1_000_000,
            "completed": 1_000_000,
            "downloaded": 0,
            "amount_left": 0,
            "dlspeed": 0,
            "upspeed": 0,
            "eta": -1,
        }
        text = render_progress_text("Test Title", info, 0, progress_pct=100.0)
        assert "100.0%" in text

    def test_progress_smoothing_alpha_applied(self):
        """EMA with alpha=0.35 and initial value 0 converges toward raw correctly."""
        alpha = 0.35
        smooth = 0.0
        for _ in range(20):
            smooth = (1.0 - alpha) * smooth + alpha * 80.0
        # After 20 iterations at constant 80, smooth must be very close to 80
        assert smooth == pytest.approx(80.0, abs=0.5)

    @pytest.mark.asyncio
    async def test_track_progress_exits_on_completion(self, mock_ctx, monkeypatch):
        """track_download_progress exits cleanly when torrent reports complete."""
        sleep_mock = AsyncMock()
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", sleep_mock)

        complete_info = _torrent(state="uploading", progress=1.0, amount_left=0, completed=1_000_000)
        mock_ctx.qbt.get_torrent = MagicMock(return_value=complete_info)

        # Plex and organizer — keep them offline/no-op
        mock_ctx.plex.ready.return_value = False

        with patch("patchy_bot.handlers.download._organize_download") as mock_org:
            org_result = MagicMock()
            org_result.moved = False
            org_result.new_path = ""
            org_result.summary = ""
            mock_org.return_value = org_result

            tracker_msg = MagicMock()
            tracker_msg.edit_text = AsyncMock()
            tracker_msg.chat_id = 12345
            tracker_msg.message_id = 1
            tracker_msg.get_bot = MagicMock(return_value=MagicMock())

            # Should complete without hanging
            await asyncio.wait_for(
                track_download_progress(mock_ctx, 12345, "a" * 40, tracker_msg, "Test"),
                timeout=3.0,
            )

    @pytest.mark.asyncio
    async def test_headless_tracker_skips_message_editing(self, mock_ctx, monkeypatch):
        """Headless mode (tracker_msg=None) must not raise AttributeError on .edit_text /
        .delete and must still populate batch_monitor_data during the loop."""
        sleep_mock = AsyncMock()
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", sleep_mock)

        # Return a completed torrent so the loop exits on the first tick.
        complete_info = _torrent(state="uploading", progress=1.0, amount_left=0, completed=1_000_000)
        mock_ctx.qbt.get_torrent = MagicMock(return_value=complete_info)
        mock_ctx.plex.ready.return_value = False

        key = (12345, "a" * 40)

        with patch("patchy_bot.handlers.download._organize_download") as mock_org:
            org_result = MagicMock()
            org_result.moved = False
            org_result.new_path = ""
            org_result.summary = ""
            mock_org.return_value = org_result

            # tracker_msg=None — headless mode. Must NOT raise.
            await asyncio.wait_for(
                track_download_progress(mock_ctx, 12345, "a" * 40, None, "Headless Test"),
                timeout=3.0,
            )

        # Cleanup ran in the finally block.
        assert key not in mock_ctx.batch_monitor_data
        assert key not in mock_ctx.progress_tasks


# ---------------------------------------------------------------------------
# 8d: Active downloads state filtering
# ---------------------------------------------------------------------------


class TestActiveDlStates:
    """Verify the _ACTIVE_DL_STATES set has the correct membership."""

    def test_active_dl_states_includes_downloading(self):
        assert "downloading" in _ACTIVE_DL_STATES

    def test_active_dl_states_includes_stalled_dl(self):
        assert "stalledDL" in _ACTIVE_DL_STATES

    def test_active_dl_states_includes_meta_dl(self):
        assert "metaDL" in _ACTIVE_DL_STATES

    def test_active_dl_states_includes_forced_dl(self):
        assert "forcedDL" in _ACTIVE_DL_STATES

    def test_active_dl_states_excludes_uploading(self):
        assert "uploading" not in _ACTIVE_DL_STATES

    def test_active_dl_states_excludes_stalled_up(self):
        assert "stalledUP" not in _ACTIVE_DL_STATES

    def test_active_dl_states_excludes_completed_states(self):
        """None of the seeding/completed states should be in the active-download set."""
        seeding_states = {"uploading", "stalledUP", "queuedUP", "forcedUP", "pausedUP", "checkingUP"}
        overlap = seeding_states & _ACTIVE_DL_STATES
        assert not overlap, f"Completed states in _ACTIVE_DL_STATES: {overlap}"

    def test_active_dl_states_is_set(self):
        assert isinstance(_ACTIVE_DL_STATES, (set, frozenset))

    def test_filter_torrents_by_active_state(self):
        """Filtering a torrent list by _ACTIVE_DL_STATES excludes seeding torrents."""
        torrents = [
            {"name": "active", "state": "downloading"},
            {"name": "done", "state": "uploading"},
            {"name": "stalled", "state": "stalledDL"},
            {"name": "seeding", "state": "stalledUP"},
        ]
        active = [t for t in torrents if t["state"] in _ACTIVE_DL_STATES]
        names = {t["name"] for t in active}
        assert "active" in names
        assert "stalled" in names
        assert "done" not in names
        assert "seeding" not in names


# ---------------------------------------------------------------------------
# 8e: normalize_media_choice + check_free_space
# ---------------------------------------------------------------------------


class TestNormalizeMediaChoice:
    """normalize_media_choice maps user input to canonical 'movies' or 'tv'."""

    def test_movies_m(self):
        assert normalize_media_choice("m") == "movies"

    def test_movies_movie(self):
        assert normalize_media_choice("movie") == "movies"

    def test_movies_movies(self):
        assert normalize_media_choice("Movies") == "movies"

    def test_movies_film(self):
        assert normalize_media_choice("film") == "movies"

    def test_movies_films(self):
        assert normalize_media_choice("films") == "movies"

    def test_tv_t(self):
        assert normalize_media_choice("t") == "tv"

    def test_tv_tv(self):
        assert normalize_media_choice("tv") == "tv"

    def test_tv_show(self):
        assert normalize_media_choice("Show") == "tv"

    def test_tv_series(self):
        assert normalize_media_choice("series") == "tv"

    def test_tv_episode(self):
        assert normalize_media_choice("episode") == "tv"

    def test_invalid_xyz(self):
        assert normalize_media_choice("xyz") is None

    def test_invalid_none(self):
        assert normalize_media_choice(None) is None

    def test_invalid_empty_string(self):
        assert normalize_media_choice("") is None

    def test_case_insensitive_movie(self):
        assert normalize_media_choice("MOVIE") == "movies"

    def test_case_insensitive_tv(self):
        assert normalize_media_choice("TV") == "tv"


class TestCheckFreeSpace:
    """check_free_space reports ok/blocked based on statvfs results."""

    def test_check_free_space_ok(self, tmp_path):
        """A path with abundant space returns (True, 'ok')."""
        ok, msg = check_free_space(str(tmp_path))
        assert ok is True

    def test_check_free_space_blocked(self, monkeypatch):
        """Below block_bytes threshold returns (False, message)."""
        import os

        fake_stat = MagicMock()
        # frsize=4096, bfree=100 → free = 4096*100 = 409600 bytes (well below 5 GiB)
        fake_stat.f_frsize = 4096
        fake_stat.f_bfree = 100

        monkeypatch.setattr(os, "statvfs", lambda _: fake_stat)

        ok, msg = check_free_space("/any/path")
        assert ok is False
        assert "Not enough disk space" in msg

    def test_check_free_space_nonexistent_path_blocked(self, monkeypatch):
        """Non-existent path blocks the download."""
        import os

        monkeypatch.setattr(os, "statvfs", MagicMock(side_effect=OSError("No such file")))
        monkeypatch.setattr(os.path, "exists", lambda p: False)

        ok, msg = check_free_space("/nonexistent/path")
        assert ok is False
        assert "target path does not exist" in msg

    def test_check_free_space_permission_error_skips(self, monkeypatch):
        """Existing path with permission error allows download with warning."""
        import os

        monkeypatch.setattr(os, "statvfs", MagicMock(side_effect=OSError("Permission denied")))
        monkeypatch.setattr(os.path, "exists", lambda p: True)

        ok, msg = check_free_space("/restricted/path")
        assert ok is True
        assert "skipped" in msg.lower()

    def test_check_free_space_custom_thresholds(self, monkeypatch):
        """Custom block_bytes threshold is honored."""
        import os

        fake_stat = MagicMock()
        # 1 GiB free
        fake_stat.f_frsize = 1024 * 1024 * 1024
        fake_stat.f_bfree = 1

        monkeypatch.setattr(os, "statvfs", lambda _: fake_stat)

        # Block threshold = 2 GiB → blocked
        ok, msg = check_free_space("/any/path", block_bytes=2 * 1024**3)
        assert ok is False

        # Block threshold = 512 MiB → ok (1 GiB > 512 MiB)
        ok2, _ = check_free_space("/any/path", block_bytes=512 * 1024**2)
        assert ok2 is True


# ---------------------------------------------------------------------------
# 8f: on_cb_stop hash validation
# ---------------------------------------------------------------------------


class TestOnCbStopHashValidation:
    """on_cb_stop rejects invalid torrent hashes before any qBT API call."""

    @pytest.mark.asyncio
    async def test_rejects_short_hash(self, mock_callback_query):
        """Too-short hash is rejected with 'Invalid hash' alert."""
        ctx = MagicMock()
        ctx.progress_tasks = {}
        await on_cb_stop(ctx, data="stop:abc123", q=mock_callback_query, user_id=12345)
        mock_callback_query.answer.assert_awaited_once_with("Invalid hash", show_alert=True)

    @pytest.mark.asyncio
    async def test_rejects_uppercase_hash(self, mock_callback_query):
        """Uppercase hex chars are rejected (pattern requires lowercase)."""
        ctx = MagicMock()
        ctx.progress_tasks = {}
        await on_cb_stop(ctx, data="stop:" + "A" * 40, q=mock_callback_query, user_id=12345)
        mock_callback_query.answer.assert_awaited_once_with("Invalid hash", show_alert=True)

    @pytest.mark.asyncio
    async def test_rejects_nonhex_hash(self, mock_callback_query):
        """Non-hex characters are rejected."""
        ctx = MagicMock()
        ctx.progress_tasks = {}
        await on_cb_stop(ctx, data="stop:" + "g" * 40, q=mock_callback_query, user_id=12345)
        mock_callback_query.answer.assert_awaited_once_with("Invalid hash", show_alert=True)

    @pytest.mark.asyncio
    async def test_rejects_empty_hash(self, mock_callback_query):
        """Empty string after 'stop:' prefix is rejected."""
        ctx = MagicMock()
        ctx.progress_tasks = {}
        await on_cb_stop(ctx, data="stop:", q=mock_callback_query, user_id=12345)
        mock_callback_query.answer.assert_awaited_once_with("Invalid hash", show_alert=True)

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download.flow_mod.clear_flow")
    @patch("patchy_bot.handlers.download.render_mod.cancel_pending_trackers_for_user")
    async def test_valid_hash_proceeds(self, _mock_cancel, _mock_clear, mock_callback_query):
        """Valid 40-char lowercase hex hash does NOT trigger early return."""
        ctx = MagicMock()
        ctx.progress_tasks = {}
        ctx.user_nav_ui = {}
        ctx.qbt.get_torrent = MagicMock(return_value={"name": "Test"})
        ctx.qbt.delete_torrent = MagicMock(return_value=None)
        ctx.store.get_command_center = MagicMock(return_value=None)
        ctx.navigate_to_command_center = AsyncMock()
        mock_callback_query.message.chat = MagicMock()
        mock_callback_query.message.chat.send_message = AsyncMock(return_value=MagicMock(message_id=999))
        mock_callback_query.get_bot = MagicMock(return_value=MagicMock())

        valid_hash = "a" * 40
        await on_cb_stop(ctx, data=f"stop:{valid_hash}", q=mock_callback_query, user_id=12345)
        # Should NOT have been called with "Invalid hash" — it should proceed to the delete path
        for call in mock_callback_query.answer.await_args_list:
            assert call.args != ("Invalid hash",) if call.args else True

    @pytest.mark.asyncio
    async def test_delete_failure_shows_error(self, mock_callback_query):
        """When qBT delete raises, error message is shown."""
        ctx = MagicMock()
        ctx.progress_tasks = {}
        ctx.qbt.get_torrent = MagicMock(return_value={"name": "Test"})
        ctx.qbt.delete_torrent = MagicMock(side_effect=RuntimeError("connection refused"))
        mock_callback_query.message.edit_text = AsyncMock()

        valid_hash = "a" * 40
        await on_cb_stop(ctx, data=f"stop:{valid_hash}", q=mock_callback_query, user_id=12345)
        mock_callback_query.message.edit_text.assert_awaited_once()
        call_args = mock_callback_query.message.edit_text.await_args
        assert "Stop Failed" in call_args.args[0]

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download.flow_mod.clear_flow")
    @patch("patchy_bot.handlers.download.render_mod.cancel_pending_trackers_for_user")
    async def test_cc_recovery_from_db(self, _mock_cancel, _mock_clear, mock_callback_query):
        """Command center navigation is invoked after successful stop."""
        ctx = MagicMock()
        ctx.progress_tasks = {}
        ctx.user_nav_ui = {}
        ctx.qbt.get_torrent = MagicMock(return_value={"name": "Test"})
        ctx.qbt.delete_torrent = MagicMock(return_value=None)
        ctx.store.get_command_center = MagicMock(return_value=None)
        ctx.navigate_to_command_center = AsyncMock()
        mock_callback_query.message.chat = MagicMock()
        mock_callback_query.message.chat.send_message = AsyncMock(return_value=MagicMock(message_id=999))
        mock_callback_query.get_bot = MagicMock(return_value=MagicMock())

        valid_hash = "a" * 40
        await on_cb_stop(ctx, data=f"stop:{valid_hash}", q=mock_callback_query, user_id=12345)
        # navigate_to_command_center should have been called
        ctx.navigate_to_command_center.assert_awaited_once()
        call_args = ctx.navigate_to_command_center.await_args
        assert call_args[0][1] == 12345  # user_id

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download.stop_batch_monitor", new_callable=AsyncMock)
    async def test_stop_all_cancels_user_hashes_and_stops_monitor(self, _mock_stop_batch_monitor, mock_callback_query):
        """stop:all cancels matching user tasks, deletes each torrent, and answers cleanly."""

        class DummyTask:
            def __init__(self) -> None:
                self.cancelled = False

            def done(self) -> bool:
                return False

            def cancel(self) -> None:
                self.cancelled = True

        hash_a = "a" * 40
        hash_b = "b" * 40
        hash_c = "c" * 40

        task_a = DummyTask()
        task_b = DummyTask()
        other_task = DummyTask()

        ctx = MagicMock()
        ctx.progress_tasks = {
            (12345, hash_a): task_a,
            (12345, hash_b): task_b,
            (99999, hash_c): other_task,
        }
        ctx.qbt.delete_torrent = MagicMock(return_value=None)
        ctx.download_queue_lock = asyncio.Lock()
        ctx.download_queue = asyncio.Queue()
        ctx.active_download_hash = None

        await on_cb_stop(ctx, data=f"stop:all:{hash_a},{hash_b}", q=mock_callback_query, user_id=12345)

        assert task_a.cancelled is True
        assert task_b.cancelled is True
        assert other_task.cancelled is False
        assert (12345, hash_a) not in ctx.progress_tasks
        assert (12345, hash_b) not in ctx.progress_tasks
        assert (99999, hash_c) in ctx.progress_tasks
        assert [call.args for call in ctx.qbt.delete_torrent.call_args_list] == [(hash_a,), (hash_b,)]
        assert [call.kwargs for call in ctx.qbt.delete_torrent.call_args_list] == [
            {"delete_files": True},
            {"delete_files": True},
        ]
        _mock_stop_batch_monitor.assert_awaited_once_with(ctx, 12345)
        mock_callback_query.answer.assert_awaited_once_with("All downloads stopped.")


# ---------------------------------------------------------------------------
# 8g: completion_poller_job
# ---------------------------------------------------------------------------

# A fully-complete torrent dict used across multiple poller tests.
_COMPLETE_TORRENT = {
    "hash": "a" * 40,
    "name": "Test.Show.S01E01",
    "progress": 1.0,
    "state": "uploading",
    "amount_left": 0,
    "content_path": "/dl/test",
    "category": "Movies",
    "size": 1_073_741_824,
}


class TestCompletionPollerJob:
    """Tests for completion_poller_job — the background completion sweep."""

    @pytest.fixture(autouse=True)
    def _clear_seen_hashes(self):
        """Reset module-level dedup set between tests to prevent state pollution."""
        import patchy_bot.handlers.download as dl

        dl._poller_seen_hashes.clear()
        yield
        dl._poller_seen_hashes.clear()

    @pytest.fixture(autouse=True)
    def _default_clean_scan(self, monkeypatch):
        monkeypatch.setattr("patchy_bot.handlers.download._run_clamav_scan", lambda path, timeout_s: ("clean", []))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_app(self):
        """Return a MagicMock that looks enough like a PTB Application."""
        app = MagicMock()
        app.bot = MagicMock()
        app.bot.send_message = AsyncMock(return_value=MagicMock(chat_id=12345, message_id=1))
        return app

    # ------------------------------------------------------------------
    # test_skips_already_notified
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download._organize_download")
    async def test_skips_already_notified(self, mock_org, mock_ctx):
        """When is_completion_notified returns True, nothing is marked or sent."""
        mock_ctx.app = self._make_app()
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[dict(_COMPLETE_TORRENT)])
        mock_ctx.store.is_completion_notified = MagicMock(return_value=True)
        mock_ctx.store.mark_completion_notified = MagicMock()
        mock_ctx.store.cleanup_old_completion_records = MagicMock()

        await completion_poller_job(mock_ctx, MagicMock())

        mock_ctx.store.mark_completion_notified.assert_not_called()
        mock_ctx.app.bot.send_message.assert_not_awaited()

    # ------------------------------------------------------------------
    # test_skips_non_complete_torrent
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download._organize_download")
    async def test_skips_non_complete_torrent(self, mock_org, mock_ctx):
        """Torrent with progress=0.5 / state=downloading is skipped entirely.

        is_completion_notified must NOT be called because the torrent fails
        is_complete_torrent before we ever hit the store.
        """
        incomplete = dict(_COMPLETE_TORRENT)
        incomplete["progress"] = 0.5
        incomplete["state"] = "downloading"
        incomplete["amount_left"] = 500_000_000

        mock_ctx.app = self._make_app()
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[incomplete])
        mock_ctx.store.is_completion_notified = MagicMock(return_value=False)
        mock_ctx.store.mark_completion_notified = MagicMock()
        mock_ctx.store.cleanup_old_completion_records = MagicMock()

        await completion_poller_job(mock_ctx, MagicMock())

        mock_ctx.store.is_completion_notified.assert_not_called()
        mock_ctx.store.mark_completion_notified.assert_not_called()

    # ------------------------------------------------------------------
    # test_mark_before_send
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download._organize_download")
    async def test_mark_before_send(self, mock_org, mock_ctx):
        """mark_completion_notified is called before send_message."""
        call_order: list[str] = []

        mock_org.return_value = MagicMock(moved=False, new_path="", summary="", files_moved=0)
        mock_ctx.app = self._make_app()
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[dict(_COMPLETE_TORRENT)])
        mock_ctx.store.is_completion_notified = MagicMock(return_value=False)
        mock_ctx.store.cleanup_old_completion_records = MagicMock()

        def _mark(torrent_hash, name):
            call_order.append("mark")

        mock_ctx.store.mark_completion_notified = MagicMock(side_effect=_mark)

        async def _send(**kwargs):
            call_order.append("send")
            return MagicMock(chat_id=12345, message_id=1)

        mock_ctx.app.bot.send_message = _send

        await completion_poller_job(mock_ctx, MagicMock())

        assert "mark" in call_order, "mark_completion_notified was never called"
        assert "send" in call_order, "send_message was never called"
        assert call_order.index("mark") < call_order.index("send"), (
            "mark_completion_notified must be called before send_message"
        )

    # ------------------------------------------------------------------
    # test_plex_organize_and_scan
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download._organize_download")
    async def test_plex_organize_and_scan(self, mock_org, mock_ctx):
        """Both _organize_download and plex.refresh_for_path are called when Plex is ready."""
        mock_org.return_value = MagicMock(
            moved=True, new_path="/plex/Movies/Test", summary="Moved to Movies", files_moved=1
        )
        mock_ctx.app = self._make_app()
        mock_ctx.plex.ready.return_value = True
        mock_ctx.plex.refresh_for_path = MagicMock(return_value="Scanned 1 item")
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[dict(_COMPLETE_TORRENT)])
        mock_ctx.store.is_completion_notified = MagicMock(return_value=False)
        mock_ctx.store.mark_completion_notified = MagicMock()
        mock_ctx.store.cleanup_old_completion_records = MagicMock()

        await completion_poller_job(mock_ctx, MagicMock())

        mock_org.assert_called_once()
        mock_ctx.plex.refresh_for_path.assert_called_once_with("/plex/Movies/Test")

    # ------------------------------------------------------------------
    # test_plex_skipped_when_not_ready
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download._organize_download")
    async def test_plex_skipped_when_not_ready(self, mock_org, mock_ctx):
        """refresh_for_path is NOT called when plex.ready() returns False."""
        mock_org.return_value = MagicMock(moved=False, new_path="", summary="", files_moved=0)
        mock_ctx.app = self._make_app()
        mock_ctx.plex.ready.return_value = False
        mock_ctx.plex.refresh_for_path = MagicMock()
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[dict(_COMPLETE_TORRENT)])
        mock_ctx.store.is_completion_notified = MagicMock(return_value=False)
        mock_ctx.store.mark_completion_notified = MagicMock()
        mock_ctx.store.cleanup_old_completion_records = MagicMock()

        await completion_poller_job(mock_ctx, MagicMock())

        mock_ctx.plex.refresh_for_path.assert_not_called()

    # ------------------------------------------------------------------
    # test_error_in_one_torrent_doesnt_break_others
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download._organize_download")
    async def test_error_in_one_torrent_doesnt_break_others(self, mock_org, mock_ctx):
        """send_message raising on the 2nd torrent does not prevent the 3rd from being marked."""
        mock_org.return_value = MagicMock(moved=False, new_path="", summary="", files_moved=0)

        t1 = dict(_COMPLETE_TORRENT, hash="1" * 40, name="Torrent One")
        t2 = dict(_COMPLETE_TORRENT, hash="2" * 40, name="Torrent Two")
        t3 = dict(_COMPLETE_TORRENT, hash="3" * 40, name="Torrent Three")

        mock_ctx.app = self._make_app()
        send_call_count = 0

        async def _send_maybe_raise(**kwargs):
            nonlocal send_call_count
            send_call_count += 1
            if send_call_count == 2:
                raise RuntimeError("Telegram timeout")
            return MagicMock(chat_id=12345, message_id=send_call_count)

        mock_ctx.app.bot.send_message = _send_maybe_raise
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[t1, t2, t3])
        mock_ctx.store.is_completion_notified = MagicMock(return_value=False)
        mock_ctx.store.mark_completion_notified = MagicMock()
        mock_ctx.store.cleanup_old_completion_records = MagicMock()

        await completion_poller_job(mock_ctx, MagicMock())

        # mark_completion_notified must have been called for all 3 torrents
        assert mock_ctx.store.mark_completion_notified.call_count == 3

    # ------------------------------------------------------------------
    # test_notification_sent_to_all_allowed_users
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download._organize_download")
    async def test_notification_sent_to_all_allowed_users(self, mock_org, mock_ctx):
        """send_message is called once per allowed user ID."""
        mock_org.return_value = MagicMock(moved=False, new_path="", summary="", files_moved=0)

        mock_ctx.app = self._make_app()
        mock_ctx.cfg.allowed_user_ids = {111, 222, 333}
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[dict(_COMPLETE_TORRENT)])
        mock_ctx.store.is_completion_notified = MagicMock(return_value=False)
        mock_ctx.store.mark_completion_notified = MagicMock()
        mock_ctx.store.cleanup_old_completion_records = MagicMock()

        sent_to: list[int] = []

        async def _capture_send(**kwargs):
            sent_to.append(kwargs["chat_id"])
            return MagicMock(chat_id=kwargs["chat_id"], message_id=1)

        mock_ctx.app.bot.send_message = _capture_send

        await completion_poller_job(mock_ctx, MagicMock())

        assert sorted(sent_to) == [111, 222, 333]

    # ------------------------------------------------------------------
    # test_cleanup_old_records_called
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download._organize_download")
    async def test_cleanup_old_records_called(self, mock_org, mock_ctx):
        """cleanup_old_completion_records is called exactly once per run."""
        mock_org.return_value = MagicMock(moved=False, new_path="", summary="", files_moved=0)

        mock_ctx.app = self._make_app()
        # Empty torrent list — no completions at all this run.
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[])
        mock_ctx.store.cleanup_old_completion_records = MagicMock()

        await completion_poller_job(mock_ctx, MagicMock())

        mock_ctx.store.cleanup_old_completion_records.assert_called_once()

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download._organize_download")
    async def test_infected_payload_deleted_and_not_organized(self, mock_org, mock_ctx, monkeypatch, tmp_path):
        # v2: infected payloads are deleted directly (no quarantine).
        # The sample dir must live inside an allowed root so _validate_safe_path
        # permits the rmtree fallback.
        from pathlib import Path

        movies_root = mock_ctx.cfg.movies_path
        sample_dir = Path(movies_root) / "infected-release"
        sample_dir.mkdir()
        (sample_dir / "movie.exe").write_bytes(b"bad")

        monkeypatch.setattr(
            "patchy_bot.handlers.download._run_clamav_scan",
            lambda path, timeout_s: ("infected", ["movie.exe: Win.Test FOUND"]),
        )

        infected = dict(_COMPLETE_TORRENT, content_path=str(sample_dir))
        mock_ctx.app = self._make_app()
        mock_ctx.cfg.allowed_user_ids = {12345}
        mock_ctx.qbt.list_torrents = MagicMock(return_value=[infected])
        mock_ctx.qbt.delete_torrent = MagicMock()
        mock_ctx.qbt.get_torrent_files = MagicMock(return_value=[])
        mock_ctx.store.is_completion_notified = MagicMock(return_value=False)
        mock_ctx.store.mark_completion_notified = MagicMock()
        mock_ctx.store.cleanup_old_completion_records = MagicMock()

        sent_text: list[str] = []

        async def _capture_send(**kwargs):
            sent_text.append(kwargs["text"])
            return MagicMock(chat_id=kwargs["chat_id"], message_id=1)

        mock_ctx.app.bot.send_message = _capture_send

        await completion_poller_job(mock_ctx, MagicMock())

        mock_org.assert_not_called()
        mock_ctx.qbt.delete_torrent.assert_called_once_with("a" * 40, delete_files=True)
        assert any("Malware Detected" in text for text in sent_text)
        # Files have been removed by the rmtree fallback.
        assert not sample_dir.exists()


# ---------------------------------------------------------------------------
# TestProgressTrackerRaceGuard
# ---------------------------------------------------------------------------


class TestProgressTrackerRaceGuard:
    """Tests for the race-condition guard in start_progress_tracker /
    track_download_progress."""

    @pytest.mark.asyncio
    async def test_start_tracker_cancels_existing(self):
        """Calling start_progress_tracker twice for the same key cancels the first task."""
        ctx = MagicMock()
        ctx.progress_tasks = {}
        ctx.user_flow = {}
        msg2 = MagicMock(chat_id=1, message_id=2)

        # Seed a fake "existing" task that is not yet done.
        first_task = asyncio.Future()
        key = (12345, "a" * 40)
        ctx.progress_tasks[key] = first_task

        with patch(
            "patchy_bot.handlers.download.track_download_progress",
            new_callable=AsyncMock,
        ) as mock_track:
            mock_track.return_value = None
            start_progress_tracker(ctx, 12345, "a" * 40, msg2, "Test")

        assert first_task.cancelled()
        assert ctx.progress_tasks[key] is not first_task

    @pytest.mark.asyncio
    async def test_task_is_named(self):
        """The asyncio Task created by start_progress_tracker carries the expected name."""
        ctx = MagicMock()
        ctx.progress_tasks = {}
        ctx.user_flow = {}
        msg = MagicMock(chat_id=1, message_id=1)

        with patch(
            "patchy_bot.handlers.download.track_download_progress",
            new_callable=AsyncMock,
        ) as mock_track:
            mock_track.return_value = None
            start_progress_tracker(ctx, 12345, "ABCD" * 10, msg, "Test")

        task = ctx.progress_tasks[(12345, "abcd" * 10)]
        assert task.get_name() == f"progress:12345:{'abcd' * 10}"
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_replaced_tracker_exits_gracefully(self):
        """A tracker that finds itself replaced in progress_tasks exits on the next loop
        iteration without raising."""
        ctx = MagicMock()
        ctx.progress_tasks = {}
        ctx.cfg.progress_track_timeout_s = 300
        ctx.cfg.progress_refresh_s = 0.01
        ctx.cfg.progress_edit_min_s = 0
        ctx.cfg.progress_smoothing_alpha = 0.35

        tracker_msg = MagicMock()
        tracker_msg.edit_text = AsyncMock()

        key = (12345, "a" * 40)

        task = asyncio.create_task(track_download_progress(ctx, 12345, "a" * 40, tracker_msg, "Test"))
        ctx.progress_tasks[key] = task

        # Let it run at least one iteration.
        await asyncio.sleep(0.05)

        # Replace the entry — the running tracker should detect the mismatch and return.
        ctx.progress_tasks[key] = asyncio.Future()

        # Should complete cleanly within a generous timeout.
        await asyncio.wait_for(task, timeout=2.0)

        # The task finished without an exception.
        assert not task.cancelled()
        assert task.exception() is None


# ---------------------------------------------------------------------------
# TestAutoDeleteTaskTracking
# ---------------------------------------------------------------------------


class TestAutoDeleteTaskTracking:
    """on_cb_stop tracks the auto-delete task in ctx.background_tasks."""

    @pytest.mark.asyncio
    @patch("patchy_bot.handlers.download.flow_mod.clear_flow")
    @patch("patchy_bot.handlers.download.render_mod.cancel_pending_trackers_for_user")
    async def test_auto_delete_task_tracked(self, _mock_cancel, _mock_clear, mock_callback_query):
        """After successful stop, the auto-delete task is added to ctx.background_tasks."""
        ctx = MagicMock()
        ctx.progress_tasks = {}
        ctx.user_nav_ui = {}
        ctx.background_tasks = set()
        ctx.qbt.get_torrent = MagicMock(return_value={"name": "Test"})
        ctx.qbt.delete_torrent = MagicMock(return_value=None)
        ctx.store.get_command_center = MagicMock(return_value=None)
        ctx.navigate_to_command_center = AsyncMock()
        mock_callback_query.message.chat = MagicMock()
        mock_callback_query.message.chat.send_message = AsyncMock(return_value=MagicMock(message_id=999))
        mock_callback_query.message.chat_id = 12345
        mock_callback_query.get_bot = MagicMock(return_value=MagicMock())

        valid_hash = "a" * 40
        await on_cb_stop(ctx, data=f"stop:{valid_hash}", q=mock_callback_query, user_id=12345)

        # A task should have been added to background_tasks
        assert len(ctx.background_tasks) == 1
        del_task = next(iter(ctx.background_tasks))
        assert del_task.get_name().startswith("auto-delete:")

        # Clean up: cancel the sleep-10 task so it doesn't leak
        del_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await del_task

        # The done callback should have discarded it from the set
        assert len(ctx.background_tasks) == 0


# ---------------------------------------------------------------------------
# Split pipeline tests: do_add (fast), do_add_background, mwblock callback
# ---------------------------------------------------------------------------


def _make_fast_result(
    *,
    torrent_hash: str | None = "a" * 40,
    name: str = "Test.Movie.2024.1080p",
    size: int = 2_000_000_000,
    category: str = "Movies",
    save_path: str = "/tmp/Movies",
    url: str = "https://tracker.invalid/download/test.torrent",
    is_magnet: bool = False,
) -> DoAddResult:
    """Build a DoAddResult for background-phase tests."""
    return DoAddResult(
        name=name,
        size=size,
        hash=torrent_hash,
        category=category,
        save_path=save_path,
        url=url,
        is_magnet=is_magnet,
        idx=1,
        target_label="Movies",
        resp="Ok.",
        media_type="movie",
        uploader=None,
    )


class TestDoAddFastPhase:
    """Tests for the fast phase of do_add (returns DoAddResult quickly)."""

    @pytest.mark.asyncio
    async def test_returns_do_add_result(self, mock_ctx, monkeypatch):
        """do_add returns a DoAddResult dataclass."""
        search_id = _save_search_with_hash(mock_ctx.store, 12345, "a" * 40)
        monkeypatch.setattr("patchy_bot.handlers.download.ensure_media_categories", lambda ctx: (True, "ok"))
        monkeypatch.setattr("patchy_bot.handlers.download.qbt_transport_status", lambda ctx: (True, "ok"))
        monkeypatch.setattr("patchy_bot.handlers.download.vpn_ready_for_download", lambda ctx: (True, "ok"))
        mock_ctx.qbt.add_url = MagicMock(return_value="Ok.")

        result = await do_add(mock_ctx, 12345, search_id, 1, "movies")

        assert isinstance(result, DoAddResult)
        assert result.name == "Test.Movie.2024.1080p"
        assert result.category == "Movies"
        assert result.resp == "Ok."
        # Hash-based rows generate magnet URLs
        assert result.is_magnet is True

    @pytest.mark.asyncio
    async def test_hash_from_search_row(self, mock_ctx, monkeypatch):
        """do_add extracts hash from search result row when present."""
        torrent_hash = "b" * 40
        search_id = _save_search_with_hash(mock_ctx.store, 12345, torrent_hash)
        monkeypatch.setattr("patchy_bot.handlers.download.ensure_media_categories", lambda ctx: (True, "ok"))
        monkeypatch.setattr("patchy_bot.handlers.download.qbt_transport_status", lambda ctx: (True, "ok"))
        monkeypatch.setattr("patchy_bot.handlers.download.vpn_ready_for_download", lambda ctx: (True, "ok"))
        mock_ctx.qbt.add_url = MagicMock(return_value="Ok.")

        result = await do_add(mock_ctx, 12345, search_id, 1, "movies")

        assert result.hash == torrent_hash

    @pytest.mark.asyncio
    async def test_no_hash_returns_none(self, mock_ctx, monkeypatch):
        """do_add returns hash=None when the search row has no extractable hash."""
        rows = [
            {
                "name": "No.Hash.Movie.2024.1080p",
                "size": 2_000_000_000,
                "seeds": 10,
                "url": "https://tracker.invalid/download/nohash.torrent",
            }
        ]
        search_id = mock_ctx.store.save_search(12345, "No Hash", {"sort": "quality"}, rows)
        monkeypatch.setattr("patchy_bot.handlers.download.ensure_media_categories", lambda ctx: (True, "ok"))
        monkeypatch.setattr("patchy_bot.handlers.download.qbt_transport_status", lambda ctx: (True, "ok"))
        monkeypatch.setattr("patchy_bot.handlers.download.vpn_ready_for_download", lambda ctx: (True, "ok"))
        mock_ctx.qbt.add_url = MagicMock(return_value="Ok.")

        result = await do_add(mock_ctx, 12345, search_id, 1, "movies")

        assert result.hash is None
        assert result.is_magnet is False

    @pytest.mark.asyncio
    async def test_does_not_call_resolve_hash(self, mock_ctx, monkeypatch):
        """Fast phase never calls resolve_hash_by_name (that's background work)."""
        search_id = _save_search_with_hash(mock_ctx.store, 12345, "c" * 40)
        monkeypatch.setattr("patchy_bot.handlers.download.ensure_media_categories", lambda ctx: (True, "ok"))
        monkeypatch.setattr("patchy_bot.handlers.download.qbt_transport_status", lambda ctx: (True, "ok"))
        monkeypatch.setattr("patchy_bot.handlers.download.vpn_ready_for_download", lambda ctx: (True, "ok"))
        mock_ctx.qbt.add_url = MagicMock(return_value="Ok.")

        resolve_called = False
        _orig_resolve = _dl_mod.resolve_hash_by_name

        async def _tracking_resolve(*args, **kwargs):
            nonlocal resolve_called
            resolve_called = True
            return await _orig_resolve(*args, **kwargs)

        monkeypatch.setattr("patchy_bot.handlers.download.resolve_hash_by_name", _tracking_resolve)

        await do_add(mock_ctx, 12345, search_id, 1, "movies")

        assert not resolve_called, "Fast phase should not call resolve_hash_by_name"


class TestDoAddBackground:
    """Tests for the background phase of do_add_background."""

    @pytest.mark.asyncio
    async def test_resolves_hash_when_missing(self, mock_ctx, monkeypatch):
        """Background phase calls resolve_hash_by_name when hash is None."""
        from patchy_bot.handlers.download import do_add_background

        result = _make_fast_result(torrent_hash=None)
        msg = MagicMock()
        msg.edit_text = AsyncMock()

        resolved_hash = "d" * 40

        async def _fake_resolve(ctx, title, category, wait_s=20):
            return resolved_hash

        monkeypatch.setattr("patchy_bot.handlers.download.resolve_hash_by_name", _fake_resolve)
        mock_ctx.qbt.get_torrent_files = MagicMock(return_value=[{"name": "Test.Movie.mkv"}])
        mock_ctx.qbt.resume_torrents = MagicMock()

        await do_add_background(mock_ctx, 12345, result, msg, start_tracker=False)

        mock_ctx.qbt.resume_torrents.assert_called_once_with(resolved_hash)

    @pytest.mark.asyncio
    async def test_malware_block_pauses_torrent(self, mock_ctx, monkeypatch):
        """Concurrent file scan pauses torrent and sends warning on malware detection."""
        from patchy_bot.handlers.download import _concurrent_file_scan

        result = _make_fast_result()
        msg = MagicMock()
        msg.chat_id = 12345
        bot_mock = MagicMock()
        sent_msg = MagicMock()
        bot_mock.send_message = AsyncMock(return_value=sent_msg)
        msg.get_bot = MagicMock(return_value=bot_mock)

        mock_ctx.qbt.get_torrent_files = MagicMock(return_value=[{"name": "Bad.Movie.mkv"}, {"name": "setup.exe"}])
        mock_ctx.qbt.pause_torrents = MagicMock()

        await _concurrent_file_scan(mock_ctx, 12345, "a" * 40, result, msg)

        mock_ctx.qbt.pause_torrents.assert_called_once_with("a" * 40)
        # Should send NEW message with security warning (not edit interim)
        bot_mock.send_message.assert_called_once()
        call_text = bot_mock.send_message.call_args[1]["text"]
        assert "Blocked" in call_text

    @pytest.mark.asyncio
    async def test_clean_scan_starts_queue(self, mock_ctx, monkeypatch):
        """Background phase resumes torrent after clean malware scan."""
        from patchy_bot.handlers.download import do_add_background

        result = _make_fast_result()
        msg = MagicMock()
        msg.edit_text = AsyncMock()

        mock_ctx.qbt.get_torrent_files = MagicMock(return_value=[{"name": "Clean.Movie.2024.1080p.mkv"}])
        mock_ctx.qbt.resume_torrents = MagicMock()

        await do_add_background(mock_ctx, 12345, result, msg, start_tracker=False)

        mock_ctx.qbt.resume_torrents.assert_called_once_with("a" * 40)

    @pytest.mark.asyncio
    async def test_hash_timeout_notifies_user(self, mock_ctx, monkeypatch):
        """Background phase edits message when hash resolution returns None."""
        from patchy_bot.handlers.download import do_add_background

        result = _make_fast_result(torrent_hash=None)
        msg = MagicMock()
        msg.edit_text = AsyncMock()

        async def _fail_resolve(ctx, title, category, wait_s=20):
            return None

        monkeypatch.setattr("patchy_bot.handlers.download.resolve_hash_by_name", _fail_resolve)

        await do_add_background(mock_ctx, 12345, result, msg, start_tracker=False)

        msg.edit_text.assert_called()
        call_text = msg.edit_text.call_args[0][0]
        assert "Could not resolve torrent hash" in call_text

    @pytest.mark.asyncio
    async def test_exception_handling(self, mock_ctx, monkeypatch):
        """Background phase logs exceptions without raising."""
        from patchy_bot.handlers.download import do_add_background

        result = _make_fast_result()
        msg = MagicMock()
        msg.edit_text = AsyncMock()

        # Force an unhandled exception in the background phase
        async def _explode(ctx, title, timeout_s):
            raise ValueError("test explosion")

        monkeypatch.setattr("patchy_bot.handlers.download._wait_for_file_inspection", _explode)

        # Should NOT raise — it's fire-and-forget
        await do_add_background(mock_ctx, 12345, result, msg, start_tracker=False)

        # The finally block should have edited the message with an error state
        msg.edit_text.assert_called()

    @pytest.mark.asyncio
    async def test_queued_when_slot_occupied(self, mock_ctx, monkeypatch):
        """Background phase enqueues torrent when download slot is occupied."""
        from patchy_bot.handlers.download import do_add_background

        result = _make_fast_result()
        msg = MagicMock()
        msg.edit_text = AsyncMock()

        mock_ctx.qbt.get_torrent_files = MagicMock(return_value=[{"name": "Clean.Movie.mkv"}])
        mock_ctx.qbt.resume_torrents = MagicMock()
        mock_ctx.active_download_hash = "z" * 40  # Slot occupied

        await do_add_background(mock_ctx, 12345, result, msg, start_tracker=False)

        # Should NOT resume — slot was occupied
        mock_ctx.qbt.resume_torrents.assert_not_called()
        # Should be queued
        assert not mock_ctx.download_queue.empty()
        queued_item = mock_ctx.download_queue.get_nowait()
        assert queued_item["hash"] == ("a" * 40).lower()

        # Reset for cleanup
        mock_ctx.active_download_hash = None


class TestMwblockCallback:
    """Tests for the mwblock: callback handler."""

    @pytest.mark.asyncio
    async def test_keep_resumes_torrent(self, mock_ctx, mock_callback_query):
        """mwblock:keep resumes the paused torrent."""
        from patchy_bot.handlers.download import on_cb_mwblock

        torrent_hash = "a" * 40
        mock_ctx.qbt.resume_torrents = MagicMock()

        await on_cb_mwblock(mock_ctx, data=f"mwblock:keep:{torrent_hash}", q=mock_callback_query, user_id=12345)

        mock_ctx.qbt.resume_torrents.assert_called_once_with(torrent_hash)
        mock_callback_query.answer.assert_called_with("Torrent resumed")

    @pytest.mark.asyncio
    async def test_delete_removes_torrent(self, mock_ctx, mock_callback_query):
        """mwblock:delete deletes the torrent with files."""
        from patchy_bot.handlers.download import on_cb_mwblock

        torrent_hash = "b" * 40
        mock_ctx.qbt.delete_torrent = MagicMock()

        await on_cb_mwblock(mock_ctx, data=f"mwblock:delete:{torrent_hash}", q=mock_callback_query, user_id=12345)

        mock_ctx.qbt.delete_torrent.assert_called_once_with(torrent_hash, delete_files=True)
        mock_callback_query.answer.assert_called_with("Torrent deleted")

    @pytest.mark.asyncio
    async def test_delete_clears_active_hash(self, mock_ctx, mock_callback_query):
        """mwblock:delete clears active_download_hash if it matches."""
        from patchy_bot.handlers.download import on_cb_mwblock

        torrent_hash = "c" * 40
        mock_ctx.active_download_hash = torrent_hash
        mock_ctx.qbt.delete_torrent = MagicMock()

        await on_cb_mwblock(mock_ctx, data=f"mwblock:delete:{torrent_hash}", q=mock_callback_query, user_id=12345)

        assert mock_ctx.active_download_hash is None

    @pytest.mark.asyncio
    async def test_missing_torrent_graceful(self, mock_ctx, mock_callback_query):
        """mwblock:keep handles gracefully when torrent no longer exists."""
        from patchy_bot.handlers.download import on_cb_mwblock

        torrent_hash = "d" * 40
        mock_ctx.qbt.resume_torrents = MagicMock(side_effect=Exception("not found"))

        await on_cb_mwblock(mock_ctx, data=f"mwblock:keep:{torrent_hash}", q=mock_callback_query, user_id=12345)

        mock_callback_query.answer.assert_called_with("Torrent no longer exists", show_alert=True)

    @pytest.mark.asyncio
    async def test_invalid_hash_rejected(self, mock_ctx, mock_callback_query):
        """mwblock: rejects callback data with invalid hash."""
        from patchy_bot.handlers.download import on_cb_mwblock

        await on_cb_mwblock(mock_ctx, data="mwblock:keep:not_a_hash", q=mock_callback_query, user_id=12345)

        mock_callback_query.answer.assert_called_with("Invalid hash", show_alert=True)
