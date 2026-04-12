# Module Map

> Generated from codebase on 2026-04-11. Total: 33 Python files, ~21,680 lines.

## patchy_bot/ (core)

| File | Purpose | Lines |
|------|---------|-------|
| `bot.py` | Main application — command handlers, callback router, lifecycle, background runners | 4,813 |
| `store.py` | SQLite persistence — 14 tables, 60 CRUD methods, WAL mode | 1,600 |
| `config.py` | `Config` dataclass loaded from env vars via `Config.from_env()` | 200 |
| `types.py` | `HandlerContext` dataclass — shared state/clients injected into all handlers | 96 |
| `dispatch.py` | `CallbackDispatcher` — exact + prefix-based callback routing | 53 |
| `quality.py` | Torrent quality scoring engine backed by RTN (rank-torrent-name) | 463 |
| `malware.py` | Heuristic malware/fake-content scanner — search-time and download-time | 268 |
| `health.py` | Download health checks — VPN, qBT connectivity, disk space | 210 |
| `plex_organizer.py` | Post-download media organizer for Plex directory structure | 398 |
| `utils.py` | Pure utility functions: `_h()`, `human_size()`, `now_ts()`, `episode_code()` | 356 |
| `rate_limiter.py` | Per-user sliding-window rate limiter | 67 |
| `logging_config.py` | JSON-structured log formatter for journalctl/jq | 48 |
| `__main__.py` | Entry point — `python -m patchy_bot` | 92 |
| `__init__.py` | Package init | 58 |

## patchy_bot/handlers/

| File | Purpose | Lines |
|------|---------|-------|
| `commands.py` | 18 slash command implementations (`/start`, `/search`, `/schedule`, etc.) | 1,161 |
| `schedule.py` | TV episode tracking, TVMaze/TMDB metadata, auto-acquire, schedule runner | 3,369 |
| `download.py` | Download tracking, progress monitoring, completion polling | 2,442 |
| `remove.py` | Media removal — search, browse, selection, safety checks, deletion, Plex cleanup | 2,683 |
| `search.py` | Search parsing, filtering, sorting, rendering | 552 |
| `chat.py` | LLM / Patchy-chat handler functions | 239 |
| `base.py` | Abstract base handler class | 34 |
| `_shared.py` | Shared utilities used by multiple handler modules | 207 |
| `__init__.py` | Package init | 12 |

## patchy_bot/clients/

| File | Purpose | Lines |
|------|---------|-------|
| `qbittorrent.py` | `QBClient` — qBittorrent WebUI API client, thread-safe with `threading.Lock` | 287 |
| `plex.py` | `PlexInventoryClient` — Plex XML API, episode inventory, remove verification | 409 |
| `tv_metadata.py` | `TVMetadataClient` — TVMaze show search + TMDB movie search/release dates | 339 |
| `llm.py` | `PatchyLLMClient` — OpenAI-compatible chat client for Patchy personality | 111 |
| `__init__.py` | Package init | 1 |

## patchy_bot/ui/

| File | Purpose | Lines |
|------|---------|-------|
| `keyboards.py` | Shared keyboard builders (pagination, navigation, selection) | 332 |
| `rendering.py` | Render helpers — nav-UI, flow-UI, ephemeral-message lifecycle | 333 |
| `text.py` | Shared text builders used across multiple flows | 424 |
| `flow.py` | Flow state management — `set_flow()`, `get_flow()`, `clear_flow()` | 22 |
| `__init__.py` | Package init | 1 |
