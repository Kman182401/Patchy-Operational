---
tags: [todo, priority-medium, open]
created: 2026-04-11
module: patchy_bot/bot.py
related: []
---

# Todo: bot.py Phase 2 decomposition

## Problem / What
`bot.py` is the largest file at 4,813 lines. Phase 1 extracted handlers into `handlers/`, clients into `clients/`, and UI into `ui/`. However, `bot.py` still contains:

- BotApp class with all command handler methods (delegated to `handlers/commands.py` but wired in bot.py)
- Callback routing bridge methods (`_on_cb_*`) that delegate to handler modules
- Background runner orchestration (schedule, remove, completion, health check, command center refresh)
- Application lifecycle (build, start, stop, signal handling)
- Inline handler logic for some flows that hasn't been extracted yet

## Expected Behavior / Why
Reducing `bot.py` further improves maintainability and makes it easier to test individual subsystems in isolation. Target: under 2,000 lines with only lifecycle, routing, and runner orchestration remaining.

## Context
- Affects: `bot.py`, potentially all handler modules
- Root cause: incremental decomposition — Phase 1 done, Phase 2 pending
- Related: [[Architecture/modules|Module Map]]

## Claude Code Notes
This is a multi-session effort. Each extraction should:
1. Move one logical group of methods to the appropriate handler module
2. Update imports and delegation in bot.py
3. Run full test suite (`pytest -q`) after each extraction
4. Verify no behavior changes — this is a pure refactor
5. Keep the `_on_cb_*` bridge pattern consistent

Prioritize extracting the largest remaining inline handler groups first. Do NOT touch `qbt_telegram_bot.py`.
