"""Remove-system helpers: search, browse, selection, safety checks, deletion, Plex cleanup.

Extracted from BotApp -- all remove-domain logic lives here as
module-level functions.  Static/class methods become plain functions.
Instance methods take a HandlerContext as their first argument.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import shutil
import time
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..types import HandlerContext
from ..ui.keyboards import compact_action_rows, nav_footer
from ..utils import (
    _h,
    extract_season_number,
    format_remove_episode_label,
    format_remove_season_label,
    human_size,
    is_remove_media_file,
    normalize_title,
    now_ts,
    remove_tv_item_sort_key,
)

LOG = logging.getLogger("qbtg")

# ---------------------------------------------------------------------------
# Show-name stop regex (used by extract_movie_name / extract_show_name)
# ---------------------------------------------------------------------------

_SHOW_NAME_STOP = re.compile(
    r"\b(S\d{1,2}E\d{1,2}|S\d{2}(?=[\s._-]|$)|Season|SEASON|COMPLETE|PROPER|REPACK"
    r"|4K|UHD|\d{3,4}p|BluRay|Blu-Ray|WEB|HDTV|WEBRip|BDRip|DVDRip"
    r"|x264|x265|HEVC|H\.264|H\.265|10bit|6CH|HDR|DDP|Atmos|AAC|AC3)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Runner intervals
# ---------------------------------------------------------------------------


def remove_runner_interval_s() -> int:
    return 60


def remove_retry_backoff_s(retry_count: int) -> int:
    steps = [30, 60, 120, 300, 600]
    idx = max(0, min(int(retry_count or 0), len(steps) - 1))
    return steps[idx]


# ---------------------------------------------------------------------------
# Filesystem helpers (pure -- no ctx needed)
# ---------------------------------------------------------------------------


def path_size_bytes(path: str) -> int:
    try:
        if os.path.isfile(path):
            return max(0, os.path.getsize(path))
        total = 0
        for dirpath, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
            for filename in filenames:
                full = os.path.join(dirpath, filename)
                if os.path.islink(full):
                    continue
                try:
                    total += max(0, os.path.getsize(full))
                except OSError:
                    continue
        return total
    except OSError:
        return 0


def remove_match_score(query_norm: str, candidate_norm: str) -> int:
    if not query_norm or not candidate_norm:
        return 0
    if query_norm == candidate_norm:
        return 100
    if query_norm in candidate_norm:
        return 70
    if candidate_norm in query_norm:
        return 55
    q_tokens = set(query_norm.split())
    c_tokens = set(candidate_norm.split())
    overlap = len(q_tokens & c_tokens)
    if overlap <= 0:
        return 0
    return overlap * 10


# ---------------------------------------------------------------------------
# Name extraction helpers (pure)
# ---------------------------------------------------------------------------


def extract_movie_name(folder_name: str) -> str:
    """Return a clean 'Title (Year)' string for a movie folder/file name."""
    name = folder_name
    name = re.sub(r"^www\.\S+\s*[-\u2013]\s*", "", name)
    name = name.replace("_", " ")
    if "." in name:
        name = name.replace(".", " ")
    # Extract year -- prefer (YYYY) in parens, fall back to bare YYYY
    year: str | None = None
    m = re.search(r"\((\d{4})\)", name)
    if m:
        year = m.group(1)
    else:
        m = re.search(r"\b((?:19|20)\d{2})\b", name)
        if m:
            year = m.group(1)
    # Cut at first quality/encoding marker
    m_stop = _SHOW_NAME_STOP.search(name)
    if m_stop:
        name = name[: m_stop.start()]
    # Cut at bare year position if it wasn't wrapped in parens
    if year and f"({year})" not in name:
        m_yr = re.search(rf"\b{re.escape(year)}\b", name)
        if m_yr:
            name = name[: m_yr.start()]
    # Strip trailing bracketed/parenthesized blocks (year parens already captured above)
    name = re.sub(r"\s*[\[{(][^\])}]*[\])}]\s*$", "", name)
    name = re.sub(r"\s*[-\u2013]\s*[A-Za-z0-9]{2,12}\s*$", "", name)
    name = re.sub(r"[\s.\-_\[({]+$", "", name).strip()
    title = name or folder_name
    if year and f"({year})" not in title:
        return f"{title} ({year})"
    return title


def extract_show_name(folder_name: str) -> str:
    """Normalise a torrent-style folder name to a clean show title."""
    name = folder_name
    # Strip site junk: "www.Site.org - " prefix
    name = re.sub(r"^www\.\S+\s*[-\u2013]\s*", "", name)
    # Common separator cleanup before further parsing.
    name = name.replace("_", " ")
    if "." in name:
        name = name.replace(".", " ")
    # Drop trailing bracketed tag blocks often used for source/release noise.
    name = re.sub(r"\s*[\[{(][^\])}]*[\])}]\s*$", "", name)
    # Cut at the first quality/episode marker
    m = _SHOW_NAME_STOP.search(name)
    if m:
        name = name[: m.start()]
    # Strip bare trailing year labels too, not just "(2024)".
    name = re.sub(r"\s+(19|20)\d{2}\s*$", "", name)
    # Remove a trailing release-group suffix such as "- NTb" or "-TGx".
    name = re.sub(r"\s*[-\u2013]\s*[A-Za-z0-9]{2,12}\s*$", "", name)
    # Strip trailing year-in-parens: "(2024)"
    name = re.sub(r"\s*\(\d{4}\)\s*$", "", name)
    # Strip trailing punctuation / whitespace
    name = re.sub(r"[\s.\-_]+$", "", name).strip()
    return name or folder_name


# ---------------------------------------------------------------------------
# Library roots & candidate discovery (need ctx for cfg paths)
# ---------------------------------------------------------------------------


def remove_roots(ctx: HandlerContext) -> list[dict[str, str]]:
    roots: list[dict[str, str]] = []
    seen: set[str] = set()
    for key, label, path in [
        ("movies", "Movies", ctx.cfg.movies_path),
        ("tv", "TV", ctx.cfg.tv_path),
        ("spam", "Spam", ctx.cfg.spam_path),
    ]:
        root_path = str(path or "").strip()
        if not root_path or not os.path.isdir(root_path):
            continue
        real = os.path.realpath(root_path)
        if real in seen:
            continue
        seen.add(real)
        roots.append({"key": key, "label": label, "path": real})
    return roots


def find_remove_candidates(ctx: HandlerContext, query: str, limit: int = 8) -> list[dict[str, Any]]:
    query_norm = normalize_title(query)
    candidates: list[tuple[int, dict[str, Any]]] = []
    for root in remove_roots(ctx):
        root_path = root["path"]
        try:
            entries = list(os.scandir(root_path))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                entry_path = os.path.realpath(entry.path)
                if os.path.dirname(entry_path) != root_path:
                    continue
                is_dir = entry.is_dir(follow_symlinks=False)
                if not is_dir and root["key"] in {"movies", "tv"} and not is_remove_media_file(entry.name):
                    continue
                score = remove_match_score(query_norm, normalize_title(entry.name))
                if score <= 0:
                    continue
                size_bytes = path_size_bytes(entry_path)
                if root["key"] == "tv":
                    remove_kind = "show" if is_dir else "episode"
                elif root["key"] == "movies":
                    remove_kind = "movie"
                else:
                    remove_kind = "item"
                item_name = entry.name
                show_name: str | None = None
                season_number: int | None = None
                if root["key"] == "tv":
                    if is_dir:
                        show_name = extract_show_name(entry.name)
                    else:
                        season_number = extract_season_number(entry.name)
                        item_name = format_remove_episode_label(entry.name, season_number)
                candidates.append(
                    (
                        score,
                        {
                            "name": item_name,
                            "source_name": entry.name,
                            "path": entry_path,
                            "root_key": root["key"],
                            "root_label": root["label"],
                            "root_path": root_path,
                            "is_dir": is_dir,
                            "size_bytes": size_bytes,
                            "remove_kind": remove_kind,
                            "show_name": show_name,
                            "season_number": season_number,
                        },
                    )
                )
            except OSError:
                continue
    deduped: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for _score, candidate in sorted(
        candidates, key=lambda item: (item[0], item[1]["size_bytes"], item[1]["name"].lower()), reverse=True
    ):
        if candidate["path"] in seen_paths:
            continue
        seen_paths.add(candidate["path"])
        deduped.append(candidate)
        if len(deduped) >= max(1, limit):
            break
    return deduped


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------


def remove_prompt_keyboard(selected_count: int = 0) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton("\U0001f4da Browse Plex Library", callback_data="rm:browse")],
    ]
    if selected_count > 0:
        rows.append(
            [InlineKeyboardButton(f"\U0001f9fe Review Selection ({selected_count})", callback_data="rm:review")]
        )
        rows.append([InlineKeyboardButton("\U0001f9f9 Clear Selection", callback_data="rm:clear")])
    rows.append([InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")])
    rows.extend(nav_footer(include_home=False))
    return InlineKeyboardMarkup(compact_action_rows(rows))


def remove_browse_root_keyboard(movie_count: int, show_count: int, selected_count: int = 0) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(f"\U0001f3ac Movies ({movie_count})", callback_data="rm:browsecat:movies"),
            InlineKeyboardButton(f"\U0001f4fa Shows ({show_count})", callback_data="rm:browsecat:tv"),
        ],
    ]
    if selected_count > 0:
        rows.append(
            [InlineKeyboardButton(f"\U0001f9fe Review Selection ({selected_count})", callback_data="rm:review")]
        )
        rows.append([InlineKeyboardButton("\U0001f9f9 Clear Selection", callback_data="rm:clear")])
    rows.extend(nav_footer(back_data="rm:cancel", include_home=False))
    return InlineKeyboardMarkup(compact_action_rows(rows))


# ---------------------------------------------------------------------------
# Selection helpers
# ---------------------------------------------------------------------------


def remove_selected_path(candidate: dict[str, Any]) -> str:
    return os.path.realpath(str(candidate.get("path") or "").strip())


def remove_enrich_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(candidate)
    if enriched.get("size_bytes") is None:
        enriched["size_bytes"] = path_size_bytes(str(enriched.get("path") or ""))
    return enriched


def remove_selection_items(flow: dict[str, Any] | None) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for raw in list((flow or {}).get("selected_items") or []):
        candidate = remove_enrich_candidate(dict(raw))
        if remove_selected_path(candidate):
            selected.append(candidate)
    return selected


def remove_selected_paths(flow: dict[str, Any] | None) -> set[str]:
    return {remove_selected_path(candidate) for candidate in remove_selection_items(flow)}


def remove_selection_count(flow: dict[str, Any] | None) -> int:
    return len(remove_selection_items(flow))


def remove_toggle_candidate(flow: dict[str, Any], candidate: dict[str, Any]) -> bool:
    candidate = remove_enrich_candidate(candidate)
    target_path = remove_selected_path(candidate)
    if not target_path:
        return False
    selected = remove_selection_items(flow)
    updated: list[dict[str, Any]] = []
    removed_exact = False
    for existing in selected:
        existing_path = remove_selected_path(existing)
        if not existing_path:
            continue
        if existing_path == target_path:
            removed_exact = True
            continue
        if existing_path.startswith(target_path + os.sep):
            continue
        if target_path.startswith(existing_path + os.sep):
            continue
        updated.append(existing)
    if not removed_exact:
        updated.append(candidate)
    flow["selected_items"] = sorted(
        updated,
        key=lambda item: (
            str(item.get("root_label") or ""),
            str(item.get("name") or "").lower(),
            str(item.get("path") or ""),
        ),
    )
    return not removed_exact


def remove_selection_total_size(candidates: list[dict[str, Any]]) -> int:
    return sum(int(remove_enrich_candidate(candidate).get("size_bytes") or 0) for candidate in candidates)


def remove_effective_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for raw in candidates:
        candidate = remove_enrich_candidate(dict(raw))
        path = remove_selected_path(candidate)
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        candidate["_resolved_path"] = path
        deduped.append(candidate)
    deduped.sort(key=lambda item: (item["_resolved_path"].count(os.sep), item["_resolved_path"]))
    collapsed: list[dict[str, Any]] = []
    for candidate in deduped:
        path = candidate["_resolved_path"]
        if any(
            path == kept["_resolved_path"] or path.startswith(kept["_resolved_path"] + os.sep) for kept in collapsed
        ):
            continue
        collapsed.append(candidate)
    for candidate in collapsed:
        candidate.pop("_resolved_path", None)
    return collapsed


# ---------------------------------------------------------------------------
# Toggle / label helpers
# ---------------------------------------------------------------------------


def remove_toggle_label(candidate: dict[str, Any], selected_paths: set[str]) -> str:
    prefix = "\u2705 " if remove_selected_path(candidate) in selected_paths else ""
    name = remove_display_name(candidate)
    return f"{prefix}{name[:56]}"


def remove_kind_label(kind: str, is_dir: bool) -> str:
    mapping = {
        "movie": "movie" if not is_dir else "movie folder",
        "show": "series",
        "season": "season",
        "episode": "episode" if not is_dir else "episode folder",
        "item": "item" if not is_dir else "folder",
    }
    return mapping.get(str(kind or "").strip(), "folder" if is_dir else "file")


def remove_display_name(candidate: dict[str, Any], *, single_season_show: bool = False) -> str:
    kind = str(candidate.get("remove_kind") or "").strip()
    name = str(candidate.get("name") or "Item")
    if kind == "movie":
        return extract_movie_name(name)
    if kind == "show":
        return str(candidate.get("show_name") or extract_show_name(name) or name)
    if kind == "season":
        show_name = str(candidate.get("show_name") or "").strip()
        season_number = int(candidate.get("season_number") or 0)
        if show_name and season_number > 0:
            if single_season_show:
                return show_name
            return f"{show_name} Season {season_number}"
        return format_remove_season_label(name)
    if kind == "episode":
        source_name = str(candidate.get("source_name") or "").strip()
        if source_name:
            season_number = int(candidate.get("season_number") or 0) or None
            return format_remove_episode_label(source_name, season_number)
        return name
    return name


def remove_series_selected(candidate: dict[str, Any], selected_paths: set[str]) -> bool:
    group_items = list(candidate.get("group_items") or [])
    if group_items:
        return any(remove_selected_path(item) in selected_paths for item in group_items)
    return remove_selected_path(candidate) in selected_paths


# ---------------------------------------------------------------------------
# Text builders
# ---------------------------------------------------------------------------


def remove_candidate_text(candidate: dict[str, Any]) -> str:
    candidate = remove_enrich_candidate(candidate)
    kind = remove_kind_label(str(candidate.get("remove_kind") or ""), bool(candidate.get("is_dir")))
    size_txt = human_size(int(candidate.get("size_bytes") or 0))
    name = remove_display_name(candidate)
    return f"{_h(name)} ({_h(candidate.get('root_label') or '')} <i>{_h(kind)}</i>, <code>{_h(size_txt)}</code>)"


def remove_candidates_text(query: str, candidates: list[dict[str, Any]], selected_paths: set[str] | None = None) -> str:
    chosen = set(selected_paths or set())
    lines = [f"<b>\U0001f5d1\ufe0f Remove: Search Results</b>\nQuery: <code>{_h(query)}</code>", ""]
    for idx, candidate in enumerate(candidates, start=1):
        prefix = "\u2705 " if remove_selected_path(candidate) in chosen else ""
        lines.append(f"{idx}. {prefix}{remove_candidate_text(candidate)}")
    lines.extend(
        [
            "",
            f"Selected so far: <b>{len(chosen)}</b> item(s)",
            "<i>Tap items to toggle them, then use Review Selection when you're ready.</i>",
        ]
    )
    return "\n".join(lines)


def remove_confirm_text(candidates: list[dict[str, Any]]) -> str:
    effective = remove_effective_candidates(candidates)
    count = len(effective)
    total_size = human_size(remove_selection_total_size(effective))
    numbered_items = []
    path_lines = []
    for idx, candidate in enumerate(effective[:12], start=1):
        candidate = remove_enrich_candidate(candidate)
        kind = remove_kind_label(str(candidate.get("remove_kind") or ""), bool(candidate.get("is_dir")))
        size_txt = human_size(int(candidate.get("size_bytes") or 0))
        name = _h(remove_display_name(candidate))
        root_label = _h(candidate.get("root_label") or "")
        numbered_items.append(f"{idx}. <b>{name}</b> ({root_label} {_h(kind)}, <code>{_h(size_txt)}</code>)")
        path_lines.append(_h(str(candidate.get("path") or "")))
    if count > 12:
        numbered_items.append(f"\u2026and {count - 12} more item(s).")
        path_lines.append(f"\u2026and {count - 12} more.")
    paths_block = "\n".join(path_lines)
    lines = [
        "<b>\u26a0\ufe0f Confirm Permanent Delete</b>",
        "\u2501" * 20,
        f"Selected <b>{count}</b> item(s) totaling <b>{_h(total_size)}</b>:",
        "",
    ]
    lines.extend(numbered_items)
    lines.extend(
        [
            "",
            f"<blockquote expandable>Full paths:\n{paths_block}</blockquote>",
            "",
            "<b>This will fully delete the selected items from disk.</b>",
        ]
    )
    return "\n".join(lines)


def remove_show_actions_text(show_candidate: dict[str, Any], series_selected: bool) -> str:
    group_items: list[dict[str, Any]] = show_candidate.get("group_items") or []
    if len(group_items) > 1:
        total_size = sum(path_size_bytes(str(i.get("path") or "")) for i in group_items)
        detail = f"{show_candidate.get('name')} (TV series, {human_size(total_size)}, {len(group_items)} folders)"
    else:
        show_candidate = remove_enrich_candidate(show_candidate)
        detail = remove_candidate_text(show_candidate)
    series_status = (
        "\u2705 <b>Entire series is selected for deletion.</b>"
        if series_selected
        else "\u2139\ufe0f <b>Entire series is not currently selected.</b>"
    )
    return (
        "<b>\U0001f4fa TV Delete Options</b>\n\n"
        f"Selected series: {detail}\n"
        f"{series_status}\n\n"
        "<i>Choose whether to remove the entire series or browse seasons and episodes.</i>"
    )


def remove_season_actions_text(season_candidate: dict[str, Any]) -> str:
    season_candidate = remove_enrich_candidate(season_candidate)
    show_name = str(season_candidate.get("show_name") or "Show")
    return (
        "<b>\U0001f4c2 Season Delete Options</b>\n\n"
        f"Series: {_h(show_name)}\n"
        f"Selected season: {remove_candidate_text(season_candidate)}\n\n"
        "<i>Choose whether to remove the entire season or browse individual episodes.</i>"
    )


# ---------------------------------------------------------------------------
# More keyboards
# ---------------------------------------------------------------------------


def remove_candidate_keyboard(
    candidates: list[dict[str, Any]], selected_paths: set[str] | None = None
) -> InlineKeyboardMarkup:
    chosen = set(selected_paths or set())
    rows: list[list[InlineKeyboardButton]] = []
    for idx, candidate in enumerate(candidates[:8]):
        if str(candidate.get("remove_kind") or "") == "show":
            show_name = remove_display_name(candidate)
            series_selected = remove_series_selected(candidate, chosen)
            series_label = f"Delete Series: {show_name}"
            if series_selected:
                series_label = f"\u2705 {series_label}"
            rows.append([InlineKeyboardButton(f"\U0001f5d1 {series_label}"[:64], callback_data=f"rm:delseries:{idx}")])

            season_items = [
                item
                for item in remove_show_children(candidate)
                if str(item.get("remove_kind") or "") == "season" and int(item.get("season_number") or 0) > 0
            ]
            season_items.sort(key=remove_tv_item_sort_key)
            single_season_show = len(season_items) == 1
            for season_item in season_items[:8]:
                season_number = int(season_item.get("season_number") or 0)
                if season_number <= 0:
                    continue
                label = remove_display_name(season_item, single_season_show=single_season_show)
                rows.append(
                    [InlineKeyboardButton(label[:56], callback_data=f"rm:showseason:{idx}:{season_number}")]
                )
            continue
        rows.append([InlineKeyboardButton(remove_toggle_label(candidate, chosen), callback_data=f"rm:pick:{idx}")])
    rows.append([InlineKeyboardButton(f"\U0001f9fe Review Selection ({len(chosen)})", callback_data="rm:review")])
    if chosen:
        rows.append([InlineKeyboardButton("\U0001f9f9 Clear Selection", callback_data="rm:clear")])
    rows.append([InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")])
    rows.extend(nav_footer(include_home=False))
    return InlineKeyboardMarkup(rows)


def remove_confirm_keyboard(selected_count: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(f"\u2705 Confirm Delete ({selected_count})", callback_data="rm:confirm")]
    ]
    rows.append([InlineKeyboardButton("\U0001f9f9 Clear Selection", callback_data="rm:clear")])
    rows.append([InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")])
    rows.extend(nav_footer(include_home=False))
    return InlineKeyboardMarkup(compact_action_rows(rows))


def remove_show_action_keyboard(series_selected: bool, selected_count: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if not series_selected:
        rows.append(
            [
                InlineKeyboardButton("\U0001f5d1 Select Entire Series", callback_data="rm:series"),
                InlineKeyboardButton("\U0001f4c2 Browse Seasons", callback_data="rm:seasons"),
            ]
        )
    rows.append([InlineKeyboardButton(f"\U0001f9fe Review Selection ({selected_count})", callback_data="rm:review")])
    if selected_count > 0:
        rows.append([InlineKeyboardButton("\U0001f9f9 Clear Selection", callback_data="rm:clear")])
    rows.append([InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")])
    rows.extend(nav_footer(include_home=False))
    return InlineKeyboardMarkup(compact_action_rows(rows))


def remove_season_action_keyboard(selected: bool, selected_count: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                "\u2705 Entire Season Selected" if selected else "\U0001f5d1 Select Entire Season",
                callback_data="rm:seasondel",
            ),
            InlineKeyboardButton("\U0001f39e Browse Episodes", callback_data="rm:episodes"),
        ],
        [InlineKeyboardButton(f"\U0001f9fe Review Selection ({selected_count})", callback_data="rm:review")],
    ]
    if selected_count > 0:
        rows.append([InlineKeyboardButton("\U0001f9f9 Clear Selection", callback_data="rm:clear")])
    rows.append([InlineKeyboardButton("\u2b05\ufe0f Back to Series", callback_data="rm:back:show")])
    rows.append([InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")])
    rows.extend(nav_footer(include_home=False))
    return InlineKeyboardMarkup(compact_action_rows(rows))


def remove_season_detail_keyboard(
    season_candidate: dict[str, Any], selected_paths: set[str] | None, show_idx: int
) -> InlineKeyboardMarkup:
    del show_idx
    chosen = set(selected_paths or set())
    season_number = int(season_candidate.get("season_number") or 0)
    selected = remove_selected_path(season_candidate) in chosen
    if selected and season_number > 0:
        delete_label = f"\u2705 Season {season_number} Selected"
    elif selected:
        delete_label = "\u2705 Season Selected"
    elif season_number > 0:
        delete_label = f"\U0001f5d1 Delete Season {season_number}"
    else:
        delete_label = "\U0001f5d1 Delete Season"
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(delete_label, callback_data="rm:seasondel")],
        [InlineKeyboardButton("\U0001f4cb Select Episodes", callback_data="rm:episodes")],
        [
            InlineKeyboardButton("\u25c0\ufe0f Back", callback_data="rm:backtoshow"),
            InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def remove_page_bounds(items: list[dict[str, Any]], page: int, per_page: int = 8) -> tuple[int, int, int, int]:
    total_pages = max(1, math.ceil(max(1, len(items)) / per_page))
    page = max(0, min(int(page), total_pages - 1))
    start = page * per_page
    end = min(start + per_page, len(items))
    return page, total_pages, start, end


def remove_paginated_keyboard(
    items: list[dict[str, Any]],
    page: int,
    *,
    item_prefix: str,
    nav_prefix: str,
    back_callback: str | None = None,
    selected_paths: set[str] | None = None,
    compact_browse_footer: bool = False,
) -> InlineKeyboardMarkup:
    page, total_pages, start, end = remove_page_bounds(items, page)
    chosen = set(selected_paths or set())
    rows: list[list[InlineKeyboardButton]] = []
    for idx in range(start, end):
        candidate = items[idx]
        rows.append(
            [InlineKeyboardButton(remove_toggle_label(candidate, chosen), callback_data=f"{item_prefix}:{idx}")]
        )
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("\u2b05\ufe0f Prev", callback_data=f"{nav_prefix}:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next \u27a1\ufe0f", callback_data=f"{nav_prefix}:{page + 1}"))
    if nav_row:
        rows.append(nav_row)
    review_button = InlineKeyboardButton(f"\U0001f9fe Review Selection ({len(chosen)})", callback_data="rm:review")
    clear_button = InlineKeyboardButton("\U0001f9f9 Clear Selection", callback_data="rm:clear")
    back_button = InlineKeyboardButton("\u2b05\ufe0f Back", callback_data=back_callback) if back_callback else None
    home_button = InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")

    if compact_browse_footer and not chosen:
        if len(nav_row) == 1 and back_button is not None:
            rows[-1] = [back_button, nav_row[0]]
            rows.append([review_button, home_button])
        else:
            rows.append([review_button])
            if back_button is not None:
                rows.append([back_button, home_button])
            else:
                rows.append([home_button])
    else:
        rows.append([review_button])
        if chosen:
            rows.append([clear_button])
        if back_button is not None:
            rows.append([back_button])
        rows.append([home_button])
    rows.extend(nav_footer(include_home=False))
    return InlineKeyboardMarkup(rows)


def remove_list_text(
    title: str, items: list[dict[str, Any]], page: int, *, hint: str, selected_paths: set[str] | None = None
) -> str:
    page, total_pages, start, end = remove_page_bounds(items, page)
    chosen = set(selected_paths or set())
    lines = [f"<b>{_h(title)}</b>"]
    if total_pages > 1:
        lines.extend(["", f"<i>Page {page + 1}/{total_pages}</i>"])
    lines.extend(["", f"Selected so far: <b>{len(chosen)}</b> item(s)", f"<i>{_h(hint)}</i>"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Library browsing
# ---------------------------------------------------------------------------


def remove_library_items(ctx: HandlerContext, root_key: str) -> list[dict[str, Any]]:
    roots = {root["key"]: root for root in remove_roots(ctx)}
    root = roots.get(str(root_key or ""))
    if not root:
        return []
    root_path = root["path"]
    items: list[dict[str, Any]] = []
    try:
        entries = sorted(os.scandir(root_path), key=lambda entry: entry.name.lower())
    except OSError:
        return []
    for entry in entries:
        try:
            if entry.is_symlink():
                continue
            entry_path = os.path.realpath(entry.path)
            if os.path.dirname(entry_path) != root_path:
                continue
            is_dir = entry.is_dir(follow_symlinks=False)
            if not is_dir and root["key"] in {"movies", "tv"} and not is_remove_media_file(entry.name):
                continue
            if root["key"] == "tv":
                rkind = "show" if is_dir else "episode"
            elif root["key"] == "movies":
                rkind = "movie"
            else:
                rkind = "item"
            item_name = entry.name
            show_name: str | None = None
            season_number: int | None = None
            if root["key"] == "tv":
                if is_dir:
                    show_name = extract_show_name(entry.name)
                else:
                    season_number = extract_season_number(entry.name)
                    item_name = format_remove_episode_label(entry.name, season_number)
            items.append(
                {
                    "name": item_name,
                    "source_name": entry.name,
                    "path": entry_path,
                    "root_key": root["key"],
                    "root_label": root["label"],
                    "root_path": root_path,
                    "is_dir": is_dir,
                    "size_bytes": None,
                    "remove_kind": rkind,
                    "show_name": show_name,
                    "season_number": season_number,
                }
            )
        except OSError:
            continue
    items.sort(key=remove_tv_item_sort_key)
    return items


def remove_show_children(show_candidate: dict[str, Any]) -> list[dict[str, Any]]:
    show_path = os.path.realpath(str(show_candidate.get("path") or ""))
    root_path = os.path.realpath(str(show_candidate.get("root_path") or ""))
    show_name = str(show_candidate.get("name") or "Show")
    if not show_path or not root_path or not os.path.isdir(show_path):
        return []
    if os.path.commonpath([show_path, root_path]) != root_path:
        return []
    items: list[dict[str, Any]] = []
    try:
        entries = sorted(os.scandir(show_path), key=lambda entry: entry.name.lower())
    except OSError:
        return []
    for entry in entries:
        try:
            if entry.is_symlink():
                continue
            child_path = os.path.realpath(entry.path)
            if os.path.dirname(child_path) != show_path:
                continue
            is_dir = entry.is_dir(follow_symlinks=False)
            if is_dir:
                season_number = extract_season_number(entry.name)
                if season_number is None:
                    continue
                display_name = format_remove_season_label(entry.name)
            else:
                if not is_remove_media_file(entry.name):
                    continue
                season_number = None
                display_name = format_remove_episode_label(entry.name)
            items.append(
                {
                    "name": display_name,
                    "source_name": entry.name,
                    "path": child_path,
                    "root_key": str(show_candidate.get("root_key") or "tv"),
                    "root_label": str(show_candidate.get("root_label") or "TV"),
                    "root_path": root_path,
                    "is_dir": is_dir,
                    "size_bytes": None,
                    "remove_kind": "season" if is_dir else "episode",
                    "show_name": show_name,
                    "show_path": show_path,
                    "season_number": season_number,
                }
            )
        except OSError:
            continue
    items.sort(key=remove_tv_item_sort_key)
    return items


def remove_season_children(season_candidate: dict[str, Any]) -> list[dict[str, Any]]:
    season_path = os.path.realpath(str(season_candidate.get("path") or ""))
    root_path = os.path.realpath(str(season_candidate.get("root_path") or ""))
    show_path = os.path.realpath(str(season_candidate.get("show_path") or ""))
    season_number = int(season_candidate.get("season_number") or 0) or extract_season_number(
        str(season_candidate.get("name") or "")
    )
    if not season_path or not root_path or not os.path.isdir(season_path):
        return []
    if os.path.commonpath([season_path, root_path]) != root_path:
        return []
    items: list[dict[str, Any]] = []
    try:
        entries = sorted(os.scandir(season_path), key=lambda entry: entry.name.lower())
    except OSError:
        return []
    for entry in entries:
        try:
            if entry.is_symlink() or entry.is_dir(follow_symlinks=False) or not is_remove_media_file(entry.name):
                continue
            child_path = os.path.realpath(entry.path)
            if os.path.dirname(child_path) != season_path:
                continue
            items.append(
                {
                    "name": format_remove_episode_label(entry.name, season_number),
                    "source_name": entry.name,
                    "path": child_path,
                    "root_key": str(season_candidate.get("root_key") or "tv"),
                    "root_label": str(season_candidate.get("root_label") or "TV"),
                    "root_path": root_path,
                    "is_dir": False,
                    "size_bytes": None,
                    "remove_kind": "episode",
                    "show_name": str(season_candidate.get("show_name") or "Show"),
                    "show_path": show_path,
                    "season_name": str(season_candidate.get("name") or "Season"),
                    "season_path": season_path,
                    "season_number": season_number,
                }
            )
        except OSError:
            continue
    items.sort(key=remove_tv_item_sort_key)
    return items


# ---------------------------------------------------------------------------
# Show-group helpers (normalize + group TV folders by show name)
# ---------------------------------------------------------------------------


def remove_group_tv_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group flat TV top-level items by normalised show name."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = extract_show_name(str(item.get("name") or "")).lower()
        groups.setdefault(key, []).append(item)

    result: list[dict[str, Any]] = []
    for group_items in groups.values():
        # Clean-named folders (with spaces) first, then torrent packs
        group_items.sort(key=lambda i: (0 if " " in str(i.get("name", "")) else 1, str(i.get("name", "")).lower()))
        primary = group_items[0]
        display_name = extract_show_name(str(primary.get("name") or ""))
        result.append(
            {
                **primary,
                "name": display_name,
                "remove_kind": "show",
                "group_items": group_items,
            }
        )

    result.sort(key=lambda x: str(x.get("name") or "").lower())
    return result


def remove_show_group_children(group_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate all seasons / episode packs from every folder in a show group."""
    all_children: list[dict[str, Any]] = []
    for item in group_items:
        if not item.get("is_dir"):
            all_children.append(
                {
                    **item,
                    "name": format_remove_episode_label(str(item.get("source_name") or item.get("name") or "")),
                    "remove_kind": "episode",
                }
            )
            continue
        sub = remove_show_children(item)
        # If the folder directly contains season sub-dirs, expose those seasons
        has_dir_children = any(c.get("is_dir") for c in sub)
        if has_dir_children:
            all_children.extend(sub)
        elif sub:
            # Download pack whose contents are plain episode files -> treat
            # the pack folder itself as one deletable "season" unit
            all_children.append(
                {
                    **item,
                    "name": format_remove_season_label(str(item.get("name") or "Season")),
                    "remove_kind": "season",
                    "show_name": extract_show_name(str(item.get("name") or "")),
                    "show_path": str(item.get("path") or ""),
                    "season_number": extract_season_number(str(item.get("name") or "")),
                }
            )
        # Empty directory -> skip
    all_children.sort(key=remove_tv_item_sort_key)
    return all_children


def remove_group_any_selected(flow: dict[str, Any], group_item: dict[str, Any]) -> bool:
    """Return True if any path in the group is currently in the selection."""
    group_items = group_item.get("group_items") or [group_item]
    sel_paths = remove_selected_paths(flow)
    return any(remove_selected_path(i) in sel_paths for i in group_items)


def remove_toggle_group(flow: dict[str, Any], group_item: dict[str, Any]) -> bool:
    """Toggle all paths in a group as a batch. Returns True if group is now selected."""
    group_items = group_item.get("group_items") or [group_item]
    group_paths = {remove_selected_path(i) for i in group_items}
    any_selected = bool(group_paths & remove_selected_paths(flow))
    # Remove any existing group paths from selection first
    flow["selected_items"] = [
        s for s in (flow.get("selected_items") or []) if remove_selected_path(s) not in group_paths
    ]
    if not any_selected:
        for item in group_items:
            remove_toggle_candidate(flow, item)
        return True
    return False


# ---------------------------------------------------------------------------
# qBittorrent cleanup
# ---------------------------------------------------------------------------


def cleanup_qbt_for_path(ctx: HandlerContext, target_path: str) -> list[str]:
    """Remove qBittorrent torrents whose content matches a deleted path."""
    real_target = os.path.realpath(target_path)
    if not real_target:
        return []
    try:
        all_torrents = ctx.qbt.list_torrents(limit=5000)
    except Exception:
        LOG.warning("Failed to list qBittorrent torrents for cleanup", exc_info=True)
        return []
    cleaned: list[str] = []
    for t in all_torrents:
        content = str(t.get("content_path") or "").strip()
        if not content:
            continue
        real_content = os.path.realpath(content)
        if real_content == real_target or real_content.startswith(real_target + os.sep):
            try:
                ctx.qbt.delete_torrent(t["hash"], delete_files=False)
                cleaned.append(str(t.get("name") or t["hash"]))
            except Exception:
                LOG.warning("Failed to remove qBittorrent torrent %s", t.get("hash"), exc_info=True)
    return cleaned


# ---------------------------------------------------------------------------
# Plex cleanup job helpers
# ---------------------------------------------------------------------------


def remove_build_job_verification(
    candidate: dict[str, Any],
    target_path: str,
    identity: dict[str, Any] | None,
) -> dict[str, Any]:
    data = dict(identity or {})
    data.setdefault("target_path", target_path)
    data.setdefault("remove_kind", str(candidate.get("remove_kind") or ""))
    return data


def remove_attempt_plex_cleanup(
    ctx: HandlerContext,
    job: dict[str, Any],
    *,
    inline_timeout_s: int = 90,
) -> dict[str, Any]:
    job_id = str(job.get("job_id") or "")
    verification = dict(job.get("verification_json") or {})
    target_path = str(job.get("target_path") or "")
    remove_kind = str(job.get("remove_kind") or "")
    section_key = str(job.get("plex_section_key") or verification.get("section_key") or "").strip()
    scan_path = str(job.get("scan_path") or verification.get("scan_path") or "").strip() or target_path
    title = str(job.get("plex_title") or verification.get("title") or job.get("item_name") or "item")
    deadline = time.monotonic() + max(5.0, float(inline_timeout_s))
    attempts = 0
    last_error = ""
    while True:
        attempts += 1
        try:
            ctx.store.update_remove_job(job_id, plex_cleanup_started_at=now_ts(), status="plex_pending")
            if section_key:
                ctx.plex._request("POST", f"/library/sections/{section_key}/refresh", params={"path": scan_path})
                ctx.plex._wait_for_section_idle(section_key, timeout_s=min(30, inline_timeout_s), min_wait_s=3.0)
                ctx.plex._request("PUT", f"/library/sections/{section_key}/emptyTrash")
            else:
                # Path didn't match a known Plex section -- refresh all sections of the
                # matching content type so the deletion always surfaces in Plex.
                if remove_kind == "movie":
                    fallback_types = ["movie"]
                elif remove_kind in {"show", "season", "episode"}:
                    fallback_types = ["show"]
                else:
                    fallback_types = ["movie", "show"]
                ctx.plex.refresh_all_by_type(fallback_types)
            verified, detail = ctx.plex.verify_remove_identity_absent(target_path, remove_kind, verification)
            if verified:
                ctx.store.update_remove_job(
                    job_id,
                    status="verified",
                    verified_at=now_ts(),
                    next_retry_at=None,
                    retry_count=int(job.get("retry_count") or 0) + attempts - 1,
                    last_error_text=None,
                )
                return {"status": "verified", "detail": detail, "attempts": attempts}
            last_error = detail
        except Exception as e:
            last_error = str(e)
            LOG.warning("Remove Plex cleanup attempt failed for %s: %s", job_id, e, exc_info=True)
        if time.monotonic() >= deadline:
            next_retry = now_ts() + remove_retry_backoff_s(int(job.get("retry_count") or 0) + attempts)
            ctx.store.update_remove_job(
                job_id,
                status="plex_pending",
                next_retry_at=next_retry,
                retry_count=int(job.get("retry_count") or 0) + attempts,
                last_error_text=last_error or f"Plex cleanup still pending for {title}",
            )
            return {
                "status": "plex_pending",
                "detail": last_error or f"Plex cleanup still pending for {title}",
                "attempts": attempts,
                "next_retry_at": next_retry,
            }
        time.sleep(min(15.0, float(remove_retry_backoff_s(attempts - 1))))


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------


async def remove_runner_job(ctx: HandlerContext, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with ctx.remove_runner_lock:
        due_jobs = await asyncio.to_thread(ctx.store.list_due_remove_jobs, now_ts(), 5)
        for job in due_jobs:
            try:
                result = await asyncio.to_thread(remove_attempt_plex_cleanup, ctx, job, inline_timeout_s=45)
                LOG.info(
                    "Remove job %s processed: status=%s detail=%s",
                    job.get("job_id"),
                    result.get("status"),
                    result.get("detail"),
                )
            except Exception:
                LOG.warning("Remove job processing failed for %s", job.get("job_id"), exc_info=True)


# ---------------------------------------------------------------------------
# Core deletion pipeline (CRITICAL SAFETY LOGIC -- DO NOT WEAKEN)
# ---------------------------------------------------------------------------


def delete_remove_candidate(
    ctx: HandlerContext, candidate: dict[str, Any], *, user_id: int | None = None, chat_id: int | None = None
) -> dict[str, Any]:
    raw_root_path = str(candidate.get("root_path") or "").strip()
    raw_target_path = str(candidate.get("path") or "").strip()
    root_key = str(candidate.get("root_key") or "").strip().lower()
    remove_kind = str(candidate.get("remove_kind") or "").strip().lower()
    root_path = os.path.realpath(raw_root_path)
    target_path = os.path.realpath(raw_target_path)
    if not root_path or not target_path or not raw_target_path:
        raise RuntimeError("Invalid removal target")
    if os.path.islink(raw_target_path):
        raise RuntimeError("Refusing to delete symbolic links")
    if os.path.commonpath([target_path, root_path]) != root_path:
        raise RuntimeError("Refusing to delete outside configured media roots")
    if not os.path.exists(target_path):
        raise RuntimeError("The selected item no longer exists on disk")

    rel_parts = [part for part in os.path.relpath(target_path, root_path).split(os.sep) if part and part != "."]
    if root_key in {"movies", "spam"}:
        if len(rel_parts) != 1:
            raise RuntimeError("Refusing to delete nested paths directly")
    elif root_key == "tv":
        if remove_kind == "show":
            if len(rel_parts) != 1:
                raise RuntimeError("Refusing to delete outside a top-level TV series folder")
        elif remove_kind == "season":
            if len(rel_parts) != 2:
                raise RuntimeError("Refusing to delete outside a direct season path")
        elif remove_kind == "episode":
            if len(rel_parts) not in {1, 2, 3} or os.path.isdir(target_path):
                raise RuntimeError("Refusing to delete outside a direct episode path")
        else:
            raise RuntimeError("Unsupported TV removal type")
    else:
        raise RuntimeError("Unsupported library root for deletion")

    identity: dict[str, Any] | None = None
    deleted_size = path_size_bytes(target_path)
    display_name = remove_display_name(candidate)
    if ctx.plex.ready() and root_key in {"movies", "tv"}:
        try:
            identity = ctx.plex.resolve_remove_identity(target_path, remove_kind)
        except Exception:
            LOG.warning("Failed to resolve Plex identity before delete for %s", target_path, exc_info=True)
    if os.path.isdir(target_path):
        shutil.rmtree(target_path)
    else:
        os.remove(target_path)

    # Clean up matching qBittorrent torrents (files already gone from disk)
    qbt_cleaned = cleanup_qbt_for_path(ctx, target_path)
    if qbt_cleaned:
        LOG.info("Cleaned up %d qBittorrent torrent(s) for %s: %s", len(qbt_cleaned), target_path, qbt_cleaned)

    plex_status = "skipped"
    plex_note = "Plex cleanup skipped."
    remove_job: dict[str, Any] | None = None
    if ctx.plex.ready() and root_key in {"movies", "tv"}:
        verification = remove_build_job_verification(candidate, target_path, identity)
        remove_job = ctx.store.create_remove_job(
            user_id=int(user_id or 0),
            chat_id=int(chat_id or 0),
            item_name=display_name or str(candidate.get("name") or os.path.basename(target_path)),
            root_key=root_key,
            root_label=str(candidate.get("root_label") or ""),
            remove_kind=remove_kind,
            target_path=target_path,
            root_path=root_path,
            scan_path=str(identity.get("scan_path") or "") if identity else None,
            plex_section_key=str(identity.get("section_key") or "") if identity else None,
            plex_rating_key=str(identity.get("primary_rating_key") or "") if identity else None,
            plex_title=str(identity.get("title") or candidate.get("name") or "") if identity else None,
            verification_json=verification,
            status="plex_pending",
            disk_deleted_at=now_ts(),
            next_retry_at=now_ts(),
        )
        cleanup = remove_attempt_plex_cleanup(ctx, remove_job, inline_timeout_s=90)
        plex_status = str(cleanup.get("status") or "plex_pending")
        plex_note = str(cleanup.get("detail") or "Plex cleanup pending")
        remove_job = ctx.store.get_remove_job(str(remove_job.get("job_id") or "")) or remove_job

    size_txt = human_size(int(deleted_size or 0))
    return {
        "name": display_name,
        "root_label": str(candidate.get("root_label") or ""),
        "size_bytes": int(deleted_size or 0),
        "path": target_path,
        "disk_status": "deleted",
        "plex_status": plex_status,
        "plex_note": plex_note,
        "job_id": str(remove_job.get("job_id") or "") if remove_job else None,
        "remove_kind": remove_kind,
        "display_text": (
            "\u2705 Delete complete\n"
            f"Removed: {display_name}\n"
            f"Library: {candidate.get('root_label')}\n"
            f"Freed: {size_txt}\n"
            f"Disk path: {target_path}\n"
            f"Plex: {plex_note}"
        ),
    }


def delete_remove_candidates(
    ctx: HandlerContext, candidates: list[dict[str, Any]], *, user_id: int | None = None, chat_id: int | None = None
) -> str:
    effective = remove_effective_candidates(candidates)
    if not effective:
        raise RuntimeError("No items are selected for deletion")
    verified: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    failures: list[str] = []
    total_freed = 0
    for candidate in effective:
        enriched = remove_enrich_candidate(candidate)
        try:
            result = delete_remove_candidate(ctx, enriched, user_id=user_id, chat_id=chat_id)
            total_freed += int(result.get("size_bytes") or 0)
            if str(result.get("plex_status") or "") == "verified":
                verified.append(result)
            elif str(result.get("plex_status") or "") in {"plex_pending", "skipped"}:
                pending.append(result)
            else:
                failures.append(f"\u2022 {result.get('name')}: {result.get('plex_note')}")
        except Exception as e:
            failures.append(f"\u2022 {enriched.get('name')}: {e}")
    header = (
        "\u2705 Batch delete verified"
        if not pending and not failures
        else "\u26a0\ufe0f Batch delete completed with follow-up"
    )
    lines = [
        header,
        "",
        f"Disk deleted: {len(verified) + len(pending)}/{len(effective)} item(s)",
        f"Freed: {human_size(total_freed)}",
    ]
    if verified:
        lines.append("")
        lines.append("Verified in Plex:")
        for result in verified[:12]:
            lines.append(f"\u2022 {remove_candidate_text(result)}")
        if len(verified) > 12:
            lines.append(f"\u2022 \u2026and {len(verified) - 12} more")
    if pending:
        lines.append("")
        lines.append("Plex cleanup pending:")
        for result in pending[:12]:
            lines.append(f"\u2022 {result.get('name')}: {result.get('plex_note')}")
        if len(pending) > 12:
            lines.append(f"\u2022 \u2026and {len(pending) - 12} more pending")
    if failures:
        lines.append("")
        lines.append("Failures:")
        lines.extend(failures[:12])
        if len(failures) > 12:
            lines.append(f"\u2022 \u2026and {len(failures) - 12} more failures")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# High-level async helpers (delegated from BotApp)
# ---------------------------------------------------------------------------


async def open_remove_search_prompt(
    bot_app: Any, user_id: int, msg: Any, *, current_ui_message: Any | None = None
) -> None:
    """Open the remove search prompt UI.

    Moved from ``BotApp._open_remove_search_prompt``.
    """
    flow = bot_app._get_flow(user_id) or {"mode": "remove", "selected_items": []}
    flow["mode"] = "remove"
    flow["stage"] = "await_query"
    bot_app._set_flow(user_id, flow)
    selected_count = remove_selection_count(flow)
    await bot_app._render_remove_ui(
        user_id,
        msg,
        flow,
        "\U0001f5d1\ufe0f <b>Remove from Library</b>\n\nType the name of a movie or show to find it directly.\n\nOr tap <b>Browse Plex Library</b> to scroll through everything.",
        reply_markup=remove_prompt_keyboard(selected_count),
        current_ui_message=current_ui_message,
    )


async def open_remove_browse_root(
    bot_app: Any, user_id: int, msg: Any, *, current_ui_message: Any | None = None
) -> None:
    """Open the remove browse root UI.

    Moved from ``BotApp._open_remove_browse_root``.
    """

    ctx = getattr(bot_app, "_ctx", bot_app)
    movie_items = await asyncio.to_thread(remove_library_items, ctx, "movies")
    show_items = await asyncio.to_thread(remove_library_items, ctx, "tv")
    flow = bot_app._get_flow(user_id) or {"mode": "remove", "selected_items": []}
    flow["mode"] = "remove"
    flow["stage"] = "browse_root"
    bot_app._set_flow(user_id, flow)
    await bot_app._render_remove_ui(
        user_id,
        msg,
        flow,
        "\U0001f4da <b>Browse Plex/library items</b>\n\nChoose a library to browse, or <b>type any movie or show name</b> and the bot will find it for you directly.",
        reply_markup=remove_browse_root_keyboard(len(movie_items), len(show_items), remove_selection_count(flow)),
        current_ui_message=current_ui_message,
    )


async def render_remove_search_results(
    bot_app: Any,
    user_id: int,
    msg: Any,
    flow: dict[str, Any],
    *,
    current_ui_message: Any | None = None,
) -> None:
    candidates = list(flow.get("candidates") or [])
    selected_paths = remove_selected_paths(flow)
    await bot_app._render_remove_ui(
        user_id,
        msg,
        flow,
        remove_candidates_text(str(flow.get("query") or "Search"), candidates, selected_paths),
        reply_markup=remove_candidate_keyboard(candidates, selected_paths),
        current_ui_message=current_ui_message,
    )


async def render_remove_season_detail(
    bot_app: Any,
    user_id: int,
    msg: Any,
    flow: dict[str, Any],
    season_candidate: dict[str, Any],
    *,
    current_ui_message: Any | None = None,
) -> None:
    selected_paths = remove_selected_paths(flow)
    await bot_app._render_remove_ui(
        user_id,
        msg,
        flow,
        remove_season_actions_text(season_candidate),
        reply_markup=remove_season_detail_keyboard(
            season_candidate,
            selected_paths,
            int(flow.get("show_idx") or 0),
        ),
        current_ui_message=current_ui_message,
    )


async def on_cb_remove(bot_app: Any, *, data: str, q: Any, user_id: int) -> None:
    """Handle all ``rm:*`` callback queries.

    Moved from ``BotApp._on_cb_remove``.  Receives the BotApp instance
    so it can call rendering methods that still live there.
    """
    from ..ui import keyboards as _kb_mod

    ctx = getattr(bot_app, "_ctx", bot_app)

    if data == "rm:cancel":
        bot_app._clear_flow(user_id)
        await bot_app._render_command_center(q.message, user_id=user_id)
        return

    if data == "rm:browse":
        await bot_app._open_remove_browse_root(user_id, q.message, current_ui_message=q.message)
        return

    if data.startswith("rm:browsecat:"):
        category = data.split(":", 2)[2]
        candidates = await asyncio.to_thread(remove_library_items, ctx, category)
        if category == "tv":
            candidates = remove_group_tv_items(candidates)
        label = "Movies" if category == "movies" else "Shows"
        if not candidates:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                bot_app._get_flow(user_id) or {"mode": "remove", "selected_items": []},
                f"No {label.lower()} were found in the configured library path.",
                reply_markup=remove_browse_root_keyboard(
                    len(await asyncio.to_thread(remove_library_items, ctx, "movies")),
                    len(await asyncio.to_thread(remove_library_items, ctx, "tv")),
                    remove_selection_count(bot_app._get_flow(user_id) or {}),
                ),
                current_ui_message=q.message,
            )
            return
        flow = bot_app._get_flow(user_id) or {"mode": "remove", "selected_items": []}
        flow["mode"] = "remove"
        flow["stage"] = "choose_item"
        flow["query"] = f"Browse {label}"
        flow["candidates"] = candidates
        flow["browse_category"] = category
        bot_app._set_flow(user_id, flow)
        selected_paths = remove_selected_paths(flow)
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            remove_list_text(
                f"\U0001f4da {label} in Plex/library",
                candidates,
                0,
                hint="Tap items to toggle them, or page through the library.",
                selected_paths=selected_paths,
            ),
            reply_markup=remove_paginated_keyboard(
                candidates,
                0,
                item_prefix="rm:pick",
                nav_prefix="rm:bpage",
                back_callback="rm:browse",
                selected_paths=selected_paths,
                compact_browse_footer=True,
            ),
            current_ui_message=q.message,
        )
        return

    if data.startswith("rm:bpage:"):
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        candidates = list(flow.get("candidates") or [])
        if not candidates:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "That library browse expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        page = int(data.split(":", 2)[2])
        label = "Movies" if str(flow.get("browse_category") or "") == "movies" else "Shows"
        selected_paths = remove_selected_paths(flow)
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            remove_list_text(
                f"\U0001f4da {label} in Plex/library",
                candidates,
                page,
                hint="Tap items to toggle them, or page through the library.",
                selected_paths=selected_paths,
            ),
            reply_markup=remove_paginated_keyboard(
                candidates,
                page,
                item_prefix="rm:pick",
                nav_prefix="rm:bpage",
                back_callback="rm:browse",
                selected_paths=selected_paths,
                compact_browse_footer=True,
            ),
            current_ui_message=q.message,
        )
        return

    if data.startswith("rm:pick:"):
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        candidates = list(flow.get("candidates") or [])
        idx = int(data.split(":", 2)[2])
        if idx < 0 or idx >= len(candidates):
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "That item is no longer available. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        selected = remove_enrich_candidate(dict(candidates[idx]))
        flow["selected"] = selected
        flow.pop("season_items", None)
        flow.pop("episode_items", None)
        if (
            str(selected.get("root_key") or "") == "tv"
            and str(selected.get("remove_kind") or "") == "show"
            and bool(selected.get("is_dir"))
        ):
            series_selected = remove_group_any_selected(flow, selected)
            flow["stage"] = "show_actions"
            bot_app._set_flow(user_id, flow)
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                remove_show_actions_text(selected, series_selected),
                reply_markup=remove_show_action_keyboard(series_selected, remove_selection_count(flow)),
                current_ui_message=q.message,
            )
            return
        remove_toggle_group(flow, selected)
        flow["stage"] = "choose_item"
        bot_app._set_flow(user_id, flow)
        selected_paths = remove_selected_paths(flow)
        if flow.get("browse_category"):
            label = "Movies" if str(flow.get("browse_category") or "") == "movies" else "Shows"
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                remove_list_text(
                    f"\U0001f4da {label} in Plex/library",
                    candidates,
                    0,
                    hint="Tap items to toggle them, or page through the library.",
                    selected_paths=selected_paths,
                ),
                reply_markup=remove_paginated_keyboard(
                    candidates,
                    0,
                    item_prefix="rm:pick",
                    nav_prefix="rm:bpage",
                    back_callback="rm:browse",
                    selected_paths=selected_paths,
                    compact_browse_footer=True,
                ),
                current_ui_message=q.message,
            )
        else:
            await render_remove_search_results(bot_app, user_id, q.message, flow, current_ui_message=q.message)
        return

    if data.startswith("rm:delseries:"):
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        candidates = list(flow.get("candidates") or [])
        idx = int(data.split(":", 2)[2])
        if idx < 0 or idx >= len(candidates):
            return
        selected = remove_enrich_candidate(dict(candidates[idx]))
        remove_toggle_group(flow, selected)
        flow["stage"] = "choose_item"
        flow["selected"] = selected
        bot_app._set_flow(user_id, flow)
        await render_remove_search_results(bot_app, user_id, q.message, flow, current_ui_message=q.message)
        return

    if data.startswith("rm:showseason:"):
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        parts = data.split(":")
        if len(parts) != 4:
            return
        candidates = list(flow.get("candidates") or [])
        idx = int(parts[2])
        season_number = int(parts[3])
        if idx < 0 or idx >= len(candidates):
            return
        selected = remove_enrich_candidate(dict(candidates[idx]))
        season_items = await asyncio.to_thread(remove_show_children, selected)
        season_candidate = next(
            (
                remove_enrich_candidate(dict(item))
                for item in season_items
                if str(item.get("remove_kind") or "") == "season" and int(item.get("season_number") or 0) == season_number
            ),
            None,
        )
        if season_candidate is None:
            return
        flow["stage"] = "season_detail"
        flow["selected"] = selected
        flow["selected_child"] = season_candidate
        flow["season_candidate"] = season_candidate
        flow["show_idx"] = idx
        flow["season_parent_stage"] = "season_detail"
        bot_app._set_flow(user_id, flow)
        await render_remove_season_detail(bot_app, user_id, q.message, flow, season_candidate, current_ui_message=q.message)
        return

    if data == "rm:series":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove" or flow.get("stage") != "show_actions":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        selected = dict(flow.get("selected") or {})
        if not selected:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        remove_toggle_group(flow, selected)
        bot_app._set_flow(user_id, flow)
        series_selected = remove_group_any_selected(flow, selected)
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            remove_show_actions_text(selected, series_selected),
            reply_markup=remove_show_action_keyboard(series_selected, remove_selection_count(flow)),
            current_ui_message=q.message,
        )
        return

    if data == "rm:seasons":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove" or flow.get("stage") != "show_actions":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        selected = dict(flow.get("selected") or {})
        group_items = selected.get("group_items")
        if group_items:
            season_items = await asyncio.to_thread(remove_show_group_children, group_items)
        else:
            season_items = await asyncio.to_thread(remove_show_children, selected)
        if not season_items:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "No seasons or direct episode files were found inside that show folder.",
                reply_markup=remove_show_action_keyboard(
                    remove_group_any_selected(flow, selected), remove_selection_count(flow)
                ),
                current_ui_message=q.message,
            )
            return
        flow["stage"] = "browse_children"
        flow["season_items"] = season_items
        bot_app._set_flow(user_id, flow)
        selected_paths = remove_selected_paths(flow)
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            remove_list_text(
                f"\U0001f4c2 {selected.get('name')} seasons / episodes",
                season_items,
                0,
                hint="Tap a season to inspect it, or toggle a direct episode file.",
                selected_paths=selected_paths,
            ),
            reply_markup=remove_paginated_keyboard(
                season_items,
                0,
                item_prefix="rm:child",
                nav_prefix="rm:cpage",
                back_callback="rm:back:show",
                selected_paths=selected_paths,
            ),
            current_ui_message=q.message,
        )
        return

    if data.startswith("rm:cpage:"):
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        season_items = list(flow.get("season_items") or [])
        selected = dict(flow.get("selected") or {})
        if not season_items or not selected:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "That season browser expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        page = int(data.split(":", 2)[2])
        selected_paths = remove_selected_paths(flow)
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            remove_list_text(
                f"\U0001f4c2 {selected.get('name')} seasons / episodes",
                season_items,
                page,
                hint="Tap a season to inspect it, or toggle a direct episode file.",
                selected_paths=selected_paths,
            ),
            reply_markup=remove_paginated_keyboard(
                season_items,
                page,
                item_prefix="rm:child",
                nav_prefix="rm:cpage",
                back_callback="rm:back:show",
                selected_paths=selected_paths,
            ),
            current_ui_message=q.message,
        )
        return

    if data.startswith("rm:child:"):
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        season_items = list(flow.get("season_items") or [])
        idx = int(data.split(":", 2)[2])
        if idx < 0 or idx >= len(season_items):
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "That season/episode choice is no longer available. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        selected_child = remove_enrich_candidate(dict(season_items[idx]))
        flow["selected_child"] = selected_child
        if str(selected_child.get("remove_kind") or "") == "season" and bool(selected_child.get("is_dir")):
            flow["stage"] = "season_actions"
            flow["season_parent_stage"] = "season_actions"
            bot_app._set_flow(user_id, flow)
            selected_paths = remove_selected_paths(flow)
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                remove_season_actions_text(selected_child),
                reply_markup=remove_season_action_keyboard(
                    remove_selected_path(selected_child) in selected_paths,
                    len(selected_paths),
                ),
                current_ui_message=q.message,
            )
            return
        remove_toggle_candidate(flow, selected_child)
        flow["stage"] = "browse_children"
        bot_app._set_flow(user_id, flow)
        selected_paths = remove_selected_paths(flow)
        parent = dict(flow.get("selected") or {})
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            remove_list_text(
                f"\U0001f4c2 {parent.get('name')} seasons / episodes",
                season_items,
                0,
                hint="Tap a season to inspect it, or toggle a direct episode file.",
                selected_paths=selected_paths,
            ),
            reply_markup=remove_paginated_keyboard(
                season_items,
                0,
                item_prefix="rm:child",
                nav_prefix="rm:cpage",
                back_callback="rm:back:show",
                selected_paths=selected_paths,
            ),
            current_ui_message=q.message,
        )
        return

    if data == "rm:seasondel":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove" or flow.get("stage") not in {"season_actions", "season_detail"}:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        selected_child = dict(flow.get("selected_child") or {})
        if not selected_child:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        remove_toggle_candidate(flow, selected_child)
        bot_app._set_flow(user_id, flow)
        selected_paths = remove_selected_paths(flow)
        if flow.get("stage") == "season_detail":
            await render_remove_season_detail(
                bot_app,
                user_id,
                q.message,
                flow,
                selected_child,
                current_ui_message=q.message,
            )
        else:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                remove_season_actions_text(selected_child),
                reply_markup=remove_season_action_keyboard(
                    remove_selected_path(selected_child) in selected_paths,
                    len(selected_paths),
                ),
                current_ui_message=q.message,
            )
        return

    if data == "rm:episodes":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove" or flow.get("stage") not in {"season_actions", "season_detail"}:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        selected_child = dict(flow.get("selected_child") or {})
        episode_items = await asyncio.to_thread(remove_season_children, selected_child)
        if not episode_items:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "No direct episode files were found inside that season folder.",
                reply_markup=remove_season_action_keyboard(
                    remove_selected_path(selected_child) in remove_selected_paths(flow),
                    remove_selection_count(flow),
                ),
                current_ui_message=q.message,
            )
            return
        flow["stage"] = "browse_episodes"
        flow["episode_items"] = episode_items
        bot_app._set_flow(user_id, flow)
        selected_paths = remove_selected_paths(flow)
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            remove_list_text(
                f"\U0001f39e {selected_child.get('show_name')} \u2014 {selected_child.get('name')}",
                episode_items,
                0,
                hint="Tap episode files to toggle them into the delete batch.",
                selected_paths=selected_paths,
            ),
            reply_markup=remove_paginated_keyboard(
                episode_items,
                0,
                item_prefix="rm:episode",
                nav_prefix="rm:epage",
                back_callback="rm:back:season",
                selected_paths=selected_paths,
            ),
            current_ui_message=q.message,
        )
        return

    if data.startswith("rm:epage:"):
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        episode_items = list(flow.get("episode_items") or [])
        selected_child = dict(flow.get("selected_child") or {})
        if not episode_items or not selected_child:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "That episode browser expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        page = int(data.split(":", 2)[2])
        selected_paths = remove_selected_paths(flow)
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            remove_list_text(
                f"\U0001f39e {selected_child.get('show_name')} \u2014 {selected_child.get('name')}",
                episode_items,
                page,
                hint="Tap episode files to toggle them into the delete batch.",
                selected_paths=selected_paths,
            ),
            reply_markup=remove_paginated_keyboard(
                episode_items,
                page,
                item_prefix="rm:episode",
                nav_prefix="rm:epage",
                back_callback="rm:back:season",
                selected_paths=selected_paths,
            ),
            current_ui_message=q.message,
        )
        return

    if data.startswith("rm:episode:"):
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        episode_items = list(flow.get("episode_items") or [])
        idx = int(data.split(":", 2)[2])
        if idx < 0 or idx >= len(episode_items):
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "That episode choice is no longer available. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        selected_episode = remove_enrich_candidate(dict(episode_items[idx]))
        remove_toggle_candidate(flow, selected_episode)
        flow["stage"] = "browse_episodes"
        bot_app._set_flow(user_id, flow)
        selected_paths = remove_selected_paths(flow)
        selected_child = dict(flow.get("selected_child") or {})
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            remove_list_text(
                f"\U0001f39e {selected_child.get('show_name')} \u2014 {selected_child.get('name')}",
                episode_items,
                0,
                hint="Tap episode files to toggle them into the delete batch.",
                selected_paths=selected_paths,
            ),
            reply_markup=remove_paginated_keyboard(
                episode_items,
                0,
                item_prefix="rm:episode",
                nav_prefix="rm:epage",
                back_callback="rm:back:season",
                selected_paths=selected_paths,
            ),
            current_ui_message=q.message,
        )
        return

    if data == "rm:back:show":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        selected = dict(flow.get("selected") or {})
        if not selected:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        flow["stage"] = "show_actions"
        bot_app._set_flow(user_id, flow)
        selected_paths = remove_selected_paths(flow)
        series_selected = remove_group_any_selected(flow, selected)
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            remove_show_actions_text(selected, series_selected),
            reply_markup=remove_show_action_keyboard(series_selected, len(selected_paths)),
            current_ui_message=q.message,
        )
        return

    if data == "rm:back:season":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        selected_child = dict(flow.get("selected_child") or {})
        if not selected_child:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        parent_stage = str(flow.get("season_parent_stage") or "season_actions")
        flow["stage"] = "season_detail" if parent_stage == "season_detail" else "season_actions"
        bot_app._set_flow(user_id, flow)
        selected_paths = remove_selected_paths(flow)
        if flow.get("stage") == "season_detail":
            await render_remove_season_detail(
                bot_app,
                user_id,
                q.message,
                flow,
                selected_child,
                current_ui_message=q.message,
            )
        else:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                remove_season_actions_text(selected_child),
                reply_markup=remove_season_action_keyboard(
                    remove_selected_path(selected_child) in selected_paths,
                    len(selected_paths),
                ),
                current_ui_message=q.message,
            )
        return

    if data == "rm:backtoshow":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        candidates = list(flow.get("candidates") or [])
        if not candidates:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        flow["stage"] = "choose_item"
        bot_app._set_flow(user_id, flow)
        await render_remove_search_results(bot_app, user_id, q.message, flow, current_ui_message=q.message)
        return

    if data == "rm:review":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        selected_items = remove_selection_items(flow)
        effective = remove_effective_candidates(selected_items)
        if not effective:
            return
        flow["stage"] = "confirm_delete"
        bot_app._set_flow(user_id, flow)
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            remove_confirm_text(effective),
            reply_markup=remove_confirm_keyboard(len(effective)),
            current_ui_message=q.message,
        )
        return

    if data == "rm:clear":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove flow has expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        flow["selected_items"] = []
        flow.pop("selected", None)
        flow.pop("selected_child", None)
        flow.pop("season_items", None)
        flow.pop("episode_items", None)
        bot_app._set_flow(user_id, flow)
        await bot_app._open_remove_browse_root(user_id, q.message, current_ui_message=q.message)
        return

    if data == "rm:confirm":
        flow = bot_app._get_flow(user_id)
        if not flow or flow.get("mode") != "remove" or flow.get("stage") != "confirm_delete":
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                {"mode": "remove", "selected_items": []},
                "That remove confirmation expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        selected_items = remove_selection_items(flow)
        effective = remove_effective_candidates(selected_items)
        if not effective:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                "That remove confirmation expired. Start /remove again.",
                reply_markup=None,
                current_ui_message=q.message,
            )
            return
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            f"\U0001f5d1 Deleting {len(effective)} selected item(s) from disk\u2026",
            reply_markup=None,
            current_ui_message=q.message,
        )
        try:
            result_text = await asyncio.to_thread(
                delete_remove_candidates,
                ctx,
                effective,
                user_id=user_id,
                chat_id=getattr(q.message, "chat_id", 0) if q.message else 0,
            )
        except Exception as e:
            await bot_app._render_remove_ui(
                user_id,
                q.message,
                flow,
                f"Delete failed: {e}",
                reply_markup=_kb_mod.home_only_keyboard(),
                current_ui_message=q.message,
            )
            return
        await bot_app._render_remove_ui(
            user_id,
            q.message,
            flow,
            result_text,
            reply_markup=_kb_mod.home_only_keyboard(),
            current_ui_message=q.message,
        )
        bot_app._clear_flow(user_id)
        return
