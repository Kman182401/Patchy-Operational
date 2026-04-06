"""Tests for patchy_bot/handlers/download.py — progress rendering and tracker."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

from patchy_bot.handlers.download import (
    completed_bytes,
    eta_label,
    format_eta,
    is_complete_torrent,
    progress_bar,
    render_progress_text,
    safe_tracker_edit,
    state_label,
    track_download_progress,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _torrent_info(
    *,
    progress: float = 0.0,
    state: str = "downloading",
    size: int = 1_000_000,
    completed: int = 0,
    downloaded: int = 0,
    amount_left: int = -1,
    dlspeed: int = 0,
    upspeed: int = 0,
    eta: int = -1,
    name: str = "Test.Torrent",
    content_path: str = "/tmp/test",
    category: str = "TV",
    **extra,
) -> dict:
    info = {
        "progress": progress,
        "state": state,
        "size": size,
        "completed": completed,
        "downloaded": downloaded,
        "amount_left": amount_left,
        "dlspeed": dlspeed,
        "upspeed": upspeed,
        "eta": eta,
        "name": name,
        "content_path": content_path,
        "category": category,
    }
    info.update(extra)
    return info


# ---------------------------------------------------------------------------
# progress_bar
# ---------------------------------------------------------------------------


class TestProgressBar:
    def test_zero(self):
        bar = progress_bar(0.0)
        # All light blocks, no full blocks
        assert "\u2588" not in bar
        assert len(bar) == 18

    def test_fifty(self):
        bar = progress_bar(50.0)
        full_count = bar.count("\u2588")
        assert full_count == 9

    def test_hundred(self):
        bar = progress_bar(100.0)
        assert bar == "\u2588" * 18

    def test_fractional(self):
        bar = progress_bar(33.3)
        # Should contain some full blocks, a partial block, and light blocks
        assert "\u2588" in bar
        assert "\u2591" in bar
        assert len(bar) == 18

    def test_clamps_above_100(self):
        bar = progress_bar(150.0)
        assert bar == "\u2588" * 18

    def test_clamps_below_0(self):
        bar = progress_bar(-10.0)
        assert "\u2588" not in bar


# ---------------------------------------------------------------------------
# format_eta
# ---------------------------------------------------------------------------


class TestFormatEta:
    def test_normal(self):
        assert format_eta(3661) == "01:01:01"

    def test_with_days(self):
        assert format_eta(90061) == "1d 01:01:01"

    def test_infinity_sentinel(self):
        assert format_eta(8640000) == "\u221e"

    def test_negative(self):
        assert format_eta(-1) == "\u221e"

    def test_zero(self):
        assert format_eta(0) == "00:00:00"

    def test_just_under_sentinel(self):
        result = format_eta(8639999)
        assert result != "\u221e"
        assert "d" in result  # Should show days


# ---------------------------------------------------------------------------
# is_complete_torrent
# ---------------------------------------------------------------------------


class TestIsCompleteTorrent:
    def test_progress_threshold(self):
        info = _torrent_info(progress=0.999)
        assert is_complete_torrent(info) is True

    def test_uploading_state(self):
        info = _torrent_info(progress=0.0, state="uploading")
        assert is_complete_torrent(info) is True

    def test_stalledUP_state(self):
        info = _torrent_info(progress=0.0, state="stalledUP")
        assert is_complete_torrent(info) is True

    def test_not_complete_downloading(self):
        info = _torrent_info(progress=0.5, state="downloading")
        assert is_complete_torrent(info) is False

    def test_completed_equals_total(self):
        info = _torrent_info(size=1000, completed=1000, progress=0.0, state="downloading")
        assert is_complete_torrent(info) is True

    def test_amount_left_zero_completes(self):
        """amount_left=0 means fully downloaded — should be detected as complete."""
        info = _torrent_info(size=1000, amount_left=0, progress=0.0, state="downloading")
        assert is_complete_torrent(info) is True


# ---------------------------------------------------------------------------
# completed_bytes
# ---------------------------------------------------------------------------


class TestCompletedBytes:
    def test_capped_at_total(self):
        info = _torrent_info(size=500, completed=9999)
        assert completed_bytes(info) == 500

    def test_uses_downloaded_when_no_completed(self):
        info = _torrent_info(size=1000, completed=0, downloaded=400)
        assert completed_bytes(info) == 400

    def test_prefers_completed_over_downloaded(self):
        info = _torrent_info(size=1000, completed=600, downloaded=400)
        assert completed_bytes(info) == 600

    def test_zero_when_nothing(self):
        info = _torrent_info(size=1000, completed=0, downloaded=0)
        assert completed_bytes(info) == 0


# ---------------------------------------------------------------------------
# state_label
# ---------------------------------------------------------------------------


class TestStateLabel:
    def test_downloading(self):
        info = _torrent_info(state="downloading", progress=0.5)
        assert state_label(info) == "downloading"

    def test_metadata(self):
        info = _torrent_info(state="metaDL", progress=0.0)
        assert state_label(info) == "getting metadata"

    def test_seeding_when_complete(self):
        info = _torrent_info(state="uploading", progress=1.0)
        assert state_label(info) == "seeding"

    def test_unknown_state(self):
        info = _torrent_info(state="somethingWeird", progress=0.3)
        assert state_label(info) == "somethingWeird"


# ---------------------------------------------------------------------------
# eta_label
# ---------------------------------------------------------------------------


class TestEtaLabel:
    def test_done_when_complete(self):
        info = _torrent_info(progress=1.0, state="uploading")
        assert eta_label(info) == "done"

    def test_metadata_state(self):
        info = _torrent_info(state="metaDL", progress=0.0)
        assert eta_label(info) == "metadata"

    def test_formatted_eta(self):
        info = _torrent_info(state="downloading", progress=0.5, eta=3661)
        assert eta_label(info) == "01:01:01"

    def test_infinity_when_no_eta(self):
        info = _torrent_info(state="downloading", progress=0.5, eta=-1)
        assert eta_label(info) == "\u221e"


# ---------------------------------------------------------------------------
# render_progress_text
# ---------------------------------------------------------------------------


class TestRenderProgressText:
    def test_contains_name(self):
        info = _torrent_info(progress=0.5, state="downloading")
        text = render_progress_text("My.Show.S01E01", info, 0)
        assert "My.Show.S01E01" in text

    def test_contains_progress_bar(self):
        info = _torrent_info(progress=0.5)
        text = render_progress_text("Test", info, 0)
        assert "\u2588" in text  # full block in progress bar

    def test_uses_override_values(self):
        info = _torrent_info(progress=0.5, dlspeed=0, upspeed=0)
        text = render_progress_text("Test", info, 0, progress_pct=75.0, dls_bps=1_000_000, uls_bps=500_000)
        assert "75.0%" in text

    def test_html_tags_present(self):
        info = _torrent_info(progress=0.3)
        text = render_progress_text("Test", info, 0)
        assert "<b>" in text
        assert "<code>" in text


# ---------------------------------------------------------------------------
# safe_tracker_edit
# ---------------------------------------------------------------------------


class TestSafeTrackerEdit:
    async def test_success_returns_true(self):
        msg = MagicMock()
        msg.edit_text = AsyncMock()
        result = await safe_tracker_edit(msg, "hello")
        assert result is True

    async def test_not_modified_returns_true(self):
        msg = MagicMock()
        msg.edit_text = AsyncMock(side_effect=Exception("message is not modified"))
        result = await safe_tracker_edit(msg, "hello")
        assert result is True

    async def test_timeout_returns_false(self):
        msg = MagicMock()
        msg.edit_text = AsyncMock(side_effect=Exception("Timed out"))
        result = await safe_tracker_edit(msg, "hello")
        assert result is False

    async def test_other_error_returns_false(self):
        msg = MagicMock()
        msg.edit_text = AsyncMock(side_effect=Exception("bad request"))
        result = await safe_tracker_edit(msg, "hello")
        assert result is False


# ---------------------------------------------------------------------------
# track_download_progress — async tracker tests
# ---------------------------------------------------------------------------


from tests.helpers import FakeOrganizeResult


class TestTrackDownloadProgress:
    """Tests for the main tracking loop. All qBT and Telegram calls are mocked."""

    async def test_completes_on_full_progress(self, mock_ctx, monkeypatch):
        """When qBT reports a completed torrent, tracker exits with a completion message."""
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())
        monkeypatch.setattr(
            "patchy_bot.handlers.download._organize_download",
            lambda *a: FakeOrganizeResult(),
        )

        info = _torrent_info(progress=1.0, state="uploading", size=1000, completed=1000)
        mock_ctx.qbt.get_torrent = MagicMock(return_value=info)
        mock_ctx.store.mark_completion_notified = MagicMock()
        mock_ctx.plex.ready.return_value = False

        tracker_msg = MagicMock()
        tracker_msg.edit_text = AsyncMock()
        tracker_msg.chat_id = 123
        tracker_msg.message_id = 456
        sent_msg = MagicMock(chat_id=123, message_id=789)
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock(return_value=sent_msg)
        tracker_msg.get_bot = MagicMock(return_value=bot_mock)

        await track_download_progress(mock_ctx, 123, "a" * 40, tracker_msg, "Test")

        # Verify the completion edit happened
        edit_calls = [str(c) for c in tracker_msg.edit_text.call_args_list]
        assert any("Download Complete" in c for c in edit_calls)

    async def test_timeout_sends_message(self, mock_ctx, monkeypatch):
        """When the tracker exceeds the timeout, it sends a timeout notice."""
        # Set a very short timeout
        mock_ctx.cfg.progress_track_timeout_s = 0  # immediate timeout
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())

        tracker_msg = MagicMock()
        tracker_msg.edit_text = AsyncMock()
        tracker_msg.chat_id = 123
        tracker_msg.message_id = 456
        sent_msg = MagicMock(chat_id=123, message_id=789)
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock(return_value=sent_msg)
        tracker_msg.get_bot = MagicMock(return_value=bot_mock)

        await track_download_progress(mock_ctx, 123, "b" * 40, tracker_msg, "Test")

        edit_calls = [str(c) for c in tracker_msg.edit_text.call_args_list]
        # Either edited with timeout text or sent fallback
        all_calls = edit_calls + [str(c) for c in bot_mock.send_message.call_args_list]
        assert any("Timed Out" in c for c in all_calls)

    async def test_qbt_error_streak_exits(self, mock_ctx, monkeypatch):
        """Five consecutive qBT errors cause the tracker to exit gracefully."""
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())
        mock_ctx.cfg.progress_track_timeout_s = 9999  # don't timeout

        mock_ctx.qbt.get_torrent = MagicMock(side_effect=ConnectionError("qBT down"))

        tracker_msg = MagicMock()
        tracker_msg.edit_text = AsyncMock()
        tracker_msg.chat_id = 123
        tracker_msg.message_id = 456
        sent_msg = MagicMock(chat_id=123, message_id=789)
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock(return_value=sent_msg)
        tracker_msg.get_bot = MagicMock(return_value=bot_mock)

        await track_download_progress(mock_ctx, 123, "c" * 40, tracker_msg, "Test")

        # Should have sent a fallback "Monitor Paused" message
        send_calls = [str(c) for c in bot_mock.send_message.call_args_list]
        assert any("Monitor Paused" in c for c in send_calls)

    async def test_task_key_cleaned_up(self, mock_ctx, monkeypatch):
        """After tracker finishes, its key is removed from progress_tasks."""
        mock_ctx.cfg.progress_track_timeout_s = 0
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())

        thash = "d" * 40
        key = (123, thash)

        tracker_msg = MagicMock()
        tracker_msg.edit_text = AsyncMock()
        tracker_msg.chat_id = 123
        tracker_msg.message_id = 456
        sent_msg = MagicMock(chat_id=123, message_id=789)
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock(return_value=sent_msg)
        tracker_msg.get_bot = MagicMock(return_value=bot_mock)

        # Pre-populate the key
        mock_ctx.progress_tasks[key] = MagicMock()

        await track_download_progress(mock_ctx, 123, thash, tracker_msg, "Test")

        assert key not in mock_ctx.progress_tasks

    async def test_torrent_not_found_after_grace(self, mock_ctx, monkeypatch):
        """If qBT returns None after 20s, tracker sends 'not found' notice."""
        call_count = 0
        real_time = time.time

        def fake_time():
            nonlocal call_count
            call_count += 1
            # After a few calls, simulate that 25 seconds have passed
            if call_count > 3:
                return real_time() + 25
            return real_time()

        monkeypatch.setattr("patchy_bot.handlers.download.time.time", fake_time)
        monkeypatch.setattr("patchy_bot.handlers.download.asyncio.sleep", AsyncMock())
        mock_ctx.cfg.progress_track_timeout_s = 9999

        mock_ctx.qbt.get_torrent = MagicMock(return_value=None)

        tracker_msg = MagicMock()
        tracker_msg.edit_text = AsyncMock()
        tracker_msg.chat_id = 123
        tracker_msg.message_id = 456
        sent_msg = MagicMock(chat_id=123, message_id=789)
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock(return_value=sent_msg)
        tracker_msg.get_bot = MagicMock(return_value=bot_mock)

        await track_download_progress(mock_ctx, 123, "e" * 40, tracker_msg, "Test")

        all_calls = [str(c) for c in tracker_msg.edit_text.call_args_list] + [
            str(c) for c in bot_mock.send_message.call_args_list
        ]
        assert any("Torrent Not Found" in c for c in all_calls)
