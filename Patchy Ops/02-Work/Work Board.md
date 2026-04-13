---
tags:
  - reference
aliases:
  - Work Board
created: 2026-04-11
updated: 2026-04-11
---

# Work Board

## Overview

This is your to-do list for Patchy Bot. It shows what needs to be done, what's in progress, and what's waiting. Tasks are split into two buckets: **Todos** (bugs and must-do work) and **Upgrades** (optional improvements that would make things nicer but aren't blocking anything).

Each task has a `status` (`open`, `in-progress`, or `done`) and a `priority` (`high`, `medium`, or `low`). These lists are maintained manually — add/remove entries when work files are created or completed.

## Todos

- [ ] **high** — [[movie-tracking-audit]]
- [ ] **medium** — [[bot-phase2-decomposition]]
- [ ] **medium** — [[download-malware-scan-visibility]]
- [ ] **medium** — [[vpn-interface-safety-docs]]

## Upgrades

- [ ] **high** — [[plex-watchlist-auto-download]]
- [ ] **medium** — [[search-result-poster-thumbnails]]
- [ ] **low** — [[alert-notifications-clear-button]]
- [ ] **low** — [[duplicate-cleanup-scheduling]]
- [ ] **low** — [[quality-dedup-cross-resolution]]
- [ ] **low** — [[search-early-exit-tuning]]

> [!code]- Claude Code Reference
> Task notes live under:
> - `02-Work/Todos/` — `[[bot-phase2-decomposition]]`, `[[vpn-interface-safety-docs]]`
> - `02-Work/Upgrades/` — `[[quality-dedup-cross-resolution]]`, `[[search-early-exit-tuning]]`
>
> Tag scheme:
> - `work/todo` — bugs and must-do work
> - `work/upgrade` — optional improvements
>
> Task notes use `tags`, `priority`, `status`, `created` in frontmatter. The two lists above are maintained manually — update them when files are added, promoted, or completed.
