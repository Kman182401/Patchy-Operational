# State Model

> Generated from `patchy_bot/types.py` on 2026-04-11. `HandlerContext` is the single shared state object injected into all handlers.

## HandlerContext Fields

### Clients (immutable after init)

| Field | Type | Purpose |
|-------|------|---------|
| `cfg` | `Config` | All settings from `.env` via `Config.from_env()` |
| `store` | `Store` | SQLite persistence layer (14 tables, 60 CRUD methods) |
| `qbt` | `QBClient` | qBittorrent WebUI API client |
| `plex` | `PlexInventoryClient` | Plex Media Server inventory client |
| `tvmeta` | `TVMetadataClient` | TVMaze + TMDB metadata client |
| `patchy_llm` | `PatchyLLMClient` | OpenAI-compatible chat client |
| `rate_limiter` | `RateLimiter` | Per-user sliding-window rate limiter |

### Shared Mutable State (in-memory, lost on restart)

| Field | Type | Scope | Purpose |
|-------|------|-------|---------|
| `user_flow` | `dict[int, dict]` | Per-user | Current modal flow state (search, schedule, remove) |
| `user_nav_ui` | `dict[int, dict[str, int]]` | Per-user | Navigation UI state (page indices, scroll positions) |
| `progress_tasks` | `dict[(int, str), Task]` | Per-(user, hash) | Active progress-tracking asyncio tasks |
| `pending_tracker_tasks` | `dict[(int, str, str), Task]` | Per-(user, hash, name) | Pending tracker resolution tasks |
| `batch_monitor_messages` | `dict[int, Any]` | Per-user | Batch download monitor message references |
| `batch_monitor_tasks` | `dict[int, Task]` | Per-user | Batch monitor asyncio tasks |
| `batch_monitor_data` | `dict[(int, str), dict]` | Per-(user, hash) | Batch monitor progress data |
| `user_ephemeral_messages` | `dict[int, list]` | Per-user | Ephemeral messages pending cleanup |
| `command_center_refresh_tasks` | `dict[int, Task]` | Per-user | Command center auto-refresh loops |
| `chat_history` | `OrderedDict[int, list]` | Per-user | LLM conversation history (max 50 users) |
| `pending_scans` | `dict[str, dict]` | Per-hash | Torrents added but not yet resumed (shown in command center) |
| `background_tasks` | `set[Task]` | Global | Fire-and-forget background tasks |
| `app` | `Application` | Global | python-telegram-bot Application reference |

### Application Callbacks (set after ctx creation)

| Field | Type | Purpose |
|-------|------|---------|
| `render_command_center` | `Callable` | Render the command center for a user |
| `navigate_to_command_center` | `Callable` | Navigate user to command center |

### Schedule Source Health (thread-safe)

| Field | Type | Purpose |
|-------|------|---------|
| `schedule_source_state` | `dict[str, dict]` | Metadata + inventory source health tracking |
| `schedule_source_state_lock` | `threading.Lock` | Protects `schedule_source_state` reads/writes |

Tracks consecutive failures with exponential backoff (60s-4h) for:
- **metadata** — TVMaze API health
- **inventory** — Plex inventory probe health

### Async Locks

| Field | Purpose |
|-------|---------|
| `schedule_runner_lock` | Prevents concurrent schedule runner executions |
| `remove_runner_lock` | Prevents concurrent remove runner executions |
| `state_lock` | General state mutation lock |
| `download_queue_lock` | Protects download queue operations |

### Sequential Download Queue

| Field | Type | Purpose |
|-------|------|---------|
| `download_queue` | `asyncio.Queue` | FIFO queue — only one torrent downloads at a time |
| `active_download_hash` | `str | None` | Hash of the currently-downloading torrent |

## Background Runners

| Runner | Interval | Purpose |
|--------|----------|---------|
| schedule-runner | 120s | Check due TV episodes + movie releases, trigger auto-downloads |
| remove-runner | 60s | Process pending media removal jobs |
| completion-poller | 60s | Detect completed torrents, organize, notify |
| command center refresh | 3s | Per-user async loop updating command center message |
| qbt-health-check | 300s | Periodic qBT connectivity check |

## State Survival Matrix

| State | Survives Restart? | Mechanism |
|-------|-------------------|-----------|
| User flow state | No | In-memory `user_flow` dict |
| Search results | Yes | SQLite `searches` + `results` tables |
| Schedule tracks | Yes | SQLite `schedule_tracks` table |
| Download progress | No | In-memory `progress_tasks` |
| Remove jobs | Yes | SQLite `remove_jobs` table |
| Movie tracks | Yes | SQLite `movie_tracks` table |
| Command center ref | Yes | SQLite `command_center_ui` table |
| Chat history | No | In-memory `OrderedDict` |
| Auth sessions | Yes | SQLite `user_auth` table |
| Health events | Yes | SQLite `download_health_events` table |
| Pending scans | No | In-memory `pending_scans` dict |
