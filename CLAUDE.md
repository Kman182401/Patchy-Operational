# Patchy Bot

Python Telegram bot managing qBittorrent downloads + Plex media library.

## Hard Rules
1. Edit `patchy_bot/` only — never touch `qbt_telegram_bot.py`
2. No git writes without explicit permission — use the `push` shell alias when authorized
3. HTML parse mode — escape user text with `_h()`
4. Callback data: `prefix:param1:param2` (colon-delimited)
5. Movie/TV feature parity: every movie feature needs a TV equivalent and vice versa
6. Selected items: `✅` prefix. Never use `⬜`
7. Navigation: "↩️ Back" / "🏠 Home" — never "Cancel"
8. Scoring functions penalize (score -= N), never hard-reject (return -9999)

## Context (read when needed)
- `telegram-qbt/CLAUDE.md` — runtime rules, DB schema, runner timing, coding patterns
- `architecture-and-patterns.md` — architecture decisions
- `domain-knowledge.md` — domain knowledge
- `reference-tables.md` — lookup tables

## Agents
4 task agents available: **explorer** (read-only research), **implementer** (write code), **reviewer** (audit), **test-runner** (run tests).
Use subagents for isolated tasks — keep main context clean.

## Session Start
1. Plan before multi-step work
2. Run `/post-changes-audit` after code changes

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
