"""Full Series Download engine (Phase B, Task 4).

Sequential, pack-first download pipeline:

  1. For each season (ascending) in the bundle:
     a. Re-check Plex inventory for this show.
     b. Skip if the season is already complete.
     c. Try a season-pack search; if a pack is found:
        - If the season was partial, delete existing episode files for this
          show + season via ``path_safety.safe_delete_file`` so Plex can
          re-index the pack cleanly.
        - Stage the pack row and call ``do_add``.
        - Wait for Plex to report the season as present.
     d. Otherwise, fall back to individual episodes.
  2. After every season, keep going until the cancel event fires or all
     seasons are processed.

All qBittorrent / store calls go through ``asyncio.to_thread`` because the
underlying clients are synchronous. The engine never holds a lock across an
``await`` and never uses ``time.sleep`` — only ``asyncio.sleep``.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..path_safety import PathSafetyError, safe_delete_file
from ..types import HandlerContext
from ..ui import keyboards as kb_mod
from ..ui import text as text_mod
from ..utils import extract_episode_codes, normalize_title
from . import schedule as schedule_handler
from . import search as search_handler

LOG = logging.getLogger("qbtg.full_series")

# Poll intervals (seconds). Tests monkeypatch asyncio.sleep, so wall clock
# values don't affect correctness.
QBT_POLL_INTERVAL_S = 10
PLEX_POLL_INTERVAL_S = 30
DEFAULT_SEASON_TIMEOUT_S = 24 * 3600
DEFAULT_EPISODE_TIMEOUT_S = 2 * 3600


@dataclass
class FullSeriesState:
    """Mutable state for a running full-series download."""

    show_name: str
    total_seasons: int
    total_episodes: int
    available_seasons: list[int] = field(default_factory=list)
    completed_seasons: list[dict[str, Any]] = field(default_factory=list)
    failed_seasons: list[dict[str, Any]] = field(default_factory=list)
    skipped_seasons: list[dict[str, Any]] = field(default_factory=list)
    current_season: int | None = None
    current_torrent_hash: str | None = None
    current_torrent_name: str | None = None
    current_progress_pct: float = 0.0
    current_size_bytes: int = 0
    current_downloaded_bytes: int = 0
    current_eta_s: int | None = None


@dataclass
class FullSeriesResult:
    """Terminal result returned by :func:`run_full_series_download`."""

    state: FullSeriesState
    cancelled: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _season_codes_from_bundle(bundle: dict[str, Any], season: int) -> set[str]:
    codes: set[str] = set()
    for ep in list(bundle.get("episodes") or []):
        if int(ep.get("season") or 0) != int(season):
            continue
        code = str(ep.get("code") or "").strip()
        if code:
            codes.add(code)
    return codes


async def _render_status(
    status_message: Any,
    text: str,
    keyboard: Any,
) -> None:
    """Edit the live status message; ignore 'not modified' responses."""
    if status_message is None:
        return
    try:
        await status_message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    except Exception as exc:
        msg = str(exc).lower()
        if "not modified" in msg:
            return
        LOG.warning("full_series status edit failed: %s", exc)


async def _refresh_state_from_qbt(ctx: HandlerContext, state: FullSeriesState) -> None:
    """Pull torrent progress from qBT into the state (no-op if no hash)."""
    h = state.current_torrent_hash
    if not h:
        return
    try:
        info = await asyncio.to_thread(ctx.qbt.get_torrent, h)
    except Exception:
        return
    if not info:
        return
    try:
        progress = float(info.get("progress") or 0.0)
        state.current_progress_pct = max(0.0, min(100.0, progress * 100.0))
        state.current_size_bytes = int(info.get("size") or 0)
        state.current_downloaded_bytes = int(info.get("downloaded") or info.get("completed") or 0)
        eta = info.get("eta")
        state.current_eta_s = int(eta) if eta is not None else None
        name = info.get("name")
        if name and not state.current_torrent_name:
            state.current_torrent_name = str(name)
    except Exception:
        LOG.debug("full_series: failed to parse torrent info", exc_info=True)


def _delete_partial_season_files(
    ctx: HandlerContext,
    show_name: str,
    season: int,
    *,
    delete_fn: Any = None,
) -> list[str]:
    """Delete existing episode files for ``show`` + ``season`` within tv_path.

    Returns the list of paths that were deleted. Any file that fails the
    path-safety guards causes a ``PathSafetyError`` to bubble up — the caller
    is expected to abort the season on any error.

    ``delete_fn`` is injectable for tests; defaults to
    :func:`path_safety.safe_delete_file`.
    """
    delete_fn = delete_fn or (lambda p, *, base: safe_delete_file(p, base=base))
    base = Path(ctx.cfg.tv_path)
    if not os.path.isdir(str(base)):
        return []

    want_norm = normalize_title(show_name)
    want_tokens = want_norm.split() if want_norm else []
    season_prefix = f"S{int(season):02d}E"
    deleted: list[str] = []

    def _dir_matches_show(dir_name: str) -> bool:
        if not want_tokens:
            return False
        dir_tokens = normalize_title(dir_name).split()
        if len(dir_tokens) < len(want_tokens):
            return False
        if dir_tokens[: len(want_tokens)] != want_tokens:
            return False
        # Exact match, or followed by a 4-digit year disambiguator (e.g.
        # "Lost" should match "Lost 2004" but not "Lost World").
        if len(dir_tokens) == len(want_tokens):
            return True
        next_token = dir_tokens[len(want_tokens)]
        return next_token.isdigit() and len(next_token) == 4

    for entry in os.scandir(str(base)):
        if not entry.is_dir(follow_symlinks=False):
            continue
        if not _dir_matches_show(entry.name):
            continue
        for dirpath, dirnames, filenames in os.walk(entry.path, topdown=True, followlinks=False):
            # Do not descend into symlinked directories.
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
            for filename in filenames:
                full = os.path.join(dirpath, filename)
                if os.path.islink(full):
                    continue
                codes = extract_episode_codes(filename)
                if not any(code.startswith(season_prefix) for code in codes):
                    continue
                # Invoke the injected delete function; it runs all guards.
                delete_fn(Path(full), base=base)
                deleted.append(full)
    return deleted


def _trigger_plex_scan(ctx: HandlerContext) -> None:
    """Best-effort Plex TV-library rescan. Swallows any failure."""
    try:
        ctx.plex.refresh_all_by_type(["show"])
    except Exception:
        LOG.debug("full_series: plex refresh failed", exc_info=True)


async def _stage_and_add(
    ctx: HandlerContext,
    *,
    user_id: int,
    row: dict[str, Any],
    query: str,
    media_type: str,
    do_add_fn: Any,
) -> Any:
    """Persist a single-row search and delegate to ``do_add``."""
    search_id = await asyncio.to_thread(
        ctx.store.save_search,
        user_id,
        query,
        {
            "query": query,
            "plugin": "enabled",
            "search_cat": "tv",
            "media_hint": "tv",
            "sort": "full-series",
            "order": "desc",
            "limit": 1,
        },
        [row],
        media_type="episode",
    )
    # save_search returns a str; newer versions may return tuple. Normalise.
    if isinstance(search_id, tuple):
        search_id = search_id[0]
    return await do_add_fn(user_id, str(search_id), 1, media_type)


async def _wait_for_codes(
    ctx: HandlerContext,
    *,
    show_name: str,
    year: int | None,
    required: set[str],
    state: FullSeriesState,
    status_message: Any,
    cancelled: asyncio.Event,
    timeout_s: int,
) -> bool:
    """Poll ``schedule_existing_codes`` until ``required`` ⊆ present, or timeout.

    Returns True on success, False on timeout or cancellation.

    Single-loop design: every ``QBT_POLL_INTERVAL_S`` tick refreshes qBT
    progress and re-renders the status message; every ``PLEX_POLL_INTERVAL_S``
    elapsed (rounded to the tick) we re-check Plex for the required codes.
    Cancellation is checked both before any I/O and after each sleep.
    """
    elapsed = 0
    since_plex_check = PLEX_POLL_INTERVAL_S  # force a check on the first iteration
    while elapsed < timeout_s:
        if cancelled.is_set():
            return False

        if since_plex_check >= PLEX_POLL_INTERVAL_S:
            since_plex_check = 0
            try:
                present, _source, _degraded = await asyncio.to_thread(
                    schedule_handler.schedule_existing_codes, ctx, show_name, year
                )
            except Exception:
                present = set()
            if required.issubset(present):
                return True

        await _refresh_state_from_qbt(ctx, state)
        await _render_status(
            status_message,
            text_mod.full_series_status_text(state),
            kb_mod.full_series_progress_keyboard(),
        )

        await asyncio.sleep(QBT_POLL_INTERVAL_S)
        if cancelled.is_set():
            return False
        elapsed += QBT_POLL_INTERVAL_S
        since_plex_check += QBT_POLL_INTERVAL_S
    return False


async def _cancel_cleanup(ctx: HandlerContext, state: FullSeriesState) -> None:
    """Delete the in-flight torrent and its files when cancelled."""
    h = state.current_torrent_hash
    if not h:
        return
    try:
        await asyncio.to_thread(ctx.qbt.delete_torrent, h, delete_files=True)
    except Exception:
        LOG.warning("full_series: cancel delete_torrent failed", exc_info=True)


# ---------------------------------------------------------------------------
# Per-season drivers
# ---------------------------------------------------------------------------


async def _drive_season_pack(
    ctx: HandlerContext,
    *,
    user_id: int,
    show_name: str,
    year: int | None,
    season: int,
    season_codes: set[str],
    missing_in_season: set[str],
    has_partial: bool,
    state: FullSeriesState,
    status_message: Any,
    cancelled: asyncio.Event,
    do_add_fn: Any,
    delete_fn: Any,
    season_timeout_s: int,
) -> bool:
    """Attempt the season-pack path for a single season.

    Returns True if the pack was added and Plex confirmed the season.
    Returns False if there is no pack or if the wait timed out — the caller
    should fall back to individual episodes or mark the season failed.

    Raises on cancellation (caller handles cleanup).
    """
    pack_row = await schedule_handler.search_season_pack(ctx, show_name, season, user_id)
    if not pack_row:
        return False

    # Partial-season cleanup: delete existing episode files so Plex can
    # re-index the pack without ghost metadata.
    if has_partial:
        try:
            deleted = await asyncio.to_thread(
                _delete_partial_season_files,
                ctx,
                show_name,
                season,
                delete_fn=delete_fn,
            )
            if deleted:
                await asyncio.to_thread(_trigger_plex_scan, ctx)
        except PathSafetyError as exc:
            LOG.warning(
                "full_series: season %d partial cleanup blocked by path safety: %s",
                season,
                exc,
            )
            state.failed_seasons.append({"season": season, "reason": "path_safety_blocked"})
            return False
        except Exception as exc:
            LOG.warning(
                "full_series: season %d partial cleanup failed: %s",
                season,
                exc,
                exc_info=True,
            )
            state.failed_seasons.append({"season": season, "reason": "cleanup_failed"})
            return False

    if cancelled.is_set():
        return False

    query = str(pack_row.get("_season_pack_query") or f"{show_name} S{season:02d}")
    try:
        add_result = await _stage_and_add(
            ctx,
            user_id=user_id,
            row=pack_row,
            query=query,
            media_type="tv",
            do_add_fn=do_add_fn,
        )
    except Exception as exc:
        LOG.warning("full_series: do_add failed for season %d pack: %s", season, exc)
        state.failed_seasons.append({"season": season, "reason": "add_failed"})
        return False

    state.current_torrent_hash = getattr(add_result, "hash", None) or None
    state.current_torrent_name = getattr(add_result, "name", None) or str(
        pack_row.get("name") or pack_row.get("fileName") or ""
    )
    state.current_progress_pct = 0.0
    state.current_eta_s = None

    await _render_status(
        status_message,
        text_mod.full_series_status_text(state),
        kb_mod.full_series_progress_keyboard(),
    )

    success = await _wait_for_codes(
        ctx,
        show_name=show_name,
        year=year,
        required=set(missing_in_season),
        state=state,
        status_message=status_message,
        cancelled=cancelled,
        timeout_s=season_timeout_s,
    )

    if cancelled.is_set():
        return False

    if not success:
        state.failed_seasons.append({"season": season, "reason": "timeout"})
        return False

    state.completed_seasons.append(
        {
            "season": season,
            "method": "pack",
            "count": len(missing_in_season),
        }
    )
    return True


async def _drive_season_individual(
    ctx: HandlerContext,
    *,
    user_id: int,
    show_name: str,
    year: int | None,
    season: int,
    missing_in_season: set[str],
    state: FullSeriesState,
    status_message: Any,
    cancelled: asyncio.Event,
    do_add_fn: Any,
    episode_timeout_s: int,
) -> None:
    """Fallback: download individual episodes for a single season."""
    downloaded = 0
    not_found: list[str] = []

    for code in sorted(missing_in_season):
        if cancelled.is_set():
            return

        query = f"{show_name} {code}"
        try:
            raw_rows = await asyncio.to_thread(
                ctx.qbt.search,
                query,
                plugin="enabled",
                search_cat="tv",
                timeout_s=int(getattr(ctx.cfg, "search_timeout_s", 45)),
                poll_interval_s=float(getattr(ctx.cfg, "poll_interval_s", 1.0)),
                early_exit_min_results=max(int(getattr(ctx.cfg, "search_early_exit_min_results", 12)), 12),
                early_exit_idle_s=float(getattr(ctx.cfg, "search_early_exit_idle_s", 2.5)),
                early_exit_max_wait_s=float(getattr(ctx.cfg, "search_early_exit_max_wait_s", 12.0)),
            )
        except Exception as exc:
            LOG.warning("full_series: episode search failed for %s: %s", code, exc)
            not_found.append(code)
            continue

        try:
            filtered = search_handler.apply_filters(
                raw_rows,
                min_seeds=0,
                min_size=None,
                max_size=None,
                min_quality=ctx.cfg.default_min_quality,
            )
            filtered = search_handler.deduplicate_results(filtered)
        except Exception as exc:
            LOG.debug("full_series: filter/dedup failed: %s", exc, exc_info=True)
            filtered = list(raw_rows)

        season_num = int(code[1:3])
        episode_num = int(code[4:6])
        exact = [
            row
            for row in filtered
            if schedule_handler.schedule_row_matches_episode(
                str(row.get("fileName") or row.get("name") or ""),
                season_num,
                episode_num,
            )
        ]
        if not exact:
            not_found.append(code)
            continue

        # Pick top-ranked exact match.
        ranked = sorted(
            exact,
            key=lambda row: schedule_handler.schedule_episode_rank_key(row, show_name, season_num, episode_num),
            reverse=True,
        )
        chosen = dict(ranked[0])
        chosen["_episode_code"] = code

        try:
            add_result = await _stage_and_add(
                ctx,
                user_id=user_id,
                row=chosen,
                query=query,
                media_type="tv",
                do_add_fn=do_add_fn,
            )
        except Exception as exc:
            LOG.warning("full_series: do_add failed for %s: %s", code, exc)
            not_found.append(code)
            continue

        state.current_torrent_hash = getattr(add_result, "hash", None) or None
        state.current_torrent_name = getattr(add_result, "name", None) or str(
            chosen.get("name") or chosen.get("fileName") or ""
        )
        state.current_progress_pct = 0.0
        state.current_eta_s = None

        await _render_status(
            status_message,
            text_mod.full_series_status_text(state),
            kb_mod.full_series_progress_keyboard(),
        )

        success = await _wait_for_codes(
            ctx,
            show_name=show_name,
            year=year,
            required={code},
            state=state,
            status_message=status_message,
            cancelled=cancelled,
            timeout_s=episode_timeout_s,
        )
        if cancelled.is_set():
            return
        if not success:
            not_found.append(code)
            continue
        downloaded += 1
        state.current_torrent_hash = None
        state.current_torrent_name = None
        state.current_progress_pct = 0.0

    if downloaded > 0:
        entry: dict[str, Any] = {
            "season": season,
            "method": "individual",
            "count": downloaded,
        }
        if not_found:
            entry["missing_episodes"] = not_found
        state.completed_seasons.append(entry)
    else:
        state.failed_seasons.append({"season": season, "reason": "no_results"})


# ---------------------------------------------------------------------------
# Primary entry point
# ---------------------------------------------------------------------------


async def run_full_series_download(
    ctx: HandlerContext,
    *,
    user_id: int,
    chat_id: int,
    show_bundle: dict[str, Any],
    show_name: str,
    year: int | None,
    status_message: Any,
    cancelled: asyncio.Event,
    do_add_fn: Any,
    delete_fn: Any = None,
) -> FullSeriesResult:
    """Run the sequential, pack-first full-series download pipeline.

    ``chat_id`` is currently unused by the engine (the status message already
    carries its chat context) but is kept in the signature so future
    notifications can bypass the edited message if needed.
    """
    del chat_id  # reserved for future out-of-band notifications

    total_episodes = len(list(show_bundle.get("episodes") or []))
    available_seasons = sorted(int(s) for s in list(show_bundle.get("available_seasons") or []) if int(s) > 0)
    state = FullSeriesState(
        show_name=show_name,
        total_seasons=len(available_seasons),
        total_episodes=total_episodes,
        available_seasons=list(available_seasons),
    )

    season_timeout_s = int(getattr(ctx.cfg, "full_series_season_timeout_s", DEFAULT_SEASON_TIMEOUT_S))
    episode_timeout_s = int(getattr(ctx.cfg, "full_series_episode_timeout_s", DEFAULT_EPISODE_TIMEOUT_S))

    await _render_status(
        status_message,
        text_mod.full_series_status_text(state),
        kb_mod.full_series_progress_keyboard(),
    )

    engine_exc: BaseException | None = None
    try:
        for season in available_seasons:
            if cancelled.is_set():
                break

            state.current_season = season
            state.current_torrent_hash = None
            state.current_torrent_name = None
            state.current_progress_pct = 0.0
            state.current_eta_s = None

            try:
                present, _source, _degraded = await asyncio.to_thread(
                    schedule_handler.schedule_existing_codes, ctx, show_name, year
                )
            except Exception:
                present = set()

            season_codes = _season_codes_from_bundle(show_bundle, season)
            if not season_codes:
                state.skipped_seasons.append({"season": season, "reason": "empty"})
                continue

            have_in_season = season_codes & present
            missing_in_season = season_codes - present

            if not missing_in_season:
                state.skipped_seasons.append({"season": season, "reason": "already_in_plex"})
                state.current_season = None
                await _render_status(
                    status_message,
                    text_mod.full_series_status_text(state),
                    kb_mod.full_series_progress_keyboard(),
                )
                continue

            has_partial = bool(have_in_season)

            pack_ok = await _drive_season_pack(
                ctx,
                user_id=user_id,
                show_name=show_name,
                year=year,
                season=season,
                season_codes=season_codes,
                missing_in_season=missing_in_season,
                has_partial=has_partial,
                state=state,
                status_message=status_message,
                cancelled=cancelled,
                do_add_fn=do_add_fn,
                delete_fn=delete_fn,
                season_timeout_s=season_timeout_s,
            )

            if cancelled.is_set():
                break

            # Structural failures (bad cleanup guard, do_add rejection) mean
            # the individual path can't help either. Timeouts and cleanup IO
            # errors are recoverable — retry per-episode.
            structural = {"path_safety_blocked", "add_failed"}
            season_fail = next(
                (e for e in state.failed_seasons if e.get("season") == season),
                None,
            )
            should_fallback = not pack_ok and (season_fail is None or season_fail.get("reason") not in structural)
            if should_fallback:
                if season_fail is not None:
                    state.failed_seasons.remove(season_fail)
                await _drive_season_individual(
                    ctx,
                    user_id=user_id,
                    show_name=show_name,
                    year=year,
                    season=season,
                    missing_in_season=missing_in_season,
                    state=state,
                    status_message=status_message,
                    cancelled=cancelled,
                    do_add_fn=do_add_fn,
                    episode_timeout_s=episode_timeout_s,
                )

            state.current_season = None
            state.current_torrent_hash = None
            state.current_torrent_name = None
            await _render_status(
                status_message,
                text_mod.full_series_status_text(state),
                kb_mod.full_series_progress_keyboard(),
            )
    except BaseException as exc:
        engine_exc = exc
        raise
    finally:
        # Always delete the in-flight torrent if we're exiting abnormally
        # (cancel OR uncaught exception). Idempotent — no-op if no hash.
        if (cancelled.is_set() or engine_exc is not None) and state.current_torrent_hash:
            try:
                await _cancel_cleanup(ctx, state)
            except Exception:
                LOG.warning("full_series: finally cleanup failed", exc_info=True)

    was_cancelled = cancelled.is_set()
    if was_cancelled:
        # Mark unfinished seasons as skipped (cancelled).
        seen = {
            int(e.get("season") or 0) for e in state.completed_seasons + state.failed_seasons + state.skipped_seasons
        }
        if state.current_season is not None:
            seen.add(int(state.current_season))
        for s in available_seasons:
            if int(s) not in seen:
                state.skipped_seasons.append({"season": int(s), "reason": "cancelled"})
        state.current_season = None
        state.current_torrent_hash = None
        state.current_torrent_name = None
        await _render_status(
            status_message,
            text_mod.full_series_cancelled_text(state),
            kb_mod.full_series_cancelled_keyboard(),
        )
    else:
        await _render_status(
            status_message,
            text_mod.full_series_complete_text(state),
            kb_mod.full_series_complete_keyboard(),
        )

    return FullSeriesResult(state=state, cancelled=was_cancelled)
