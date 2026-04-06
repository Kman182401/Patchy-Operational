"""Schedule-system helpers: TV tracking, metadata, probing, keyboards, text builders.

Extracted from BotApp -- all schedule-domain logic lives here as
module-level functions.  Static/class methods become plain functions.
Instance methods take a HandlerContext as their first argument.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from ..types import HandlerContext
from ..utils import (
    _PM,
    _h,
    _relative_time,
    episode_code,
    episode_number_from_code,
    extract_episode_codes,
    format_local_ts,
    normalize_title,
    now_ts,
)

LOG = logging.getLogger("qbtg")


# ---------------------------------------------------------------------------
# Runner interval constants
# ---------------------------------------------------------------------------


def schedule_runner_interval_s() -> int:
    return 60


def schedule_release_grace_s() -> int:
    return 90 * 60


def schedule_retry_interval_s() -> int:
    return 3600


def schedule_metadata_retry_s() -> int:
    return 15 * 60


def schedule_pending_stale_s() -> int:
    return 3 * 3600


# ---------------------------------------------------------------------------
# Cache TTL / backoff helpers
# ---------------------------------------------------------------------------


def schedule_metadata_cache_ttl_s(bundle: dict[str, Any]) -> int:
    now_value = now_ts()
    status = str(bundle.get("status") or "").strip().lower()
    if status in {"ended", "canceled", "cancelled"}:
        return 24 * 3600
    next_air_ts = 0
    for episode in list(bundle.get("episodes") or []):
        air_ts = int(episode.get("air_ts") or 0)
        if air_ts > now_value and (next_air_ts <= 0 or air_ts < next_air_ts):
            next_air_ts = air_ts
    if next_air_ts and next_air_ts - now_value <= 24 * 3600:
        return 3600
    return 6 * 3600


def schedule_metadata_retry_backoff_s(failures: int) -> int:
    if failures <= 1:
        return 15 * 60
    if failures == 2:
        return 30 * 60
    if failures == 3:
        return 60 * 60
    return 6 * 3600


def schedule_inventory_backoff_s(failures: int) -> int:
    if failures <= 1:
        return 5 * 60
    if failures == 2:
        return 15 * 60
    if failures == 3:
        return 30 * 60
    return 60 * 60


# ---------------------------------------------------------------------------
# Source health tracking
# ---------------------------------------------------------------------------


def schedule_source_snapshot(ctx: HandlerContext, key: str) -> dict[str, Any]:
    with ctx.schedule_source_state_lock:
        return dict(ctx.schedule_source_state.get(key) or {})


def schedule_mark_source_health(
    ctx: HandlerContext,
    key: str,
    *,
    ok: bool,
    detail: str | None = None,
    backoff_until: int = 0,
    effective_source: str | None = None,
) -> dict[str, Any]:
    now_value = now_ts()
    with ctx.schedule_source_state_lock:
        state = dict(ctx.schedule_source_state.get(key) or {})
        prior_status = str(state.get("status") or "unknown")
        failures = int(state.get("consecutive_failures") or 0)
        if ok:
            state["status"] = "healthy"
            state["consecutive_failures"] = 0
            state["backoff_until"] = 0
            state["last_error"] = None
            state["last_success_at"] = now_value
        else:
            failures += 1
            state["status"] = "degraded"
            state["consecutive_failures"] = failures
            state["backoff_until"] = int(backoff_until or 0)
            state["last_error"] = str(detail or "").strip() or None
        if effective_source is not None:
            state["effective_source"] = effective_source
        ctx.schedule_source_state[key] = state
    if ok and prior_status != "healthy":
        LOG.info("Schedule %s source recovered", key)
    elif not ok and prior_status != "degraded":
        LOG.warning("Schedule %s source degraded: %s", key, detail)
    return dict(state)


def schedule_should_use_plex_inventory(ctx: HandlerContext) -> bool:
    if not ctx.plex.ready():
        return False
    state = schedule_source_snapshot(ctx, "inventory")
    return int(state.get("backoff_until") or 0) <= now_ts()


# ---------------------------------------------------------------------------
# Bundle / cache helpers
# ---------------------------------------------------------------------------


def schedule_bundle_from_cache(cached: dict[str, Any] | None, *, allow_stale: bool) -> dict[str, Any] | None:
    if not cached:
        return None
    bundle = dict(cached.get("bundle_json") or {})
    if not bundle:
        return None
    now_value = now_ts()
    expires_at = int(cached.get("expires_at") or 0)
    fetched_at = int(cached.get("fetched_at") or 0)
    if expires_at > now_value:
        return bundle
    if allow_stale and fetched_at > 0 and fetched_at >= now_value - 7 * 24 * 3600:
        bundle["_metadata_stale"] = True
        bundle["_metadata_error"] = str(cached.get("last_error_text") or "").strip() or None
        return bundle
    return None


def schedule_get_show_bundle(
    ctx: HandlerContext, show_id: int, allow_stale: bool, lookup_tmdb: bool = False
) -> dict[str, Any]:
    cached = ctx.store.get_schedule_show_cache(int(show_id))
    cached_bundle = schedule_bundle_from_cache(cached, allow_stale=False)
    if cached_bundle is not None:
        if lookup_tmdb and not cached_bundle.get("tmdb_id"):
            fetched = ctx.tvmeta.get_show_bundle(int(show_id), lookup_tmdb=True)
            fetched_at = now_ts()
            ctx.store.upsert_schedule_show_cache(
                int(show_id),
                fetched,
                fetched_at,
                fetched_at + schedule_metadata_cache_ttl_s(fetched),
            )
            schedule_mark_source_health(ctx, "metadata", ok=True)
            return fetched
        return cached_bundle

    try:
        bundle = ctx.tvmeta.get_show_bundle(int(show_id), lookup_tmdb=lookup_tmdb)
        cached_tmdb_id = int((cached or {}).get("bundle_json", {}).get("tmdb_id") or 0) or None
        if cached_tmdb_id and not bundle.get("tmdb_id"):
            bundle["tmdb_id"] = cached_tmdb_id
        fetched_at = now_ts()
        ctx.store.upsert_schedule_show_cache(
            int(show_id),
            bundle,
            fetched_at,
            fetched_at + schedule_metadata_cache_ttl_s(bundle),
        )
        schedule_mark_source_health(ctx, "metadata", ok=True)
        return bundle
    except Exception as e:
        state = schedule_source_snapshot(ctx, "metadata")
        failures = int(state.get("consecutive_failures") or 0) + 1
        backoff_s = schedule_metadata_retry_backoff_s(failures)
        schedule_mark_source_health(
            ctx,
            "metadata",
            ok=False,
            detail=str(e),
            backoff_until=now_ts() + backoff_s,
        )
        stale_bundle = schedule_bundle_from_cache(cached, allow_stale=allow_stale)
        if stale_bundle is not None:
            ctx.store.upsert_schedule_show_cache(
                int(show_id),
                dict(cached.get("bundle_json") or {}),
                int(cached.get("fetched_at") or now_ts()),
                int(cached.get("expires_at") or now_ts()),
                last_error_at=now_ts(),
                last_error_text=str(e),
            )
            stale_bundle["_metadata_stale"] = True
            stale_bundle["_metadata_error"] = str(e)
            return stale_bundle
        raise


# ---------------------------------------------------------------------------
# Auto state / repair
# ---------------------------------------------------------------------------


def schedule_sanitize_auto_state(
    auto_state: dict[str, Any] | None, *, probe: dict[str, Any] | None = None
) -> dict[str, Any]:
    clean = dict(auto_state or {})
    clean.setdefault("enabled", True)
    clean.setdefault("last_auto_code", None)
    clean.setdefault("last_auto_at", None)
    clean.setdefault("retry_codes", {})
    clean.setdefault("tracking_mode", "upcoming")
    clean.setdefault("next_code", None)
    next_retry = int(clean.get("next_auto_retry_at") or 0)
    has_actionable = bool(probe and probe.get("actionable_missing_codes"))
    if not has_actionable or next_retry <= now_ts():
        clean["next_auto_retry_at"] = None
    else:
        clean["next_auto_retry_at"] = next_retry
    retry_codes = dict(clean.get("retry_codes") or {})
    clean["retry_codes"] = {str(code): int(ts) for code, ts in retry_codes.items() if int(ts or 0) > 0}
    return clean


def schedule_repair_track_state(ctx: HandlerContext, track: dict[str, Any]) -> None:
    track_id = str(track.get("track_id") or "")
    last_probe = dict(track.get("last_probe_json") or {})
    clean_auto = schedule_sanitize_auto_state(track.get("auto_state_json") or {}, probe=last_probe)
    next_air_ts = int(track.get("next_air_ts") or last_probe.get("next_air_ts") or 0) or None
    if last_probe:
        next_check_at = schedule_next_check_at(
            ctx,
            next_air_ts,
            has_actionable_missing=bool(last_probe.get("actionable_missing_codes")),
            auto_state=clean_auto,
        )
    else:
        next_check_at = now_ts() + 300
    update_fields: dict[str, Any] = {}
    if clean_auto != dict(track.get("auto_state_json") or {}):
        update_fields["auto_state_json"] = clean_auto
    if int(track.get("next_check_at") or 0) != next_check_at:
        update_fields["next_check_at"] = next_check_at
    if next_air_ts != (int(track.get("next_air_ts") or 0) or None):
        update_fields["next_air_ts"] = next_air_ts
    if update_fields:
        ctx.store.update_schedule_track(track_id, **update_fields)


def schedule_repair_all_tracks(ctx: HandlerContext) -> None:
    for track in ctx.store.list_all_schedule_tracks(True):
        schedule_repair_track_state(ctx, track)


# ---------------------------------------------------------------------------
# Flow / scheduling
# ---------------------------------------------------------------------------


def schedule_start_flow(ctx: HandlerContext, user_id: int) -> None:
    ctx.user_flow[user_id] = {"mode": "schedule", "stage": "await_show", "tracking_mode": "upcoming"}


def schedule_next_check_at(
    ctx: HandlerContext,
    next_air_ts: int | None,
    *,
    has_actionable_missing: bool,
    auto_state: dict[str, Any] | None = None,
) -> int:
    now_value = now_ts()
    auto_state = schedule_sanitize_auto_state(
        auto_state or {}, probe={"actionable_missing_codes": [1]} if has_actionable_missing else {}
    )
    next_retry = int(auto_state.get("next_auto_retry_at") or 0)
    if has_actionable_missing:
        if next_retry > now_value:
            return max(now_value + 300, next_retry)
        return now_value + 300
    if next_air_ts:
        release_ready_at = int(next_air_ts) + schedule_release_grace_s()
        if release_ready_at <= now_value:
            return now_value + 300
        delta = release_ready_at - now_value
        if delta > 7 * 24 * 3600:
            return now_value + 24 * 3600
        if delta > 24 * 3600:
            return min(now_value + 6 * 3600, release_ready_at)
        return max(now_value + 900, release_ready_at)
    return now_value + 12 * 3600


# ---------------------------------------------------------------------------
# Show info / season selection
# ---------------------------------------------------------------------------


def schedule_show_info(show: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(show.get("id") or 0),
        "name": str(show.get("name") or "Unknown show").strip(),
        "year": int(show.get("year") or 0) or None,
        "premiered": str(show.get("premiered") or "").strip(),
        "status": str(show.get("status") or "Unknown").strip() or "Unknown",
        "network": str(show.get("network") or "").strip(),
        "country": str(show.get("country") or "").strip(),
        "summary": str(show.get("summary") or "").strip(),
        "genres": list(show.get("genres") or []),
        "language": str(show.get("language") or "").strip(),
        "url": str(show.get("url") or "").strip(),
        "imdb_id": str(show.get("imdb_id") or "").strip() or None,
        "tmdb_id": int(show.get("tmdb_id") or 0) or None,
        "available_seasons": list(show.get("available_seasons") or []),
    }


def schedule_select_season(bundle: dict[str, Any]) -> int:
    available = [int(x) for x in list(bundle.get("available_seasons") or []) if int(x) > 0]
    if not available:
        return 1
    episodes = list(bundle.get("episodes") or [])
    now_value = now_ts()
    future = [
        int(ep.get("season") or 0)
        for ep in episodes
        if int(ep.get("season") or 0) > 0
        and ep.get("number") is not None
        and ep.get("air_ts")
        and int(ep.get("air_ts") or 0) > now_value
    ]
    if future:
        return max(future)
    aired = [
        int(ep.get("season") or 0)
        for ep in episodes
        if int(ep.get("season") or 0) > 0
        and ep.get("number") is not None
        and ep.get("air_ts")
        and int(ep.get("air_ts") or 0) <= now_value
    ]
    if aired:
        return max(aired)
    return max(available)


# ---------------------------------------------------------------------------
# Inventory helpers
# ---------------------------------------------------------------------------


def schedule_filesystem_inventory(ctx: HandlerContext, show_name: str, year: int | None) -> tuple[set[str], str]:
    root = ctx.cfg.tv_path
    if not os.path.isdir(root):
        return set(), f"tv folders unavailable ({root})"
    want = normalize_title(show_name)
    candidates: list[tuple[int, str]] = []
    for entry in os.scandir(root):
        if not entry.is_dir():
            continue
        title_norm = normalize_title(entry.name)
        score = 0
        if title_norm == want:
            score += 10
        elif want and want in title_norm:
            score += 6
        elif title_norm and title_norm in want:
            score += 3
        if year and str(year) in entry.name:
            score += 2
        if score > 0:
            candidates.append((score, entry.path))
    if not candidates:
        return set(), "tv folders"
    codes: set[str] = set()
    for _score, base_path in sorted(candidates, reverse=True)[:3]:
        for dirpath, _dirnames, filenames in os.walk(base_path):
            for filename in filenames:
                codes.update(extract_episode_codes(filename))
    return codes, "tv folders"


def schedule_existing_codes(ctx: HandlerContext, show_name: str, year: int | None) -> tuple[set[str], str, bool]:
    inventory_degraded = False
    if schedule_should_use_plex_inventory(ctx):
        try:
            codes, source = ctx.plex.episode_inventory(show_name, year)
            if codes or source == "plex":
                schedule_mark_source_health(ctx, "inventory", ok=True, effective_source="Plex")
                return codes, "Plex", False
        except Exception as e:
            state = schedule_source_snapshot(ctx, "inventory")
            failures = int(state.get("consecutive_failures") or 0) + 1
            inventory_degraded = True
            schedule_mark_source_health(
                ctx,
                "inventory",
                ok=False,
                detail=str(e),
                backoff_until=now_ts() + schedule_inventory_backoff_s(failures),
                effective_source="tv folders",
            )
    codes, source = schedule_filesystem_inventory(ctx, show_name, year)
    effective_source = "tv folders"
    if ctx.plex.ready() and not schedule_should_use_plex_inventory(ctx):
        inventory_degraded = True
    if not inventory_degraded:
        schedule_mark_source_health(ctx, "inventory", ok=True, effective_source=effective_source)
    return codes, source, inventory_degraded


# ---------------------------------------------------------------------------
# Probe helpers
# ---------------------------------------------------------------------------


def schedule_probe_bundle(
    ctx: HandlerContext, bundle: dict[str, Any], track: dict[str, Any] | None = None, season: int | None = None
) -> dict[str, Any]:
    show_info = schedule_show_info(bundle)
    available = [int(x) for x in list(bundle.get("available_seasons") or []) if int(x) > 0]
    chosen_season = int(season) if season and int(season) in available else schedule_select_season(bundle)
    present_all, inventory_source, inventory_degraded = schedule_existing_codes(
        ctx, show_info["name"], show_info.get("year")
    )
    pending_all = set(track.get("pending_json") or []) if track else set()
    pending_all -= present_all
    now_value = now_ts()
    grace_cutoff = now_value - schedule_release_grace_s()
    season_eps = [
        ep
        for ep in list(bundle.get("episodes") or [])
        if int(ep.get("season") or 0) == chosen_season and ep.get("number") is not None and ep.get("code")
    ]
    season_eps.sort(key=lambda ep: int(ep.get("number") or 0))

    episode_map: dict[str, str] = {}
    episode_air: dict[str, int | None] = {}
    episode_order: list[str] = []
    present_codes: list[str] = []
    released_codes: list[str] = []
    missing_codes: list[str] = []
    all_missing_codes: list[str] = []
    actionable_missing_codes: list[str] = []
    unreleased_codes: list[str] = []
    pending_codes: list[str] = []
    next_air_ts: int | None = None

    seen: set[str] = set()
    for ep in season_eps:
        code = str(ep.get("code") or "")
        if not code or code in seen:
            continue
        seen.add(code)
        episode_order.append(code)
        episode_map[code] = str(ep.get("name") or "").strip()
        episode_air[code] = int(ep.get("air_ts") or 0) or None
        air_ts = int(ep.get("air_ts") or 0) or None
        if code in present_all:
            present_codes.append(code)
        if code in pending_all:
            pending_codes.append(code)
        if code not in present_all:
            all_missing_codes.append(code)
        if (air_ts is None and not ep.get("airdate")) or (air_ts is not None and air_ts > now_value):
            unreleased_codes.append(code)
            if air_ts and (next_air_ts is None or air_ts < next_air_ts):
                next_air_ts = air_ts
            continue
        released_codes.append(code)
        if code in present_all:
            continue
        missing_codes.append(code)
        if code not in pending_all and (air_ts is None or air_ts <= grace_cutoff):
            actionable_missing_codes.append(code)

    # Cross-season missing: released episodes not in library, across ALL seasons of this show.
    series_missing_by_season: dict[int, list[str]] = {}
    series_actionable_all: list[str] = []
    _seen_series: set[str] = set()
    for _ep in sorted(
        list(bundle.get("episodes") or []), key=lambda e: (int(e.get("season") or 0), int(e.get("number") or 0))
    ):
        _ep_season = int(_ep.get("season") or 0)
        _ep_code = str(_ep.get("code") or "")
        if not _ep_code or _ep_season <= 0 or _ep_code in _seen_series:
            continue
        _seen_series.add(_ep_code)
        _air_ts = int(_ep.get("air_ts") or 0) or None
        if (_air_ts is None and not _ep.get("airdate")) or (_air_ts is not None and _air_ts > now_value):
            continue
        if _ep_code in present_all:
            continue
        series_missing_by_season.setdefault(_ep_season, []).append(_ep_code)
        if _ep_code not in pending_all and (_air_ts is None or _air_ts <= grace_cutoff):
            series_actionable_all.append(_ep_code)

    return {
        "show": show_info,
        "season": chosen_season,
        "available_seasons": available,
        "inventory_source": inventory_source,
        "inventory_degraded": inventory_degraded,
        "inventory_source_effective": "tv folders" if inventory_source != "Plex" else "Plex",
        "metadata_stale": bool(bundle.get("_metadata_stale")),
        "metadata_error": str(bundle.get("_metadata_error") or "").strip() or None,
        "present_codes": present_codes,
        "pending_codes": pending_codes,
        "released_codes": released_codes,
        "missing_codes": missing_codes,
        "all_missing_codes": all_missing_codes,
        "actionable_missing_codes": actionable_missing_codes,
        "unreleased_codes": unreleased_codes,
        "next_air_ts": next_air_ts,
        "signature": "|".join(sorted(set(actionable_missing_codes))),
        "episode_map": episode_map,
        "episode_air": episode_air,
        "episode_order": episode_order,
        "total_season_episodes": len(season_eps),
        "tracked_missing_codes": list(missing_codes),
        "tracking_mode": "upcoming",
        "tracking_code": None,
        "series_missing_by_season": series_missing_by_season,
        "series_actionable_all": series_actionable_all,
    }


def schedule_apply_tracking_mode(
    ctx: HandlerContext, track: dict[str, Any] | None, probe: dict[str, Any]
) -> dict[str, Any]:
    auto_state = schedule_episode_auto_state(track or {})
    probe = dict(probe)

    tracking_mode = str(auto_state.get("tracking_mode") or "upcoming")
    probe["tracking_mode"] = tracking_mode

    missing = list(probe.get("all_missing_codes") or probe.get("missing_codes") or [])
    if not missing:
        probe["tracking_code"] = None
        probe["actionable_missing_codes"] = []
        probe["tracked_missing_codes"] = []
        probe["signature"] = ""
        probe["next_air_ts"] = probe.get("next_air_ts")
        return probe

    if tracking_mode == "full_season":
        probe["tracking_code"] = None
        probe["tracked_missing_codes"] = list(missing)
        return probe

    episode_order = list(probe.get("episode_order") or [])
    present_codes = set(probe.get("present_codes") or [])
    pending_codes = set(probe.get("pending_codes") or [])
    episode_air = dict(probe.get("episode_air") or {})

    now_value = now_ts()
    grace_cutoff = now_value - schedule_release_grace_s()

    cursor_ep = episode_number_from_code(str(auto_state.get("next_code") or ""))
    if cursor_ep is None:
        cursor_ep = 0
        for code in episode_order:
            if code in present_codes:
                continue
            try:
                ep_num = int(episode_number_from_code(code) or 0)
            except Exception:
                continue
            air_ts = episode_air.get(code)
            if air_ts is None or (air_ts > now_value):
                cursor_ep = ep_num
                break
        if cursor_ep <= 0:
            for code in episode_order:
                if code in present_codes:
                    continue
                try:
                    ep_num = int(episode_number_from_code(code) or 0)
                except Exception:
                    continue
                cursor_ep = ep_num
                break

    target_code: str | None = None
    target_air_ts: int | None = None
    target_actionable: list[str] = []
    tracked_missing: list[str] = []
    for code in episode_order:
        ep_num = episode_number_from_code(code)
        if not ep_num:
            continue
        if ep_num < cursor_ep:
            continue
        if code in present_codes:
            continue
        target_code = code
        target_air_ts = episode_air.get(code)
        if code not in pending_codes:
            tracked_missing.append(code)
            if target_air_ts is None or target_air_ts <= grace_cutoff:
                target_actionable = [code]
        break

    if target_code:
        auto_state["next_code"] = target_code
        probe["tracking_code"] = target_code
        probe["tracked_missing_codes"] = tracked_missing
        probe["actionable_missing_codes"] = target_actionable
        probe["signature"] = "|".join(sorted(set(target_actionable)))
        if target_air_ts:
            probe["next_air_ts"] = target_air_ts
    else:
        auto_state["next_code"] = None
        probe["tracking_code"] = None
        probe["tracked_missing_codes"] = []
        probe["actionable_missing_codes"] = []
        probe["signature"] = ""

    if target_code in pending_codes:
        auto_state["next_code"] = target_code
        probe["tracking_code"] = target_code

    probe["_auto_state"] = auto_state
    return probe


def schedule_probe_track(ctx: HandlerContext, track: dict[str, Any], season: int | None = None) -> dict[str, Any]:
    bundle = schedule_get_show_bundle(
        ctx,
        int(track.get("tvmaze_id") or track.get("show_json", {}).get("id") or 0),
        allow_stale=True,
        lookup_tmdb=False,
    )
    target_season = int(season) if season else int(track.get("season") or 1)
    raw_probe = schedule_probe_bundle(ctx, bundle, track=track, season=target_season)
    return schedule_apply_tracking_mode(ctx, track, raw_probe)


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------


def schedule_candidate_keyboard(candidates: list[dict[str, Any]], nav_footer_fn: Any) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, candidate in enumerate(candidates[:5]):
        year = candidate.get("year") or "?"
        rows.append([InlineKeyboardButton(f"{candidate['name']} ({year})", callback_data=f"sch:pick:{idx}")])
    rows.append([InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")])
    rows.extend(nav_footer_fn(include_home=False))
    return InlineKeyboardMarkup(rows)


def schedule_preview_keyboard(probe: dict[str, Any], nav_footer_fn: Any) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("\u2705 Confirm & Track", callback_data="sch:confirm"),
            InlineKeyboardButton("\U0001f504 Different Show", callback_data="sch:change"),
        ]
    ]
    actionable = list(probe.get("actionable_missing_codes") or [])
    missing_current = list(probe.get("missing_codes") or [])
    series_actionable = list(probe.get("series_actionable_all") or [])
    chosen_season = int(probe.get("season") or 0)
    other_season_actionable = [c for c in series_actionable if not c.startswith(f"S{chosen_season:02d}")]
    has_any_missing = bool(missing_current or series_actionable)
    if actionable:
        rows.append(
            [InlineKeyboardButton(f"\u2b07\ufe0f Download Season {chosen_season}", callback_data="sch:confirm:all")]
        )
    if other_season_actionable or len(series_actionable) > len(actionable):
        rows.append([InlineKeyboardButton("\u2b07\ufe0f Download entire series", callback_data="sch:confirm:series")])
    if has_any_missing:
        rows.append([InlineKeyboardButton("\U0001f3af Choose specific episodes", callback_data="sch:confirm:pick")])
    if len(list(probe.get("available_seasons") or [])) > 1:
        rows.append([InlineKeyboardButton("\U0001f500 Change Season", callback_data="sch:season")])
    rows.append([InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")])
    rows.extend(nav_footer_fn(include_home=False))
    return InlineKeyboardMarkup(rows)


def schedule_missing_keyboard(track_id: str, nav_footer_fn: Any) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("\u2b07\ufe0f Download all missing", callback_data=f"sch:all:{track_id}"),
            InlineKeyboardButton("\U0001f3af Pick specific episodes", callback_data=f"sch:pickeps:{track_id}"),
        ],
        [InlineKeyboardButton("\u23ed Skip \u2014 notify me later", callback_data=f"sch:skip:{track_id}")],
    ]
    rows.extend(nav_footer_fn())
    return InlineKeyboardMarkup(rows)


def schedule_episode_picker_keyboard(track_id: str, codes: list[str], nav_footer_fn: Any) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for code in codes[:12]:
        episode_num = int(code[-2:])
        pair.append(InlineKeyboardButton(code, callback_data=f"sch:ep:{track_id}:{episode_num}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton("\u23ed Skip \u2014 notify me later", callback_data=f"sch:skip:{track_id}")])
    rows.extend(nav_footer_fn())
    return InlineKeyboardMarkup(rows)


def schedule_picker_all_missing(probe: dict, current_season: int, current_missing: list[str]) -> dict[str, list[str]]:
    """Normalize series_missing_by_season to string-keyed dict and ensure current season is present."""
    series_raw: dict = probe.get("series_missing_by_season") or {}
    result: dict[str, list[str]] = {}
    for s, codes in series_raw.items():
        if codes:
            result[str(s)] = list(codes)
    if current_missing:
        result[str(current_season)] = current_missing
    return result


def schedule_picker_text(flow: dict) -> str:
    season = int(flow.get("picker_season") or 1)
    selected: list[str] = list(flow.get("picker_selected") or [])
    all_missing: dict = flow.get("picker_all_missing") or {}
    season_codes = list(all_missing.get(str(season)) or [])
    other_seasons = sorted(int(s) for s in all_missing if int(s) != season and all_missing[s])
    n_selected = len(selected)
    lines = [
        "<b>\U0001f3af Choose Episodes to Download</b>",
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
        f"Season <b>{season}</b> \u00b7 {len(season_codes)} missing",
    ]
    if other_seasons:
        lines.append(f"Other seasons with gaps: {', '.join(f'S{s:02d}' for s in other_seasons)}")
    lines.append(f"Selected: <b>{n_selected}</b>")
    lines.append("<i>Tap to select \u00b7 \u21a9\ufe0f Back clears your selections</i>")
    return "\n".join(lines)


def schedule_picker_keyboard(flow: dict) -> InlineKeyboardMarkup:
    selected: set[str] = set(flow.get("picker_selected") or [])
    season = int(flow.get("picker_season") or 1)
    all_missing: dict = flow.get("picker_all_missing") or {}
    season_codes = list(all_missing.get(str(season)) or [])
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for code in season_codes:
        mark = "\u2705 " if code in selected else ""
        pair.append(InlineKeyboardButton(f"{mark}{code}", callback_data=f"sch:pktog:{code}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    other_seasons = sorted(int(s) for s in all_missing if int(s) != season and all_missing[s])
    if other_seasons:
        rows.append([InlineKeyboardButton(f"Season {s}", callback_data=f"sch:pkseason:{s}") for s in other_seasons[:4]])
    n = len(selected)
    label = (
        f"\u2b07\ufe0f Download {n} episode{'s' if n != 1 else ''}" if n > 0 else "Select episodes above to download"
    )
    rows.append([InlineKeyboardButton(label, callback_data="sch:pkconfirm")])
    rows.append([InlineKeyboardButton("\u21a9\ufe0f Back", callback_data="sch:pkback")])
    return InlineKeyboardMarkup(rows)


def schedule_dl_confirm_text(flow: dict) -> str:
    codes: list[str] = list(flow.get("dl_confirm_codes") or [])
    probe: dict = flow.get("probe") or {}
    show: dict = probe.get("show") or flow.get("selected_show") or flow.get("picker_show") or {}
    show_name = str(show.get("name") or "this show")
    dl_from = str(flow.get("dl_confirm_from") or "confirm")
    n = len(codes)
    by_season: dict[str, list[str]] = {}
    for c in codes:
        by_season.setdefault(c[:3], []).append(c)
    lines = [
        "<b>\U0001f4e5 Confirm Download</b>",
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
        f"<b>{_h(show_name)}</b>",
        f"<b>{n} episode{'s' if n != 1 else ''}</b> will be queued for download:",
    ]
    for prefix in sorted(by_season):
        lines.append(f"  <code>{_h(' \u00b7 '.join(by_season[prefix]))}</code>")
    lines.append("")
    if dl_from == "picker":
        lines.append("<i>These episodes will be added to your download queue.</i>")
    else:
        lines.append("<i>Tracking will also begin for future episodes of this show.</i>")
    return "\n".join(lines)


def schedule_dl_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("\u2705 Yes, download", callback_data="sch:dlgo"),
                InlineKeyboardButton("\u21a9\ufe0f Back", callback_data="sch:dlback"),
            ],
        ]
    )


# ---------------------------------------------------------------------------
# Text builders
# ---------------------------------------------------------------------------


def schedule_preview_text(probe: dict[str, Any]) -> str:
    show = probe.get("show") or {}
    tracking_mode = str(probe.get("tracking_mode") or "upcoming")
    mode_label = "full season" if tracking_mode == "full_season" else "next unreleased"
    released_count = len(probe.get("released_codes") or [])
    total_count = int(probe.get("total_season_episodes") or 0)
    present_count = len(probe.get("present_codes") or [])
    unreleased_count = len(probe.get("unreleased_codes") or [])
    network = show.get("network") or show.get("country") or "Unknown"
    source = probe.get("inventory_source") or "unknown"
    chosen_season = int(probe.get("season") or 0)
    missing_all = list(probe.get("missing_codes") or [])
    pending = set(probe.get("pending_codes") or [])
    series_missing: dict = probe.get("series_missing_by_season") or {}
    other_season_gaps = {int(s): codes for s, codes in series_missing.items() if int(s) != chosen_season}

    lines = [
        "<b>\U0001f4fa Schedule Preview</b>",
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
        f"<b>{_h(show.get('name') or '')}</b> ({_h(show.get('year') or '?')})",
        f"Season: <b>{_h(probe.get('season') or '?')}</b> \u00b7 Status: <code>{_h(show.get('status') or 'Unknown')}</code>",
        f"Network: <code>{_h(network)}</code> \u00b7 Source: <code>{_h(source)}</code>",
        f"Mode: <b>{_h(mode_label)}</b>",
        "",
        "<b>Inventory</b>",
        f"  \u2705 In library: <code>{present_count}/{total_count}</code>",
        f"  \U0001f4cb Released: <code>{released_count}/{total_count}</code>",
        f"  \u23f0 Unreleased: <code>{unreleased_count}</code>",
    ]
    if probe.get("next_air_ts"):
        rel = _relative_time(int(probe["next_air_ts"]))
        lines.append(f"  \U0001f4c5 Next episode: <code>{_h(rel)}</code>")
    if probe.get("metadata_stale"):
        lines.append("<i>\u26a0\ufe0f Metadata: using cached TV data \u2014 live source is degraded</i>")
    if probe.get("inventory_degraded"):
        lines.append("<i>\u26a0\ufe0f Inventory: Plex is degraded, using filesystem fallback</i>")

    not_queued = [c for c in missing_all if c not in pending]
    queued_missing = [c for c in missing_all if c in pending]
    if not_queued or queued_missing:
        lines.append("")
        lines.append(f"<b>Missing (Season {chosen_season}):</b>")
        if not_queued:
            lines.append(f"  \u274c <code>{_h(' \u00b7 '.join(not_queued))}</code>")
        if queued_missing:
            lines.append(f"  \u2b07\ufe0f Queued: <code>{_h(' \u00b7 '.join(queued_missing[:8]))}</code>")

    if other_season_gaps:
        lines.append("")
        lines.append("<b>Other seasons with gaps:</b>")
        for s in sorted(other_season_gaps):
            codes = other_season_gaps[s]
            sample = codes[:4]
            suffix = f" +{len(codes) - 4} more" if len(codes) > 4 else ""
            lines.append(f"  \u274c Season {s}: <code>{_h(' \u00b7 '.join(sample))}</code>{_h(suffix)}")

    summary = str(show.get("summary") or "")
    if summary:
        truncated = summary[:320] + ("\u2026" if len(summary) > 320 else "")
        lines.extend(["", f"<blockquote expandable>{_h(truncated)}</blockquote>"])
    lines.extend(["", "<i>Confirm to start background checks for this show/season.</i>"])
    return "\n".join(lines)


def schedule_track_ready_text(track: dict[str, Any], probe: dict[str, Any], *, duplicate: bool = False) -> str:
    show = track.get("show_json") or probe.get("show") or {}
    missing = list(probe.get("tracked_missing_codes") or [])
    header = "<b>\U0001f4fa Already Tracking</b>" if duplicate else "<b>\u2705 Schedule Tracking Enabled</b>"
    mode = str(probe.get("tracking_mode") or "upcoming")
    mode_label = "full season" if mode == "full_season" else "next unreleased"
    present_count = len(probe.get("present_codes") or [])
    unreleased_count = len(probe.get("unreleased_codes") or [])
    lines = [
        header,
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
        f"<b>{_h(show.get('name') or '')}</b> \u2014 Season <b>{_h(track.get('season') or '?')}</b>",
        f"Mode: <b>{_h(mode_label)}</b>",
        "",
        f"  \u2705 In library: <code>{present_count}</code>",
        f"  \U0001f50d Still needed: <b>{len(missing)}</b>",
        f"  \u23f0 Unreleased: <code>{unreleased_count}</code>",
    ]
    if probe.get("next_air_ts"):
        rel = _relative_time(int(probe["next_air_ts"]))
        lines.append(f"  \U0001f4c5 Next episode: <code>{_h(rel)}</code>")
    if probe.get("metadata_stale"):
        lines.append("")
        lines.append("<i>\u26a0\ufe0f TV metadata source degraded: using cached schedule data</i>")
    if probe.get("inventory_degraded"):
        if not probe.get("metadata_stale"):
            lines.append("")
        lines.append("<i>\u26a0\ufe0f Inventory source degraded: using filesystem fallback instead of Plex</i>")
    lines.extend(
        ["", "<i>I'll automatically search and queue missing aired episodes after the release grace window.</i>"]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Episode helpers
# ---------------------------------------------------------------------------


def episode_status_icon(probe: dict[str, Any], code: str, *, pending: set[str] | None = None) -> str:
    """Return a single emoji reflecting the episode's current status."""
    present = set(probe.get("present_codes") or [])
    unreleased = set(probe.get("unreleased_codes") or [])
    actionable = set(probe.get("actionable_missing_codes") or [])
    queued = set(probe.get("pending_codes") or [])
    if pending is not None:
        queued = queued | pending
    if code in present:
        return "\u2705"
    if code in queued:
        return "\u2b07\ufe0f"
    if code in unreleased:
        return "\u23f0"
    if code in actionable:
        return "\U0001f50d"
    return "\U0001f4cb"


def schedule_episode_label(probe: dict[str, Any], code: str, *, pending: set[str] | None = None) -> str:
    name = str((probe.get("episode_map") or {}).get(code) or "").strip()
    air_ts = (probe.get("episode_air") or {}).get(code)
    icon = episode_status_icon(probe, code, pending=pending)
    when = _relative_time(int(air_ts)) if air_ts else "released"
    return f"{icon} {code} \u2014 {name or 'Episode'} ({when})"


def schedule_episode_auto_state(track: dict[str, Any]) -> dict[str, Any]:
    return schedule_sanitize_auto_state(dict(track.get("auto_state_json") or {}))


def schedule_qbt_codes_for_show(
    ctx: HandlerContext, show_name: str, season: int, *, qbt_category_aliases_fn: Any
) -> set[str]:
    codes: set[str] = set()
    tv_categories = qbt_category_aliases_fn(ctx.cfg.tv_category, ctx.cfg.tv_path)
    try:
        torrents = ctx.qbt.list_torrents(limit=500)
        want_norm = normalize_title(show_name)
        for t in torrents:
            torrent_category = str(t.get("category") or "").strip()
            if tv_categories and torrent_category not in tv_categories:
                continue
            name = str(t.get("name") or "")
            if want_norm and want_norm not in normalize_title(name):
                continue
            t_codes = extract_episode_codes(name)
            if season > 0:
                t_codes = {c for c in t_codes if c.startswith(f"S{season:02d}")}
            codes.update(t_codes)
    except Exception:
        LOG.warning("Failed to list qBittorrent torrents for schedule reconcile", exc_info=True)
    return codes


def schedule_reconcile_pending(
    ctx: HandlerContext, track: dict[str, Any], probe: dict[str, Any], *, qbt_category_aliases_fn: Any
) -> tuple[set[str], set[str], set[str]]:
    show = track.get("show_json") or probe.get("show") or {}
    season = int(track.get("season") or 1)
    pending = set(track.get("pending_json") or [])
    present = set(probe.get("present_codes") or [])
    qbt_codes = schedule_qbt_codes_for_show(
        ctx, str(show.get("name") or ""), season, qbt_category_aliases_fn=qbt_category_aliases_fn
    )
    stale_threshold = now_ts() - schedule_pending_stale_s()
    auto_state = schedule_episode_auto_state(track)
    retry_codes = dict(auto_state.get("retry_codes") or {})
    cleared = pending & present
    stale: set[str] = set()
    for code in list(pending - present):
        if code in qbt_codes:
            continue
        added_at = retry_codes.get(code)
        if added_at and int(added_at) < stale_threshold:
            stale.add(code)
    return cleared, stale, qbt_codes


def schedule_should_attempt_auto(track: dict[str, Any], probe: dict[str, Any]) -> tuple[bool, str | None]:
    auto_state = schedule_episode_auto_state(track)
    if not auto_state.get("enabled"):
        return False, "auto disabled"
    actionable = list(probe.get("actionable_missing_codes") or [])
    if not actionable:
        return False, "no actionable missing"
    pending = set(track.get("pending_json") or [])
    candidates = [c for c in actionable if c not in pending]
    if not candidates:
        return False, "all actionable already pending"
    now_value = now_ts()
    next_retry = auto_state.get("next_auto_retry_at")
    if next_retry and int(next_retry) > now_value:
        return False, f"retry cooldown until <code>{format_local_ts(int(next_retry))}</code>"
    return True, candidates[0]


def schedule_missing_text(track: dict[str, Any], probe: dict[str, Any]) -> str:
    show = track.get("show_json") or probe.get("show") or {}
    codes = list(probe.get("actionable_missing_codes") or [])
    auto_state = schedule_episode_auto_state(track)
    next_retry = auto_state.get("next_auto_retry_at")
    inline_codes = codes[:2]
    more_codes = codes[2:10]
    overflow = max(0, len(codes) - 10)
    inline_lines = [f"  {_h(schedule_episode_label(probe, c))}" for c in inline_codes]
    more_lines = [f"\u2022 {_h(schedule_episode_label(probe, c))}" for c in more_codes]
    if overflow > 0:
        more_lines.append(f"\u2022 \u2026and {overflow} more")
    ep_count = len(codes)
    lines = [
        "<b>\U0001f4fa Missing Aired Episodes</b>",
        f"<b>{_h(show.get('name') or '')}</b> \u00b7 Season <b>{_h(track.get('season') or '?')}</b> \u00b7 <b>{ep_count}</b> episode{'s' if ep_count != 1 else ''} needed",
        "",
    ]
    lines.extend(inline_lines)
    if more_lines:
        more_block = "\n".join(more_lines)
        lines.append(f"<blockquote expandable>{more_block}</blockquote>")
    lines.append("")
    if next_retry:
        rel = _relative_time(int(next_retry))
        lines.append(f"<i>Auto-search enabled \u00b7 next attempt {rel}</i>")
    else:
        lines.append("<i>Auto-search enabled \u00b7 searching now</i>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Episode rank / match
# ---------------------------------------------------------------------------


def schedule_row_matches_episode(name: str, season: int, episode: int) -> bool:
    return episode_code(season, episode) in extract_episode_codes(name)


def schedule_episode_rank_key(row: dict[str, Any], show_name: str, season: int, episode: int) -> tuple[int, ...]:
    from ..quality import score_torrent

    name = str(row.get("fileName") or row.get("name") or "")
    seeds = int(row.get("nbSeeders") or row.get("seeders") or 0)
    size = int(row.get("fileSize") or row.get("size") or 0)
    exact_episode = 1 if schedule_row_matches_episode(name, season, episode) else 0
    exact_show = 1 if normalize_title(show_name) in normalize_title(name) else 0
    ts = score_torrent(name, size, seeds, media_type="episode")
    # Seed bucket as 5th element: quality-first with health tiebreaker
    if seeds >= 50:
        seed_tier = 5
    elif seeds >= 25:
        seed_tier = 4
    elif seeds >= 10:
        seed_tier = 3
    elif seeds >= 5:
        seed_tier = 2
    elif seeds >= 1:
        seed_tier = 1
    else:
        seed_tier = 0
    return (exact_episode, exact_show, ts.resolution_tier, ts.format_score, seed_tier)


# ---------------------------------------------------------------------------
# Download episode (async -- calls back into BotApp for _do_add / _apply_filters)
# ---------------------------------------------------------------------------


async def schedule_download_episode(
    ctx: HandlerContext,
    track: dict[str, Any],
    code: str,
    *,
    apply_filters_fn: Any,
    do_add_fn: Any,
) -> dict[str, Any]:
    m = re.fullmatch(r"S(\d{2})E(\d{2})", code)
    if not m:
        raise RuntimeError(f"Invalid episode code: {code}")
    season = int(m.group(1))
    episode = int(m.group(2))
    show = track.get("show_json") or {}
    query = f"{show.get('name')} {code}"
    defaults = ctx.store.get_defaults(int(track.get("user_id") or 0), ctx.cfg)
    raw_rows = await asyncio.to_thread(
        ctx.qbt.search,
        query,
        plugin="enabled",
        search_cat="tv",
        timeout_s=ctx.cfg.search_timeout_s,
        poll_interval_s=ctx.cfg.poll_interval_s,
        early_exit_min_results=max(ctx.cfg.search_early_exit_min_results, 12),
        early_exit_idle_s=ctx.cfg.search_early_exit_idle_s,
        early_exit_max_wait_s=ctx.cfg.search_early_exit_max_wait_s,
    )
    filtered = apply_filters_fn(
        raw_rows,
        min_seeds=int(defaults.get("default_min_seeds") or 0),
        min_size=None,
        max_size=None,
        min_quality=ctx.cfg.default_min_quality,
    )
    raw_exact = [
        row
        for row in raw_rows
        if schedule_row_matches_episode(str(row.get("fileName") or row.get("name") or ""), season, episode)
    ]
    exact = [
        row
        for row in filtered
        if schedule_row_matches_episode(str(row.get("fileName") or row.get("name") or ""), season, episode)
    ]
    if not exact:
        if raw_exact:
            raise RuntimeError(f"Exact episode {code} was found, but every exact match failed the current TV filters")
        raise RuntimeError(f"No exact qBittorrent result matched episode {code}")
    ranked = sorted(
        exact,
        key=lambda row: schedule_episode_rank_key(row, str(show.get("name") or ""), season, episode),
        reverse=True,
    )
    search_id = ctx.store.save_search(
        int(track.get("user_id") or 0),
        query,
        {
            "query": query,
            "plugin": "enabled",
            "search_cat": "tv",
            "media_hint": "tv",
            "sort": "schedule-rank",
            "order": "desc",
            "limit": 10,
        },
        ranked[:10],
    )
    return await do_add_fn(int(track.get("user_id") or 0), search_id, 1, "tv")


# ---------------------------------------------------------------------------
# Backup job
# ---------------------------------------------------------------------------


async def backup_job(ctx: HandlerContext, context: ContextTypes.DEFAULT_TYPE) -> None:
    """APScheduler job: create a daily database backup."""
    if not ctx.cfg.backup_dir:
        return
    try:
        path = await asyncio.to_thread(ctx.store.backup, ctx.cfg.backup_dir)
        size = os.path.getsize(path)
        LOG.info("Database backup created: %s (%d bytes)", path, size)
    except Exception as e:
        LOG.error("Database backup failed: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# Runner job (async -- the core background loop)
# ---------------------------------------------------------------------------


async def schedule_runner_job(
    ctx: HandlerContext,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    refresh_track_fn: Any,
) -> None:
    async with ctx.schedule_runner_lock:
        started_at = now_ts()
        due_tracks: list[dict[str, Any]] = []
        processed = 0
        try:
            await asyncio.to_thread(ctx.store.update_schedule_runner_status, last_started_at=started_at)
            due_tracks = await asyncio.to_thread(ctx.store.list_due_schedule_tracks, now_ts(), 5)
            for track in due_tracks:
                try:
                    await refresh_track_fn(track, allow_notify=True)
                    processed += 1
                except Exception:
                    LOG.warning("Schedule track refresh failed for %s", track.get("track_id"), exc_info=True)
            await asyncio.to_thread(
                ctx.store.update_schedule_runner_status,
                last_finished_at=now_ts(),
                last_success_at=now_ts(),
                last_error_at=None,
                last_error_text=None,
                last_due_count=len(due_tracks),
                last_processed_count=processed,
                metadata_source_health_json=schedule_source_snapshot(ctx, "metadata"),
                inventory_source_health_json=schedule_source_snapshot(ctx, "inventory"),
            )
        except Exception as e:
            LOG.warning("Schedule runner loop failed", exc_info=True)
            await asyncio.to_thread(
                ctx.store.update_schedule_runner_status,
                last_finished_at=now_ts(),
                last_error_at=now_ts(),
                last_error_text=str(e),
                last_due_count=len(due_tracks),
                last_processed_count=processed,
                metadata_source_health_json=schedule_source_snapshot(ctx, "metadata"),
                inventory_source_health_json=schedule_source_snapshot(ctx, "inventory"),
            )


# ---------------------------------------------------------------------------
# Refresh a single track (async -- the core per-track refresh logic)
# ---------------------------------------------------------------------------


async def schedule_refresh_track(
    ctx: HandlerContext,
    track: dict[str, Any],
    *,
    allow_notify: bool = False,
    qbt_category_aliases_fn: Any,
    should_attempt_auto_fn: Any = None,
    attempt_auto_acquire_fn: Any = None,
    notify_auto_queued_fn: Any = None,
    notify_missing_fn: Any = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    track_id = str(track.get("track_id") or "")
    try:
        probe = await asyncio.to_thread(schedule_probe_track, ctx, track)
    except Exception as e:
        metadata_state = schedule_source_snapshot(ctx, "metadata")
        retry_at = now_ts() + schedule_metadata_retry_backoff_s(
            max(1, int(metadata_state.get("consecutive_failures") or 0))
        )
        LOG.warning("Schedule metadata refresh failed for %s: %s", track_id, e)
        last_probe = dict(track.get("last_probe_json") or {})
        if last_probe:
            last_probe["metadata_error"] = str(e)
            last_probe["last_refresh_error_at"] = now_ts()
            last_probe["metadata_stale"] = bool(last_probe.get("metadata_stale"))
        await asyncio.to_thread(
            ctx.store.update_schedule_track,
            track_id,
            last_probe_json=last_probe,
            last_probe_at=now_ts(),
            next_check_at=retry_at,
        )
        updated = await asyncio.to_thread(ctx.store.get_schedule_track_any, track_id)
        if updated is None:
            raise RuntimeError(f"Schedule track {track_id} disappeared after metadata retry update")
        return updated, last_probe
    auto_state = dict(schedule_episode_auto_state(track))
    auto_state.update(dict(probe.get("_auto_state") or {}))
    auto_state = schedule_sanitize_auto_state(auto_state, probe=probe)
    pending = set(track.get("pending_json") or [])
    cleared, stale, qbt_codes = schedule_reconcile_pending(
        ctx, track, probe, qbt_category_aliases_fn=qbt_category_aliases_fn
    )
    if cleared:
        pending -= cleared
        LOG.info(
            "Schedule cleared %d pending episodes now present locally: %s", len(cleared), ", ".join(sorted(cleared))
        )
    if stale:
        pending -= stale
        retry_codes = dict(auto_state.get("retry_codes") or {})
        for code in stale:
            retry_codes.pop(code, None)
        auto_state["retry_codes"] = retry_codes
        LOG.info("Schedule recovered %d stale pending episodes: %s", len(stale), ", ".join(sorted(stale)))

    _should_auto_fn = should_attempt_auto_fn or schedule_should_attempt_auto
    should_auto, target_code = _should_auto_fn(track, probe)
    auto_acquired: str | None = None
    if should_auto and target_code and attempt_auto_acquire_fn:
        result = await attempt_auto_acquire_fn(track, target_code)
        if result:
            auto_acquired = target_code
            pending.add(target_code)
            retry_codes = dict(auto_state.get("retry_codes") or {})
            retry_codes[target_code] = now_ts()
            auto_state["retry_codes"] = retry_codes
            auto_state["last_auto_code"] = target_code
            auto_state["last_auto_at"] = now_ts()
            auto_state["next_auto_retry_at"] = now_ts() + schedule_retry_interval_s()
            if allow_notify and notify_auto_queued_fn:
                await notify_auto_queued_fn(track, target_code, result)
        else:
            auto_state["next_auto_retry_at"] = now_ts() + schedule_retry_interval_s()
    elif not probe.get("actionable_missing_codes"):
        auto_state["next_auto_retry_at"] = None
    auto_state = schedule_sanitize_auto_state(auto_state, probe=probe)
    next_check = schedule_next_check_at(
        ctx,
        probe.get("next_air_ts"),
        has_actionable_missing=bool(probe.get("actionable_missing_codes")),
        auto_state=auto_state,
    )

    store_probe = dict(probe)
    store_probe.pop("_auto_state", None)

    update_fields: dict[str, Any] = {
        "pending_json": sorted(pending),
        "auto_state_json": auto_state,
        "last_probe_json": store_probe,
        "last_probe_at": now_ts(),
        "next_check_at": next_check,
        "next_air_ts": store_probe.get("next_air_ts"),
        "show_json": probe.get("show") or track.get("show_json") or {},
    }
    if not probe.get("signature"):
        update_fields["last_missing_signature"] = None
        update_fields["skipped_signature"] = None
    await asyncio.to_thread(ctx.store.update_schedule_track, track_id, **update_fields)
    updated = await asyncio.to_thread(ctx.store.get_schedule_track_any, track_id)
    if updated is None:
        raise RuntimeError(f"Schedule track {track_id} disappeared after refresh update")
    if (
        allow_notify
        and not auto_acquired
        and probe.get("signature")
        and probe.get("signature") != updated.get("skipped_signature")
        and probe.get("signature") != updated.get("last_missing_signature")
        and notify_missing_fn
    ):
        await notify_missing_fn(updated, probe)
    return updated, probe


# ---------------------------------------------------------------------------
# Notify missing (async -- sends Telegram message)
# ---------------------------------------------------------------------------


async def schedule_notify_missing(
    ctx: HandlerContext,
    track: dict[str, Any],
    probe: dict[str, Any],
    *,
    nav_footer_fn: Any,
    track_ephemeral_message_fn: Any,
) -> None:
    if not ctx.app:
        return
    chat_id = int(track.get("chat_id") or 0)
    if not chat_id:
        LOG.warning("Schedule notify_missing skipped: no chat_id for track %s", track.get("track_id"))
        return
    text = schedule_missing_text(track, probe)
    try:
        sent = await ctx.app.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=schedule_missing_keyboard(str(track.get("track_id") or ""), nav_footer_fn),
            parse_mode=_PM,
        )
        user_id = int(track.get("user_id") or chat_id)
        track_ephemeral_message_fn(user_id, sent)
    except TelegramError as e:
        LOG.warning("Schedule notify_missing failed for track %s: %s", track.get("track_id"), e)
    store_probe = dict(probe)
    store_probe.pop("_auto_state", None)
    await asyncio.to_thread(
        ctx.store.update_schedule_track,
        str(track.get("track_id") or ""),
        last_missing_signature=str(probe.get("signature") or "") or None,
        last_probe_json=store_probe,
        last_probe_at=now_ts(),
    )


# ---------------------------------------------------------------------------
# Notify auto-queued (async -- sends Telegram message)
# ---------------------------------------------------------------------------


async def schedule_notify_auto_queued(
    ctx: HandlerContext,
    track: dict[str, Any],
    code: str,
    result: dict[str, Any],
    *,
    track_ephemeral_message_fn: Any,
    stop_download_keyboard_fn: Any,
    start_progress_tracker_fn: Any,
    start_pending_progress_tracker_fn: Any,
) -> None:
    if not ctx.app:
        return
    show = track.get("show_json") or {}
    show_name = show.get("name") or "Show"
    torrent_name = result.get("name") or "Torrent added"
    category = result.get("category") or ""
    path = result.get("path") or ""
    lines = [
        "<b>\U0001f4e1 Auto-Queued</b>",
        f"<b>{_h(show_name)}</b> <code>{_h(code)}</code>",
        "",
        f"<code>{_h(torrent_name)}</code>",
    ]
    if category:
        lines.append(f"Category: <code>{_h(category)}</code>")
    if path:
        lines.append(f"Path: <code>{_h(path)}</code>")
    text = "\n".join(lines)
    chat_id = int(track.get("chat_id") or 0)
    user_id = int(track.get("user_id") or 0)
    if not chat_id:
        LOG.warning("Schedule notify_auto_queued skipped: no chat_id for track %s", track.get("track_id"))
        return
    try:
        notif_msg = await ctx.app.bot.send_message(chat_id=chat_id, text=text, parse_mode=_PM)
        track_ephemeral_message_fn(user_id, notif_msg)
        torrent_hash = result.get("hash")
        if torrent_hash:
            tracker_msg = await ctx.app.bot.send_message(
                chat_id=chat_id,
                text=f"<b>\U0001f4e1 Live Monitor Attached</b>\n<i>Tracking {_h(code)} download progress\u2026</i>",
                reply_markup=stop_download_keyboard_fn(torrent_hash),
                parse_mode=_PM,
            )
            start_progress_tracker_fn(user_id, torrent_hash, tracker_msg, torrent_name)
        else:
            start_pending_progress_tracker_fn(user_id, torrent_name, category, notif_msg)
    except Exception:
        LOG.warning("Failed to send auto-queue notification", exc_info=True)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def schedule_active_line(track: dict[str, Any]) -> str:
    probe = dict(track.get("last_probe_json") or {})
    show = dict(track.get("show_json") or probe.get("show") or {})
    name = str(show.get("name") or track.get("show_name") or "Unknown show")
    season = int(track.get("season") or probe.get("season") or 1)
    actionable = len(probe.get("actionable_missing_codes") or [])
    pending = len(track.get("pending_json") or probe.get("pending_codes") or [])
    unreleased = len(probe.get("unreleased_codes") or [])
    if actionable > 0:
        lead = "\U0001f50d"
        status = f"<b>{actionable} missing</b>"
    elif pending > 0:
        lead = "\u2b07\ufe0f"
        status = f"<b>{pending} downloading</b>"
    elif unreleased > 0:
        lead = "\u23f0"
        status = "waiting on release"
    else:
        lead = "\u2705"
        status = "up to date"
    details: list[str] = [status]
    if unreleased > 0:
        details.append(f"{unreleased} unreleased")
    next_air_ts = int(track.get("next_air_ts") or probe.get("next_air_ts") or 0)
    if next_air_ts > 0:
        details.append(f"next {_relative_time(next_air_ts)}")
    next_check_at = int(track.get("next_check_at") or 0)
    if next_check_at > 0:
        details.append(f"check {_relative_time(next_check_at)}")
    if probe.get("metadata_stale"):
        details.append("\u26a0\ufe0f stale data")
    detail_line = " \u00b7 ".join(details[:3])
    return f"{lead} <b>{_h(name)}</b>\n   Season {season} \u00b7 {detail_line}"


def schedule_paused_line(name: str, season: int) -> str:
    return f"\u23f8 <b>{_h(name)}</b>\n   Season {season} \u00b7 <i>paused</i>"


# ---------------------------------------------------------------------------
# Callback handler — extracted from BotApp._on_cb_schedule
# ---------------------------------------------------------------------------


async def on_cb_schedule(bot_app: Any, *, data: str, q: Any, user_id: int) -> None:  # noqa: C901
    """Handle all ``sch:*`` callback-query prefixes.

    *bot_app* is either the real ``BotApp`` instance or a test ``DummyBot``.
    All flow/rendering calls go through ``bot_app._method()`` so that tests
    can override them.
    """
    ctx = getattr(bot_app, "_ctx", bot_app)

    if data == "sch:cancel":
        bot_app._clear_flow(user_id)
        await bot_app._render_command_center(q.message, user_id=user_id)
        return

    if data.startswith("sch:pick:"):
        idx = int(data.split(":", 2)[2])
        await bot_app._schedule_pick_candidate(q.message, user_id, idx)
        return

    if data == "sch:change":
        bot_app._schedule_start_flow(user_id)
        flow = bot_app._get_flow(user_id) or {"mode": "schedule", "stage": "await_show"}
        await bot_app._render_schedule_ui(
            user_id,
            q.message,
            flow,
            "<b>\u270f\ufe0f Type a show name to search</b>\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\nMonitors your Plex library and auto-queues missing episodes as they air.\n\n<i>Example: Severance</i>",
            reply_markup=None,
            current_ui_message=q.message,
        )
        return

    if data == "sch:season":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "schedule" or flow.get("stage") != "confirm":
            await bot_app._render_schedule_ui(
                user_id,
                q.message,
                {"mode": "schedule", "stage": "await_show"},
                "<b>\u23f0 Session Expired</b>\nThat schedule setup is no longer active.\n<i>Start /schedule again.</i>",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        available = list(
            (flow.get("probe") or {}).get("available_seasons")
            or flow.get("selected_show", {}).get("available_seasons")
            or []
        )
        flow["stage"] = "await_season_pick"
        bot_app._set_flow(user_id, flow)
        await bot_app._render_schedule_ui(
            user_id,
            q.message,
            flow,
            "Send the season number to track. Available seasons: " + ", ".join(str(x) for x in available),
            reply_markup=None,
            current_ui_message=q.message,
        )
        return

    if data == "sch:confirm:all":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("stage") != "confirm":
            await bot_app._schedule_confirm_selection(q.message, user_id, int(q.message.chat_id), post_action="all")
            return
        probe = dict(flow.get("probe") or {})
        codes = list(probe.get("actionable_missing_codes") or probe.get("missing_codes") or [])
        if not codes:
            await bot_app._schedule_confirm_selection(q.message, user_id, int(q.message.chat_id), post_action=None)
            return
        flow["stage"] = "dl_confirm"
        flow["dl_confirm_codes"] = codes
        flow["dl_confirm_post_action"] = "all"
        flow["dl_confirm_from"] = "confirm"
        bot_app._set_flow(user_id, flow)
        await bot_app._render_schedule_ui(
            user_id,
            q.message,
            flow,
            bot_app._schedule_dl_confirm_text(flow),
            reply_markup=bot_app._schedule_dl_confirm_keyboard(),
            current_ui_message=q.message,
        )
        return

    if data == "sch:confirm:series":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("stage") != "confirm":
            await bot_app._schedule_confirm_selection(q.message, user_id, int(q.message.chat_id), post_action="series")
            return
        probe = dict(flow.get("probe") or {})
        codes = list(probe.get("series_actionable_all") or probe.get("actionable_missing_codes") or [])
        if not codes:
            await bot_app._schedule_confirm_selection(q.message, user_id, int(q.message.chat_id), post_action=None)
            return
        flow["stage"] = "dl_confirm"
        flow["dl_confirm_codes"] = codes
        flow["dl_confirm_post_action"] = "series"
        flow["dl_confirm_from"] = "confirm"
        bot_app._set_flow(user_id, flow)
        await bot_app._render_schedule_ui(
            user_id,
            q.message,
            flow,
            bot_app._schedule_dl_confirm_text(flow),
            reply_markup=bot_app._schedule_dl_confirm_keyboard(),
            current_ui_message=q.message,
        )
        return

    if data == "sch:confirm:pick":
        await bot_app._schedule_confirm_selection(q.message, user_id, int(q.message.chat_id), post_action="pick")
        return

    if data == "sch:confirm":
        await bot_app._schedule_confirm_selection(q.message, user_id, int(q.message.chat_id))
        return

    if data.startswith("sch:all:"):
        track_id = data.split(":", 2)[2]
        track = await asyncio.to_thread(ctx.store.get_schedule_track, user_id, track_id)
        if not track:
            await bot_app._render_nav_ui(
                user_id,
                q.message,
                "That schedule entry was not found.",
                reply_markup=bot_app._home_only_keyboard(),
                current_ui_message=q.message,
            )
            return
        probe = dict(track.get("last_probe_json") or {})
        codes = list(probe.get("actionable_missing_codes") or probe.get("missing_codes") or [])
        await bot_app._schedule_download_requested(q.message, track, codes)
        return

    if data.startswith("sch:pickeps:"):
        track_id = data.split(":", 2)[2]
        track = await asyncio.to_thread(ctx.store.get_schedule_track, user_id, track_id)
        if not track:
            await bot_app._render_nav_ui(
                user_id,
                q.message,
                "That schedule entry was not found.",
                reply_markup=bot_app._home_only_keyboard(),
                current_ui_message=q.message,
            )
            return
        probe = dict(track.get("last_probe_json") or {})
        current_season = int(track.get("season") or 1)
        current_missing = list(probe.get("actionable_missing_codes") or probe.get("missing_codes") or [])
        all_missing = bot_app._schedule_picker_all_missing(probe, current_season, current_missing)
        if not any(all_missing.values()):
            await bot_app._render_nav_ui(
                user_id,
                q.message,
                "There are no current missing episodes to pick from.",
                reply_markup=bot_app._home_only_keyboard(),
                current_ui_message=q.message,
            )
            return
        picker_flow: dict[str, Any] = {
            "mode": "schedule",
            "stage": "picker",
            "picker_selected": [],
            "picker_season": current_season,
            "picker_all_missing": all_missing,
            "picker_has_preview": False,
            "picker_track_id": track_id,
            "picker_show": dict(track.get("show_json") or {}),
        }
        bot_app._set_flow(user_id, picker_flow)
        await bot_app._render_schedule_ui(
            user_id,
            q.message,
            picker_flow,
            bot_app._schedule_picker_text(picker_flow),
            reply_markup=bot_app._schedule_picker_keyboard(picker_flow),
            current_ui_message=q.message,
        )
        return

    if data.startswith("sch:pktog:"):
        code = data[len("sch:pktog:") :]
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("stage") != "picker":
            await q.answer("Session expired \u2014 start over.", show_alert=True)
            return
        selected_list: list[str] = list(flow.get("picker_selected") or [])
        if code in selected_list:
            selected_list.remove(code)
        else:
            selected_list.append(code)
        flow["picker_selected"] = selected_list
        bot_app._set_flow(user_id, flow)
        await bot_app._render_schedule_ui(
            user_id,
            q.message,
            flow,
            bot_app._schedule_picker_text(flow),
            reply_markup=bot_app._schedule_picker_keyboard(flow),
            current_ui_message=q.message,
        )
        return

    if data.startswith("sch:pkseason:"):
        new_season = int(data.split(":", 2)[2])
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("stage") != "picker":
            await q.answer("Session expired \u2014 start over.", show_alert=True)
            return
        flow["picker_season"] = new_season
        bot_app._set_flow(user_id, flow)
        await bot_app._render_schedule_ui(
            user_id,
            q.message,
            flow,
            bot_app._schedule_picker_text(flow),
            reply_markup=bot_app._schedule_picker_keyboard(flow),
            current_ui_message=q.message,
        )
        return

    if data == "sch:pkconfirm":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("stage") != "picker":
            await q.answer("Session expired \u2014 start over.", show_alert=True)
            return
        selected_codes = list(flow.get("picker_selected") or [])
        if not selected_codes:
            await q.answer("No episodes selected.", show_alert=True)
            return
        flow["stage"] = "dl_confirm"
        flow["dl_confirm_codes"] = selected_codes
        flow["dl_confirm_post_action"] = "pick"
        flow["dl_confirm_from"] = "picker"
        bot_app._set_flow(user_id, flow)
        await bot_app._render_schedule_ui(
            user_id,
            q.message,
            flow,
            bot_app._schedule_dl_confirm_text(flow),
            reply_markup=bot_app._schedule_dl_confirm_keyboard(),
            current_ui_message=q.message,
        )
        return

    if data == "sch:pkback":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("stage") != "picker":
            await q.answer("Session expired.", show_alert=True)
            return
        if flow.get("picker_has_preview"):
            probe = dict(flow.get("probe") or {})
            flow["stage"] = "confirm"
            bot_app._set_flow(user_id, flow)
            await bot_app._render_schedule_ui(
                user_id,
                q.message,
                flow,
                bot_app._schedule_preview_text(probe),
                reply_markup=bot_app._schedule_preview_keyboard(probe),
                current_ui_message=q.message,
            )
        else:
            bot_app._clear_flow(user_id)
            await bot_app._render_nav_ui(
                user_id,
                q.message,
                "<b>\u21a9\ufe0f Cancelled</b>",
                reply_markup=bot_app._home_only_keyboard(),
                current_ui_message=q.message,
            )
        return

    if data == "sch:dlgo":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("stage") != "dl_confirm":
            await q.answer("Session expired \u2014 start over.", show_alert=True)
            return
        post_action = str(flow.get("dl_confirm_post_action") or "all")
        dl_from = str(flow.get("dl_confirm_from") or "confirm")
        if dl_from == "picker":
            selected_codes = list(flow.get("dl_confirm_codes") or [])
            pk_track_id = str(flow.get("picker_track_id") or "")
            pk_track = await asyncio.to_thread(ctx.store.get_schedule_track, user_id, pk_track_id)
            if not pk_track:
                await bot_app._render_schedule_ui(
                    user_id,
                    q.message,
                    flow,
                    "That schedule entry was not found.",
                    reply_markup=None,
                    current_ui_message=q.message,
                )
                bot_app._clear_flow(user_id)
                return
            bot_app._clear_flow(user_id)
            n = len(selected_codes)
            await bot_app._render_schedule_ui(
                user_id,
                q.message,
                flow,
                f"Queuing {n} episode{'s' if n != 1 else ''}\u2026",
                reply_markup=None,
                current_ui_message=q.message,
            )
            await bot_app._schedule_download_requested(q.message, pk_track, selected_codes)
        else:
            flow["stage"] = "confirm"
            bot_app._set_flow(user_id, flow)
            await bot_app._schedule_confirm_selection(
                q.message, user_id, int(q.message.chat_id), post_action=post_action
            )
        return

    if data == "sch:dlback":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("stage") != "dl_confirm":
            await q.answer("Session expired.", show_alert=True)
            return
        dl_from = str(flow.get("dl_confirm_from") or "confirm")
        if dl_from == "picker":
            flow["stage"] = "picker"
            bot_app._set_flow(user_id, flow)
            await bot_app._render_schedule_ui(
                user_id,
                q.message,
                flow,
                bot_app._schedule_picker_text(flow),
                reply_markup=bot_app._schedule_picker_keyboard(flow),
                current_ui_message=q.message,
            )
        else:
            probe = dict(flow.get("probe") or {})
            flow["stage"] = "confirm"
            bot_app._set_flow(user_id, flow)
            await bot_app._render_schedule_ui(
                user_id,
                q.message,
                flow,
                bot_app._schedule_preview_text(probe),
                reply_markup=bot_app._schedule_preview_keyboard(probe),
                current_ui_message=q.message,
            )
        return

    if data.startswith("sch:ep:"):
        _, _, track_id, episode_raw = data.split(":", 3)
        track = await asyncio.to_thread(ctx.store.get_schedule_track, user_id, track_id)
        if not track:
            await bot_app._render_nav_ui(
                user_id,
                q.message,
                "That schedule entry was not found.",
                reply_markup=bot_app._home_only_keyboard(),
                current_ui_message=q.message,
            )
            return
        code = episode_code(int(track.get("season") or 1), int(episode_raw))
        await bot_app._schedule_download_requested(q.message, track, [code])
        return

    if data.startswith("sch:skip:"):
        track_id = data.split(":", 2)[2]
        track = await asyncio.to_thread(ctx.store.get_schedule_track, user_id, track_id)
        if not track:
            await bot_app._render_nav_ui(
                user_id,
                q.message,
                "That schedule entry was not found.",
                reply_markup=bot_app._home_only_keyboard(),
                current_ui_message=q.message,
            )
            return
        probe = dict(track.get("last_probe_json") or {})
        signature = str(probe.get("signature") or "") or None
        await asyncio.to_thread(
            ctx.store.update_schedule_track,
            track_id,
            skipped_signature=signature,
            last_missing_signature=signature,
        )
        await bot_app._render_nav_ui(
            user_id,
            q.message,
            "\U0001f44d Got it \u2014 I'll skip this notification.\n"
            "<i>I'll alert you again if new episodes air or the missing count changes.</i>",
            reply_markup=bot_app._home_only_keyboard(),
            current_ui_message=q.message,
        )
        return

    if data == "sch:addnew":
        bot_app._schedule_start_flow(user_id)
        text = (
            "<b>\u270f\ufe0f Type a show name to search</b>\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
            "Monitors your Plex library and auto-queues missing episodes as they air.\n\n"
            "<i>Example: Severance</i>"
        )
        kb = InlineKeyboardMarkup(bot_app._nav_footer(back_data="menu:schedule", include_home=False))
        await bot_app._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)
        return

    if data == "sch:myshows":
        tracks = await asyncio.to_thread(ctx.store.list_schedule_tracks, user_id, False, 50)
        if not tracks:
            await bot_app._render_nav_ui(
                user_id,
                q.message,
                "<b>\U0001f4cb My Shows</b>\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\nNo shows tracked yet.\nTap <b>Add New Show</b> to get started.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("\u2795 Add New Show", callback_data="sch:addnew")],
                    ]
                    + bot_app._nav_footer(back_data="menu:schedule", include_home=False)
                ),
                current_ui_message=q.message,
            )
            return
        lines = [
            "<b>\U0001f4cb My Shows</b>",
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
            "<i>\u23f8 Pause or \u25b6\ufe0f Resume tracking. \U0001f6ab Stop to remove a show.</i>",
        ]
        rows: list[list[InlineKeyboardButton]] = []
        for track in tracks:
            show = dict(track.get("show_json") or {})
            name = str(show.get("name") or track.get("show_name") or "Unknown")
            season = int(track.get("season") or 1)
            tid = track["track_id"]
            enabled = track.get("enabled")
            lines.append("")
            if enabled:
                lines.append(bot_app._schedule_active_line(track))
            else:
                lines.append(bot_app._schedule_paused_line(name, season))
            if enabled:
                rows.append(
                    [
                        InlineKeyboardButton(f"\u23f8 {name}", callback_data=f"sch:pause:{tid}"),
                        InlineKeyboardButton("\U0001f6ab Stop Tracking", callback_data=f"sch:dconf:{tid}"),
                    ]
                )
            else:
                rows.append(
                    [
                        InlineKeyboardButton(f"\u25b6\ufe0f {name}", callback_data=f"sch:pause:{tid}"),
                        InlineKeyboardButton("\U0001f6ab Stop Tracking", callback_data=f"sch:dconf:{tid}"),
                    ]
                )
        rows.append([InlineKeyboardButton("\u2795 Add New Show", callback_data="sch:addnew")])
        rows += bot_app._nav_footer(back_data="menu:schedule", include_home=False)
        await bot_app._render_nav_ui(
            user_id,
            q.message,
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(rows),
            current_ui_message=q.message,
        )
        return

    if data.startswith("sch:pause:"):
        tid = data.split(":", 2)[2]
        track = await asyncio.to_thread(ctx.store.get_schedule_track, user_id, tid)
        if not track:
            await bot_app._render_nav_ui(
                user_id,
                q.message,
                "Track not found.",
                reply_markup=bot_app._home_only_keyboard(),
                current_ui_message=q.message,
            )
            return
        new_enabled = not track.get("enabled")
        await asyncio.to_thread(ctx.store.update_schedule_track, tid, enabled=new_enabled)
        show = dict(track.get("show_json") or {})
        name = str(show.get("name") or track.get("show_name") or "Unknown")
        action = "resumed" if new_enabled else "paused"
        await q.answer(f"{name} {action}")
        # Re-render My Shows list
        tracks = await asyncio.to_thread(ctx.store.list_schedule_tracks, user_id, False, 50)
        lines = [
            "<b>\U0001f4cb My Shows</b>",
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
            "<i>\u23f8 Pause or \u25b6\ufe0f Resume tracking. \U0001f6ab Stop to remove a show.</i>",
        ]
        rows_list: list[list[InlineKeyboardButton]] = []
        for t in tracks:
            s = dict(t.get("show_json") or {})
            n = str(s.get("name") or t.get("show_name") or "Unknown")
            sn = int(t.get("season") or 1)
            t_id = t["track_id"]
            lines.append("")
            if t.get("enabled"):
                lines.append(bot_app._schedule_active_line(t))
                rows_list.append(
                    [
                        InlineKeyboardButton(f"\u23f8 {n}", callback_data=f"sch:pause:{t_id}"),
                        InlineKeyboardButton("\U0001f6ab Stop Tracking", callback_data=f"sch:dconf:{t_id}"),
                    ]
                )
            else:
                lines.append(bot_app._schedule_paused_line(n, sn))
                rows_list.append(
                    [
                        InlineKeyboardButton(f"\u25b6\ufe0f {n}", callback_data=f"sch:pause:{t_id}"),
                        InlineKeyboardButton("\U0001f6ab Stop Tracking", callback_data=f"sch:dconf:{t_id}"),
                    ]
                )
        rows_list.append([InlineKeyboardButton("\u2795 Add New Show", callback_data="sch:addnew")])
        rows_list += bot_app._nav_footer(back_data="menu:schedule", include_home=False)
        await bot_app._render_nav_ui(
            user_id,
            q.message,
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(rows_list),
            current_ui_message=q.message,
        )
        return

    if data.startswith("sch:dconf:"):
        tid = data.split(":", 2)[2]
        track = await asyncio.to_thread(ctx.store.get_schedule_track, user_id, tid)
        if not track:
            await bot_app._render_nav_ui(
                user_id,
                q.message,
                "Track not found.",
                reply_markup=bot_app._home_only_keyboard(),
                current_ui_message=q.message,
            )
            return
        show = dict(track.get("show_json") or {})
        name = str(show.get("name") or track.get("show_name") or "Unknown")
        season = int(track.get("season") or 1)
        text = (
            f"<b>\U0001f5d1 Delete Tracking?</b>\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
            f"Stop tracking <b>{_h(name)}</b> S{season:02d}?\n\n"
            f"<i>This removes the schedule entry. It won't delete any downloaded files.</i>"
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Yes, delete", callback_data=f"sch:del:{tid}"),
                    InlineKeyboardButton("Cancel", callback_data="sch:myshows"),
                ],
            ]
        )
        await bot_app._render_nav_ui(user_id, q.message, text, reply_markup=kb, current_ui_message=q.message)
        return

    if data.startswith("sch:del:"):
        tid = data.split(":", 2)[2]
        track = await asyncio.to_thread(ctx.store.get_schedule_track, user_id, tid)
        show_name = "Unknown"
        if track:
            show = dict(track.get("show_json") or {})
            show_name = str(show.get("name") or track.get("show_name") or "Unknown")
        deleted = await asyncio.to_thread(ctx.store.delete_schedule_track, tid, user_id)
        if deleted:
            await q.answer(f"{show_name} removed")
        # Re-render My Shows list (reuse sch:myshows logic)
        tracks = await asyncio.to_thread(ctx.store.list_schedule_tracks, user_id, False, 50)
        if not tracks:
            await bot_app._render_nav_ui(
                user_id,
                q.message,
                "<b>\U0001f4cb My Shows</b>\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\nNo shows tracked yet.\nTap <b>Add New Show</b> to get started.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("\u2795 Add New Show", callback_data="sch:addnew")],
                    ]
                    + bot_app._nav_footer(back_data="menu:schedule", include_home=False)
                ),
                current_ui_message=q.message,
            )
            return
        lines = [
            "<b>\U0001f4cb My Shows</b>",
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
            "<i>\u23f8 Pause or \u25b6\ufe0f Resume tracking. \U0001f6ab Stop to remove a show.</i>",
        ]
        rows_del: list[list[InlineKeyboardButton]] = []
        for t in tracks:
            s = dict(t.get("show_json") or {})
            n = str(s.get("name") or t.get("show_name") or "Unknown")
            sn = int(t.get("season") or 1)
            t_id = t["track_id"]
            lines.append("")
            if t.get("enabled"):
                lines.append(bot_app._schedule_active_line(t))
                rows_del.append(
                    [
                        InlineKeyboardButton(f"\u23f8 {n}", callback_data=f"sch:pause:{t_id}"),
                        InlineKeyboardButton("\U0001f6ab Stop Tracking", callback_data=f"sch:dconf:{t_id}"),
                    ]
                )
            else:
                lines.append(bot_app._schedule_paused_line(n, sn))
                rows_del.append(
                    [
                        InlineKeyboardButton(f"\u25b6\ufe0f {n}", callback_data=f"sch:pause:{t_id}"),
                        InlineKeyboardButton("\U0001f6ab Stop Tracking", callback_data=f"sch:dconf:{t_id}"),
                    ]
                )
        rows_del.append([InlineKeyboardButton("\u2795 Add New Show", callback_data="sch:addnew")])
        rows_del += bot_app._nav_footer(back_data="menu:schedule", include_home=False)
        await bot_app._render_nav_ui(
            user_id,
            q.message,
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(rows_del),
            current_ui_message=q.message,
        )
        return

    # Command center actions
