"""Shared text builders used across multiple flows."""

from __future__ import annotations

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
    next_check_at = int(track.get("next_check_at") or 0)
    if next_check_at > 0:
        details.append(f"check {_relative_time(next_check_at)}")
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
        date_type = str(track.get("release_date_type") or "")
        cur = now_ts()
        if rel_status == "pre_theatrical":
            status_line = "\U0001f3ac Not yet released"
        elif rel_status == "in_theaters":
            if home_ts:
                status_line = f"\U0001f3ac In theaters \u00b7 Home est. {_relative_time(int(home_ts))}"
            else:
                status_line = "\U0001f3ac In theaters"
        elif rel_status == "waiting_home":
            if home_ts:
                status_line = f"\u23f3 Waiting \u00b7 Home release {_relative_time(int(home_ts))}"
            else:
                status_line = "\u23f3 Waiting for home release"
        elif rel_status == "home_available":
            status_line = "\U0001f50d Searching for torrent\u2026"
        elif rel_status == "unknown" and release_ts > cur:
            label = date_type.capitalize() if date_type else "Release"
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


def help_text() -> str:
    """Help menu intro — shown with section navigation buttons."""
    return "<b>ℹ️ Help &amp; Quick Start</b>\n━━━━━━━━━━━━━━━━━━━━\n\nTap a topic below to learn more."


def help_section_text(section: int) -> str:
    """Return formatted text for a single help section."""
    title, body = HELP_SECTIONS[section]
    return f"<b>ℹ️ Help — {title}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{body}"
