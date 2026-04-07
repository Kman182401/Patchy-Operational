"""Search parsing, filtering, sorting, and rendering.

Extracted from BotApp -- these are the pure / near-pure search helper
functions.  Static methods become plain functions.  Instance methods
that only needed ``self`` for config or a single helper now take
explicit parameters instead.

Functions
---------
- ``build_search_parser``  -- argparse parser for /search
- ``apply_filters``        -- filter search result rows
- ``deduplicate_results``  -- deduplicate by info hash, keep best seeder
- ``sort_rows``            -- sort result rows by key
- ``prioritize_results``   -- pin best 4K at #1, then 1080p only
- ``parse_tv_filter``      -- parse "S1E2" style filter text
- ``build_tv_query``       -- build TV search query string
- ``strip_patchy_name``    -- strip bot name prefix from text
- ``extract_search_intent``-- determine if text is a search query
- ``render_page``          -- render one page of search results as HTML + keyboard
"""

from __future__ import annotations

import argparse
import json
import math
import re
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..quality import score_torrent
from ..utils import _h, human_size, quality_tier
from .download import is_direct_torrent_link

# ---------------------------------------------------------------------------
# Search parser
# ---------------------------------------------------------------------------


def build_search_parser() -> argparse.ArgumentParser:
    """Create the argparse parser for the /search command."""
    p = argparse.ArgumentParser(prog="/search", add_help=False)
    p.add_argument("--plugin", default="enabled")
    p.add_argument("--search-cat", default="all")
    p.add_argument("--min-seeds", type=int)
    p.add_argument("--min-size")
    p.add_argument("--max-size")
    p.add_argument("--min-quality", type=int, choices=[0, 480, 720, 1080, 2160])
    p.add_argument("--sort", choices=["seeds", "size", "name", "leechers", "quality"])
    p.add_argument("--order", choices=["asc", "desc"])
    p.add_argument("--limit", type=int)
    p.add_argument("query", nargs="+")
    return p


# ---------------------------------------------------------------------------
# Filtering & sorting
# ---------------------------------------------------------------------------


def apply_filters(
    rows: list[dict[str, Any]],
    *,
    min_seeds: int,
    min_size: int | None,
    max_size: int | None,
    min_quality: int,
    media_type: str = "movie",
) -> list[dict[str, Any]]:
    """Filter search result rows by seeds, size, quality, and source availability."""
    out: list[dict[str, Any]] = []
    for r in rows:
        seeds = int(r.get("nbSeeders") or r.get("seeders") or 0)
        size = int(r.get("fileSize") or r.get("size") or 0)
        name = str(r.get("fileName") or r.get("name") or "")
        if seeds < min_seeds:
            continue
        if min_size is not None and size < min_size:
            continue
        if max_size is not None and size > max_size:
            continue
        # quality_tier() is a resolution floor (2160/1080/720/480), NOT a quality score
        if min_quality > 0 and quality_tier(name) < min_quality:
            continue

        # Keep only results that have a usable direct torrent source.
        rh = str(r.get("fileHash") or r.get("hash") or "").strip().lower()
        has_hash = bool(re.fullmatch(r"[a-f0-9]{40}", rh))
        if not has_hash:
            candidates = [
                str(r.get("fileUrl") or r.get("file_url") or "").strip(),
                str(r.get("url") or "").strip(),
                str(r.get("descrLink") or r.get("descr_link") or "").strip(),
            ]
            if not any(is_direct_torrent_link(c) for c in candidates if c):
                continue

        # Score the result — reject garbage (CAM, TS, AV1, upscaled, zero-seed, LQ groups)
        ts = score_torrent(name, size, seeds, media_type=media_type)
        if ts.is_rejected:
            continue
        # Reject non-English results (empty = assumed English, or must contain 'en')
        if ts.parsed.languages and "en" not in ts.parsed.languages:
            continue
        # Attach score to the row for sorting
        r["_quality_score"] = ts

        out.append(r)
    return out


def deduplicate_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate search results that share the same info hash.

    When multiple plugins return the same torrent, keep the entry with the
    highest seed count.  Rows without a valid 40-char hex hash are always
    kept (we cannot compare them).  The output preserves the original order
    of first-seen entries (stable).
    """
    seen: dict[str, int] = {}  # hash → index into *out*
    out: list[dict[str, Any]] = []

    for row in rows:
        h = str(row.get("fileHash") or row.get("hash") or "").strip().lower()
        if not re.fullmatch(r"[a-f0-9]{40}", h):
            # No usable hash — keep unconditionally.
            out.append(row)
            continue

        seeds = int(row.get("nbSeeders") or row.get("seeders") or 0)

        if h in seen:
            existing_idx = seen[h]
            existing_seeds = int(
                out[existing_idx].get("nbSeeders") or out[existing_idx].get("seeders") or 0,
            )
            if seeds > existing_seeds:
                out[existing_idx] = row  # replace with better-seeded entry
        else:
            seen[h] = len(out)
            out.append(row)

    return out


def sort_rows(rows: list[dict[str, Any]], key: str, order: str) -> list[dict[str, Any]]:
    """Sort search result rows by the given key and order."""
    reverse = order == "desc"
    if key == "quality":
        return sorted(
            rows,
            key=lambda x: (
                getattr(x.get("_quality_score"), "resolution_tier", 0),
                getattr(x.get("_quality_score"), "format_score", 0),
            ),
            reverse=reverse,
        )
    if key == "seeds":
        return sorted(rows, key=lambda x: int(x.get("nbSeeders") or x.get("seeders") or 0), reverse=reverse)
    if key == "size":
        return sorted(rows, key=lambda x: int(x.get("fileSize") or x.get("size") or 0), reverse=reverse)
    if key == "leechers":
        return sorted(rows, key=lambda x: int(x.get("nbLeechers") or x.get("leechers") or 0), reverse=reverse)
    return sorted(rows, key=lambda x: str(x.get("fileName") or x.get("name") or "").lower(), reverse=reverse)


def prioritize_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank results: best 4K first, then 1080p, then 720p and below.

    Separates results into above-1080p, exactly-1080p, and below-1080p buckets.
    At most one above-1080p result (the highest-seeded) is kept and
    placed first.  All remaining slots are filled with 1080p results
    then lower-resolution results, each group sorted by seed count descending.
    """
    above: list[dict[str, Any]] = []
    at_1080: list[dict[str, Any]] = []
    below: list[dict[str, Any]] = []

    for r in rows:
        name = str(r.get("name") or r.get("fileName") or "")
        tier = quality_tier(name)
        if tier > 1080:
            above.append(r)
        elif tier == 1080:
            at_1080.append(r)
        else:
            below.append(r)

    def _seeds(x: dict[str, Any]) -> int:
        return int(x.get("nbSeeders") or x.get("seeders") or 0)

    def _is_trash(x: dict[str, Any]) -> bool:
        ts = x.get("_quality_score")
        if ts is not None:
            return bool(getattr(ts, "parsed", None) and ts.parsed.trash)
        return False

    # Within each bucket: non-trash first (sorted by seeds desc),
    # then trash sources last (sorted by seeds desc).
    def _sort_key(x: dict[str, Any]) -> tuple[int, int]:
        return (1 if _is_trash(x) else 0, -_seeds(x))

    above.sort(key=_sort_key)
    at_1080.sort(key=_sort_key)
    below.sort(key=_sort_key)

    result: list[dict[str, Any]] = []
    if above:
        result.append(above[0])
    result.extend(at_1080)
    result.extend(below)
    return result


# ---------------------------------------------------------------------------
# TV filter / query helpers
# ---------------------------------------------------------------------------


def parse_tv_filter(text: str) -> tuple[int | None, int | None] | None:
    """Parse 'S1E2' style filter text, returning (season, episode) or None."""
    t = text.strip().lower()

    m = re.search(r"\bs(?:eason\s*)?(\d{1,2})\s*[\-\s_]?e(?:pisode\s*)?(\d{1,2})\b", t)
    if m:
        return int(m.group(1)), int(m.group(2))

    m = re.search(r"\bseason\s*(\d{1,2})\b", t)
    season = int(m.group(1)) if m else None
    m = re.search(r"\bepisode\s*(\d{1,2})\b", t)
    episode = int(m.group(1)) if m else None
    if season is not None or episode is not None:
        return season, episode

    m = re.search(r"\bs(\d{1,2})\b", t)
    season = int(m.group(1)) if m else None
    m = re.search(r"\be(\d{1,2})\b", t)
    episode = int(m.group(1)) if m else None
    if season is not None or episode is not None:
        return season, episode

    return None


def parse_strict_season_episode(text: str) -> tuple[int, int] | None:
    """Parse text that contains BOTH a season AND an episode number.

    Accepts: S1E2, s1e2, season 1 episode 2, season 1 ep 2, etc.
    Returns (season, episode) only when both are present; None otherwise.
    """
    t = text.strip().lower()

    # SxEy / S01E02 style
    m = re.search(r"\bs(?:eason\s*)?(\d{1,2})\s*[\-\s_]?e(?:p(?:isode\s*)?)?(\d{1,2})\b", t)
    if m:
        return int(m.group(1)), int(m.group(2))

    # "season N episode M" / "season N ep M"
    ms = re.search(r"\bseason\s*(\d{1,2})\b", t)
    me = re.search(r"\b(?:episode|ep)\s*(\d{1,2})\b", t)
    if ms and me:
        return int(ms.group(1)), int(me.group(1))

    return None


def parse_season_number(text: str) -> int | None:
    """Parse a bare season number from text.

    Accepts: "1", "S1", "s1", "season 1", "Season 1".
    Returns the season number or None.
    """
    t = text.strip().lower()

    # "season N" or "s N"
    m = re.search(r"\bseason\s*(\d{1,2})\b", t)
    if m:
        return int(m.group(1))

    # "sN" or "s N" shorthand (standalone so we don't eat "s1e2")
    m = re.search(r"\bs(\d{1,2})\b", t)
    if m:
        return int(m.group(1))

    # bare integer
    m = re.fullmatch(r"\s*(\d{1,2})\s*", t)
    if m:
        return int(m.group(1))

    return None


def parse_episode_number(text: str) -> int | None:
    """Parse a bare episode number from text.

    Accepts: "5", "E5", "e5", "episode 5", "ep 5".
    """
    t = text.strip().lower()

    m = re.search(r"\b(?:episode|ep)\s*(\d{1,3})\b", t)
    if m:
        return int(m.group(1))

    m = re.search(r"\be(\d{1,3})\b", t)
    if m:
        return int(m.group(1))

    m = re.fullmatch(r"\s*(\d{1,3})\s*", t)
    if m:
        return int(m.group(1))

    return None


def build_tv_query(title: str, season: int | None, episode: int | None) -> str:
    """Build a TV search query string from title and optional season/episode."""
    title = title.strip()
    if season is not None and episode is not None:
        return f"{title} S{season:02d}E{episode:02d}"
    if season is not None:
        return f"{title} S{season:02d}"
    if episode is not None:
        return f"{title} E{episode:02d}"
    return title


# ---------------------------------------------------------------------------
# Intent extraction
# ---------------------------------------------------------------------------


def strip_patchy_name(text: str, patchy_chat_name: str | None) -> str:
    """Strip the bot's name prefix from user text."""
    name = re.escape(patchy_chat_name or "Patchy")
    cleaned = re.sub(rf"^\s*(?:hey|hi|hello|yo)\s+@?{name}\s*[:,!\-]?\s*", "", text, flags=re.I)
    cleaned = re.sub(rf"^\s*@?{name}\s*[:,!\-]?\s*", "", cleaned, flags=re.I)
    return cleaned.strip()


def extract_search_intent(text: str, patchy_chat_name: str | None) -> tuple[str | None, str]:
    """Determine if text is a search query.

    Returns (query, media_hint) where query is None if no search intent found.
    """
    t = strip_patchy_name(text, patchy_chat_name) or text.strip()
    low = t.lower().strip()

    # Strong intent: explicit search verbs.
    patterns = [
        r"^(?:please\s+)?(?:search|find|look\s+for|get|download|grab)\s+(?:for\s+)?(?P<q>.+)$",
        r"^(?:can you|could you|would you|pls|please)\s+(?:search|find|look\s+for)\s+(?:for\s+)?(?P<q>.+)$",
    ]

    query: str | None = None
    for p in patterns:
        m = re.match(p, t, flags=re.I)
        if m:
            query = (m.group("q") or "").strip()
            break

    # Also allow plain prefixed media queries.
    media_hint = "any"
    if query is None:
        if low.startswith("movie ") or low.startswith("movies "):
            query = re.sub(r"^movies?\s+", "", t, flags=re.I).strip()
            media_hint = "movies"
        elif low.startswith("tv ") or low.startswith("show ") or low.startswith("series "):
            query = re.sub(r"^(tv|show|series)\s+", "", t, flags=re.I).strip()
            media_hint = "tv"

    if not query:
        return None, "any"

    query = query.rstrip(" ?!.\t\n\r")
    if len(query) < 2:
        return None, "any"

    qlow = query.lower()
    if qlow.startswith("movie ") or qlow.startswith("movies "):
        query = re.sub(r"^movies?\s+", "", query, flags=re.I).strip()
        media_hint = "movies"
    elif qlow.startswith("tv ") or qlow.startswith("show ") or qlow.startswith("series "):
        query = re.sub(r"^(tv|show|series)\s+", "", query, flags=re.I).strip()
        media_hint = "tv"

    return query, media_hint


# ---------------------------------------------------------------------------
# Results rendering
# ---------------------------------------------------------------------------


def render_page(
    search_meta: dict[str, Any],
    rows: list[dict[str, Any]],
    page: int,
    *,
    page_size: int,
    nav_footer_fn: Any,
) -> tuple[str, InlineKeyboardMarkup | None]:
    """Render one page of search results as HTML text + inline keyboard.

    Parameters
    ----------
    search_meta : dict
        The search metadata dict from the store.
    rows : list[dict]
        All result rows for this search.
    page : int
        1-based page number to render.
    page_size : int
        Number of results per page (from cfg.page_size).
    nav_footer_fn : callable
        A function that returns the navigation footer keyboard rows
        (replaces self._nav_footer()).
    """
    total = len(rows)
    ps = page_size
    pages = max(1, math.ceil(total / ps))
    page = max(1, min(page, pages))
    start = (page - 1) * ps
    view = rows[start : start + ps]

    opts = search_meta["options"]
    min_q = int(opts.get("min_quality") or 0)
    qtxt = f"{min_q}p+" if min_q else "any"
    media_hint = str(opts.get("media_hint") or "any")
    sid = search_meta["search_id"]
    query = search_meta["query"]
    lines = [
        f"<b>🔎 Search:</b> <code>{_h(query)}</code>",
        f"Results: <b>{total}</b> • Page: <b>{page}/{pages}</b>",
        f"Sort: {opts.get('sort', 'seeds')} {opts.get('order', 'desc')} • Quality: <code>{qtxt}</code> • Type: <code>{media_hint}</code>",
    ]
    lines.append("")

    for row in view:
        idx = row["idx"]
        name = str(row["name"])
        seeds = int(row.get("seeds") or 0)
        size = human_size(int(row.get("size") or 0))
        site = str((row.get("site") or "?").replace("https://", "").replace("http://", ""))
        # Jackett wraps real tracker name in brackets at end of torrent name
        bracket_match = re.search(r"\[([^\[\]]+)\]\s*$", name)
        if bracket_match:
            site = bracket_match.group(1)
            name = name[: bracket_match.start()].rstrip()
        # Build shortened quality label and extract source type from quality_json
        q_raw = row.get("quality_json")
        q_data = None
        if q_raw:
            try:
                q_data = json.loads(q_raw) if isinstance(q_raw, str) else q_raw
            except (json.JSONDecodeError, TypeError):
                q_data = None

        source_type = str(q_data.get("source") or "").strip() if q_data else ""
        is_trash = bool(q_data.get("trash")) if q_data else False
        parts: list[str] = []
        res = str(q_data.get("resolution") or "").strip() if q_data else ""
        if res and res != "unknown":
            parts.append(res)
        codec_raw = str(q_data.get("codec") or "").strip() if q_data else ""
        codec_map = {"avc": "x264", "hevc": "x265", "av1": "AV1", "xvid": "XviD"}
        if codec_raw:
            parts.append(codec_map.get(codec_raw.lower(), codec_raw.upper()))
        audio_map = {
            "dolby digital plus": "DDP",
            "dolby digital": "DD5.1",
            "truehd": "TrueHD",
            "dts lossy": "DTS",
            "dts lossless": "DTS-HD",
            "aac": "AAC",
            "atmos": "Atmos",
            "mp3": "MP3",
        }
        for a in (q_data.get("audio") or []) if q_data else []:
            abbr = audio_map.get(a.lower(), a)
            if abbr not in parts:
                parts.append(abbr)
        grp = str(q_data.get("group") or "").strip() if q_data else ""
        if grp:
            parts.append(f"[{grp}]")
        short_qlbl = " ".join(parts) if parts else "Unknown"

        lines.append(f"<b>{idx}.</b> <code>{_h(name)}</code>")
        trash_tag = "⚠️ " if is_trash else ""
        lines.append(
            f"   {trash_tag}🌱 <b>{seeds}</b> seeds | 📡 {_h(source_type) if source_type else 'Unknown'} | 🎞 <code>{_h(short_qlbl)}</code> | 📦 <code>{size}</code> | 🌐 <i>{_h(site)}</i>"
        )
        lines.append("")

    # Show trash-source legend if any result on this page has the ⚠️ flag
    if any(
        bool(
            (
                json.loads(r.get("quality_json"))
                if isinstance(r.get("quality_json"), str)
                else r.get("quality_json") or {}
            ).get("trash")
        )
        for r in view
    ):
        lines.append(
            "<i>⚠️ = TeleSync / CAM source — recorded in a theater, not a digital release. "
            "Expect lower picture and audio quality.</i>"
        )
        lines.append("")
    lines.append("<i>Tap Add on a result, then choose Movies or TV.</i>")
    text = "\n".join(lines)

    kb_rows: list[list[InlineKeyboardButton]] = []
    for row in view:
        idx = row["idx"]
        seeds = int(row.get("seeds") or 0)
        kb_rows.append(
            [
                InlineKeyboardButton(
                    text=f"⬇️ Add #{idx} ({seeds} seeds)", callback_data=f"a:{search_meta['search_id']}:{idx}"
                )
            ]
        )

    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"p:{search_meta['search_id']}:{page - 1}"))
    if page < pages:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"p:{search_meta['search_id']}:{page + 1}"))
    if nav:
        kb_rows.append(nav)
    kb_rows.extend(nav_footer_fn())

    return text, InlineKeyboardMarkup(kb_rows) if kb_rows else None
