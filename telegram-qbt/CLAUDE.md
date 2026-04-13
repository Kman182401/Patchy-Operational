# telegram-qbt Runtime Notes

Repo-root rules in `../CLAUDE.md` apply. This file adds `telegram-qbt/` runtime specifics.

## Overview
Python 3.12+, python-telegram-bot (polling), SQLite WAL, asyncio. Entry: `patchy_bot/__main__.py` → `bot.py`. Service: `telegram-qbt-bot.service`.

## Architecture
- `handlers/` — commands, search, schedule, download, remove, chat
- `ui/` — flow state, keyboards, rendering, templates
- `clients/` — qBT (thread-safe), Plex XML, TVMaze/TMDB, LLM
- Routing: `CallbackDispatcher` in `dispatch.py`
- State: `HandlerContext` dataclass in `types.py`
- Persistence: `store.py` — 14 tables, WAL, busy_timeout=5000

## Telegram UI Rules
- HTML parse mode only. Escape dynamic values with `_h()`.
- Callback data: `prefix:param1:param2` (e.g., `sch:track:12345`).
- Selected items prefixed `✅`; unselected plain. Never `⬜`.
- Navigation: "↩️ Back" / "🏠 Home" — never "Cancel".
- Inline buttons for navigation — no text input when buttons work.

## Code Patterns
- `Config.from_env()` for settings
- `build_requests_session()` for HTTP clients
- `user_flow` via `ui/flow.py` — `set_flow` / `get_flow` / `clear_flow`
- Scoring penalizes (`score -= N`), never hard-rejects (`-9999`)
- In-memory cache for hot loops; DB as restart-safe fallback
- `asyncio.to_thread` does NOT forward kwargs — wrap as `lambda: func(..., kw=val)`
- Module-level mutable async state (e.g. `_clamav_consecutive_errors`) must be guarded by `asyncio.Lock`; release before blocking I/O
- Type hints required on new function signatures

## Parity Rule
Any change to Movie Search also applies to TV Search. Check both after modifying either.

## Safety: Path
- Traversal guard, symlink rejection, depth validation on all file ops
- `PurePosixPath.is_relative_to()` for containment — never `str.startswith()`
- Validate extensions before moving to Plex dirs (VIDEO_EXTS / KEEP_EXTS)
- Never `os.path.exists()` + `shutil.move()` — TOCTOU; use try/except

## Safety: SQLite
- File perms `0o600`
- WAL + busy_timeout=5000 — don't hold transactions open
- Call `conn.commit()` before `BEGIN IMMEDIATE` after `ALTER TABLE ADD COLUMN` (implicit txn)
- Multi-step migrations: explicit `BEGIN IMMEDIATE ... COMMIT/ROLLBACK` wrapper with defensive `DROP TABLE IF EXISTS <new>` before `CREATE`
- Paged bulk `DELETE` (`LIMIT 1000` loop) on retention cleanup

## Safety: Thread + VPN
- `QBClient` uses `threading.Lock()` — keep scope minimal, never hold across awaits
- Never set `current_network_interface` to VPN interface (breaks libtorrent DNS)
- OS-level Surfshark kill-switch handles VPN routing

## Service Ops
```bash
sudo systemctl restart telegram-qbt-bot.service
journalctl -u telegram-qbt-bot.service -f
```
DB: `telegram-qbt/patchy_bot.db`. Daily backup at 03:00 if `BACKUP_DIR` set.

## Background Runners
| Runner | Interval | Purpose |
|---|---|---|
| schedule-runner | 60s | TV/movie due checks → auto-download |
| remove-runner | 60s | Pending removal jobs |
| completion-poller | 60s | Organize + notify completed torrents |
| command center refresh | 3s | Per-user UI update loop |
| qbt-health-check | 300s | qBT connectivity |
