"""Tests for the Full Series Download engine."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from patchy_bot.handlers import full_series as fs_mod
from patchy_bot.handlers.full_series import (
    FullSeriesState,
    run_full_series_download,
)
from patchy_bot.ui import text as text_mod

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_bundle(seasons: int, eps_per_season: int) -> dict[str, Any]:
    episodes = []
    airdate_base = 2020
    for s in range(1, seasons + 1):
        for e in range(1, eps_per_season + 1):
            episodes.append(
                {
                    "season": s,
                    "number": e,
                    "code": f"S{s:02d}E{e:02d}",
                    "airdate": f"{airdate_base + s - 1}-01-0{min(e, 9)}",
                    "air_ts": 0,
                }
            )
    return {
        "id": 1,
        "name": "Example Show",
        "year": airdate_base,
        "available_seasons": list(range(1, seasons + 1)),
        "episodes": episodes,
    }


def _make_ctx(
    *,
    present_by_call: list[set[str]] | None = None,
    pack_rows: dict[int, dict[str, Any] | None] | None = None,
    search_rows: list[dict[str, Any]] | None = None,
) -> Any:
    """Build a ctx SimpleNamespace with minimal attributes."""

    class _Store:
        def __init__(self) -> None:
            self.saved: list[dict[str, Any]] = []
            self._counter = 0

        def save_search(self, user_id, query, options, rows, *, media_type="movie"):
            self._counter += 1
            sid = f"sid-{self._counter}"
            self.saved.append({"sid": sid, "rows": rows, "query": query})
            return sid

    class _Qbt:
        def __init__(self) -> None:
            self.deleted: list[str] = []
            self.get_calls: list[str] = []

        def get_torrent(self, torrent_hash: str):
            self.get_calls.append(torrent_hash)
            return {
                "hash": torrent_hash,
                "name": "pack-name",
                "progress": 0.5,
                "size": 1000,
                "downloaded": 500,
                "eta": 120,
            }

        def delete_torrent(self, torrent_hash: str, *, delete_files: bool = False):
            self.deleted.append(torrent_hash)

        def search(self, query: str, **_kwargs: Any):
            return list(search_rows or [])

    class _Plex:
        def refresh_all_by_type(self, types):
            return list(types)

    cfg = SimpleNamespace(
        tv_path="/tmp/tv",
        default_min_quality=720,
        search_timeout_s=15,
        poll_interval_s=0.01,
        search_early_exit_min_results=12,
        search_early_exit_idle_s=0.01,
        search_early_exit_max_wait_s=0.05,
        full_series_season_timeout_s=2,
        full_series_episode_timeout_s=2,
    )

    ctx = SimpleNamespace(
        cfg=cfg,
        store=_Store(),
        qbt=_Qbt(),
        plex=_Plex(),
    )
    return ctx


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(*_a: Any, **_kw: Any) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _noop)


# ---------------------------------------------------------------------------
# Confirm text tests
# ---------------------------------------------------------------------------


def test_confirm_text_counts() -> None:
    text = text_mod.full_series_confirm_text(
        show_name="Example Show",
        network="HBO",
        year_start=2010,
        year_end=2019,
        total_seasons=8,
        total_episodes=73,
        in_plex=12,
        to_download=61,
    )
    assert "8 seasons · 73 episodes" in text
    assert "✅ 12 episodes already in Plex" in text
    assert "61 episodes to download" in text
    assert "HBO" in text
    assert "2010" in text and "2019" in text


def test_confirm_text_all_in_plex() -> None:
    text = text_mod.full_series_confirm_text(
        show_name="Example Show",
        network="HBO",
        year_start=2010,
        year_end=2010,
        total_seasons=1,
        total_episodes=10,
        in_plex=10,
        to_download=0,
    )
    assert "0 episodes to download" in text
    assert "✅ 10 episodes already in Plex" in text


# ---------------------------------------------------------------------------
# Engine tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_season_in_plex_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _make_bundle(seasons=1, eps_per_season=2)
    ctx = _make_ctx()
    # Plex reports season 1 already complete.
    monkeypatch.setattr(
        fs_mod.schedule_handler,
        "schedule_existing_codes",
        lambda _c, _n, _y: ({"S01E01", "S01E02"}, "Plex", False),
    )

    status_message = MagicMock()
    status_message.edit_text = AsyncMock()

    cancelled = asyncio.Event()
    do_add = AsyncMock()
    result = await run_full_series_download(
        ctx,
        user_id=1,
        chat_id=10,
        show_bundle=bundle,
        show_name="Example Show",
        year=2020,
        status_message=status_message,
        cancelled=cancelled,
        do_add_fn=do_add,
    )
    assert result.cancelled is False
    assert any(s.get("season") == 1 and s.get("reason") == "already_in_plex" for s in result.state.skipped_seasons)
    do_add.assert_not_called()


@pytest.mark.asyncio
async def test_pack_found_queues_and_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _make_bundle(seasons=1, eps_per_season=2)
    ctx = _make_ctx()

    # First call: nothing in Plex. Second call (after wait): season 1 present.
    call_log: list[int] = []

    def _present(_c, _n, _y):
        call_log.append(len(call_log))
        if len(call_log) == 1:
            return (set(), "Plex", False)
        return ({"S01E01", "S01E02"}, "Plex", False)

    monkeypatch.setattr(fs_mod.schedule_handler, "schedule_existing_codes", _present)

    async def _pack(_ctx, _show, _season, _user):
        return {"name": "Example Show S01 1080p", "_season_pack_query": "Example Show S01 1080p"}

    monkeypatch.setattr(fs_mod.schedule_handler, "search_season_pack", _pack)

    do_add = AsyncMock(return_value=SimpleNamespace(hash="abc123", name="Example Show S01 1080p"))

    status_message = MagicMock()
    status_message.edit_text = AsyncMock()

    result = await run_full_series_download(
        ctx,
        user_id=1,
        chat_id=10,
        show_bundle=bundle,
        show_name="Example Show",
        year=2020,
        status_message=status_message,
        cancelled=asyncio.Event(),
        do_add_fn=do_add,
    )
    assert result.cancelled is False
    assert len(result.state.completed_seasons) == 1
    assert result.state.completed_seasons[0]["method"] == "pack"
    assert result.state.completed_seasons[0]["count"] == 2
    do_add.assert_awaited()


@pytest.mark.asyncio
async def test_no_pack_falls_back_to_individual(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _make_bundle(seasons=1, eps_per_season=2)
    ctx = _make_ctx()

    seq: list[set[str]] = [set(), {"S01E01"}, {"S01E01", "S01E02"}]
    idx = {"i": 0}

    def _present(_c, _n, _y):
        i = min(idx["i"], len(seq) - 1)
        idx["i"] += 1
        return (seq[i], "Plex", False)

    monkeypatch.setattr(fs_mod.schedule_handler, "schedule_existing_codes", _present)

    async def _pack(_ctx, _show, _season, _user):
        return None

    monkeypatch.setattr(fs_mod.schedule_handler, "search_season_pack", _pack)
    monkeypatch.setattr(
        fs_mod.schedule_handler,
        "schedule_row_matches_episode",
        lambda _name, _s, _e: True,
    )
    monkeypatch.setattr(
        fs_mod.schedule_handler,
        "schedule_episode_rank_key",
        lambda *_a, **_kw: (1,),
    )

    class _FakeQbt:
        def get_torrent(self, h):
            return {"progress": 1.0, "size": 1, "downloaded": 1, "eta": 0, "name": "ep"}

        def delete_torrent(self, h, *, delete_files=False):
            pass

        def search(self, q, **_kw):
            return [{"name": f"Example Show {q.split()[-1]}", "nbSeeders": 10, "fileSize": 100}]

    ctx.qbt = _FakeQbt()

    monkeypatch.setattr(
        fs_mod.search_handler,
        "apply_filters",
        lambda rows, **_kw: list(rows),
    )
    monkeypatch.setattr(
        fs_mod.search_handler,
        "deduplicate_results",
        lambda rows: list(rows),
    )

    do_add = AsyncMock(return_value=SimpleNamespace(hash="h1", name="ep"))
    status_message = MagicMock()
    status_message.edit_text = AsyncMock()

    result = await run_full_series_download(
        ctx,
        user_id=1,
        chat_id=10,
        show_bundle=bundle,
        show_name="Example Show",
        year=2020,
        status_message=status_message,
        cancelled=asyncio.Event(),
        do_add_fn=do_add,
    )
    assert result.cancelled is False
    assert len(result.state.completed_seasons) == 1
    assert result.state.completed_seasons[0]["method"] == "individual"
    assert do_add.await_count >= 1


@pytest.mark.asyncio
async def test_partial_season_no_pack_downloads_only_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _make_bundle(seasons=1, eps_per_season=3)
    ctx = _make_ctx()

    # Season 1 has E01 already; we need E02 and E03.
    seq = [
        {"S01E01"},  # first Plex check in season loop
        {"S01E01"},  # before downloading E02
        {"S01E01", "S01E02"},  # after E02 arrives
        {"S01E01", "S01E02"},  # before downloading E03
        {"S01E01", "S01E02", "S01E03"},  # after E03 arrives
    ]
    idx = {"i": 0}

    def _present(_c, _n, _y):
        i = min(idx["i"], len(seq) - 1)
        idx["i"] += 1
        return (seq[i], "Plex", False)

    monkeypatch.setattr(fs_mod.schedule_handler, "schedule_existing_codes", _present)

    async def _pack(_ctx, _show, _season, _user):
        return None

    monkeypatch.setattr(fs_mod.schedule_handler, "search_season_pack", _pack)
    monkeypatch.setattr(
        fs_mod.schedule_handler,
        "schedule_row_matches_episode",
        lambda _name, _s, _e: True,
    )
    monkeypatch.setattr(
        fs_mod.schedule_handler,
        "schedule_episode_rank_key",
        lambda *_a, **_kw: (1,),
    )
    monkeypatch.setattr(fs_mod.search_handler, "apply_filters", lambda rows, **_kw: list(rows))
    monkeypatch.setattr(fs_mod.search_handler, "deduplicate_results", lambda rows: list(rows))

    class _Qbt2:
        def get_torrent(self, h):
            return {"progress": 1.0, "size": 1, "downloaded": 1, "eta": 0, "name": "ep"}

        def delete_torrent(self, *_a, **_kw):
            pass

        def search(self, q, **_kw):
            return [{"name": f"Example Show {q.split()[-1]}", "nbSeeders": 10, "fileSize": 100}]

    ctx.qbt = _Qbt2()

    do_add = AsyncMock(return_value=SimpleNamespace(hash="h", name="ep"))
    status_message = MagicMock()
    status_message.edit_text = AsyncMock()

    await run_full_series_download(
        ctx,
        user_id=1,
        chat_id=10,
        show_bundle=bundle,
        show_name="Example Show",
        year=2020,
        status_message=status_message,
        cancelled=asyncio.Event(),
        do_add_fn=do_add,
    )
    # Exactly 2 individual downloads (E02 + E03).
    assert do_add.await_count == 2


@pytest.mark.asyncio
async def test_failed_season_skipped_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _make_bundle(seasons=2, eps_per_season=1)
    ctx = _make_ctx()

    # Track per-season state: once S2 pack has been added, S02E01 "appears" in Plex.
    state_flag = {"s2_added": False}

    def _present(_c, _n, _y):
        present: set[str] = set()
        if state_flag["s2_added"]:
            present.add("S02E01")
        return (present, "Plex", False)

    monkeypatch.setattr(fs_mod.schedule_handler, "schedule_existing_codes", _present)

    # S01 pack: none. S02 pack: found.
    pack_calls = {"i": 0}

    async def _pack(_ctx, _show, season, _user):
        pack_calls["i"] += 1
        if season == 2:
            return {
                "name": "Example Show S02 1080p",
                "_season_pack_query": "Example Show S02 1080p",
            }
        return None

    monkeypatch.setattr(fs_mod.schedule_handler, "search_season_pack", _pack)

    # S01 episode search returns nothing.
    class _Qbt3:
        def get_torrent(self, h):
            return {"progress": 1.0, "size": 1, "downloaded": 1, "eta": 0, "name": "ep"}

        def delete_torrent(self, *_a, **_kw):
            pass

        def search(self, q, **_kw):
            return []

    ctx.qbt = _Qbt3()
    monkeypatch.setattr(fs_mod.search_handler, "apply_filters", lambda rows, **_kw: list(rows))
    monkeypatch.setattr(fs_mod.search_handler, "deduplicate_results", lambda rows: list(rows))
    monkeypatch.setattr(
        fs_mod.schedule_handler,
        "schedule_row_matches_episode",
        lambda *_a, **_kw: True,
    )

    async def _mark_added(user_id, search_id, idx, media_type):
        state_flag["s2_added"] = True
        return SimpleNamespace(hash="h", name="pack")

    do_add = AsyncMock(side_effect=_mark_added)
    status_message = MagicMock()
    status_message.edit_text = AsyncMock()

    result = await run_full_series_download(
        ctx,
        user_id=1,
        chat_id=10,
        show_bundle=bundle,
        show_name="Example Show",
        year=2020,
        status_message=status_message,
        cancelled=asyncio.Event(),
        do_add_fn=do_add,
    )
    # Season 1 failed (no results); season 2 completed via pack.
    assert any(f["season"] == 1 for f in result.state.failed_seasons)
    assert any(c["season"] == 2 and c["method"] == "pack" for c in result.state.completed_seasons)


@pytest.mark.asyncio
async def test_cancel_stops_current_and_marks_remaining_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _make_bundle(seasons=3, eps_per_season=1)
    ctx = _make_ctx()
    cancelled_event = asyncio.Event()

    async def _pack(_ctx, _show, season, _user):
        return {
            "name": f"Example Show S{season:02d} 1080p",
            "_season_pack_query": f"Example Show S{season:02d}",
        }

    monkeypatch.setattr(
        fs_mod.schedule_handler,
        "schedule_existing_codes",
        lambda _c, _n, _y: (set(), "Plex", False),
    )
    monkeypatch.setattr(fs_mod.schedule_handler, "search_season_pack", _pack)

    async def _do_add_and_cancel(user_id, search_id, idx, media_type):
        # Capture the hash first, then fire the cancel so the engine enters
        # the Plex wait loop with current_torrent_hash populated.
        cancelled_event.set()
        return SimpleNamespace(hash="abc", name="pack")

    do_add = AsyncMock(side_effect=_do_add_and_cancel)
    status_message = MagicMock()
    status_message.edit_text = AsyncMock()

    result = await run_full_series_download(
        ctx,
        user_id=1,
        chat_id=10,
        show_bundle=bundle,
        show_name="Example Show",
        year=2020,
        status_message=status_message,
        cancelled=cancelled_event,
        do_add_fn=do_add,
    )
    assert result.cancelled is True
    # The torrent we added should have been deleted during cleanup.
    assert "abc" in ctx.qbt.deleted
    # At least one remaining season marked as cancelled.
    assert any(s.get("reason") == "cancelled" for s in result.state.skipped_seasons)


@pytest.mark.asyncio
async def test_sequential_execution_only_one_torrent_at_a_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _make_bundle(seasons=2, eps_per_season=1)
    ctx = _make_ctx()

    # Each season's wait immediately resolves.
    call_idx = {"i": 0}

    def _present(_c, _n, _y):
        call_idx["i"] += 1
        if call_idx["i"] == 1:
            return (set(), "Plex", False)
        if call_idx["i"] == 2:
            return ({"S01E01"}, "Plex", False)
        if call_idx["i"] == 3:
            return ({"S01E01"}, "Plex", False)
        return ({"S01E01", "S02E01"}, "Plex", False)

    monkeypatch.setattr(fs_mod.schedule_handler, "schedule_existing_codes", _present)

    concurrent_max = {"n": 0}
    live = {"n": 0}

    async def _pack(_ctx, _show, season, _user):
        live["n"] += 1
        concurrent_max["n"] = max(concurrent_max["n"], live["n"])
        await asyncio.sleep(0)
        live["n"] -= 1
        return {
            "name": f"Example Show S{season:02d} 1080p",
            "_season_pack_query": f"Example Show S{season:02d}",
        }

    monkeypatch.setattr(fs_mod.schedule_handler, "search_season_pack", _pack)

    do_add = AsyncMock(return_value=SimpleNamespace(hash="h", name="pack"))
    status_message = MagicMock()
    status_message.edit_text = AsyncMock()

    await run_full_series_download(
        ctx,
        user_id=1,
        chat_id=10,
        show_bundle=bundle,
        show_name="Example Show",
        year=2020,
        status_message=status_message,
        cancelled=asyncio.Event(),
        do_add_fn=do_add,
    )
    assert concurrent_max["n"] <= 1


def test_status_text_mix_of_states() -> None:
    state = FullSeriesState(
        show_name="Example Show",
        total_seasons=3,
        total_episodes=30,
    )
    state.completed_seasons.append({"season": 1, "method": "pack", "count": 10})
    state.failed_seasons.append({"season": 2, "reason": "timeout"})
    state.current_season = 3
    state.current_torrent_name = "Example Show S03 1080p"
    state.current_progress_pct = 42.0

    out = text_mod.full_series_status_text(state)
    assert "✅ Season 1" in out
    assert "⚠️ Season 2" in out
    assert "⏳ Season 3" in out
    assert "42.0%" in out


@pytest.mark.asyncio
async def test_plex_inventory_refreshed_between_seasons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _make_bundle(seasons=2, eps_per_season=1)
    ctx = _make_ctx()

    calls: list[str] = []
    call_seq = [
        set(),  # S1 entry check
        {"S01E01"},  # S1 pack wait resolves
        {"S01E01"},  # S2 entry check
        {"S01E01", "S02E01"},  # S2 pack wait resolves
    ]
    idx = {"i": 0}

    def _present(_c, _n, _y):
        calls.append("present")
        i = min(idx["i"], len(call_seq) - 1)
        idx["i"] += 1
        return (call_seq[i], "Plex", False)

    monkeypatch.setattr(fs_mod.schedule_handler, "schedule_existing_codes", _present)

    async def _pack(_ctx, _show, season, _user):
        return {
            "name": f"Example Show S{season:02d} 1080p",
            "_season_pack_query": f"Example Show S{season:02d}",
        }

    monkeypatch.setattr(fs_mod.schedule_handler, "search_season_pack", _pack)

    do_add = AsyncMock(return_value=SimpleNamespace(hash="h", name="pack"))
    status_message = MagicMock()
    status_message.edit_text = AsyncMock()

    await run_full_series_download(
        ctx,
        user_id=1,
        chat_id=10,
        show_bundle=bundle,
        show_name="Example Show",
        year=2020,
        status_message=status_message,
        cancelled=asyncio.Event(),
        do_add_fn=do_add,
    )
    # At least once per season (we called it >= 2 times).
    assert calls.count("present") >= 2
