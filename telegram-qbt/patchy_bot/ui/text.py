"""Shared text builders used across multiple flows."""

from __future__ import annotations

from typing import Any

from ..utils import _h, _relative_time, now_ts

# ---------------------------------------------------------------------------
# Tracked-list shared helpers (TV shows + Movies)
# ---------------------------------------------------------------------------


def tracked_list_header(title: str, icon: str) -> str:
    """Header line for My Shows / My Movies screens."""
    return f"<b>{icon} {_h(title)}</b>\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"


def tv_track_line(track: dict) -> str:
    """Format a single TV track row for the My Shows list.

    Mirrors the logic previously in BotApp._schedule_active_line /
    BotApp._schedule_paused_line -- extracted here so it can be called
    without a BotApp reference.
    """
    enabled = track.get("enabled", 1)
    probe = dict(track.get("last_probe_json") or {})
    show = dict(track.get("show_json") or probe.get("show") or {})
    name = str(show.get("name") or track.get("show_name") or "Unknown show")
    season = int(track.get("season") or probe.get("season") or 1)

    if enabled is not None and not enabled:
        return f"<b>{_h(name)}</b>\n   <b>S{season} \u00b7 paused</b>"

    actionable = len(probe.get("actionable_missing_codes") or [])
    pending = len(track.get("pending_json") or probe.get("pending_codes") or [])
    unreleased = len(probe.get("unreleased_codes") or [])

    if actionable > 0:
        status = f"{actionable} ep. missing" if actionable == 1 else f"{actionable} eps. missing"
    elif pending > 0:
        status = f"{pending} downloading"
    elif unreleased > 0:
        status = f"{unreleased} ep. left" if unreleased == 1 else f"{unreleased} eps. left"
    else:
        status = "up to date"

    details: list[str] = [status]
    next_air_ts = int(track.get("next_air_ts") or probe.get("next_air_ts") or 0)
    if next_air_ts > 0:
        details.append(f"next {_relative_time(next_air_ts)}")
    elif enabled is not None and enabled and (actionable > 0 or unreleased > 0):
        details.append("next: unknown")
    if probe.get("metadata_stale"):
        details.append("\u26a0\ufe0f stale data")
    detail_line = " \u00b7 ".join(details[:3])
    return f"<b>{_h(name)}</b>\n   <b>S{season} \u00b7 {_h(detail_line)}</b>"


def movie_track_line(track: dict) -> str:
    """Format a single movie track row for the My Movies list."""
    title = str(track.get("title") or "Unknown")
    year = track.get("year")
    enabled = track.get("enabled", 1)
    status = str(track.get("status") or "pending")
    year_str = f" ({year})" if year else ""

    if not enabled:
        return f"\u23f8 <b>{_h(title)}{_h(year_str)}</b>\n   <i>paused</i>"

    if status == "downloading":
        status_line = "\u2b07\ufe0f Downloading"
    elif status == "done":
        status_line = "\u2705 Downloaded"
    else:
        rel_status = str(track.get("release_status") or "unknown")
        home_ts = track.get("home_release_ts")
        release_ts = int(track.get("release_date_ts") or 0)
        home_is_inferred = bool(track.get("home_date_is_inferred", 1))
        cur = now_ts()
        if rel_status == "pre_theatrical":
            status_line = "\U0001f3ac Not yet released"
        elif rel_status == "in_theaters":
            if home_ts:
                label = "Est. home release" if home_is_inferred else "Home release"
                status_line = f"\U0001f3ac In theaters \u00b7 {label} {_relative_time(int(home_ts))}"
            else:
                status_line = "\U0001f3ac In theaters"
        elif rel_status == "waiting_home":
            if home_ts:
                label = "Est. home release" if home_is_inferred else "Home release"
                status_line = f"\u23f3 Waiting \u00b7 {label} {_relative_time(int(home_ts))}"
            else:
                status_line = "\u23f3 Waiting for home release"
        elif rel_status == "home_available":
            status_line = "\U0001f50d Searching for torrent\u2026"
        elif rel_status == "unknown" and release_ts > cur:
            label = "Est. home release" if home_is_inferred else "Home release"
            status_line = f"\u23f3 Waiting \u2014 {label} {_relative_time(release_ts)}"
        else:
            status_line = "\U0001f50d Searching for torrent\u2026"

    return f"<b>{_h(title)}{_h(year_str)}</b>\n   {status_line}"


def tracked_list_text(
    header: str,
    items: list[dict],
    page: int,
    total_pages: int,
    line_fn,
) -> str:
    """Assemble full list message text: header + item lines + page indicator."""
    lines = [header]
    for item in items:
        lines.append("")
        lines.append(line_fn(item))
    if total_pages > 1:
        lines.append(f"\n<i>Page {page + 1} of {total_pages}</i>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TV search text
# ---------------------------------------------------------------------------


def tv_filter_choice_text() -> str:
    """Intro text shown when a TV search flow begins."""
    return (
        "<b>📺 TV Search</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Choose a search mode below, or skip filters to search by title only.\n\n"
        "<i>Example: Severance</i>"
    )


def tv_filter_prompt_text(error: str | None = None) -> str:
    """Prompt asking the user to type a season AND episode filter (both required)."""
    lines = [
        "<b>📺 Set Season + Episode</b>",
        "",
        "Send both the season and episode number.",
        "<i>Examples: S1E2 · season 1 episode 2</i>",
    ]
    if error:
        lines.extend(["", error])
    return "\n".join(lines)


def tv_strict_filter_error_text() -> str:
    """Error shown when the user provides only a season or only an episode number."""
    return "<b>⚠️ Both season and episode are required.</b>\n<i>Example: S1E2 or season 1 episode 2</i>"


def tv_full_season_prompt_text(error: str | None = None) -> str:
    """Prompt asking the user to enter a season number for the Full Season flow."""
    lines = [
        "<b>📺 Full Season</b>",
        "",
        "Send the season number.",
        "<i>Examples: 1 · S2 · season 3</i>",
    ]
    if error:
        lines.extend(["", error])
    return "\n".join(lines)


def tv_full_season_title_prompt_text(season: int) -> str:
    """Prompt asking the user to enter the show title after choosing a season."""
    return (
        f"<b>📺 Full Season — S{season:02d}</b>\n\n"
        "Send the show title to search.\n"
        f"Results will be filtered to Season {season} packs only.\n\n"
        "<i>Example: Severance</i>"
    )


def tv_no_season_packs_text() -> str:
    """Shown when a Full Season search finds no season-pack results."""
    return (
        "<b>📭 No Season Packs Found</b>\n\n"
        "<i>No complete season packs were found for this search. "
        "Try Skip Filters or Set Season+Episode to find individual episodes.</i>"
    )


def tv_title_prompt_text(season: int | None = None, episode: int | None = None) -> str:
    """Prompt asking the user to type a show title, optionally with filter info."""
    lines = ["<b>📺 TV Search</b>", ""]
    if season is not None or episode is not None:
        season_txt = f"S{season:02d}" if season is not None else "Any season"
        episode_txt = f"E{episode:02d}" if episode is not None else "Any episode"
        lines.append(f"Filter locked: <code>{season_txt} {episode_txt}</code>")
        lines.append("")
    lines.append("Send the show title to search.")
    lines.append("<i>Example: Severance</i>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Post-add follow-up text
# ---------------------------------------------------------------------------


def tv_followup_same_season_text(show_title: str, season: int) -> str:
    """Ask whether the user wants to stay in the same season."""
    return f"<b>📺 {_h(show_title)} — S{season:02d}</b>\n\nStay in the same season?"


def tv_followup_episode_prompt_text(show_title: str, season: int, error: str | None = None) -> str:
    """Prompt for just an episode number within a known season."""
    lines = [
        f"<b>📺 {_h(show_title)} — S{season:02d}</b>",
        "",
        "Send the episode number.",
        "<i>Examples: 5 · E5 · episode 5</i>",
    ]
    if error:
        lines.extend(["", error])
    return "\n".join(lines)


def tv_followup_season_episode_prompt_text(show_title: str, error: str | None = None) -> str:
    """Prompt for both season and episode number."""
    lines = [
        f"<b>📺 {_h(show_title)}</b>",
        "",
        "Send the season and episode number.",
        "<i>Examples: S1E2 · season 1 episode 2</i>",
    ]
    if error:
        lines.extend(["", error])
    return "\n".join(lines)


def tv_followup_season_prompt_text(show_title: str, error: str | None = None) -> str:
    """Prompt for a season number (for another-season follow-up)."""
    lines = [
        f"<b>📺 {_h(show_title)}</b>",
        "",
        "Send the season number.",
        "<i>Examples: 1 · S2 · season 3</i>",
    ]
    if error:
        lines.extend(["", error])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command center text
# ---------------------------------------------------------------------------


def start_text(
    storage_ok: bool,
    storage_reason: str,
    *,
    storage_usage: str,
    vpn_ok: bool,
    vpn_reason: str,
    downloads: str,
) -> str:
    """Assemble the command-center body text from pre-computed status strings.

    Args:
        storage_ok: Whether media storage paths are accessible.
        storage_reason: Human-readable reason string when storage is not OK.
        storage_usage: Pre-rendered storage usage line (from BotApp).
        vpn_ok: Whether the VPN gate is ready.
        vpn_reason: Human-readable reason string when VPN is not ready.
        downloads: Pre-rendered active-downloads section (may be empty string).
    """
    storage_line = "✅ Storage: ready" if storage_ok else f"⚠️ Storage: {storage_reason}"
    vpn_line = "✅ VPN gate: ready" if vpn_ok else f"⚠️ VPN gate: {vpn_reason}"
    return (
        "<b>🛡️ Plex Download Command Center</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{storage_line}\n"
        f"{storage_usage}\n"
        f"{vpn_line}\n"
        f"{downloads}\n"
        "<b>Tips</b>\n"
        "  • 🗓️ <b>Schedule</b> — track shows and alert on missing episodes\n"
        "  • 🗑️ <b>Remove</b> — browse and delete from Plex library\n"
    )


# ---------------------------------------------------------------------------
# Help text — sectioned menu
# ---------------------------------------------------------------------------

# Section data: {number: (title, body)}
HELP_SECTIONS: dict[int, tuple[str, str]] = {
    1: (
        "First-time setup",
        "• If locked, send your password once in chat (or use <code>/unlock &lt;password&gt;</code>).\n"
        "• Open <code>/start</code> to launch the command center.",
    ),
    2: (
        "Daily workflow",
        "• Tap Movie Search or TV Search.\n"
        "• Enter a title.\n"
        "• Select a result and choose Movies or TV.\n"
        "• The bot enforces VPN + storage checks before adding downloads.",
    ),
    3: (
        "Natural language (Patchy chat)",
        '• Chat normally (example: "Hey Patchy!", "How\'s qBittorrent doing?").\n'
        '• Ask search explicitly (example: "find dune part two", "search movie interstellar", "tv severance s1e2").\n'
        "• While the bot is waiting for a title/filter, your message is treated as input for that step.",
    ),
    4: (
        "Slash commands",
        "• <code>/start</code> — open command center\n"
        "• <code>/search &lt;query&gt; [options]</code> — advanced search\n"
        "• <code>/schedule</code> — track a show and auto-acquire new aired episodes\n"
        "• <code>/remove</code> — search or browse Plex/library items, then delete after confirmation\n"
        "• <code>/show &lt;search_id&gt; [page]</code> — reopen search results\n"
        "• <code>/add &lt;search_id&gt; &lt;index&gt; &lt;movies|tv&gt;</code> — add specific result\n"
        "• <code>/active [n]</code> — current active transfers + scheduled tracking\n"
        "• <code>/profile</code> — policy + routing + VPN gate status\n"
        "• <code>/categories</code> — category/path mapping\n"
        "• <code>/plugins</code> — installed qB search plugins\n"
        "• <code>/unlock &lt;password&gt;</code> / <code>/logout</code> — access control",
    ),
    5: (
        "Schedule mode",
        "• Use <code>/schedule</code> or tap 🗓️ Schedule in command center.\n"
        "• Enter a show name, confirm the right title, and let the bot inspect Plex/library inventory automatically.\n"
        "• The bot stores the show ids, tracks the current season, and checks for newly aired missing episodes in the background.\n"
        "• <i>Automation: after release + grace, the bot retries qBittorrent hourly and auto-queues valid episode matches.</i>",
    ),
    6: (
        "Search options (advanced)",
        "<i>Use with <code>/search</code>:</i>\n"
        "• <code>--min-seeds N</code>\n"
        "• <code>--min-size 700MB</code>\n"
        "• <code>--max-size 8GB</code>\n"
        "• <code>--min-quality 1080</code>\n"
        "• <code>--sort seeds|size|name|leechers</code>\n"
        "• <code>--order asc|desc</code>\n"
        "• <code>--limit 1-50</code>\n"
        "\n"
        "<i>Example:</i>\n"
        "<code>/search dune part two --min-seeds 25 --min-quality 1080 --sort seeds --order desc --limit 10</code>",
    ),
    7: (
        "Quality terms key",
        "<b>Source (best → worst):</b>\n"
        "• <b>REMUX</b> — Full Blu-ray, no re-encoding. Best quality, largest.\n"
        "• <b>BluRay</b> — Re-encoded from Blu-ray disc. Great quality.\n"
        "• <b>WEB-DL</b> — Direct download from streaming (Netflix, etc.).\n"
        "• <b>WEBRip</b> — Screen-captured from streaming. Slightly below WEB-DL.\n"
        "• <b>HDTV</b> — Captured from TV broadcast.\n"
        "\n"
        "<b>Video codecs:</b>\n"
        "• <b>x264</b> (H.264) — Widely compatible, larger files.\n"
        "• <b>x265</b> (H.265) — Better compression, smaller files.\n"
        "\n"
        "<b>Audio:</b>\n"
        "• <b>DDP</b> — Dolby Digital Plus (streaming standard).\n"
        "• <b>DD5.1</b> — Dolby Digital 5.1 surround.\n"
        "• <b>TrueHD / Atmos</b> — Lossless Blu-ray audio (best).\n"
        "• <b>DTS / DTS-HD</b> — Lossless surround alternative.",
    ),
}

# Short button labels for the help menu
HELP_LABELS: dict[int, str] = {
    1: "🔐 Setup",
    2: "📋 Workflow",
    3: "💬 Chat",
    4: "⌨️ Commands",
    5: "🗓️ Schedule",
    6: "🔍 Search Options",
    7: "🎞 Quality Key",
}


# ---------------------------------------------------------------------------
# Candidate cycling captions (TV + Movie search results)
# ---------------------------------------------------------------------------


def tv_candidate_caption(candidate: dict[str, Any], idx: int, total: int) -> str:
    """Build a single-result caption for TV show candidate cycling UI."""
    name = str(candidate.get("name") or "Unknown")
    year = str(candidate.get("year") or "?")
    status = str(candidate.get("status") or "Unknown")
    net = str(candidate.get("network") or candidate.get("country") or "Unknown network")
    return (
        f"<b>📺 Pick the Correct Show ({idx + 1} of {total})</b>\n"
        f"\n"
        f"<b>{_h(name)}</b> (<code>{_h(year)}</code>) • <code>{_h(status)}</code> • <i>{_h(net)}</i>\n"
        f"\n"
        f"<i>Tap the button to select, or send another title to search again.</i>"
    )


def movie_candidate_caption(candidate: dict[str, Any], idx: int, total: int, query: str) -> str:
    """Build a single-result caption for movie candidate cycling UI."""
    title = str(candidate.get("title") or "Unknown")
    year = candidate.get("year")
    year_str = f" ({_h(str(year))})" if year else ""
    return (
        f'<b>🎬 Results for "{_h(query)}" ({idx + 1} of {total})</b>\n'
        f"\n"
        f"<b>{_h(title)}</b>{year_str}\n"
        f"\n"
        f"<i>Tap the button to select, or send another title to search again.</i>"
    )


def _truncate_plain(text: str, limit: int = 100) -> str:
    """Collapse whitespace and truncate plain text with an ellipsis."""
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


def tv_show_picker_text(results: list[dict[str, Any]]) -> str:
    """Build the TVMaze show-picker message body.

    ``results`` is a list of TVMetadataClient.search_shows() dicts. Summaries
    are already HTML-stripped by the client; we still truncate and escape
    defensively. All dynamic values are escaped with ``_h()``.
    """
    lines: list[str] = ["<b>📺 Pick a show</b>", ""]
    if not results:
        lines.append("<i>No matches found.</i>")
        return "\n".join(lines)

    for idx, show in enumerate(results, start=1):
        name = str(show.get("name") or "Unknown")
        year = show.get("year")
        network = str(show.get("network") or show.get("country") or "")
        summary = _truncate_plain(str(show.get("summary") or ""), 100)

        header_bits: list[str] = [f"<b>{idx}. {_h(name)}</b>"]
        if year:
            header_bits.append(f"(<code>{_h(str(year))}</code>)")
        if network:
            header_bits.append(f"• <i>{_h(network)}</i>")
        lines.append(" ".join(header_bits))
        if summary:
            lines.append(f"   {_h(summary)}")
        lines.append("")

    lines.append("<i>Tap a show to continue.</i>")
    return "\n".join(lines)


def movie_picker_text(results: list[dict[str, Any]]) -> str:
    """Build the TMDB movie-picker message body.

    ``results`` is a list of TVMetadataClient.search_movies() dicts. Overviews
    are plain text from TMDB; they still get collapsed, truncated, and escaped.
    """
    lines: list[str] = ["<b>🎬 Pick a movie</b>", ""]
    if not results:
        lines.append("<i>No matches found.</i>")
        return "\n".join(lines)

    for idx, movie in enumerate(results, start=1):
        title = str(movie.get("title") or "Unknown")
        year = movie.get("year")
        overview = _truncate_plain(str(movie.get("overview") or ""), 100)

        header_bits: list[str] = [f"<b>{idx}. {_h(title)}</b>"]
        if year:
            header_bits.append(f"(<code>{_h(str(year))}</code>)")
        lines.append(" ".join(header_bits))
        if overview:
            lines.append(f"   {_h(overview)}")
        lines.append("")

    lines.append("<i>Tap a movie to continue.</i>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Full Series Download (Phase B) — text builders
# ---------------------------------------------------------------------------


def full_series_loading_text(show_name: str) -> str:
    """Loading indicator shown while bundle + inventory are being fetched."""
    return f"⏳ Loading <b>{_h(show_name)}</b> metadata…"


def full_series_bundle_error_text(show_name: str) -> str:
    """Error shown when the TVMaze bundle fetch fails."""
    return (
        f"<b>⚠️ Couldn't load metadata for {_h(show_name)}</b>\n\n"
        "<i>The TVMaze lookup failed, so the full-series flow can't continue.\n"
        "You can try a raw search instead.</i>"
    )


def full_series_confirm_text(
    show_name: str,
    network: str | None,
    year_start: int | None,
    year_end: int | None,
    total_seasons: int,
    total_episodes: int,
    in_plex: int,
    to_download: int,
) -> str:
    """Render the full-series confirmation screen."""
    network_str = str(network or "Unknown network")
    if year_start and year_end and year_start != year_end:
        year_line = f"{year_start}\u2013{year_end}"
    elif year_start:
        year_line = str(year_start)
    else:
        year_line = "year unknown"
    return (
        "<b>📦 Full Series Download</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>{_h(show_name)}</b>\n"
        f"{_h(network_str)} · {_h(year_line)}\n"
        f"{int(total_seasons)} seasons · {int(total_episodes)} episodes\n"
        f"✅ {int(in_plex)} episodes already in Plex\n"
        f"{int(to_download)} episodes to download\n\n"
        "<i>Season packs will be attempted first.\n"
        "Individual episodes used as fallback.\n"
        "Downloads are sequential — one at a time.</i>"
    )


def _fs_season_summary_line(entry: dict) -> str:
    season = int(entry.get("season") or 0)
    method = str(entry.get("method") or "")
    reason = str(entry.get("reason") or "")
    count = int(entry.get("count") or 0)
    if entry.get("_status") == "completed":
        if method == "pack":
            return f"✅ Season {season} · pack ({count} eps)"
        return f"✅ Season {season} · individual ({count} eps)"
    if entry.get("_status") == "failed":
        return f"⚠️ Season {season} · {reason or 'failed'}"
    if entry.get("_status") == "skipped":
        if reason == "already_in_plex":
            return f"✅ Season {season} · already in Plex"
        if reason == "cancelled":
            return f"⏸ Season {season} · cancelled"
        return f"⏸ Season {season} · {reason or 'skipped'}"
    return f"⏸ Season {season}"


def _fs_progress_line(state: object) -> str:
    # Local import to avoid circular reference (handlers/download imports ui/text too).
    from ..handlers.download import progress_bar

    pct = float(getattr(state, "current_progress_pct", 0.0) or 0.0)
    bar = progress_bar(pct, width=18)
    eta = getattr(state, "current_eta_s", None)
    eta_str = _format_eta(eta)
    return f"<code>{bar}</code> {pct:5.1f}%  ETA {eta_str}"


def _format_eta(eta_s: int | None) -> str:
    if eta_s is None:
        return "—"
    try:
        s = int(eta_s)
    except (TypeError, ValueError):
        return "—"
    if s <= 0 or s >= 8_640_000:
        return "—"
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    h = s // 3600
    m = (s % 3600) // 60
    return f"{h}h {m}m"


def full_series_status_text(state: object) -> str:
    """Render the live status message for a full-series download.

    ``state`` is a FullSeriesState instance from handlers.full_series, but we
    accept ``object`` to avoid a circular import at module load.
    """
    show_name = str(getattr(state, "show_name", "") or "Unknown")
    total_seasons = int(getattr(state, "total_seasons", 0) or 0)
    raw_available = list(getattr(state, "available_seasons", []) or [])
    try:
        available_seasons = sorted({int(s) for s in raw_available if int(s) > 0})
    except (TypeError, ValueError):
        available_seasons = []
    if not available_seasons and total_seasons > 0:
        # Backwards-compat: older state objects may not expose the list.
        available_seasons = list(range(1, total_seasons + 1))
    completed = list(getattr(state, "completed_seasons", []) or [])
    failed = list(getattr(state, "failed_seasons", []) or [])
    skipped = list(getattr(state, "skipped_seasons", []) or [])
    current_season = getattr(state, "current_season", None)
    current_name = str(getattr(state, "current_torrent_name", "") or "")

    lines: list[str] = [
        "<b>📦 Full Series Download</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"<b>{_h(show_name)}</b>",
        "",
    ]

    # Each entry gets a status tag so the shared formatter can render it.
    entries: list[dict] = []
    for e in completed:
        entries.append({**e, "_status": "completed"})
    for e in failed:
        entries.append({**e, "_status": "failed"})
    for e in skipped:
        entries.append({**e, "_status": "skipped"})
    # Sort by season ascending.
    entries.sort(key=lambda x: int(x.get("season") or 0))
    for entry in entries:
        lines.append(_fs_season_summary_line(entry))

    if current_season is not None:
        lines.append("")
        lines.append(f"⏳ Season {int(current_season)} · downloading")
        if current_name:
            lines.append(f"<i>{_h(current_name)}</i>")
        lines.append(_fs_progress_line(state))

    # Waiting seasons (in available_seasons but not yet started / completed / failed).
    seen_seasons = {int(e.get("season") or 0) for e in completed + failed + skipped}
    if current_season is not None:
        seen_seasons.add(int(current_season))
    waiting = [s for s in available_seasons if s not in seen_seasons]
    if waiting:
        lines.append("")
        for s in waiting:
            lines.append(f"⏸ Season {s} · waiting")

    return "\n".join(lines)


def full_series_complete_text(state: object) -> str:
    """Final summary shown when the full-series run finishes."""
    show_name = str(getattr(state, "show_name", "") or "Unknown")
    completed = list(getattr(state, "completed_seasons", []) or [])
    failed = list(getattr(state, "failed_seasons", []) or [])
    skipped = list(getattr(state, "skipped_seasons", []) or [])

    total_eps = sum(int(e.get("count") or 0) for e in completed)
    lines = [
        "<b>✅ Full Series Complete</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"<b>{_h(show_name)}</b>",
        "",
        f"Downloaded {len(completed)} seasons · {total_eps} episodes",
    ]
    if failed:
        lines.append(f"⚠️ {len(failed)} season(s) failed")
    if skipped:
        lines.append(f"⏸ {len(skipped)} season(s) skipped")
    return "\n".join(lines)


def full_series_cancelled_text(state: object) -> str:
    """Summary shown when the user cancels a full-series run."""
    show_name = str(getattr(state, "show_name", "") or "Unknown")
    completed = list(getattr(state, "completed_seasons", []) or [])
    skipped = list(getattr(state, "skipped_seasons", []) or [])
    return (
        "<b>🛑 Full Series Cancelled</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>{_h(show_name)}</b>\n\n"
        f"Completed {len(completed)} seasons before cancel.\n"
        f"Remaining {len(skipped)} seasons skipped."
    )


def help_text() -> str:
    """Help menu intro — shown with section navigation buttons."""
    return "<b>ℹ️ Help &amp; Quick Start</b>\n━━━━━━━━━━━━━━━━━━━━\n\nTap a topic below to learn more."


def help_section_text(section: int) -> str:
    """Return formatted text for a single help section."""
    title, body = HELP_SECTIONS[section]
    return f"<b>ℹ️ Help — {title}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{body}"
