# Task ID: 12

**Title:** Test backfill for extracted modules

**Status:** pending

**Dependencies:** 4, 5, 6, 7, 8, 9

**Priority:** medium

**Description:** Add targeted tests for the largest coverage gaps exposed during extraction. Minimum new tests: (1) handlers/search.py — _apply_filters with quality/size/seed filters, _sort_rows with various keys; (2) handlers/download.py — _progress_bar at 0/50/100%, _format_eta edge cases, _is_complete_torrent for various states; (3) handlers/commands.py — _health_report returns valid HTML, _speed_report formats correctly; (4) handlers/chat.py — _chat_needs_qbt_snapshot returns correct boolean. Target: +30 new tests minimum.

**Details:**

Current test coverage has major gaps: download tracking (0 tests), search execution (0 tests), LLM chat (0 tests), command handlers (0 tests), QBClient (0 tests), TVMetadataClient (0 tests). This task focuses on the extracted handler modules. Each handler module should have at least 3-5 focused unit tests. Tests should use the existing DummyBot/DummyStore mock patterns from the current test files. New tests go in tests/test_handlers.py or domain-specific files like tests/test_search.py, tests/test_download.py.

**Test Strategy:**

Run full test suite. Coverage for each new handler module should have at least 3 focused unit tests. No existing tests should regress. Total test count should be 192+.
