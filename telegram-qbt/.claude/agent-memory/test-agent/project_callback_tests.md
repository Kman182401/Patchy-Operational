---
name: Callback routing tests
description: 22 tests in test_callbacks.py covering menu/flow/stop/rm/sch callbacks and CallbackDispatcher routing
type: project
---

22 tests in `tests/test_callbacks.py` covering callback routing and state transitions.

**Why:** Handlers extracted to `handlers/commands.py`, `handlers/download.py`, `handlers/remove.py`, `handlers/schedule.py` need isolated tests that don't depend on the full BotApp.

**How to apply:** Uses a `FakeBotApp` class that wraps `HandlerContext` and captures rendering/flow method calls. Tests call handler functions directly (e.g., `on_cb_menu(fake_app, data=..., q=..., user_id=...)`). Reuses `conftest.py` fixtures (`mock_ctx`, etc.) for the underlying context.

Coverage breakdown:
- 8 menu:* tests (movie, tv, schedule no-tracks, schedule with-tracks, remove, active, help, profile)
- 3 flow:* tests (tv_filter_set, tv_filter_skip, tv_full_series)
- 3 stop:* tests (cancel task, delete fails, TV category label)
- 2 rm:* tests (cancel clears flow, browse opens root)
- 1 sch:* test (cancel clears flow)
- 5 dispatcher tests (prefix routing, exact-beats-prefix, unhandled returns false)
