---
tags:
  - changelog
aliases:
  - April 2026 Changelog
created: 2026-04-11
updated: 2026-04-13
---

# April 2026 Changelog

## Overview

April was a month of hardening. Key highlights:

- **Malware Engine v2 — Session 5** — per-user attribution, a `/malware_stats` slash command, structured `SignalID` reason codes, a weekly malware digest runner, and a fresh architecture page in the vault.
- **Python skill suite + Context7 CLI migration** — 14-skill Python suite installed under `.claude/skills/`, Context7 moved off the MCP plugin onto the `ctx7` CLI, and global `context7-skills-scout` / `find-docs` skills added.
- **TV scheduling fix** — shows that aired multiple episodes on the same day were only picking up the first one. That's fixed.
- **Batch cleanup on the 7th** — seventeen smaller bugs knocked out in one sweep, covering everything from VPN reconnect handling to file-move race conditions to the smoothing math that drives the live progress display.
- **Malware scan gate** — the download pipeline now catches suspicious files before they reach your library.
- **Movie scheduling system** — you can now track a film and have it grab itself the moment a non-theater release happens.
- **Command center flicker** — fixed. No more flashing during rapid refreshes.
- **Obsidian vault** — created and seeded (the vault you're reading right now).

> [!code]- Claude Code Reference
>
> ## 2026-04-13 (late)
>
> **Skill infrastructure + Context7 CLI migration**
>
> - Python skill suite installed at `.claude/skills/` (mirrored under `skills/patchy-bot/`): `skill-creator`, 11 python skills (`-error-handling`, `-resilience`, `-background-jobs`, `-resource-management`, `-observability`, `-type-safety`, `-anti-patterns`, `-design-patterns`, `-configuration`, `-code-style`, `writing-python`), `context7-skill`, and the project meta-skill `patchy-bot-python-router`.
> - Global skills added at `~/.claude/skills/`: `context7-skills-scout`, `find-docs`.
> - Context7 migrated from MCP plugin to `ctx7` CLI (CLI + Skills mode). MCP plugin disabled. Pro subscription still active.
> - `CLAUDE.md` Web Research Policy rewritten to reference the CLI workflow (`ctx7 library …` → `ctx7 docs …`).
> - Code-simplifier cleanup on `handlers/download.py`: removed superfluous `_log_*` / `_cp_*` closure-bind locals around `log_malware_block` calls in the completion security gate and poller.
>
> Files modified: `.claude/skills/**`, `skills/patchy-bot/**`, `~/.claude/skills/context7-skills-scout/`, `~/.claude/skills/find-docs/`, `CLAUDE.md`, `telegram-qbt/patchy_bot/handlers/download.py`.
>
> ## 2026-04-13
>
> **Malware Engine v2 — Session 5**
>
> - `/malware_stats` slash command — aggregated scan stats from `malware_scan_log`, available to allowed users.
> - Structured `SignalID` constants in `malware.py` — eliminates string drift between the scanner and consumers of reason codes.
> - `malware_scan_log.user_id` column — per-user attribution for blocked downloads.
> - Weekly malware digest runner (`_maybe_send_malware_digest` in `handlers/download.py`) — sends a summary to all allowed users when the period saw any blocks.
> - ClamAV operations docs added at `docs/clamav-operations.md` (freshclam guide).
> - Vault: new architecture reference page `01-System/Malware Engine v2.md` documenting the scoring system, all 23+ detection signals, data flow, and key design decisions.
> - Vault: parked future idea `04-Ideas/telegram-malware-config.md` for adjusting scoring thresholds via Telegram.
>
> Files modified: `patchy_bot/malware.py`, `patchy_bot/store.py`, `patchy_bot/handlers/commands.py`, `patchy_bot/handlers/download.py`, `docs/clamav-operations.md`, plus the vault notes above.
>
> ## 2026-04-11
>
> - Obsidian vault created and populated by Claude Code
> - Architecture docs generated from actual codebase analysis
> - 4 task notes seeded from codebase analysis (2 todos, 2 upgrades)
> - `Preferences.md` populated from CLAUDE.md rules and project conventions
> - `vault-manager` subagent created
> - Vault rewritten in Phases A–D into the `00-Home/` … `05-Changelog/` layout with plain-English overviews + collapsed Claude Code reference callouts
>
> ## 2026-04-10
>
> - Episode filtering fix: correct season/episode matching in schedule runner
> - Next-ep callback fix: proper navigation after episode pick
> - Inspection timeout: increased file inspection timeout to 20s
> - Candidate cycling: fixed torrent candidate rotation on quality miss
>
> ## 2026-04-08
>
> - Movie release scheduling system: TMDB release date tracking, auto-download on home release
> - `msch:` callback namespace for movie schedule operations
> - `movie_tracks` table with theatrical/digital/physical/home release dates
>
> ## 2026-04-07
>
> Batch of 17 fixes:
>
> - qBT firewalled status auto-clear on reconnection
> - Completion poller deduplication guard
> - Hash resolver recency ordering
> - EMA NoneType guard for `smooth_progress_pct` / `smooth_dls` / `smooth_uls`
> - Plex organizer TOCTOU race fix (try/except instead of exists-then-move)
> - Non-media file rejection in organizer
> - Path safety: `PurePosixPath.is_relative_to()` for containment
> - Stall detection reannounce trigger
> - Tracker error streak removal logic
> - Pending timeout notification
> - Quality scoring trash penalty
> - Malware scan gate in download pipeline
> - Pending tracker lost header / keyboard fix
> - Season navigation arrows replace text input
> - HTML escape in add summary
> - Schedule menu label and movie button UX
> - User message cleanup in schedule flow
>
> ## 2026-04-06
>
> - Malware scan gate: two-stage filtering (search-time + download-time)
> - `malware_scan_log` table for audit trail
> - Keyword, size, uploader, executable, password-archive, file-count checks
>
> ## 2026-04-04
>
> - UI flash fix: command center refresh race condition resolved
> - Reduced refresh flicker during rapid state transitions
