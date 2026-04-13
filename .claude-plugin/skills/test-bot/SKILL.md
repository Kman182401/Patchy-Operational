---
name: test-bot
description: Run Patchy Bot verification from the project venv. Use automatically after Python, test, typing, or lint-relevant changes, and before claiming code is done. Prefer this for real code changes; do not use for docs-only or skill-only edits.
---

# Full Quality Check Suite

Run the project verification commands against the Patchy Bot codebase and report a unified pass/fail summary.

All commands run from `/home/karson/Patchy_Bot/telegram-qbt` using the project venv.

## Agent Delegation

This skill delegates to the following agents during execution. Always use these agents — do not implement inline what an agent can handle.

- **Primary:** Delegate test execution, lint checks, and failure diagnosis to the `test-runner`.
- **On config/tooling failure:** If the venv or toolchain is missing, route the environment problem to the `implementer`.

## Step 1 — Run the verification stack

Run these commands from the project root:

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

If the task only touched a narrow area, it is fine to run targeted pytest selection first. Before final handoff, prefer the broader suite when practical.

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

If a command fails because the tool is missing or the venv is broken, report that as an environment/setup issue, not as an application test failure.

## Step 4 — Verdict

End with a single-line verdict:
- **All clear** — all three checks passed, safe to restart/deploy
- **Issues found** — list the count and offer to fix them

## Key config
- ruff config: `pyproject.toml` (line-length 120, rules E/F/W/I/UP)
- mypy config: `pyproject.toml` (strict-ish, Python 3.12)
- pytest config: `pyproject.toml`, tests in `tests/`
