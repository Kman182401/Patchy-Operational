# Task ID: 14

**Title:** Multi-episode premiere batch download fix

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Fix schedule system so multiple simultaneously-released episodes are all downloaded in one runner cycle instead of one-per-hour.

**Details:**

Changed schedule_apply_tracking_mode (removed break after first episode), schedule_should_attempt_auto (return full candidate list), schedule_refresh_track (loop over all targets). Both handlers/schedule.py and bot.py updated. 7 new tests added.

**Test Strategy:**

4 tests in test_parsing.py for multi-episode tracking mode, 3 tests in test_runners.py for batch auto-acquire behavior. All 462 tests pass.
