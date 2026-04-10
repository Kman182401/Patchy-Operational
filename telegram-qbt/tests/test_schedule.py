"""Tests for schedule track creation lifecycle.

Covers the fix for premature track activation: tracks created via the
``sch:confirm:pick`` path must start with ``enabled=0`` and only become
``enabled=1`` after the user confirms through the picker → dlgo flow.
Backing out via ``sch:pkback`` must delete the disabled track.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from patchy_bot.handlers.schedule import on_cb_schedule
from patchy_bot.store import Store
from patchy_bot.types import HandlerContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER_ID = 12345
CHAT_ID = 12345


def _make_show() -> dict[str, Any]:
    return {"name": "Test Show", "id": 42, "tmdb_id": 100, "imdb_id": "tt1234567", "year": 2024}


def _make_probe(*, season: int = 1) -> dict[str, Any]:
    return {
        "season": season,
        "pending_codes": ["S01E01"],
        "missing_codes": ["S01E01", "S01E02"],
        "actionable_missing_codes": ["S01E01", "S01E02"],
        "signature": "sig123",
        "next_air_ts": 0,
    }


class FakeBotApp:
    """Minimal stand-in for BotApp that records method calls for schedule tests."""

    def __init__(self, ctx: HandlerContext) -> None:
        self._ctx = ctx
        self.store = ctx.store
        self.cfg = ctx.cfg
        self.flow: dict[int, dict[str, Any]] = {}
        self.render_calls: list[tuple[str, tuple, dict]] = []

    def _set_flow(self, user_id: int, flow: dict[str, Any]) -> None:
        self.flow[user_id] = flow

    def _get_flow(self, user_id: int) -> dict[str, Any] | None:
        return self.flow.get(user_id)

    def _clear_flow(self, user_id: int) -> None:
        self.flow.pop(user_id, None)

    async def _render_schedule_ui(self, *args: Any, **kwargs: Any) -> MagicMock:
        self.render_calls.append(("schedule_ui", args, kwargs))
        m = MagicMock()
        m.chat_id = CHAT_ID
        m.message_id = 1
        return m

    async def _render_nav_ui(self, *args: Any, **kwargs: Any) -> MagicMock:
        self.render_calls.append(("nav_ui", args, kwargs))
        m = MagicMock()
        m.chat_id = CHAT_ID
        m.message_id = 1
        return m

    def _home_only_keyboard(self) -> MagicMock:
        return MagicMock()

    async def _schedule_confirm_selection(
        self, msg: Any, user_id: int, chat_id: int, post_action: str | None = None
    ) -> None:
        """Stub that records the call for assertion."""
        self.render_calls.append(("confirm_selection", (msg, user_id, chat_id, post_action), {}))

    def _schedule_preview_text(self, probe: dict) -> str:
        return "<b>Preview</b>"

    def _schedule_preview_keyboard(self, probe: dict) -> MagicMock:
        return MagicMock()

    def _schedule_picker_text(self, flow: dict) -> str:
        return "<b>Picker</b>"

    def _schedule_picker_keyboard(self, flow: dict) -> MagicMock:
        return MagicMock()

    def _schedule_dl_confirm_text(self, flow: dict) -> str:
        return "<b>Download Confirm</b>"

    def _schedule_dl_confirm_keyboard(self) -> MagicMock:
        return MagicMock()

    async def _schedule_download_requested(self, msg: Any, track: dict, codes: list) -> None:
        self.render_calls.append(("download_requested", (msg, track, codes), {}))

    async def _cleanup_poster_photo(self, user_id: int, flow: Any = None) -> None:
        pass


@pytest.fixture
def fake_app(mock_ctx: HandlerContext) -> FakeBotApp:
    return FakeBotApp(mock_ctx)


@pytest.fixture
def query() -> MagicMock:
    q = MagicMock()
    q.data = "sch:pkback"
    q.answer = AsyncMock()
    reply_msg = MagicMock()
    reply_msg.chat_id = CHAT_ID
    reply_msg.message_id = 999
    q.message = MagicMock()
    q.message.edit_text = AsyncMock()
    q.message.reply_text = AsyncMock(return_value=reply_msg)
    q.message.delete = AsyncMock()
    q.message.chat_id = CHAT_ID
    q.message.message_id = 100
    q.message.get_bot = MagicMock(return_value=MagicMock())
    return q


# ---------------------------------------------------------------------------
# Store-level tests
# ---------------------------------------------------------------------------


class TestCreateScheduleTrackEnabled:
    """Verify the ``enabled`` parameter on ``create_schedule_track``."""

    def test_default_enabled_is_1(self, mock_store: Store) -> None:
        show = _make_show()
        probe = _make_probe()
        created, track = mock_store.create_schedule_track(
            user_id=USER_ID,
            chat_id=CHAT_ID,
            show=show,
            season=1,
            probe=probe,
            next_check_at=9999,
        )
        assert created is True
        assert track["enabled"] == 1

    def test_enabled_0_creates_disabled_track(self, mock_store: Store) -> None:
        show = _make_show()
        probe = _make_probe()
        created, track = mock_store.create_schedule_track(
            user_id=USER_ID,
            chat_id=CHAT_ID,
            show=show,
            season=1,
            probe=probe,
            next_check_at=9999,
            enabled=0,
        )
        assert created is True
        assert track["enabled"] == 0

    def test_disabled_track_invisible_to_due_query(self, mock_store: Store) -> None:
        show = _make_show()
        probe = _make_probe()
        mock_store.create_schedule_track(
            user_id=USER_ID,
            chat_id=CHAT_ID,
            show=show,
            season=1,
            probe=probe,
            next_check_at=0,
            enabled=0,
        )
        due = mock_store.list_due_schedule_tracks(due_ts=999999)
        assert len(due) == 0

    def test_update_enabled_activates_track(self, mock_store: Store) -> None:
        show = _make_show()
        probe = _make_probe()
        created, track = mock_store.create_schedule_track(
            user_id=USER_ID,
            chat_id=CHAT_ID,
            show=show,
            season=1,
            probe=probe,
            next_check_at=0,
            enabled=0,
        )
        tid = track["track_id"]
        assert track["enabled"] == 0
        mock_store.update_schedule_track(tid, enabled=1)
        updated = mock_store.get_schedule_track(USER_ID, tid)
        assert updated is not None
        assert updated["enabled"] == 1

    def test_dedup_returns_existing_track(self, mock_store: Store) -> None:
        show = _make_show()
        probe = _make_probe()
        _, first = mock_store.create_schedule_track(
            user_id=USER_ID,
            chat_id=CHAT_ID,
            show=show,
            season=1,
            probe=probe,
            next_check_at=9999,
            enabled=1,
        )
        created, second = mock_store.create_schedule_track(
            user_id=USER_ID,
            chat_id=CHAT_ID,
            show=show,
            season=1,
            probe=probe,
            next_check_at=9999,
            enabled=0,
        )
        assert created is False
        assert second["track_id"] == first["track_id"]
        assert second["enabled"] == 1  # existing track stays enabled


# ---------------------------------------------------------------------------
# Handler-level tests — sch:pkback deletes disabled track
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pkback_deletes_disabled_track(
    fake_app: FakeBotApp,
    query: MagicMock,
    mock_store: Store,
) -> None:
    """sch:pkback must delete the pending disabled track and remove pending_track_id from flow."""
    show = _make_show()
    probe = _make_probe()
    _, track = mock_store.create_schedule_track(
        user_id=USER_ID,
        chat_id=CHAT_ID,
        show=show,
        season=1,
        probe=probe,
        next_check_at=9999,
        enabled=0,
    )
    tid = track["track_id"]

    fake_app.flow[USER_ID] = {
        "mode": "schedule",
        "stage": "picker",
        "picker_has_preview": True,
        "picker_track_id": tid,
        "pending_track_id": tid,
        "probe": probe,
    }

    await on_cb_schedule(fake_app, data="sch:pkback", q=query, user_id=USER_ID)

    # Track must be deleted
    assert mock_store.get_schedule_track(USER_ID, tid) is None
    # pending_track_id must be gone from flow
    flow = fake_app.flow.get(USER_ID)
    assert flow is None or "pending_track_id" not in flow


@pytest.mark.asyncio
async def test_pkback_without_pending_track_is_safe(
    fake_app: FakeBotApp,
    query: MagicMock,
) -> None:
    """sch:pkback with no pending_track_id should not error."""
    fake_app.flow[USER_ID] = {
        "mode": "schedule",
        "stage": "picker",
        "picker_has_preview": True,
        "picker_track_id": "some-id",
        "probe": _make_probe(),
    }

    await on_cb_schedule(fake_app, data="sch:pkback", q=query, user_id=USER_ID)

    flow = fake_app.flow.get(USER_ID)
    assert flow is not None
    assert flow["stage"] == "confirm"


# ---------------------------------------------------------------------------
# Handler-level tests — sch:dlgo from picker activates track
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dlgo_from_picker_activates_track(
    fake_app: FakeBotApp,
    query: MagicMock,
    mock_store: Store,
) -> None:
    """sch:dlgo with dl_confirm_from=picker must flip the pending track to enabled=1."""
    show = _make_show()
    probe = _make_probe()
    _, track = mock_store.create_schedule_track(
        user_id=USER_ID,
        chat_id=CHAT_ID,
        show=show,
        season=1,
        probe=probe,
        next_check_at=9999,
        enabled=0,
    )
    tid = track["track_id"]

    fake_app.flow[USER_ID] = {
        "mode": "schedule",
        "stage": "dl_confirm",
        "dl_confirm_codes": ["S01E01"],
        "dl_confirm_post_action": "pick",
        "dl_confirm_from": "picker",
        "picker_track_id": tid,
        "pending_track_id": tid,
    }

    await on_cb_schedule(fake_app, data="sch:dlgo", q=query, user_id=USER_ID)

    # Track must now be enabled
    updated = mock_store.get_schedule_track(USER_ID, tid)
    assert updated is not None
    assert updated["enabled"] == 1


@pytest.mark.asyncio
async def test_dlgo_from_picker_without_pending_still_works(
    fake_app: FakeBotApp,
    query: MagicMock,
    mock_store: Store,
) -> None:
    """sch:dlgo from picker when no pending_track_id (dedup hit) should still proceed."""
    show = _make_show()
    probe = _make_probe()
    _, track = mock_store.create_schedule_track(
        user_id=USER_ID,
        chat_id=CHAT_ID,
        show=show,
        season=1,
        probe=probe,
        next_check_at=9999,
        enabled=1,
    )
    tid = track["track_id"]

    fake_app.flow[USER_ID] = {
        "mode": "schedule",
        "stage": "dl_confirm",
        "dl_confirm_codes": ["S01E01"],
        "dl_confirm_post_action": "pick",
        "dl_confirm_from": "picker",
        "picker_track_id": tid,
        # No pending_track_id — dedup case
    }

    await on_cb_schedule(fake_app, data="sch:dlgo", q=query, user_id=USER_ID)

    # Track stays enabled
    updated = mock_store.get_schedule_track(USER_ID, tid)
    assert updated is not None
    assert updated["enabled"] == 1
    # Download was requested
    assert any(name == "download_requested" for name, _, _ in fake_app.render_calls)


# ---------------------------------------------------------------------------
# Handler-level tests — sch:dlback preserves pending_track_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dlback_from_picker_preserves_pending_track_id(
    fake_app: FakeBotApp,
    query: MagicMock,
) -> None:
    """sch:dlback from picker must keep pending_track_id in the flow."""
    fake_app.flow[USER_ID] = {
        "mode": "schedule",
        "stage": "dl_confirm",
        "dl_confirm_codes": ["S01E01"],
        "dl_confirm_post_action": "pick",
        "dl_confirm_from": "picker",
        "picker_track_id": "track-abc",
        "pending_track_id": "track-abc",
        "picker_selected": ["S01E01"],
        "picker_season": 1,
        "picker_all_missing": {"1": ["S01E01"]},
    }

    await on_cb_schedule(fake_app, data="sch:dlback", q=query, user_id=USER_ID)

    flow = fake_app.flow.get(USER_ID)
    assert flow is not None
    assert flow["stage"] == "picker"
    assert flow.get("pending_track_id") == "track-abc"
