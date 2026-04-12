---
tags:
  - work/upgrade
aliases:
  - Search result poster thumbnails
created: 2026-04-11
updated: 2026-04-11
status: open
priority: medium
---

# Search result poster thumbnails

## Overview

When you search for a show or movie in Patchy Bot, the results come back as plain text — title, year, maybe quality. That's fine when the title is unique, but it's risky when the title is common. Imagine searching for "The Office" and getting back results for the US version, the UK version, a 2001 documentary, and a 1980s sitcom — all mostly indistinguishable from text alone. The user could easily pick the wrong one and download the wrong show.

This upgrade adds a **visual identifier** — a poster image or thumbnail — to each search result. The user gets a glance-confirmation that "yes, this is the show I meant" before they hit download. TMDB (The Movie Database, the same service the scheduler already uses for release dates) provides poster URLs for free, so the data source is already wired up.

The trade-off is that Telegram has different limits and rendering for image messages versus text messages — sending a photo with a caption is a different API call than sending plain text with inline buttons, and the buttons-on-photos pattern is slightly more limited. The implementation needs to weigh sending a small inline preview versus a larger photo card per result, and it needs to keep search responsive (don't block on poster fetches).

> [!code]- Claude Code Reference
> **Affected files**
> - `patchy_bot/clients/tv_metadata.py` — `TVMetadataClient` already talks to TMDB; add a method to fetch poster URLs (`/movie/{id}` and `/tv/{id}` endpoints return `poster_path`; full URL is `https://image.tmdb.org/t/p/w185{poster_path}`)
> - `patchy_bot/ui/rendering.py` — search result rendering; this is where the poster URL needs to be plumbed into the message build
> - `patchy_bot/handlers/search.py` — call site that builds the result list; needs to pass the poster URL through
>
> **Telegram API considerations**
> - `send_photo` with `caption` and `reply_markup` works for inline keyboards on photo messages, but caption is limited to 1024 characters
> - For result lists, `send_media_group` does not support inline keyboards — would need one message per result
> - Alternative: keep text-based results and use `link_preview_options` to show a preview from the TMDB poster URL
> - Cache poster URLs in memory for the duration of the search session to avoid re-fetching
>
> **Parity**
> - Apply to both Movie Search and TV Search paths (movies/TV parity rule)
>
> **Tests**
> - Mock TMDB poster responses in `tests/test_handlers.py` search tests
> - Confirm `pytest -q` is green
