# Patchy Bot Runtime Notes

Apply the repo-root project memory in [`../CLAUDE.md`](/home/karson/Patchy_Bot/CLAUDE.md) first. This file only adds `telegram-qbt` runtime context.

## Runtime Layout

- Entry point: [`patchy_bot/__main__.py`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/__main__.py)
- Core app wiring: [`patchy_bot/bot.py`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/bot.py)
- Domain logic: [`patchy_bot/handlers/`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/handlers)
- Telegram UI text/keyboards/rendering: [`patchy_bot/ui/`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/ui)
- Clients: [`patchy_bot/clients/`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/clients)
- Persistence: [`patchy_bot/store.py`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/store.py)
- Service file: [`telegram-qbt-bot.service`](/home/karson/Patchy_Bot/telegram-qbt/telegram-qbt-bot.service)
- Test shim: [`qbt_telegram_bot.py`](/home/karson/Patchy_Bot/telegram-qbt/qbt_telegram_bot.py)

## Current Conventions

- Config loads through `Config.from_env()`.
- Service startup runs `python -m patchy_bot`, not `python qbt_telegram_bot.py`.
- Telegram flows are chat-first; do not introduce a Mini App unless the flow clearly outgrows editable chat UX.
- New callbacks should stay namespaced and short.
- Preserve the `qbt_telegram_bot.py` import path for tests unless the task explicitly changes that contract.

## Verification

- Default test command: `.venv/bin/python -m pytest -q`
- Ruff config and mypy config live in [`pyproject.toml`](/home/karson/Patchy_Bot/telegram-qbt/pyproject.toml)
- Use targeted tests first when debugging, then run the broader suite before final handoff when practical
