# Task ID: 13

**Title:** Final cleanup — remove dead code from bot.py

**Status:** pending

**Dependencies:** 4, 5, 6, 7, 8, 9, 10

**Priority:** low

**Description:** After all extractions are complete: (1) Remove all delegation stubs from bot.py that now just call handler methods — replace with direct handler references in build_application. (2) Remove orphaned imports. (3) Verify bot.py is under 1,000 lines. (4) Update the backward-compat shim in qbt_telegram_bot.py to re-export from new module locations if needed. (5) Update patchy_bot/__init__.py re-exports.

**Details:**

This is the final task. After all domain extractions, bot.py should contain only: BotApp.__init__ (create clients, state, handler instances), build_application (register handlers via dispatcher), on_text (thin router delegating to handlers based on flow mode), shared state declarations, and _post_init/_post_stop lifecycle. Target: bot.py under 1,000 lines (down from 6,671). The backward-compat shim qbt_telegram_bot.py must continue to re-export all public names. Run the full test suite one final time to confirm zero regressions.

**Test Strategy:**

Run full test suite — all 192+ tests must pass. Import from qbt_telegram_bot in a test script and verify all documented public names are still accessible. Deploy and verify complete end-to-end flow: /start -> search movie -> add -> monitor progress -> complete -> /schedule show -> /remove item. Verify wc -l patchy_bot/bot.py < 1000.
