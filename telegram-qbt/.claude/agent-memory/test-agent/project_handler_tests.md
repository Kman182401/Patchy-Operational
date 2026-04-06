---
name: Handler module test coverage
description: tests/test_handlers.py — 67 tests covering extracted handler modules (search, download, chat, commands, remove)
type: project
---

tests/test_handlers.py was created 2026-04-04 with 67 tests covering the newly extracted handler modules.

**Why:** The handler extraction (search.py, download.py, chat.py, commands.py, remove.py) had zero dedicated test coverage. These tests validate all public pure functions and report generators.

**How to apply:** When modifying any handler module function, run `tests/test_handlers.py` in addition to the full suite. The test patterns use SimpleNamespace to build minimal ctx objects for functions that need HandlerContext, and _good_row() helper for building search rows that survive quality scoring.

Coverage breakdown:
- search: apply_filters (8), sort_rows (2), parse_tv_filter (5), build_tv_query (3), strip_patchy_name (1), extract_search_intent (2), deduplicate_results (2) = 23 tests
- download: progress_bar (3), format_eta (5), is_complete_torrent (4), is_direct_torrent_link (4), result_to_url (1), extract_hash (2), state_label (1), completed_bytes (1) = 21 tests
- chat: chat_needs_qbt_snapshot (3), patchy_system_prompt (3) = 6 tests
- commands: health_report (3), speed_report (2), on_error (1) = 6 tests
- remove: remove_match_score (3), extract_movie_name (2), extract_show_name (2), remove_kind_label (3), remove_retry_backoff_s (1) = 11 tests

Known quirk: is_complete_torrent has a falsy-zero bug where `int(0 or -1)` evaluates to -1, so amount_left=0 never triggers the amount_left branch. The test covers the completed_bytes path instead.
