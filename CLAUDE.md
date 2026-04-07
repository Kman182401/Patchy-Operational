# Patchy Bot — Project Intelligence

## Git Policy — ~/Patchy_Bot
MUST NOT run any git-write commands (add, commit, push, reset, rebase, merge, branch create/delete, tag, stash) in ~/Patchy_Bot unless the user explicitly requests it in the current message. Read-only git commands (status, log, diff, show, remote -v) are always allowed. Editing files is allowed — committing them is not.

## System Overview

Patchy Bot is a Telegram bot managing qBittorrent downloads and Plex media library operations. It runs as a systemd service (`telegram-qbt-bot.service`) via `python -m patchy_bot` from a venv at `.venv/`. Python 3.12+, SQLite (WAL mode) for persistence, async via python-telegram-bot polling.

## Package Map

    patchy_bot/
      __main__.py          # Entry: logging → Config → BotApp → polling
      bot.py               # BotApp: ALL handlers, callbacks, runners (~6,671 lines — refactor target)
      config.py            # @dataclass, 45 env vars via Config.from_env()
      store.py             # SQLite: 11 tables, 24+ CRUD methods, WAL mode
      utils.py             # Pure functions, constants, episode parsing
      rate_limiter.py      # Per-user sliding-window rate limiter
      logging_config.py    # JSON log formatter for journalctl
      clients/
        qbittorrent.py     # QBClient: qBT WebUI API v2 wrapper (thread-safe)
        llm.py             # PatchyLLMClient: OpenAI-compat with model fallback
        tv_metadata.py     # TVMetadataClient: TVMaze + TMDB
        plex.py            # PlexInventoryClient: Plex XML API ops

    Supporting:
      plex_organizer.py    # Moves downloads → Plex folder structure
      qbt_telegram_bot.py  # Backward-compat shim (tests import from here)

    tests/
      test_parsing.py          # 122+ tests, primary suite
      test_delete_safety.py    # 17 path-safety tests
      test_auth_ratelimit.py   # 19 auth/rate-limit tests

## Domain Boundaries in bot.py

bot.py is monolithic. These are the logical domains and their approximate line ranges:

- **Auth system:** Allowlist check → rate limiting → password gate → brute-force protection → session TTL
- **Text input router (`on_text`):** Auth gate → active flow dispatch → quick shortcuts → prefixed searches → intent extraction → fallback
- **Callback router (`on_callback`):** 53+ prefixes via if/elif chain (nav:, a:, d:, p:, menu:, flow:, sch:, rm:, stop:)
- **Schedule system:** TVMaze lookup → season selection → Plex inventory probe → episode tracking → background runner (120s interval) → smart next-check scheduling → auto-download with episode ranking
- **Remove system:** Fuzzy search / browse → multi-select → safety checks (path traversal, symlink, depth) → disk delete → qBT cleanup → Plex cleanup with retry
- **Download tracking:** Per-download progress tasks → pending monitors → completion poller (60s) → Plex organize + scan
- **Command Center:** Single-message edit pattern, per-user refresh loop (5s), persisted message location
- **UI patterns:** All flows use `user_flow[uid]` dict with `mode` and `stage` keys

## State Management

| Storage | Scope | Survives restart? |
|---------|-------|-------------------|
| `user_flow` | Per-user modal state | No |
| `user_nav_ui` | Command center message ref | Yes (DB-backed) |
| `progress_tasks` | Download monitor asyncio Tasks | No |
| `chat_history` | LRU-bounded LLM history | No |
| `schedule_source_state` | Metadata/inventory health | No |
| SQLite `Store` | Everything persistent | Yes |

## Coding Conventions

- HTML parse mode for all Telegram messages; escape with `_h(text)`
- Callback data format: `prefix:param1:param2` (colon-delimited)
- New flows MUST use `user_flow[uid]` with `mode` and `stage`
- New callbacks MUST use namespaced prefixes (e.g., `myfeature:action`)
- Episode codes: `S01E02` format via `episode_code(season, episode)`
- Size display: `human_size(bytes)` and `parse_size_to_bytes("1.5 GiB")`
- Time: `now_ts()` for UNIX timestamps, `_relative_time(ts)` for display
- HTTP: `build_requests_session()` with retry/backoff on 429/5xx
- Torrent quality: `quality_tier(name)` returns 2160/1080/720/480/0

## Testing Patterns

- Run: `.venv/bin/python -m pytest tests/ -q`
- Mocks: DummyBot, DummyStore in test files
- Time mocking: `monkeypatch` on `patchy_bot.bot.now_ts`
- Sleep bypass: `monkeypatch` on `patchy_bot.clients.plex.time.sleep`
- HTTP mocking: FakeSession class
- Tests import from `qbt_telegram_bot` (backward-compat shim) — do NOT break this

## Safety Rules

- NEVER read `.env` or secrets files unless explicitly needed
- Path operations MUST pass traversal guard, symlink rejection, depth validation
- Media paths cannot resolve to system-critical directories (/, /etc, /var, etc.)
- VPN interface name must match: `^[a-zA-Z0-9_-]+$`
- SQLite file permissions: owner-only 0o600
- qBT client is thread-safe via threading.Lock() — preserve this
- Path containment checks MUST use `PurePosixPath.is_relative_to()`, never `str.startswith()` with `os.sep`
- File move operations MUST use try/except for `FileExistsError`, never check-then-move (TOCTOU race)

## Service Operations

- Service: `sudo systemctl restart telegram-qbt-bot.service`
- Logs: `journalctl -u telegram-qbt-bot.service -f`
- DB: `state.sqlite3` in working directory (WAL mode, busy_timeout=5000)
- Backup: `Store.backup()` — SQLite online backup API, 7 rotations
- Dependencies: network-online.target, qbittorrent.service, tailscaled.service

## Phase 2 Refactor Targets

The BotApp class at ~6,671 lines is the primary decomposition target:
1. Split callback router → domain-specific handlers with prefix dispatcher
2. Extract handler modules → handlers/search.py, handlers/schedule.py, handlers/remove.py, handlers/commands.py
3. Extract UI builders → All _*_keyboard() and _*_text() methods into ui/ modules
4. Re-enable Patchy chat → Remove hardcoded disable, configure LLM provider
5. Add pytest config → [tool.pytest.ini_options] in pyproject.toml

## Subagent Routing

Claude Code has 9 custom subagents in `.claude/agents/`. Use them proactively:
- **schedule-agent** — Episode tracking, TVMaze, auto-download, schedule runner logic
- **remove-agent** — Deletion flows, path safety, Plex cleanup, remove runner
- **search-download-agent** — Torrent search, download initiation, progress tracking
- **plex-agent** — Plex inventory, media organization, library refresh, PlexInventoryClient
- **config-infra-agent** — Config, env vars, startup sequence, service management
- **database-agent** — SQLite store, schema, migrations, CRUD methods, backup
- **ui-agent** — Telegram keyboards, message rendering, callback routing, flow UI
- **test-agent** — Writing/running tests, mocking patterns, coverage
- **security-agent** — Auth system, rate limiting, path safety, input validation, secrets
  - For Patchy Bot security reviews, use project `security-agent` (has domain-specific context for auth, path safety, rate limiting).
  - User-level `security-auditor` is for cross-project or generic security audits not specific to Patchy Bot.

## Subagent-Driven Development (Mandatory)

ALL work MUST use the subagent-driven-development workflow (superpowers skill). Use project subagents above as implementers. One subagent at a time, two-stage review (spec then quality) after each task. Never implement inline. Model selection: haiku (1-2 files), sonnet (multi-file), opus (design/review).

## Task Master

Use Task Master for all task tracking. Run `task-master list` at session start. Prefer CLI over MCP tools. Full reference: `.taskmaster/CLAUDE.md`.

@./.taskmaster/CLAUDE.md
