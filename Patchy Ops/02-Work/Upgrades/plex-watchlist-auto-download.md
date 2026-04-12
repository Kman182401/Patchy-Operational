---
tags:
  - work/upgrade
aliases:
  - Plex Watchlist auto-download
created: 2026-04-11
updated: 2026-04-11
status: open
priority: high
---

# Plex Watchlist auto-download

## Overview

Plex has a feature called the **Watchlist** — it's the "things I want to watch later" list that any Plex user can build from the Plex web or mobile app. Right now Patchy Bot doesn't know about it. This upgrade closes that gap: the moment you add a movie or TV show to your Plex Watchlist, the bot notices, figures out whether it's already released, and either downloads it immediately or schedules it for whenever the release happens.

For TV shows, this should plug into the existing schedule runner — the same code that polls for next episodes for currently-tracked shows. For movies, it should plug into the movie release scheduling system that was added in early April (the `movie_tracks` table and `msch:` callbacks). That system already knows how to track a movie's theatrical / digital / physical / home release dates and trigger a download when the home release lands; the watchlist integration just needs to feed new movies into it.

The hardest part is the Plex API side: there isn't a stable, well-documented "list watchlist items" endpoint, and what does exist may require an authenticated call against `metadata.provider.plex.tv` rather than the local Plex server. The implementation needs to figure out how to authenticate, how to detect changes (poll vs. webhook), and how to deduplicate against things the user has already added directly through Patchy.

> [!code]- Claude Code Reference
> **Note from user:** "Will execute after my Claude usage resets on Friday." This is queued for the next active work window.
>
> **Affected files**
> - `patchy_bot/clients/plex.py` — `PlexInventoryClient` currently talks to the local Plex server. The Watchlist lives on `metadata.provider.plex.tv` and requires the user's Plex token. May need a new client or a new method on the existing one.
> - `patchy_bot/handlers/schedule.py` — movie branch needs an entry point for "ingest this movie from the watchlist"; TV branch needs the same for shows
> - `patchy_bot/store.py` — `movie_tracks` table is the scheduling backbone; reuse it. May need a new column or sentinel for "source = watchlist" so the user can tell where a tracked item came from.
>
> **Plex Watchlist API research needed**
> - Endpoint: `https://metadata.provider.plex.tv/library/sections/watchlist/all` (requires Plex token)
> - Auth: `X-Plex-Token` header — already known and stored for the local server
> - Response format: Plex XML, similar to local server
> - Change detection: simplest is polling on a slow tick (5–10 min); webhooks are not officially supported for watchlist
>
> **Parity**
> - Both movie and TV watchlist items must work
> - Reuse existing scheduling code paths — do not fork
>
> **Tests**
> - Mock Plex Watchlist responses in `tests/`
> - Confirm `pytest -q` from `telegram-qbt/` is green
