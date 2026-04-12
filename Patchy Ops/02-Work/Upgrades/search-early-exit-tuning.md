---
tags:
  - work/upgrade
aliases:
  - Search early-exit tuning
created: 2026-04-11
updated: 2026-04-11
status: open
priority: low
---

# Search early-exit tuning

## Overview

When you search for a torrent, the bot doesn't just hit one tracker — it asks several search plugins at once and waits for results. Waiting forever would make searches feel slow, so the search has an "early exit" rule: if it already has enough good results and nothing new has come in for a few seconds, it stops waiting and returns what it has.

That early-exit behavior is controlled by three knobs: how many results count as "enough," how long to wait after the last new result before bailing, and an absolute maximum wait time. Right now those numbers were set by educated guessing, not by actually measuring how the plugins behave in the real world. The job here is to log real timing data, look at how each plugin actually responds, and tune the knobs so searches are as fast as possible without losing quality.

There's also a related note in the code about multi-user load: if a bunch of people search at the same time, the underlying thread pool needs to be big enough to handle them in parallel.

> [!code]- Claude Code Reference
> **Affected files**
> - `telegram-qbt/patchy_bot/clients/qbittorrent.py` — `QBClient.search()`, the early-exit logic
> - `telegram-qbt/patchy_bot/handlers/search.py` — caller side
>
> **The knobs**
> - `early_exit_min_results`
> - `early_exit_idle_s`
> - `early_exit_max_wait_s`
>
> **Implementation notes from the code**
> - `QBClient.search()` uses synchronous `time.sleep()` polling, called via `asyncio.to_thread()`
> - There's a NOTE around line 73 about ThreadPoolExecutor sizing for multi-user concurrency
>
> **Approach**
> 1. Add timing instrumentation: log per-plugin first-result time, total result count over time, and exit reason
> 2. Capture data over a representative set of real searches (movies, TV, popular vs obscure)
> 3. Pick new defaults from the observed curves
> 4. Run `.venv/bin/python -m pytest -q` after any parameter change
