# Task ID: 2

**Title:** Build the callback dispatcher

**Status:** done

**Dependencies:** 1 ✓

**Priority:** high

**Description:** Create patchy_bot/dispatch.py with a CallbackDispatcher class supporting exact-match and prefix-match registration. Replace the on_callback 1,251-line if/elif chain in bot.py with a dispatcher that routes to the same existing methods (still on BotApp). This is a mechanical refactor — behavior does not change, only the dispatch mechanism.

**Details:**

The dispatcher supports two registration modes: register_exact(data, handler) for exact string matches like 'nav:home', and register_prefix(prefix, handler) for prefix matches like 'rm:'. Prefixes are sorted by length descending for longest-match-first. In this task, all 53 existing prefixes are registered on the dispatcher but still call the same BotApp methods. The on_callback method shrinks to: auth check, answer query, dispatch call.

**Test Strategy:**

Register all 53 current prefixes on the dispatcher. Unit test that each prefix routes to the correct method name. Run existing callback tests — all must pass. Deploy and verify all Telegram button flows work.

## Subtasks

### 2.1. Design CallbackDispatcher class with exact and prefix match

**Status:** pending  
**Dependencies:** None  

Create patchy_bot/dispatch.py with register_exact(), register_prefix(), and dispatch() methods. Include type hints and docstrings.

### 2.2. Register all 53 callback prefixes on the dispatcher

**Status:** pending  
**Dependencies:** None  

Map every existing if/elif branch to a dispatcher registration. Group by domain: nav (1), add/download (3), remove (18), schedule (18), menu (9), flow (3), stop (1).

### 2.3. Replace on_callback if/elif chain with dispatcher.dispatch() call

**Status:** pending  
**Dependencies:** None  

Reduce on_callback to: auth check, q.answer(), cleanup ephemeral, dispatcher.dispatch(data, ...). Move the try/except error handling into the dispatcher.

### 2.4. Add dispatcher unit tests and verify existing callback tests pass

**Status:** pending  
**Dependencies:** None  

Write tests that register a few prefixes and verify dispatch routes correctly. Run full test suite to confirm zero regressions.
