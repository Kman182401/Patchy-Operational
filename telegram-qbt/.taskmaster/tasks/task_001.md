# Task ID: 1

**Title:** Create shared types and handler base class

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Create patchy_bot/types.py with a HandlerContext dataclass that wraps the shared state handlers need (cfg, store, qbt, plex, tvmeta, llm, rate_limiter, user_flow, user_nav_ui, progress_tasks, chat_history). Create patchy_bot/handlers/base.py with a BaseHandler ABC that accepts this context. This establishes the contract all extracted handlers will follow.

**Details:**

HandlerContext bundles all shared state into one object so extracted handler modules have clean, explicit dependencies instead of reaching back into BotApp. The BaseHandler ABC defines register_callbacks() and register_commands() methods that each handler implements. Create patchy_bot/handlers/__init__.py as well.

**Test Strategy:**

Import types.py and base.py, instantiate HandlerContext with dummy values, create a trivial BaseHandler subclass. Run existing test suite — must still pass with 162 tests.
