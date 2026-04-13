# Patchy Bot — Project Instructions

## Guardrails
- Do not run raw git write commands in `/home/karson/Patchy_Bot`. The `push` shell alias is the only sanctioned commit+push path.
- Prefer code over docs when they disagree.
- Keep changes targeted. Do not rewrite unrelated flows.
- Do not edit `telegram-qbt/qbt_telegram_bot.py` (back-compat shim).
- Use the `patchy-bot-python-router` skill for module ownership and routing.

## Core Invariants
- Runtime code lives in `telegram-qbt/patchy_bot/`.
- Restart-safe state → SQLite via `telegram-qbt/patchy_bot/store.py`. Transient UI state in memory.
- Movie and TV search/add/UI paths stay aligned unless user wants divergence.
- Escape dynamic values in Telegram HTML with `_h()`.
- Download/progress changes must update BOTH the immediate path AND the deferred-hash pending path.

## Restart Rule
After changes under `telegram-qbt/patchy_bot/`, restart `telegram-qbt-bot.service`.

## Push Rule
- After any change under `/home/karson/Patchy_Bot/`, run the `push` shell alias. Only sanctioned git path.
- End-of-task order: post-changes-audit → restart service (if runtime changed) → `push` → `/revise-claude-md`.

## /revise-claude-md Rule
At end of any productive session, invoke `/revise-claude-md` (claude-md-management plugin) AFTER push so updates land in the next commit. If it proposes nothing, report "no new learnings" — never fabricate.

## Verification
- Test: `.venv/bin/python -m pytest -q` in `telegram-qbt/`
- Ruff + mypy config: `telegram-qbt/pyproject.toml`
- Fix pre-existing issues in-session — never report "done" with known errors.

## Compaction: PRESERVE
- Files modified this session + what changed
- Current task + acceptance criteria
- Test commands + last status
- Callback namespaces being worked on (`msch:`, `sch:`, `dl:`)
- Error messages / stack traces being debugged
- Movie/TV parity rule if either search path touched
- Handler files modified (for restart decision)

## Compaction: DROP
- Verbose file-read outputs
- Full test suite output (keep only pass/fail counts + failing names)
- Large grep/glob results
- Completed subtask details
- Earlier iterations of rewritten code

## Research Policy
- Use Context7 via `ctx7` CLI before writing library code (python-telegram-bot, TMDB, qBT, Plex, asyncio, SQLite, pytest). `context7-skills-scout` auto-activates.
- After every ctx7 lookup, scan the 4 canonical skill libraries for same-topic skills; surface to user, never install without approval.
- WebSearch the exact error + library + version on errors. Skip research for trivial changes.

## Obsidian Vault (`Patchy Ops/`)
- Before tasks: check `03-Reference/Preferences.md`.
- After task changes: update status + append `05-Changelog/` entry.
- On architecture changes: update `01-System/` docs.
- On learned preferences: add to `03-Reference/Preferences.md`.
- After modifications: refresh `00-Home/Dashboard.md`.
- New notes use `_templates/` frontmatter.
