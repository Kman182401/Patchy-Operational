# Task ID: 6

**Title:** Extract the schedule handler

**Status:** done

**Dependencies:** 2 ✓, 3 ✓, 5 ✓

**Priority:** high

**Description:** Move all _schedule_* methods (~60 methods, lines 1300-2791) plus _backup_job into patchy_bot/handlers/schedule.py. Register all sch:* callback prefixes (18 prefixes). Update bot.py on_text schedule flow branches to delegate. This is the largest extraction (~1,490 lines).

**Details:**

The schedule system is the largest domain in bot.py. It includes: runner configuration methods (interval, grace, retry, backoff), source health tracking, bootstrap logic, TVMaze bundle/cache management, probe logic (filesystem inventory, Plex inventory, episode status), auto-download with episode ranking, notification system, 18 keyboard builders, 8 text builders, the background runner job (120s interval), and the download-episode flow. Depends on task 5 because schedule auto-download calls _do_add and progress tracking methods. The _backup_job (line 2305) runs as a daily scheduled job and calls store.backup().

**Test Strategy:**

All existing schedule tests in test_parsing.py (~12 tests) must pass. Deploy and test: /schedule flow, show lookup, season pick, episode picker, confirm tracking, verify schedule runner fires on interval.

## Subtasks

### 6.1. Extract schedule runner config and source health methods

**Status:** pending  
**Dependencies:** None  

Move _schedule_runner_interval_s through _schedule_should_use_plex_inventory (~L1300-1399) into handlers/schedule.py.

### 6.2. Extract schedule bootstrap and cache management

**Status:** pending  
**Dependencies:** None  

Move _schedule_bootstrap, _schedule_bundle_from_cache, _schedule_get_show_bundle, show_info, select_season (~L1400-1634) into handlers/schedule.py.

### 6.3. Extract schedule probe and inventory logic

**Status:** pending  
**Dependencies:** None  

Move _schedule_filesystem_inventory, _schedule_existing_codes, _schedule_probe_bundle, _schedule_apply_tracking_mode, _schedule_probe_track (~L1634-1904) into handlers/schedule.py.

### 6.4. Extract schedule UI builders (keyboards + text)

**Status:** pending  
**Dependencies:** None  

Move all _schedule_*_keyboard and _schedule_*_text methods (~L1904-2165) — already partially in ui/ from task 3, wire remaining schedule-specific ones.

### 6.5. Extract schedule auto-download and episode logic

**Status:** pending  
**Dependencies:** None  

Move _schedule_episode_auto_state, _schedule_qbt_codes_for_show, _schedule_reconcile_pending, _schedule_should_attempt_auto, _schedule_attempt_auto_acquire, _schedule_notify_auto_queued, _schedule_missing_text (~L2165-2305).

### 6.6. Extract schedule runner job and background refresh

**Status:** pending  
**Dependencies:** None  

Move _schedule_runner_job, _schedule_refresh_track, _schedule_notify_missing, _backup_job, and all download/confirm methods (~L2305-2791). Register sch:* callbacks.

### 6.7. Wire schedule handler into bot.py and verify all schedule tests pass

**Status:** pending  
**Dependencies:** None  

Replace bot.py schedule methods with delegation to the new handler. Run full test suite — 12+ schedule tests must pass. Deploy and test /schedule flow end to end.
