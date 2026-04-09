# Patchy Bot — Project Instructions

## Guardrails

- Do not run git write commands in `/home/karson/Patchy_Bot` unless the user explicitly asks in the current message.
- Prefer code over docs when they disagree.
- Keep changes targeted. Do not rewrite unrelated flows or move files without a clear reason.
- Do not break [`telegram-qbt/qbt_telegram_bot.py`](/home/karson/Patchy_Bot/telegram-qbt/qbt_telegram_bot.py); it is a back-compat shim unless the user explicitly wants it changed.
- Use the `patchy-bot` skill for the architecture map, module ownership, callback namespaces, DB ownership, and restart/test commands.

## Core Invariants

- Most runtime code lives in [`telegram-qbt/patchy_bot/`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot).
- State that must survive restarts belongs in SQLite via [`telegram-qbt/patchy_bot/store.py`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/store.py). Transient chat/UI flow state can stay in memory.
- Search, add-flow, and Telegram UI behavior should stay aligned across movie and TV paths unless the user explicitly wants divergence.
- Dynamic values inserted into Telegram HTML messages must be escaped with `_h()`.
- If a download/progress change touches both the immediate path and the deferred-hash pending path, update both paths.

## Restart Rule

- After changes under [`telegram-qbt/patchy_bot/`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot) or related runtime config/service files, restart [`telegram-qbt/telegram-qbt-bot.service`](/home/karson/Patchy_Bot/telegram-qbt/telegram-qbt-bot.service) when applying changes locally is appropriate.

## File Ownership

- Runtime code: [`telegram-qbt/patchy_bot/`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot)
- Repo-local Claude behavior: [`.claude/`](/home/karson/Patchy_Bot/.claude), [`skills/`](/home/karson/Patchy_Bot/skills), [`.claude-plugin/`](/home/karson/Patchy_Bot/.claude-plugin)

## High-Value Conventions

- Run `pytest -q` in [`telegram-qbt/`](/home/karson/Patchy_Bot/telegram-qbt) for touched Python areas when tests exist.
- Prefer the curated project-local skills; do not restore a mirrored global skill library to this repo.
- Keep instructions that are workflow-specific, command-specific, or operationally detailed out of this file.
- Treat `.claude/memory/MEMORY.md` as an index, not a narrative log.
- Preserve path safety and media-type validation when moving or deleting files.
