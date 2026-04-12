---
tags:
  - work/todo
aliases:
  - Movie tracking audit
created: 2026-04-11
updated: 2026-04-11
status: open
priority: high
---

# Movie tracking audit

## Overview

The movie tracking system (the part of the bot that lets you tell it "I want this movie when it comes out" and then auto-downloads when the release lands) needs a deep audit and fix. The user has flagged that something is wrong — movies aren't being scheduled, tracked, or released the way they should be. This is a hunt-and-fix task: walk through the whole movie scheduling flow end-to-end, find where reality has drifted from the design, and patch it.

The audit should cover:

- **Adding** a movie to tracking — does the search → schedule path actually create a `movie_tracks` row with the right fields?
- **Tracking** over time — does the schedule runner actually re-check TMDB release dates for movies, or only for TV shows?
- **Releasing** — when a movie's home-release date arrives, does the runner actually trigger a download? Does it pick the right release window (digital vs. physical vs. home)?
- **Notification and UI** — does the user get told what's happening, and is the schedule menu showing the correct movie state?

Because this is a system-level audit rather than a single-symptom bug, the work should start with reading code (not changing it) and producing a list of concrete defects, then fixing them one at a time with tests.

> [!code]- Claude Code Reference
> **Affected files**
> - `patchy_bot/handlers/schedule.py` — movie branch (look for `msch:` prefix handlers and the movie variants of the schedule UI)
> - `patchy_bot/clients/tv_metadata.py` — TMDB movie functions: `get_movie`, release-date lookup helpers
> - `patchy_bot/store.py` — `movie_tracks` table schema and CRUD helpers; check column meanings against current usage
> - `patchy_bot/bot.py` — schedule runner orchestration; confirm the movie code path actually runs on each tick
>
> **Callback namespace**
> - `msch:` is the movie-schedule callback prefix — registered via `CallbackDispatcher` in `dispatch.py`
>
> **Audit checklist**
> 1. Read `movie_tracks` schema and confirm field semantics (theatrical / digital / physical / home dates, status, what triggers a download)
> 2. Trace add-to-tracking flow from `search.py` → `schedule.py` → `store.add_movie_track`
> 3. Trace runner tick: does it iterate `movie_tracks` and call TMDB? Does it compare release dates against `now_ts()` correctly?
> 4. Trace release trigger: when a date passes, does it actually start a download via the same path manual movie downloads use?
> 5. Check the schedule menu rendering for movies — does it show the right next action?
> 6. Confirm parity with TV tracking where the flows overlap
>
> **Tests**
> - Existing coverage: `tests/test_movie_schedule.py` — extend it for any defects found
> - Confirm `pytest -q` from `telegram-qbt/` is green after each fix
