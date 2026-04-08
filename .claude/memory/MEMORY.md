# Patchy Bot — Claude Code Memory Index
_Last updated: 2026-04-07_

This is the primary context file for Claude Code working on Patchy Bot.
**Read this file at the start of every session before doing any work.**
After any write to a category file, update the matching summary line below.

---

## Quick Reference
- **Project:** Patchy Bot | Root: `~/Patchy_Bot/`
- **Package:** `~/Patchy_Bot/telegram-qbt/patchy_bot/`
- **Service:** `telegram-qbt-bot.service` — restart after any patchy_bot/ changes
- **Python:** 3.12+ | sqlite3 WAL | python-telegram-bot (polling) | asyncio
- **No git writes** without explicit permission from the user

---

## Recent Session
_Full history in [sessions.md](sessions.md)_

> Last session: 2026-04-07 — Memory system initialized, migrated 17 items from old memory locations

---

## Key Decisions
_Full rationale in [decisions.md](decisions.md)_

- 2026-04-07 — No git in Patchy_Bot — direct file edits + service restart after git reset incident
- 2026-04-06 — Plex autoEmptyTrash=1 + purge_deleted_path — ghost media entries from replaced downloads
- 2026-04-07 — qBT interface binding removed — breaks libtorrent DNS; OS kill-switch handles VPN
- 2026-04-04 — Package restructure — monolith split into patchy_bot/ package; qbt_telegram_bot.py is compat shim
- 2026-04-07 — CAM/TS/SCR penalized not rejected — movie schedule needs trash sources as last resort

---

## Known Bugs & Fixes
_Full details in [bugs.md](bugs.md)_

- 2026-04-07 — 17 bug fixes: qBT firewalled auto-clear, poller dedup, hash resolver recency, EMA NoneType, organizer TOCTOU race, non-media rejection, path safety PurePosixPath, stall reannounce, tracker error streak removal, pending timeout notification, quality trash penalty, malware scan gate, pending tracker lost header/keyboard, season nav arrows, HTML escape in add summary, schedule menu UX, user message cleanup

---

## Patterns & Conventions Discovered
_Full details in [patterns.md](patterns.md)_

- Always HTML-escape dynamic values with `_h()` for parse_mode=HTML messages
- Never use `os.path.exists()` check before `shutil.move()` — use try/except for TOCTOU safety
- Never fuzzy-match torrent names without recency filter
- Never kill long-running monitors based on transient Telegram API errors
- Never require text input when inline buttons work — breaks callback-driven UX
- Always validate file extensions before moving into Plex library dirs
- Never use prompt-type hooks (PostToolUse or Stop) — they halt or loop
- Always use project subagents for domain work — never implement inline
- Movie/TV search changes must be applied to both paths (parity rule)
- Never bind qBT to VPN interface — OS kill-switch handles routing

---

## Memory Infrastructure
- Event buffer: `.event-buffer.jsonl` (written by PostToolUse hook, rotated on Stop)
- Buffer archives: `.event-buffer-YYYYMMDD-HHMMSS.jsonl` (last 5 kept)
- Category files: decisions.md | bugs.md | patterns.md | sessions.md
