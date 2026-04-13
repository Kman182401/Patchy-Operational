---
tags:
  - work/todo
aliases: []
created: 2026-04-13
updated: 2026-04-13
status: open
priority: low
---

# Duplicate Cleanup Scheduling

## Overview

Session 4 of the Malware Engine v2 upgrade added a `_maybe_run_daily_cleanups` tick inside `completion_poller_job` that runs `cleanup_old_health_events(30)` and the new `cleanup_old_malware_logs(90)` once per 24h. The existing apscheduler `health-event-cleanup` job is still registered at startup (visible in systemd logs: `Added job "health-event-cleanup" to job store "default"`), so health-event rows now get purged by two independent code paths daily. Redundant but not broken — both call the same paged-DELETE method so there is no corruption risk, just wasted work.

## What Needs to Happen

Pick one owner for daily retention cleanup and remove the other:

- **Option A (preferred):** Keep the apscheduler `health-event-cleanup` job, extend it to also call `cleanup_old_malware_logs(90)`, and delete `_maybe_run_daily_cleanups` + the `_daily_cleanup_lock` / `_last_daily_cleanup_ts` globals from `handlers/download.py`. Apscheduler already has retry/misfire handling; the poller tick was a workaround for not having a dedicated scheduler hook at the time.
- **Option B:** Keep the poller tick and unregister the apscheduler `health-event-cleanup` job at startup. Simpler diff but loses the explicit scheduler entry in systemd logs, which is useful for debugging retention regressions.

> [!code]- Claude Code Reference
> **Affected files:** `telegram-qbt/patchy_bot/handlers/download.py` (poller tick + locks), `telegram-qbt/patchy_bot/bot.py` (apscheduler job registration)
> **Implementation notes:** Both paths call `store.cleanup_old_health_events(30)` via `asyncio.to_thread`; the new path additionally calls `store.cleanup_old_malware_logs(90)`. Both methods are paged (1000-row batches) so concurrent runs are safe but wasteful.
> **Test commands:** `.venv/bin/python -m pytest -q tests/test_completion_security_gate.py tests/test_store.py`
> **Related:** Session 4 Malware Engine v2 data-layer upgrade
