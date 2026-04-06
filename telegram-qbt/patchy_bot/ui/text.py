"""Shared text builders used across multiple flows."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# TV search text
# ---------------------------------------------------------------------------


def tv_filter_choice_text() -> str:
    """Intro text shown when a TV search flow begins."""
    return (
        "<b>📺 TV Search</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send the show title to search.\n"
        "You can optionally lock the search to a season or episode first.\n\n"
        "<i>Example: Severance</i>"
    )


def tv_filter_prompt_text(error: str | None = None) -> str:
    """Prompt asking the user to type a season/episode filter."""
    lines = [
        "<b>📺 TV Filter</b>",
        "",
        "Send the season/episode filter.",
        "<i>Examples: S1E2 · season 1 episode 2 · season 2 · episode 5</i>",
    ]
    if error:
        lines.extend(["", error])
    return "\n".join(lines)


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
# Help text
# ---------------------------------------------------------------------------


def help_text() -> str:
    """Full help/quick-start message."""
    return (
        "<b>ℹ️ Help &amp; Quick Start</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "<b>1) First-time setup</b>\n"
        "• If locked, send your password once in chat (or use <code>/unlock &lt;password&gt;</code>).\n"
        "• Open <code>/start</code> to launch the command center.\n"
        "\n"
        "<b>2) Daily workflow</b>\n"
        "• Tap Movie Search or TV Search.\n"
        "• Enter a title.\n"
        "• Select a result and choose Movies or TV.\n"
        "• The bot enforces VPN + storage checks before adding downloads.\n"
        "\n"
        "<b>3) Natural language (Patchy chat)</b>\n"
        '• Chat normally (example: "Hey Patchy!", "How\'s qBittorrent doing?").\n'
        '• Ask search explicitly (example: "find dune part two", "search movie interstellar", "tv severance s1e2").\n'
        "• While the bot is waiting for a title/filter, your message is treated as input for that step.\n"
        "\n"
        "<b>4) Slash commands</b>\n"
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
        "• <code>/unlock &lt;password&gt;</code> / <code>/logout</code> — access control\n"
        "\n"
        "<b>5) Schedule mode</b>\n"
        "• Use <code>/schedule</code> or tap 🗓️ Schedule in command center.\n"
        "• Enter a show name, confirm the right title, and let the bot inspect Plex/library inventory automatically.\n"
        "• The bot stores the show ids, tracks the current season, and checks for newly aired missing episodes in the background.\n"
        "• <i>Automation: after release + grace, the bot retries qBittorrent hourly and auto-queues valid episode matches.</i>\n"
        "\n"
        "<b>6) Search options (advanced)</b>\n"
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
        "<code>/search dune part two --min-seeds 25 --min-quality 1080 --sort seeds --order desc --limit 10</code>"
        "\n"
        "\n"
        "<b>7) Quality terms key</b>\n"
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
        "• <b>DTS / DTS-HD</b> — Lossless surround alternative."
    )
