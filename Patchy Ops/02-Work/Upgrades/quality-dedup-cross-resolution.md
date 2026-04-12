---
tags:
  - work/upgrade
aliases:
  - Quality dedup and cross-resolution comparison
created: 2026-04-11
updated: 2026-04-11
status: open
priority: low
---

# Quality dedup and cross-resolution comparison

## Overview

When the bot searches for a movie or show, it often gets back a bunch of torrents that are basically the same release in different sizes and resolutions — a 4K copy, a 1080p copy, a 720p copy, sometimes multiple "rips" of each. The `quality.py` scoring engine sorts those by quality and picks the best, but right now it leaves three deliberate gaps that we wrote down for later:

1. **Quality-based deduplication.** If two results are clearly the same release in different encodes, should we collapse them into one entry? Doing this well is tricky because deciding "is this actually the same movie" gets messy.
2. **Cross-resolution comparison.** Is a 720p Blu-ray remux actually better than a 1080p web download? It depends on the person, so we currently just trust the resolution-first ordering.
3. **Re-scoring old database results.** When we change the scoring algorithm, should we re-score old saved searches? Right now we don't, because old searches expire on their own after 24 hours.

These were intentionally deferred — they're trade-offs, not bugs. The note exists so if priorities change we know exactly where to start.

> [!code]- Claude Code Reference
> **Affected files**
> - `telegram-qbt/patchy_bot/quality.py` — the deferred decisions are documented around lines 384–397
> - Search result rendering paths in `telegram-qbt/patchy_bot/handlers/search.py`
>
> **The three deferred items in code**
> 1. Content-identity matching for dedup (same movie, different encode)
> 2. Subjective cross-resolution trade-offs (720p remux vs 1080p WEB-DL)
> 3. Re-scoring old DB results when the algorithm changes (24h TTL makes this mostly moot)
>
> **Why deferred**
> - Content identity matching is complex and error-prone
> - Resolution-first ordering is predictable and what users currently expect
> - TTL-based expiry makes re-scoring unnecessary in practice
>
> **If implementing #1 (dedup):** do not break the existing resolution-tier-first ordering. Run `.venv/bin/python -m pytest -q` and especially watch `tests/test_parsing.py` and any quality-ranking tests.
>
> **Do not implement unless explicitly requested.**
