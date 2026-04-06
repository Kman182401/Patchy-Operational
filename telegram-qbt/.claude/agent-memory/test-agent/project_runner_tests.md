---
name: Background runner tests
description: 31 tests covering completion_poller_job, remove_runner_job, schedule_runner_job, and pure helpers from download.py/remove.py
type: project
---

tests/test_runners.py contains 31 tests across three background runner subsystems:

- **Completion poller** (8 tests): No-app early return, qbt error handling, skip-already-notified, detect-finished with notification, organize-download call, plex-scan trigger, multi-user notification, old-record cleanup
- **Remove runner** (4 tests): No-due-jobs, process-due-job via monkeypatched cleanup, cleanup-failure resilience, lock-serialization
- **Schedule runner** (5 tests): No-due-tracks, process-due-tracks, refresh-failure handling, success-status update, error-status update with last_error_text
- **Remove pure helpers** (5 tests): interval constant, backoff at 0/mid/high counts, missing-path returns 0
- **Download pure helpers** (9 tests): magnet/torrent/webpage link detection, empty-string edge, result_to_url with hash and file_url, extract_hash from row/magnet/neither

**Why:** Closes coverage gap on background runners (completion poller, remove runner, schedule runner) that previously had zero tests.

**How to apply:** When modifying any runner logic, run `pytest tests/test_runners.py -v` to verify. Schedule runner tests use DummyBotApp + unbound method call pattern (`BotApp._schedule_runner_job(app, None)`).
