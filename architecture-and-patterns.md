# Patchy Bot Architecture & Patterns

Last updated: April 2026. If anything here conflicts with the actual source code, the code is correct — flag the discrepancy to the user.

## System Overview
Telegram bot managing qBittorrent downloads and Plex media library. Runs as systemd service (`telegram-qbt-bot.service`) via `python -m patchy_bot` from a venv at `.venv/`.

## Package Map
patchy_bot/
main.py          # Entry: logging -> Config -> BotApp -> polling
bot.py               # BotApp: handlers, callbacks, runners (~6,700 lines, undergoing refactoring)
config.py            # @dataclass, 45 env vars via Config.from_env()
store.py             # SQLite: 11 tables, 26+ CRUD methods, WAL mode
utils.py             # Pure functions, constants, episode parsing
quality.py           # Two-layer torrent quality scoring
rate_limiter.py      # Per-user sliding-window rate limiter
logging_config.py    # JSON log formatter for journalctl
plex_organizer.py    # Moves downloads -> Plex folder structure
handlers/
base.py            # Abstract BaseHandler + HandlerContext
commands.py        # 17 slash commands
search.py          # Torrent search + result rendering
schedule.py        # TV episode tracking + auto-download
download.py        # Progress tracking + completion monitoring
remove.py          # Media deletion + path safety
chat.py            # LLM personality integration
clients/
qbittorrent.py     # QBClient: qBT WebUI v2 (thread-safe)
llm.py             # PatchyLLMClient: OpenAI-compatible
tv_metadata.py     # TVMetadataClient: TVMaze + TMDB
plex.py            # PlexInventoryClient: Plex XML API

## Domain Boundaries & Data Flow

### Auth System
Flow: Allowlist check -> rate limiting -> password gate -> brute-force protection -> session TTL.
Tables: user_auth, auth_attempts.
Design decision: Auth is checked at the handler entry point, not in middleware, because different commands have different auth requirements.

### Search & Download
Flow: Text input -> intent extraction -> qBT search -> quality scoring -> result pagination -> download initiation -> progress tracking -> completion -> Plex organize -> library scan.
Tables: searches, results, user_defaults, notified_completions.
Design decision: Search results are persisted to SQLite (not held in memory) so pagination survives bot restarts and users can return to results later.

### Schedule System
Flow: TVMaze show lookup -> season selection -> Plex inventory probe -> missing episode detection -> auto-download with quality ranking -> background runner (120s interval).
Tables: schedule_tracks, schedule_show_cache, schedule_runner_status.
Design decision: The runner is interval-based (not event-driven) because episode air times from TVMaze are approximate — polling catches edge cases that event-driven would miss.

### Remove System
Flow: Fuzzy search / browse library -> multi-select -> safety validation (path traversal, symlink, depth) -> disk delete -> qBT torrent cleanup -> Plex cleanup with retry.
Tables: remove_jobs.
Design decision: Deletion is a multi-step job pipeline (not a single operation) because Plex cleanup can fail and needs retry. Jobs persist in DB so they survive restarts.

### Command Center
Single persistent message per user, edited in place. Refresh loop (5s). Message location stored in DB.
Tables: command_center_ui.
Design decision: One persistent message (edited in place) instead of sending new messages — avoids chat spam and keeps the UI clean.

## Key Architectural Patterns

### HandlerContext (Shared State Object)
Passed to all handlers. Contains all clients, stores, state dicts, and locks. This is the dependency injection mechanism — handlers never instantiate their own clients.
- Clients: cfg, store, qbt, plex, tvmeta, patchy_llm, rate_limiter
- State dicts: user_flow, user_nav_ui, progress_tasks, pending_tracker_tasks, user_ephemeral_messages, command_center_refresh_tasks
- Locks: schedule_runner_lock, remove_runner_lock, state_lock
- Schedule: schedule_source_state, schedule_source_state_lock

### Callback Router
53+ callback prefixes dispatched via if/elif chain in bot.py. Prefixes are namespaced:
- nav: Navigation, a: Add/download, d: Download details, p: Pagination
- rm: Remove operations, sch: Schedule management, menu: Menu navigation
- flow: State transitions, stop: Cancel operations
Design decision: if/elif chain (not a dict dispatch) because some callbacks need partial prefix matching and fallthrough logic.

### User Flow State Machine
`user_flow[uid]` dict with `mode` and `stage` keys for modal interactions. This is the mechanism for multi-step conversations (search -> filter -> select -> confirm). Flows are in-memory and don't survive restarts — by design, since they represent transient UI state.

### Background Runners
- Schedule runner: 120s interval, checks due tracks, probes Plex, auto-downloads
- Remove runner: Processes pending deletion jobs with retry
- Completion poller: 60s interval, detects finished downloads
- Progress tracker: Per-download asyncio task, updates progress message
- Command center refresh: 5s per-user loop

### State Persistence Model
| Storage | Scope | Survives Restart? | Why |
|---------|-------|-------------------|-----|
| user_flow | Per-user modal state | No | Transient UI state |
| user_nav_ui | Command center ref | Yes (DB) | Persistent UI |
| progress_tasks | Download monitors | No | Recreated on restart |
| pending_tracker_tasks | Pending monitors | No | Recreated on restart |
| chat_history | LRU-bounded LLM context | No | Acceptable to lose |
| schedule_source_state | Health tracking | No | Rebuilt on first run |
| SQLite Store | All persistent data | Yes | Core data |

## Service Dependencies
- network-online.target
- qbittorrent.service
- tailscaled.service

Restart command: `sudo systemctl restart telegram-qbt-bot.service`

After ANY code change to the patchy_bot/ package, the service must be restarted for changes to take effect.
