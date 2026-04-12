---
tags:
  - work/todo
aliases:
  - bot.py Phase 2 decomposition
created: 2026-04-11
updated: 2026-04-11
status: open
priority: medium
---

# bot.py Phase 2 decomposition

## Overview

The main file that runs the bot, `bot.py`, is over 5,000 lines long — that's like a book with no chapters. Everything from command registration, to the loops that run in the background, to the inline button handlers is crammed into one place. When a file gets that big it becomes hard to read, scary to change, and easy to break by accident.

We already did a "Phase 1" cleanup that pulled the bulk of the handlers into their own folders (`handlers/`, `clients/`, `ui/`). Phase 2 is about finishing that job: keep moving logical groups of code out of `bot.py` until the only things left are starting up the bot, shutting it down, wiring callbacks to the right handler, and kicking off the background runners. The goal is to get `bot.py` under 2,000 lines without changing how anything actually behaves.

This is a long, careful job. Each move has to be a pure refactor — no behavior changes — and the test suite has to pass after every step.

> [!code]- Claude Code Reference
> **Affected files**
> - `telegram-qbt/patchy_bot/bot.py` — currently ~5,023 lines
> - `telegram-qbt/patchy_bot/handlers/*.py` — destinations for extracted logic
> - Do NOT touch `telegram-qbt/qbt_telegram_bot.py` (back-compat shim)
>
> **What still lives in bot.py**
> - `BotApp` class with command handler bridge methods (delegate to `handlers/commands.py`)
> - `_on_cb_*` callback routing bridge methods
> - Background runner orchestration (schedule, remove, completion poller, qbt health check, command center refresh)
> - Application lifecycle: build, start, stop, signal handling
> - Some inline handler logic that hasn't been extracted yet
>
> **Target:** under 2,000 lines, only lifecycle + routing + runner orchestration remaining.
>
> **Per-extraction checklist**
> 1. Move one logical group of methods to the right `handlers/` module
> 2. Update imports and delegation in `bot.py`
> 3. Run `.venv/bin/python -m pytest -q` from `telegram-qbt/`
> 4. Verify no behavior change — pure refactor only
> 5. Keep the `_on_cb_*` bridge pattern consistent
>
> Prioritize the largest remaining inline handler groups first.
