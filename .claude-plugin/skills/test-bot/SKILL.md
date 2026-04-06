---
name: test-bot
description: Run the full quality check suite for Patchy Bot — pytest, ruff lint, and mypy type checking. Use when the user says "test", "run tests", "check code", "lint", "quality check", or before marking any code change as done. Also use proactively after editing bot code.
---

# Full Quality Check Suite

Run all three code quality tools against the Patchy Bot codebase and report a unified pass/fail summary.

All commands run from `/home/karson/Patchy_Bot/telegram-qbt` using the project venv.

## Agent Delegation

This skill delegates to the following agents during execution. Always use these agents — do not implement inline what an agent can handle.

- **Primary:** Delegate test execution, lint checks, and failure diagnosis to the `test-agent`.
- **On failure:** If tests fail, delegate root cause analysis to the `error-detective` agent with the pytest output.

## Step 1 — Run all three checks in parallel

Run these three commands simultaneously:

### pytest
```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -m pytest -q 2>&1
```

### ruff
```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -m ruff check . 2>&1
```

### mypy
```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -m mypy patchy_bot/ qbt_telegram_bot.py 2>&1
```

## Step 2 — Summarize results

Report a clear summary table:

```
| Check  | Result | Details          |
|--------|--------|------------------|
| pytest | PASS   | 12 passed        |
| ruff   | FAIL   | 3 errors         |
| mypy   | PASS   | no issues found  |
```

## Step 3 — For any failures, show details

For each failing check:
1. Show the exact error output (file, line, message)
2. Explain what the error means in plain English
3. Suggest a fix or offer to fix it

## Step 4 — Verdict

End with a single-line verdict:
- **All clear** — all three checks passed, safe to restart/deploy
- **Issues found** — list the count and offer to fix them

## Key config
- ruff config: `pyproject.toml` (line-length 120, rules E/F/W/I/UP)
- mypy config: `pyproject.toml` (strict-ish, Python 3.12)
- pytest config: standard, tests in `tests/` directory
