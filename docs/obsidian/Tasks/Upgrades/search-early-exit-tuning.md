---
tags: [upgrade, priority-low, open]
created: 2026-04-11
module: patchy_bot/clients/qbittorrent.py
related: []
---

# Upgrade: Search early-exit parameter tuning

## Problem / What
The `QBClient.search()` method uses synchronous `time.sleep()` polling and is called via `asyncio.to_thread()`. The early-exit parameters (`early_exit_min_results`, `early_exit_idle_s`, `early_exit_max_wait_s`) have reasonable defaults but haven't been benchmarked against real-world plugin response patterns.

The NOTE in the code (line 73) highlights that for multi-user scenarios, the event loop's ThreadPoolExecutor needs enough workers to handle concurrent searches.

## Expected Behavior / Why
Optimized early-exit parameters could reduce average search latency while still capturing enough results for quality ranking.

## Context
- Affects: `clients/qbittorrent.py`, search UX latency
- Root cause: defaults set by estimation, not measurement
- Related: [[Architecture/clients|Clients]]

## Claude Code Notes
Requires real-world testing to measure actual plugin response curves. Consider logging search timing metrics before changing defaults. Run `pytest -q` after any parameter changes.
