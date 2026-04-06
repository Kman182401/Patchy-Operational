---
name: Progress tracking test coverage
description: 43 tests covering download progress rendering (progress_bar, format_eta, is_complete, state_label, etc.) and async tracker loop in patchy_bot/handlers/download.py
type: project
---

tests/test_progress.py covers patchy_bot/handlers/download.py with 43 tests:
- progress_bar: zero/50/100/fractional/clamp cases (6 tests)
- format_eta: normal/days/infinity/negative/zero/boundary (6 tests)
- is_complete_torrent: progress threshold, upload states, completed==total, amount_left falsy bug (6 tests)
- completed_bytes: capped at total, fallback to downloaded, prefers completed (4 tests)
- state_label: downloading, metadata, seeding, unknown (4 tests)
- eta_label: done, metadata, formatted, infinity (4 tests)
- render_progress_text: name presence, bar chars, override values, HTML tags (4 tests)
- safe_tracker_edit: success, not-modified, timeout, other error (4 tests)
- track_download_progress async: completion, timeout, qbt error streak, key cleanup, torrent-not-found (5 tests)

**Known bug documented:** `is_complete_torrent` has a falsy-zero bug where `int(amount_left or -1)` coerces 0 to -1, making the amount_left==0 completion path dead code. Test `test_amount_left_zero_falsy_bug` documents this.

**How to apply:** When modifying download.py progress functions, run `pytest tests/test_progress.py -v` to verify.
