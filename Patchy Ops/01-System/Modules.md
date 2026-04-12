---
tags:
  - system/modules
aliases:
  - Module Map
created: 2026-04-11
updated: 2026-04-11
---

# Modules

## Overview

The Patchy Bot codebase is organized as one Python package called `patchy_bot`, which lives at `telegram-qbt/patchy_bot/`.

A package is a folder of related Python files that work together. Each file inside the package is called a module, and each module is responsible for one job.

Below is a plain-English tour of every module, grouped by floor of the building.

**Top-level files**

- `__main__.py` — The light switch. When you run `python -m patchy_bot`, this is the file that turns the bot on, sets up logging, builds the bot object, and starts the loop that listens to Telegram.
- `bot.py` — The bot's central nervous system. It builds the giant `BotApp` class that wires every command, button, and background loop together.
- `config.py` — The settings reader. It pulls every option (passwords, paths, URLs, limits) out of the `.env` file so the rest of the code can ask for them by name.
- `dispatch.py` — The phone directory for buttons. When a Telegram button is tapped, this file matches the button's hidden code to the right handler. See [[Callback Routes]].
- `types.py` — The shared clipboard. It defines `HandlerContext`, the single object that every handler is given so they can share clients, locks, and per-user state. See [[State & Flows]].
- `store.py` — The notebook. All persistent state lives here in SQLite. See [[SQLite Tables]].
- `utils.py` — A box of small reusable tools (timestamp helpers, HTML escaping, byte formatters, retry-aware HTTP sessions).
- `health.py` — The doctor. Checks VPN status, free disk space, and qBittorrent connectivity, and produces the `/health` report.
- `malware.py` — The bouncer. Scans torrent names and downloaded files for fakes, scams, and known-bad patterns.
- `quality.py` — The film critic. Parses release names like `Movie.2024.2160p.WEB-DL.x265-GROUP` and gives them a score so the best version wins.
- `plex_organizer.py` — The librarian. After a download finishes, it renames and moves the files into the right Plex folders.
- `rate_limiter.py` — The traffic cop. Limits how often each user can hit certain commands.
- `logging_config.py` — The court reporter. Configures log format (plain text or structured JSON).

**`handlers/` — one file per user-facing area**

- `base.py` — Tiny shared base class for handler modules.
- `_shared.py` — Helper functions reused across handlers (formatting, error replies, common keyboard pieces).
- `commands.py` — Every slash command (`/start`, `/search`, `/health`, etc.).
- `search.py` — The search flow: take a query, hit qBittorrent's search plugins, filter, score, and present results.
- `download.py` — The add/progress/completion pipeline: add torrent, watch progress, react to finish, hand off to the organizer.
- `schedule.py` — TV episode tracking + movie release tracking. Owns the schedule menu, the schedule runner, and movie tracking callbacks.
- `remove.py` — Lets the user delete shows, seasons, or movies from disk and Plex safely.
- `chat.py` — Free-form Patchy-themed chat through an OpenAI-compatible LLM.

**`clients/` — wrappers around outside services**

- `qbittorrent.py` — `QBClient`. Talks to the qBittorrent Web API (login, search, add torrent, list, pause, resume, delete). Thread-safe.
- `plex.py` — `PlexInventoryClient`. Talks to Plex's XML API to check what's already in the library and to trigger refreshes/cleanups.
- `tv_metadata.py` — `TVMetadataClient`. Talks to TVMaze for shows/episodes and TMDB for movies and release dates.
- `llm.py` — `PatchyLLMClient`. Talks to any OpenAI-compatible chat endpoint for the Patchy chat persona.

**`ui/` — Telegram presentation layer**

- `flow.py` — Tiny `set_flow` / `get_flow` / `clear_flow` helpers for per-user "what page are you on" state.
- `keyboards.py` — All inline keyboard builders (the rows of buttons).
- `rendering.py` — Functions that build the long HTML messages (command center, results lists, schedule view).
- `text.py` — Static text snippets and templates.

> [!code]- Claude Code Reference
>
> **Top-level (`telegram-qbt/patchy_bot/`)**
>
> - **`__main__.py`** — 92 lines
>   - Key exports: `main()`
> - **`bot.py`** — 5023 lines
>   - Key exports: `BotApp` (constructs handlers, dispatcher, runners; `build_application()`)
> - **`config.py`** — 200 lines
>   - Key exports: `Config` (dataclass, `Config.from_env()`)
> - **`dispatch.py`** — 53 lines
>   - Key exports: `CallbackDispatcher` (`register_exact`, `register_prefix`, `dispatch`)
> - **`types.py`** — 96 lines
>   - Key exports: `HandlerContext` (dataclass with all clients + shared mutable state)
> - **`store.py`** — 1663 lines
>   - Key exports: `Store` (14 tables, ~60 CRUD methods, WAL, `threading.Lock()`)
> - **`utils.py`** — 356 lines
>   - Key exports: `now_ts`, `human_size`, `episode_code`, `_h`, `build_requests_session`, parsing helpers
> - **`health.py`** — 210 lines
>   - Key exports: `collect_health_report()`, VPN/disk/qBT probes
> - **`malware.py`** — 268 lines
>   - Key exports: `scan_search_result()`, `scan_completed_files()`, fake-name + extension checks
> - **`quality.py`** — 463 lines
>   - Key exports: `score_torrent()`, `quality_label()`, RTN-style parser, resolution/source/codec scoring
> - **`plex_organizer.py`** — 398 lines
>   - Key exports: `organize_completed_download()`, episode/movie file naming, safe move
> - **`rate_limiter.py`** — 67 lines
>   - Key exports: `RateLimiter` (`allow`, `prune_stale`)
> - **`logging_config.py`** — 48 lines
>   - Key exports: `_JsonFormatter`
>
> **`handlers/`**
>
> - **`handlers/__init__.py`** — 12 lines
>   - Key exports: re-exports
> - **`handlers/base.py`** — 34 lines
>   - Key exports: `BaseHandler`
> - **`handlers/_shared.py`** — 207 lines
>   - Key exports: shared formatting + reply helpers
> - **`handlers/commands.py`** — 1161 lines
>   - Key exports: `cmd_start`, `cmd_help`, `cmd_health`, `cmd_speed`, `cmd_search`, `cmd_schedule`, `cmd_remove`, `cmd_show`, `cmd_add`, `cmd_categories`, `cmd_mkcat`, `cmd_setminseeds`, `cmd_setlimit`, `cmd_profile`, `cmd_active`, `cmd_plugins`, `cmd_unlock`, `cmd_logout`
> - **`handlers/search.py`** — 552 lines
>   - Key exports: `on_search_query`, result rendering, filter callbacks
> - **`handlers/download.py`** — 2442 lines
>   - Key exports: `on_add_torrent`, progress trackers, completion poller, deferred-hash pending path
> - **`handlers/schedule.py`** — 3522 lines
>   - Key exports: TV tracking, schedule runner, `msch:` movie callbacks, season/episode pickers
> - **`handlers/remove.py`** — 2683 lines
>   - Key exports: remove menu, plex inventory walker, removal job creation/runner
> - **`handlers/chat.py`** — 239 lines
>   - Key exports: LLM chat handler with per-user history
>
> **`clients/`**
>
> - **`clients/__init__.py`** — 1 line
>   - Key exports: —
> - **`clients/qbittorrent.py`** — 287 lines
>   - Key exports: `QBClient` (login, search, add_url, list_categories, create_category, ensure_category, list_active, get_transfer_info, get_preferences, set_preferences, get_torrent, delete_torrent, pause_torrents, resume_torrents, get_torrent_files, list_torrents, list_search_plugins, get_torrent_trackers, reannounce_torrent)
> - **`clients/plex.py`** — 409 lines
>   - Key exports: `PlexInventoryClient` (`ready`, `episode_inventory`, `movie_exists`, `resolve_remove_identity`, `refresh_for_path`, `purge_deleted_path`, `refresh_all_by_type`, `verify_remove_identity_absent`)
> - **`clients/tv_metadata.py`** — 339 lines
>   - Key exports: `TVMetadataClient` (`search_shows`, `get_show_bundle`, `search_movies`, `get_movie_release_dates`, `get_movie_home_release`, `get_movie_release_status`); also `MovieReleaseStatus` enum and `MovieReleaseDates` dataclass
> - **`clients/llm.py`** — 111 lines
>   - Key exports: `PatchyLLMClient` (`ready`, `chat`)
>
> **`ui/`**
>
> - **`ui/__init__.py`** — 1 line
>   - Key exports: —
> - **`ui/flow.py`** — 22 lines
>   - Key exports: `set_flow`, `get_flow`, `clear_flow`
> - **`ui/keyboards.py`** — 332 lines
>   - Key exports: inline-keyboard builders for command center, search results, schedule, remove, picker, etc.
> - **`ui/rendering.py`** — 333 lines
>   - Key exports: message renderers for command center, status lines, schedule list
> - **`ui/text.py`** — 424 lines
>   - Key exports: static strings and HTML templates
>
> **Total runtime LOC:** ~22,100 across 33 files (excludes `__pycache__`).
