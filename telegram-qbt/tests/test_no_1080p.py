"""Tests for the no-1080p fallback feature in the schedule system."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from patchy_bot.handlers.schedule import (
    No1080pError,
    schedule_download_episode,
    schedule_no_1080p_backoff_s,
    schedule_refresh_track,
    schedule_sanitize_auto_state,
)
from patchy_bot.utils import now_ts

# ---------------------------------------------------------------------------
# 1. sanitize_auto_state includes no_1080p_miss
# ---------------------------------------------------------------------------


def test_sanitize_auto_state_includes_no_1080p_miss() -> None:
    state = schedule_sanitize_auto_state({})
    assert "no_1080p_miss" in state
    assert state["no_1080p_miss"] == {}


# ---------------------------------------------------------------------------
# 2. backoff boundaries (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "miss,expected",
    [
        (0, 3600),
        (2, 3600),
        (3, 14400),
        (5, 14400),
        (6, 43200),
        (9, 43200),
        (10, 86400),
        (20, 86400),
    ],
)
def test_no_1080p_backoff_s_boundaries(miss: int, expected: int) -> None:
    assert schedule_no_1080p_backoff_s(miss) == expected


# ---------------------------------------------------------------------------
# Shared helper: build a minimal track dict
# ---------------------------------------------------------------------------


def _make_track(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "track_id": "t1",
        "user_id": 12345,
        "chat_id": 12345,
        "show_json": {"name": "Show"},
        "pending_json": [],
        "auto_state_json": {"enabled": True, "no_1080p_miss": {}},
        "last_probe_json": {},
        "season": 1,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 3. No1080pError raised when only lower-res results exist
# ---------------------------------------------------------------------------


async def test_no_1080p_error_raised_when_lower_res_only(mock_ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "patchy_bot.handlers.schedule.asyncio.to_thread",
        AsyncMock(
            return_value=[
                {
                    "fileName": "Show.S01E01.720p.WEB-DL",
                    "name": "Show.S01E01.720p.WEB-DL",
                    "nbSeeders": 50,
                    "fileSize": 1_000_000_000,
                },
                {
                    "fileName": "Show.S01E01.480p.HDTV",
                    "name": "Show.S01E01.480p.HDTV",
                    "nbSeeders": 30,
                    "fileSize": 500_000_000,
                },
            ]
        ),
    )

    score_720 = MagicMock()
    score_720.resolution_tier = 2  # 720p — below threshold
    score_480 = MagicMock()
    score_480.resolution_tier = 1  # 480p — below threshold

    def fake_filters(rows: list[dict], **kw: Any) -> list[dict]:
        for r in rows:
            if "720p" in r.get("fileName", ""):
                r["_quality_score"] = score_720
            else:
                r["_quality_score"] = score_480
        return rows

    mock_ctx.store.get_defaults = MagicMock(return_value={"default_min_seeds": 0})
    track = _make_track()

    with pytest.raises(No1080pError) as exc_info:
        await schedule_download_episode(
            mock_ctx,
            track,
            "S01E01",
            apply_filters_fn=fake_filters,
            do_add_fn=AsyncMock(),
        )

    assert exc_info.value.lower_res_count == 2
    assert exc_info.value.code == "S01E01"


# ---------------------------------------------------------------------------
# 4. No1080pError NOT raised when a 1080p result is present
# ---------------------------------------------------------------------------


async def test_no_1080p_error_not_raised_when_1080p_present(mock_ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "patchy_bot.handlers.schedule.asyncio.to_thread",
        AsyncMock(
            return_value=[
                {
                    "fileName": "Show.S01E01.1080p.WEB-DL",
                    "name": "Show.S01E01.1080p.WEB-DL",
                    "nbSeeders": 50,
                    "fileSize": 2_000_000_000,
                    "hash": "a" * 40,
                },
            ]
        ),
    )

    score_1080 = MagicMock()
    score_1080.resolution_tier = 3  # 1080p — meets threshold
    score_1080.format_score = 5

    def fake_filters(rows: list[dict], **kw: Any) -> list[dict]:
        for r in rows:
            r["_quality_score"] = score_1080
        return rows

    mock_ctx.store.get_defaults = MagicMock(return_value={"default_min_seeds": 0})
    mock_ctx.store.save_search = MagicMock(return_value="search-1")
    do_add = AsyncMock(
        return_value={
            "summary": "ok",
            "name": "Show.S01E01.1080p",
            "hash": "a" * 40,
            "category": "TV",
            "path": "/tv",
        }
    )
    track = _make_track()

    result = await schedule_download_episode(
        mock_ctx,
        track,
        "S01E01",
        apply_filters_fn=fake_filters,
        do_add_fn=do_add,
    )

    assert result is not None


# ---------------------------------------------------------------------------
# Shared setup for refresh_track tests
# ---------------------------------------------------------------------------


def _patch_refresh_track_deps(
    monkeypatch: pytest.MonkeyPatch, mock_ctx: Any, probe: dict[str, Any], track: dict[str, Any] | None = None
) -> None:
    """Patch schedule_probe_track and asyncio.to_thread so refresh_track runs in-process."""
    monkeypatch.setattr(
        "patchy_bot.handlers.schedule.schedule_probe_track",
        MagicMock(return_value=probe),
    )

    # Capture auto_state written to update_schedule_track
    saved_kwargs: dict[str, Any] = {}

    def fake_update(_track_id: str, **kwargs: Any) -> None:
        saved_kwargs.update(kwargs)

    mock_ctx.store.update_schedule_track = MagicMock(side_effect=fake_update)

    # Return the track with the captured auto_state from the update call
    base_track = dict(track or _make_track())

    def fake_get_any(_track_id: str) -> dict[str, Any]:
        result = dict(base_track)
        if "auto_state_json" in saved_kwargs:
            result["auto_state_json"] = saved_kwargs["auto_state_json"]
        if "pending_json" in saved_kwargs:
            result["pending_json"] = saved_kwargs["pending_json"]
        return result

    mock_ctx.store.get_schedule_track_any = MagicMock(side_effect=fake_get_any)

    # Pass-through: run the callable synchronously so store methods execute
    monkeypatch.setattr(
        "patchy_bot.handlers.schedule.asyncio.to_thread",
        AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw)),
    )
    # qbt.list_torrents is called by schedule_reconcile_pending
    mock_ctx.qbt.list_torrents = MagicMock(return_value=[])


def _minimal_probe(codes: list[str] | None = None) -> dict[str, Any]:
    codes = codes or ["S01E01"]
    return {
        "actionable_missing_codes": codes,
        "missing_codes": codes,
        "present_codes": [],
        "show": {"name": "Show"},
        "next_air_ts": None,
        "signature": None,
        "season": 1,
    }


def _insert_track(mock_ctx: Any, auto_state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Insert a real schedule track row and return it with an overridden auto_state_json."""
    show = {"id": 9999, "name": "Show"}
    probe = {"pending_codes": [], "signature": None, "next_air_ts": None}
    initial_auto = auto_state or {"enabled": True, "no_1080p_miss": {}}
    _, track = mock_ctx.store.create_schedule_track(
        user_id=12345,
        chat_id=12345,
        show=show,
        season=1,
        probe=probe,
        next_check_at=now_ts() + 3600,
        initial_auto_state=initial_auto,
    )
    return track


# ---------------------------------------------------------------------------
# 5. refresh_track increments miss counter on No1080pError
# ---------------------------------------------------------------------------


async def test_refresh_track_increments_miss_on_no_1080p(mock_ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    track = _make_track()
    probe = _minimal_probe()
    _patch_refresh_track_deps(monkeypatch, mock_ctx, probe, track=track)

    updated, _ = await schedule_refresh_track(
        mock_ctx,
        track,
        qbt_category_aliases_fn=MagicMock(return_value={"TV"}),
        should_attempt_auto_fn=MagicMock(return_value=(True, ["S01E01"])),
        attempt_auto_acquire_fn=AsyncMock(side_effect=No1080pError("S01E01", 3)),
    )

    auto_state = updated["auto_state_json"]
    assert auto_state["no_1080p_miss"]["S01E01"] == 1
    assert auto_state["next_auto_retry_at"] is not None
    assert abs(auto_state["next_auto_retry_at"] - (now_ts() + 3600)) < 10


# ---------------------------------------------------------------------------
# 6. refresh_track escalates backoff at miss 3 (starts at 2)
# ---------------------------------------------------------------------------


async def test_refresh_track_escalates_backoff_at_miss_3(mock_ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # Pre-seed miss count at 2 — next call makes it 3
    track = _make_track(auto_state_json={"enabled": True, "no_1080p_miss": {"S01E01": 2}})
    probe = _minimal_probe()
    _patch_refresh_track_deps(monkeypatch, mock_ctx, probe, track=track)

    updated, _ = await schedule_refresh_track(
        mock_ctx,
        track,
        qbt_category_aliases_fn=MagicMock(return_value={"TV"}),
        should_attempt_auto_fn=MagicMock(return_value=(True, ["S01E01"])),
        attempt_auto_acquire_fn=AsyncMock(side_effect=No1080pError("S01E01", 2)),
    )

    auto_state = updated["auto_state_json"]
    assert auto_state["no_1080p_miss"]["S01E01"] == 3
    # miss 3 triggers 4-hour (14400s) backoff
    assert abs(auto_state["next_auto_retry_at"] - (now_ts() + 14400)) < 10


# ---------------------------------------------------------------------------
# 7. refresh_track clears miss counter on successful acquisition
# ---------------------------------------------------------------------------


async def test_refresh_track_resets_miss_on_success(mock_ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # Pre-seed with 3 misses
    track = _make_track(auto_state_json={"enabled": True, "no_1080p_miss": {"S01E01": 3}})
    probe = _minimal_probe()
    _patch_refresh_track_deps(monkeypatch, mock_ctx, probe, track=track)

    success_result = {
        "summary": "ok",
        "name": "Show.S01E01.1080p",
        "hash": "b" * 40,
        "category": "TV",
        "path": "/tv",
    }

    updated, _ = await schedule_refresh_track(
        mock_ctx,
        track,
        qbt_category_aliases_fn=MagicMock(return_value={"TV"}),
        should_attempt_auto_fn=MagicMock(return_value=(True, ["S01E01"])),
        attempt_auto_acquire_fn=AsyncMock(return_value=success_result),
    )

    auto_state = updated["auto_state_json"]
    # "S01E01" must be removed from the miss dict after a successful download
    assert "S01E01" not in auto_state.get("no_1080p_miss", {})


# ---------------------------------------------------------------------------
# 8. notify_no_1080p_fn called exactly once when miss reaches 3
# ---------------------------------------------------------------------------


async def test_notify_called_at_miss_3_only(mock_ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # Pre-seed miss count at 2 — one more call makes it 3 and should notify
    track = _make_track(auto_state_json={"enabled": True, "no_1080p_miss": {"S01E01": 2}})
    probe = _minimal_probe()
    _patch_refresh_track_deps(monkeypatch, mock_ctx, probe, track=track)

    notify_spy = AsyncMock()

    await schedule_refresh_track(
        mock_ctx,
        track,
        allow_notify=True,
        qbt_category_aliases_fn=MagicMock(return_value={"TV"}),
        should_attempt_auto_fn=MagicMock(return_value=(True, ["S01E01"])),
        attempt_auto_acquire_fn=AsyncMock(side_effect=No1080pError("S01E01", 2)),
        notify_no_1080p_fn=notify_spy,
    )

    notify_spy.assert_called_once()
    call_args = notify_spy.call_args[0]
    assert call_args[1] == "S01E01"  # code
    assert call_args[2] == 3  # miss_count
