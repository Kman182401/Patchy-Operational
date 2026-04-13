---
name: patchy-bot-python-router
description: Routes Patchy Bot Python work to the correct upstream Python skill based on the file or module being touched. USE WHEN editing, adding, reviewing, or debugging code under telegram-qbt/patchy_bot/, designing a new Patchy Bot module, or planning a fix that involves runners, the Store, qBT/Plex/Telegram clients, env config, logging, retries, or error handling. Acts as a lookup table from "what I'm changing" to "which library skill to invoke first."
---

# Patchy Bot Python Skill Router

This is a **routing layer** between Patchy Bot's runtime code and the 11 installed Python skills (`python-error-handling-skill`, `python-resilience-skill`, `python-background-jobs-skill`, `python-resource-management-skill`, `python-observability-skill`, `python-type-safety-skill`, `python-anti-patterns-skill`, `python-design-patterns-skill`, `python-configuration-skill`, `python-code-style-skill`, `writing-python-skill`).

When you start work on Patchy Bot Python code, consult this table FIRST. It tells you which upstream skill is load-bearing for that area, so you can invoke the most relevant one(s) automatically instead of guessing.

## Module → Skill mapping

| If you are touching… | Primary skill | Secondary skills | Why |
|----------------------|---------------|------------------|-----|
| `telegram-qbt/patchy_bot/store.py` (SQLite Store) | `python-resource-management` | `python-error-handling`, `python-resilience` | Connection lifecycle, async context managers, transaction safety, deadlock retries |
| `telegram-qbt/patchy_bot/runners/*` (completion poller, schedule runner, movie-track runner, remove-runner, pending-monitor) | `python-background-jobs` | `python-resilience`, `python-observability` | Long-running async loops, idempotency, retry/backoff, structured logging for runner state |
| `telegram-qbt/patchy_bot/qbt_client.py` and any qBT API calls | `python-resilience` | `python-error-handling`, `python-observability` | qBT is VPN-fronted and frequently `firewalled`/transient; needs retry, timeouts, status logging |
| `telegram-qbt/patchy_bot/plex_client.py` (PlexInventoryClient) | `python-resilience` | `python-resource-management`, `python-error-handling` | Plex XML API is flaky on big libraries; HTTP session lifecycle matters |
| `telegram-qbt/patchy_bot/handlers/*` (Telegram callback handlers) | `python-error-handling` | `python-design-patterns`, `python-observability` | Each handler is a boundary; needs validation, exception conversion to user-facing messages, logging |
| `telegram-qbt/patchy_bot/config.py` and env-var loading | `python-configuration` | `python-type-safety` | Externalized config, typed settings, validate at startup |
| `telegram-qbt/patchy_bot/logging_setup.py` and any new logging | `python-observability` | — | Structured logging, correlation IDs, four golden signals |
| Any new module from scratch | `writing-python` | `python-design-patterns`, `python-code-style`, `python-type-safety` | Idiomatic 3.x, KISS, SRP, ruff-clean, fully type-hinted |
| Any code review / pre-commit pass | `python-anti-patterns` | `python-code-style`, `python-design-patterns` | Checklist of what NOT to do |
| Type errors, mypy/pyright failures, generic class design | `python-type-safety` | — | Type narrowing, protocols, generics |
| Adding a retry/backoff/timeout anywhere | `python-resilience` | `python-error-handling` | Don't reinvent — use the documented decorators |
| Adding a new background loop, scheduler, queue, or worker | `python-background-jobs` | `python-resilience`, `python-observability` | Idempotency rules, dead-letter handling |

## Patchy Bot–specific overrides

These rules **override** generic upstream skill advice when they conflict:

1. **Never bind qBT to a VPN interface.** The OS kill-switch handles VPN; interface binding breaks libtorrent DNS. Resilience patterns must NOT recommend interface binding as a fix for `firewalled` status. (See auto-memory `feedback_no_qbt_interface_binding.md`.)
2. **Don't introduce `pydantic-settings`** without explicit user approval. Patchy Bot uses plain `os.getenv` + `config.py`. The `python-configuration` skill recommends pydantic-settings; if you want to use it, ask first.
3. **Don't introduce `Celery`/`RQ`/`Dramatiq`.** Patchy Bot has its own runner system (`runners/`). The `python-background-jobs` skill discusses these queues — apply the *patterns* (idempotency, dead-letter, etc.) but to the existing runner code, not by adding a new dependency.
4. **Don't introduce Prometheus/OpenTelemetry exporters** without explicit approval. Apply the `python-observability` skill's *structured logging* guidance only; the metrics/tracing sections are aspirational for now.
5. **Don't introduce `uv`.** Patchy Bot uses pip / venv. The `writing-python` skill assumes uv — translate its commands mentally.
6. **HTML escape with `_h()`.** Any dynamic value going into a Telegram HTML message must be wrapped. Generic error-handling advice that constructs user-facing strings must respect this rule.
7. **Path safety with `PurePosixPath`.** When `python-resource-management` discusses file handles, the Patchy Bot media paths must continue to use `PurePosixPath` for traversal-safety checks (see `bugs_2026-04-07.md`).
8. **Movie/TV parity.** Any change to a search/add path must be applied symmetrically. Generic design-pattern refactors that touch only one side are wrong by default.
9. **Two-stage subagent review.** Per `feedback_subagent_driven_dev.md`, all real code work is dispatched to domain subagents (database-agent, schedule-agent, etc.). This router skill is consulted by *those subagents*; main thread should still delegate.

## How to use this skill

Step 1 — Identify the target file or area of change.
Step 2 — Look up the row in the table above.
Step 3 — Invoke the **primary** skill for that area before writing code.
Step 4 — If the change spans multiple rows, invoke each primary skill once.
Step 5 — Apply the Patchy Bot–specific overrides above on top of whatever the upstream skills recommend.
Step 6 — Continue with the normal end-of-task routine: post-changes-audit → code-simplifier → restart service → push → /revise-claude-md.

## Quick decision tree

- "I'm fixing a bug" → check the affected file → primary skill from table → also `python-anti-patterns` as a checklist
- "I'm adding a feature" → `writing-python` + `python-design-patterns` + the file-area primary
- "I'm refactoring" → `python-design-patterns` + `python-anti-patterns` + the file-area primary
- "Something flaky is breaking" → `python-resilience` first, then file-area primary
- "I'm adding a runner / scheduler / poller" → `python-background-jobs` always
- "I'm adding new env config" → `python-configuration` always
- "I'm adding logging" → `python-observability` always
