# Patchy Bot — Project Intelligence

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

## Subagent-Driven Development (Mandatory)

ALL work in this project MUST use the subagent-driven-development workflow. No exceptions — not even "simple" changes.

### The Process
1. **Break work into tasks** — Use TodoWrite to create a task list from the user's request
2. **Dispatch one implementer subagent per task** — Use the matching project subagent (schedule-agent, database-agent, ui-agent, etc.). Provide full task spec, file paths, and context. Never let the subagent inherit session context — construct exactly what it needs.
3. **Two-stage review after EACH task:**
   - **Stage 1 — Spec compliance:** Dispatch a code-reviewer subagent to verify the implementation matches what was asked. If issues found → implementer fixes → re-review.
   - **Stage 2 — Code quality:** Dispatch a second code-reviewer subagent to check quality, bugs, style. If issues found → implementer fixes → re-review.
4. **Mark task complete** only after both reviews pass
5. **Move to next task** — repeat steps 2-4
6. **After all tasks** — run test-agent for the full test suite, then restart the service

### Rules
- NEVER implement code inline in the main session — always dispatch a subagent
- NEVER skip either review stage
- NEVER proceed to the next task with open review issues
- One implementer subagent at a time (no parallel implementation — conflicts)
- If a subagent asks questions, answer them before letting it proceed
- If a subagent reports BLOCKED, assess and re-dispatch with more context or break the task smaller

### Model Selection for Subagents
- Mechanical tasks (1-2 files, clear spec): use `haiku` model
- Integration tasks (multi-file, judgment needed): use `sonnet` model
- Architecture/design/review tasks: use default (opus) model

## Task Master Workflow (Enforced)

Task Master is the project's task tracker. Use it automatically — don't wait to be asked.

### Session Start
- Run `task-master list` at the start of every session to see what's in flight.
- If the user gives a direction without referencing a specific task, check if an existing task already covers it before creating a new one.

### Before Starting Work
1. Check `task-master next` to find the highest-priority unblocked task.
2. If the user's request maps to an existing task or subtask, work on that — don't create a duplicate.
3. If the user's request is new work not covered by any task, create one: `task-master add-task --prompt="<description>"`.
4. Set the task to in-progress: `task-master set-status --id=<id> --status=in-progress`.

### During Implementation
- Log meaningful progress to the task: `task-master update-subtask --id=<id> --prompt="<what you did, what worked, what didn't>"`.
- If you discover a subtask is more complex than expected, expand it: `task-master expand --id=<id>`.
- If blocked, update the task with why and set status to `blocked`.

### After Completing Work
1. Run tests to confirm nothing broke.
2. Mark the task done: `task-master set-status --id=<id> --status=done`.
3. Check `task-master next` and tell the user what's up next.

### Planning
- Do not save plans to files. Keep all plans in the chat only.
- For multi-step work, use Task Master to break it into tasks/subtasks rather than maintaining a separate plan.
- Use `task-master analyze-complexity --research` before expanding large tasks.

### Rules
- Never read secrets or env files unless explicitly needed.
- Prefer `task-master` CLI commands over direct MCP tool calls when both are available — CLI output is easier for the user to follow.
- Don't create tasks for trivial one-line fixes. Use judgment — if it takes <2 minutes and needs no tracking, just do it.

## Git Policy — ~/Patchy_Bot
MUST NOT run any git-write commands (add, commit, push, reset, rebase, merge, branch create/delete, tag, stash) in ~/Patchy_Bot unless the user explicitly requests it in the current message. Read-only git commands (status, log, diff, show, remote -v) are always allowed. Editing files is allowed — committing them is not.

## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines, treat as if import is in the main CLAUDE.md file.**
@./.taskmaster/CLAUDE.md
