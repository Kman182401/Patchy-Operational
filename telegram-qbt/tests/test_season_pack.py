from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from patchy_bot.bot import BotApp
from patchy_bot.handlers import schedule as schedule_handler


class _StoreStub:
    def __init__(self, track: dict[str, object]) -> None:
        self.track = dict(track)
        self.updated_fields: list[dict[str, object]] = []

    def update_schedule_track(self, track_id: str, **fields: object) -> None:
        assert track_id == self.track["track_id"]
        self.track.update(fields)
        self.updated_fields.append(fields)

    def get_schedule_track_any(self, track_id: str) -> dict[str, object]:
        assert track_id == self.track["track_id"]
        return dict(self.track)


@pytest.mark.asyncio
async def test_search_season_pack_returns_first_1080p_non_episode_result() -> None:
    queries: list[str] = []

    class FakeQbt:
        def search(self, query: str, **_kwargs: object) -> list[dict[str, object]]:
            queries.append(query)
            return [
                {"name": "Example Show S01 1080p WEB-DL", "nbSeeders": 22, "fileSize": 12_000_000_000},
                {"name": "Example Show S01 720p WEB-DL", "nbSeeders": 99, "fileSize": 8_000_000_000},
            ]

    ctx = SimpleNamespace(
        qbt=FakeQbt(),
        cfg=SimpleNamespace(
            poll_interval_s=0.01,
            search_early_exit_min_results=12,
            search_early_exit_idle_s=0.01,
            search_early_exit_max_wait_s=0.05,
        ),
    )

    result = await schedule_handler.search_season_pack(ctx, "Example Show", 1, 123)  # pyright: ignore[reportArgumentType]

    assert result is not None
    assert result["name"] == "Example Show S01 1080p WEB-DL"
    assert result["_season_pack_query"] == "Example Show S01 1080p"
    assert queries == ["Example Show S01 1080p"]


@pytest.mark.asyncio
async def test_search_season_pack_rejects_episode_results_and_falls_through() -> None:
    queries: list[str] = []

    class FakeQbt:
        def search(self, query: str, **_kwargs: object) -> list[dict[str, object]]:
            queries.append(query)
            if len(queries) == 1:
                return [
                    {"name": "Example Show S01E01 1080p WEB-DL", "nbSeeders": 50, "fileSize": 1_000_000_000},
                    {"name": "Example Show S01E02 1080p WEB-DL", "nbSeeders": 45, "fileSize": 1_100_000_000},
                ]
            return [
                {"name": "Example Show Season 1 1080p BluRay", "nbSeeders": 18, "fileSize": 14_000_000_000},
            ]

    ctx = SimpleNamespace(
        qbt=FakeQbt(),
        cfg=SimpleNamespace(
            poll_interval_s=0.01,
            search_early_exit_min_results=12,
            search_early_exit_idle_s=0.01,
            search_early_exit_max_wait_s=0.05,
        ),
    )

    result = await schedule_handler.search_season_pack(ctx, "Example Show", 1, 123)  # pyright: ignore[reportArgumentType]

    assert result is not None
    assert result["name"] == "Example Show Season 1 1080p BluRay"
    assert queries == ["Example Show S01 1080p", "Example Show S01"]


@pytest.mark.asyncio
async def test_search_season_pack_returns_none_when_all_queries_empty() -> None:
    queries: list[str] = []

    class FakeQbt:
        def search(self, query: str, **_kwargs: object) -> list[dict[str, object]]:
            queries.append(query)
            return []

    ctx = SimpleNamespace(
        qbt=FakeQbt(),
        cfg=SimpleNamespace(
            poll_interval_s=0.01,
            search_early_exit_min_results=12,
            search_early_exit_idle_s=0.01,
            search_early_exit_max_wait_s=0.05,
        ),
    )

    result = await schedule_handler.search_season_pack(ctx, "Example Show", 1, 123)  # pyright: ignore[reportArgumentType]

    assert result is None
    assert queries == [
        "Example Show S01 1080p",
        "Example Show S01",
        "Example Show Season 1 1080p",
        "Example Show Season 1",
    ]


def _base_track() -> dict[str, object]:
    return {
        "track_id": "track-1",
        "user_id": 77,
        "season": 1,
        "show_json": {"name": "Example Show"},
        "pending_json": [],
        "auto_state_json": {"enabled": True, "tracking_mode": "full_season"},
    }


def _base_probe(
    *, tracking_mode: str = "full_season", missing_codes: list[str], unreleased_codes: list[str]
) -> dict[str, object]:
    return {
        "show": {"name": "Example Show"},
        "season": 1,
        "tracking_mode": tracking_mode,
        "missing_codes": list(missing_codes),
        "all_missing_codes": list(missing_codes),
        "actionable_missing_codes": list(missing_codes),
        "tracked_missing_codes": list(missing_codes),
        "unreleased_codes": list(unreleased_codes),
        "present_codes": [],
        "pending_codes": [],
        "total_season_episodes": 3,
        "next_air_ts": None,
        "signature": "|".join(missing_codes),
    }


@pytest.mark.asyncio
async def test_schedule_refresh_track_uses_season_pack_for_full_missing_full_season(monkeypatch) -> None:
    track = _base_track()
    probe = _base_probe(
        missing_codes=["S01E01", "S01E02", "S01E03"],
        unreleased_codes=[],
    )
    store = _StoreStub(track)
    ctx = SimpleNamespace(store=store)
    notify_auto_queued = AsyncMock()
    download_season_pack = AsyncMock(return_value={"name": "Example Show S01 1080p WEB-DL"})
    attempt_auto_acquire = AsyncMock(return_value=None)

    monkeypatch.setattr(schedule_handler, "schedule_probe_track", lambda _ctx, _track: dict(probe))
    monkeypatch.setattr(schedule_handler, "schedule_reconcile_pending", lambda *_args, **_kwargs: (set(), set(), set()))
    monkeypatch.setattr(schedule_handler, "schedule_is_season_complete", lambda _probe: False)

    updated, returned_probe = await schedule_handler.schedule_refresh_track(
        ctx,  # pyright: ignore[reportArgumentType]
        track,
        allow_notify=True,
        qbt_category_aliases_fn=lambda *_args, **_kwargs: set(),
        attempt_auto_acquire_fn=attempt_auto_acquire,
        download_season_pack_fn=download_season_pack,
        notify_auto_queued_fn=notify_auto_queued,
    )

    download_season_pack.assert_awaited_once_with(track)
    attempt_auto_acquire.assert_not_called()
    notify_auto_queued.assert_awaited_once()
    assert updated["pending_json"] == ["S01E01", "S01E02", "S01E03"]
    assert updated["auto_state_json"]["last_auto_code"] == "S01"
    assert returned_probe["tracking_mode"] == "full_season"


@pytest.mark.asyncio
async def test_schedule_refresh_track_skips_season_pack_for_partial_season(monkeypatch) -> None:
    track = _base_track()
    probe = _base_probe(
        missing_codes=["S01E01", "S01E02"],
        unreleased_codes=[],
    )
    store = _StoreStub(track)
    ctx = SimpleNamespace(store=store)
    download_season_pack = AsyncMock(return_value={"name": "unused"})
    attempt_auto_acquire = AsyncMock(return_value=None)

    monkeypatch.setattr(schedule_handler, "schedule_probe_track", lambda _ctx, _track: dict(probe))
    monkeypatch.setattr(schedule_handler, "schedule_reconcile_pending", lambda *_args, **_kwargs: (set(), set(), set()))
    monkeypatch.setattr(schedule_handler, "schedule_is_season_complete", lambda _probe: False)

    await schedule_handler.schedule_refresh_track(
        ctx,  # pyright: ignore[reportArgumentType]
        track,
        allow_notify=False,
        qbt_category_aliases_fn=lambda *_args, **_kwargs: set(),
        attempt_auto_acquire_fn=attempt_auto_acquire,
        download_season_pack_fn=download_season_pack,
    )

    download_season_pack.assert_not_called()
    assert attempt_auto_acquire.await_count == 2


@pytest.mark.asyncio
async def test_schedule_refresh_track_skips_season_pack_for_upcoming_mode(monkeypatch) -> None:
    track = _base_track()
    track["auto_state_json"] = {"enabled": True, "tracking_mode": "upcoming"}
    probe = _base_probe(
        tracking_mode="upcoming",
        missing_codes=["S01E01", "S01E02", "S01E03"],
        unreleased_codes=[],
    )
    store = _StoreStub(track)
    ctx = SimpleNamespace(store=store)
    download_season_pack = AsyncMock(return_value={"name": "unused"})
    attempt_auto_acquire = AsyncMock(return_value=None)

    monkeypatch.setattr(schedule_handler, "schedule_probe_track", lambda _ctx, _track: dict(probe))
    monkeypatch.setattr(schedule_handler, "schedule_reconcile_pending", lambda *_args, **_kwargs: (set(), set(), set()))
    monkeypatch.setattr(schedule_handler, "schedule_is_season_complete", lambda _probe: False)

    await schedule_handler.schedule_refresh_track(
        ctx,  # pyright: ignore[reportArgumentType]
        track,
        allow_notify=False,
        qbt_category_aliases_fn=lambda *_args, **_kwargs: set(),
        attempt_auto_acquire_fn=attempt_auto_acquire,
        download_season_pack_fn=download_season_pack,
    )

    download_season_pack.assert_not_called()
    assert attempt_auto_acquire.await_count == 3


def test_episode_picker_has_download_season_button() -> None:
    codes = ["S02E01", "S02E03", "S02E04"]
    keyboard = schedule_handler.schedule_episode_picker_keyboard(
        track_id="track-42", codes=codes, nav_footer_fn=lambda: []
    )
    first_row = keyboard.inline_keyboard[0]
    assert len(first_row) == 1
    btn = first_row[0]
    assert btn.callback_data == "sch:all:track-42"
    assert "Download Season 2" in btn.text


def test_episode_picker_download_season_button_empty_codes() -> None:
    keyboard = schedule_handler.schedule_episode_picker_keyboard(
        track_id="track-42", codes=[], nav_footer_fn=lambda: []
    )
    assert keyboard is not None
    # With empty codes, there should be no season download button — only skip + footer
    for row in keyboard.inline_keyboard:
        for btn in row:
            assert "Download Season" not in (btn.text or "")


@pytest.mark.asyncio
async def test_bot_schedule_refresh_track_delegates_to_handler(monkeypatch) -> None:
    expected = ({"track_id": "track-1"}, {"probe": True})
    recorded: dict[str, object] = {}

    async def fake_schedule_refresh_track(ctx, track, **kwargs):
        recorded["ctx"] = ctx
        recorded["track"] = track
        recorded["kwargs"] = kwargs
        return expected

    monkeypatch.setattr(schedule_handler, "schedule_refresh_track", fake_schedule_refresh_track)

    bot = SimpleNamespace(
        _ctx="CTX",
        _qbt_category_aliases=object(),
        _schedule_should_attempt_auto=object(),
        _schedule_attempt_auto_acquire=object(),
        _schedule_download_season_pack=object(),
        _schedule_notify_auto_queued=object(),
        _schedule_notify_no_1080p=object(),
        _schedule_notify_missing=object(),
    )

    result = await BotApp._schedule_refresh_track(bot, {"track_id": "track-1"}, allow_notify=True)  # pyright: ignore[reportArgumentType]

    assert result == expected
    assert recorded["ctx"] == "CTX"
    assert recorded["kwargs"]["download_season_pack_fn"] is bot._schedule_download_season_pack  # pyright: ignore[reportIndexIssue]
