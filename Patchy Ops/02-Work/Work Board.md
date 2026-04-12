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

Each task has a `status` (`open`, `in-progress`, or `done`) and a `priority` (`high`, `medium`, or `low`). The two tables below pull live counts straight from the task notes — you don't have to update them by hand.

## Todos

```dataview
TABLE priority, status, created
FROM #work/todo
WHERE status != "done"
SORT priority ASC
```

## Upgrades

```dataview
TABLE priority, status, created
FROM #work/upgrade
WHERE status != "done"
SORT priority ASC
```

> [!code]- Claude Code Reference
> Task notes live under:
> - `02-Work/Todos/` — `[[bot-phase2-decomposition]]`, `[[vpn-interface-safety-docs]]`
> - `02-Work/Upgrades/` — `[[quality-dedup-cross-resolution]]`, `[[search-early-exit-tuning]]`
>
> Tag scheme:
> - `work/todo` — bugs and must-do work
> - `work/upgrade` — optional improvements
>
> Frontmatter fields used by the dataview queries: `tags`, `priority`, `status`, `created`.
