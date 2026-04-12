---
tags:
  - changelog
aliases:
  - April 2026 Changelog
created: 2026-04-11
updated: 2026-04-11
---

# April 2026 Changelog

## Overview

April was a month of hardening. Key highlights:

- **TV scheduling fix** — shows that aired multiple episodes on the same day were only picking up the first one. That's fixed.
- **Batch cleanup on the 7th** — seventeen smaller bugs knocked out in one sweep, covering everything from VPN reconnect handling to file-move race conditions to the smoothing math that drives the live progress display.
- **Malware scan gate** — the download pipeline now catches suspicious files before they reach your library.
- **Movie scheduling system** — you can now track a film and have it grab itself the moment a non-theater release happens.
- **Command center flicker** — fixed. No more flashing during rapid refreshes.
- **Obsidian vault** — created and seeded (the vault you're reading right now).

> [!code]- Claude Code Reference
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
