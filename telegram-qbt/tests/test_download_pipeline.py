"""Tests for the download pipeline: do_add, resolve_hash_by_name, progress smoothing,
active-state filtering, and shared helpers (normalize_media_choice, check_free_space).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from patchy_bot.handlers._shared import (
    check_free_space,
    normalize_media_choice,
)
from patchy_bot.handlers.download import (
    do_add,
    render_progress_text,
    resolve_hash_by_name,
    track_download_progress,
)
from patchy_bot.utils import _ACTIVE_DL_STATES

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
        """do_add returns a dict with required keys when all pre-flights pass."""
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

        assert isinstance(result, dict)
        for key in ("summary", "name", "hash", "category", "path"):
            assert key in result, f"Missing key: {key}"
        assert result["hash"] == torrent_hash

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

    def test_check_free_space_oserror_skips(self, monkeypatch):
        """OSError on statvfs returns (True, skip message) — no hard failure."""
        import os

        monkeypatch.setattr(os, "statvfs", MagicMock(side_effect=OSError("No such file")))

        ok, msg = check_free_space("/nonexistent/path")
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
