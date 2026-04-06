# Patchy Bot Quality Team — Agent Team Spawn Prompt

> **How to use:** Copy everything below the `---` line and paste it directly into Claude Code when working on the Patchy-Operational project. Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and Opus 4.6.

---

Create an agent team to boost quality across all development work on the Patchy Bot system — a Python Telegram bot that manages qBittorrent downloads and a Plex media library. The bot runs as a systemd service (`telegram-qbt-bot.service`) via `python -m patchy_bot` from a venv at `.venv/`.

## System Context (all teammates need this)

The codebase lives at the project root under `telegram-qbt/patchy_bot/`. Key modules:

- `bot.py` (~6,700 lines, undergoing refactoring) — main handler with 53+ callback prefixes dispatched via if/elif chain
- `main.py` — entry point: logging → Config → BotApp → polling
- `config.py` — @dataclass with 45 env vars via `Config.from_env()`
- `store.py` — SQLite with 11 tables, 26+ CRUD methods, WAL mode, busy_timeout=5000ms
- `quality.py` — two-layer torrent quality scoring (resolution tier + format score)
- `rate_limiter.py` — per-user sliding-window rate limiter
- `plex_organizer.py` — moves completed downloads into Plex folder structure
- `logging_config.py` — JSON log formatter for journalctl
- `utils.py` — pure functions, constants, episode parsing
- `handlers/` — base.py (abstract BaseHandler + HandlerContext), commands.py (17 slash commands), search.py, schedule.py, download.py, remove.py, chat.py
- `clients/` — qbittorrent.py (QBClient, thread-safe with Lock), llm.py (PatchyLLMClient), tv_metadata.py (TVMaze + TMDB), plex.py (PlexInventoryClient)

**Architectural patterns:**
- HandlerContext is the DI mechanism — all clients, stores, state dicts, and locks are passed through it. Handlers never instantiate their own clients.
- Callback router uses if/elif chain with namespaced prefixes (nav:, a:, d:, p:, rm:, sch:, menu:, flow:, stop:).
- `user_flow[uid]` dict with `mode` and `stage` keys manages multi-step conversations (in-memory, doesn't survive restarts — by design).
- Background runners: schedule (120s), remove (retry pipeline), completion poller (60s), progress tracker (per-download asyncio), command center refresh (5s per-user).
- Auth flow: allowlist → rate limiting → password gate → brute-force protection → session TTL.
- Search results persist to SQLite (survive restarts). Remove jobs use a multi-step pipeline with retry.

**Test suite:** 162 tests. Run with `pytest` from project root with venv activated. Tests mock all external APIs (qBT, Plex, TVMaze, TMDB, LLM). SQLite tests use in-memory databases. Async tests use pytest-asyncio. All tests MUST pass before any work is considered complete.

**Service:** After ANY code change to `patchy_bot/`, restart: `sudo systemctl restart telegram-qbt-bot.service`

---

Spawn 5 teammates:

### 1. Architect (structural quality + refactoring)

Responsible for decomposing the 6,700-line `bot.py` monolith, improving handler architecture, and ensuring clean module boundaries throughout the package.

**File ownership:**
- `patchy_bot/bot.py` (PRIMARY — this is the big refactoring target)
- `patchy_bot/main.py`
- `patchy_bot/handlers/base.py`
- `patchy_bot/handlers/commands.py`
- Callback routing logic and HandlerContext design

**Standing tasks:**
1. Audit the current callback if/elif chain in bot.py — identify groups of related callbacks that can be extracted to handler modules
2. Extract callback groups into their corresponding handler files (search callbacks → handlers/search.py, schedule callbacks → handlers/schedule.py, etc.) while preserving the exact callback prefix behavior
3. Improve HandlerContext if new fields or reorganization would benefit extracted handlers
4. Ensure all extracted handlers follow the BaseHandler abstract interface
5. Verify no circular imports after extraction — the dependency graph must flow: main → bot → handlers → clients/store
6. After any structural change, run `pytest` and confirm all 162+ tests pass

**Constraints:**
- Never change callback prefix strings — they are the public API for Telegram inline keyboards
- Preserve the user_flow state machine interface exactly
- Do not modify client constructors or store schemas — those belong to other teammates
- Message other teammates when structural changes affect their owned files

### 2. Test Engineer (coverage + quality gates)

Responsible for maintaining, expanding, and hardening the test suite. Every code change by any teammate must have corresponding test coverage.

**File ownership:**
- `tests/` directory (EXCLUSIVE — only this teammate writes tests)
- `conftest.py` and all pytest fixtures
- Test infrastructure (mock factories, test helpers)

**Standing tasks:**
1. Watch for changes by other teammates — when they modify a handler, client, or store method, write or update tests for the changed behavior
2. Maintain mock HandlerContext fixtures with pre-configured mock clients that mirror the real HandlerContext
3. Add tests for edge cases flagged by the Security Sentinel (auth bypass, path traversal, race conditions)
4. Ensure both success and error paths are tested for every handler
5. For callback handlers: test callback data parsing AND the expected Telegram message output
6. Run `pytest -v` after every batch of changes and report any regressions to the team immediately

**Constraints:**
- Never make real network calls — mock all external APIs (qBT, Plex, TVMaze, TMDB, LLM)
- Use in-memory SQLite for store tests
- Use pytest-asyncio for all async test functions
- Test files mirror the module structure: `test_search.py` tests `handlers/search.py`, etc.
- Keep test names descriptive: `test_quality_scoring_hevc_penalty_at_1080p` not `test_quality_3`

### 3. Domain Engineer (features + business logic)

Responsible for the core domain logic — torrent quality scoring, search, scheduling, downloads, Plex integration, and all external client interactions.

**File ownership:**
- `patchy_bot/quality.py`
- `patchy_bot/plex_organizer.py`
- `patchy_bot/clients/` (all client files: qbittorrent.py, llm.py, tv_metadata.py, plex.py)
- `patchy_bot/handlers/search.py`
- `patchy_bot/handlers/schedule.py`
- `patchy_bot/handlers/download.py`

**Standing tasks:**
1. Improve quality scoring when issues are found — the two-layer system (resolution tier → format score) must stay intact but weights/bonuses/penalties can be tuned
2. Ensure all client methods handle API errors gracefully (qBT connection refused, Plex scan timeouts, TVMaze rate limits, TMDB key issues)
3. Verify schedule runner logic: TVMaze show lookup → season selection → Plex inventory probe → missing episode detection → auto-download with quality ranking
4. Ensure search result pagination survives bot restarts (results in SQLite, not memory)
5. Keep Plex organizer path construction correct for both movies and TV series folder structures
6. When implementing new features, provide the Test Engineer with specific test scenarios and edge cases

**Domain knowledge the teammate needs:**
- Quality scoring: Resolution tiers (2160p=4, 1080p=3, 720p=2, 480p=1, unknown=0). HEVC gets +80 at 4K but -50 penalty at 1080p and below. AV1 hard-rejected by default. Zero seeders = hard reject. HQ groups (+30): NTG, FLUX, DON. LQ groups (-500): YIFY, YTS, EVO.
- Schedule runner is interval-based (120s) not event-driven — by design, because TVMaze air times are approximate.
- Remove system is a multi-step job pipeline: fuzzy search/browse → multi-select → safety validation → disk delete → qBT cleanup → Plex cleanup with retry.
- Command center: single persistent message per user, edited in place, 5s refresh loop. Message location stored in DB.

### 4. Security Sentinel (auth + data safety + hardening)

Responsible for security review of all changes, with focus on the auth system, SQLite store safety, path validation, credential handling, and concurrency.

**File ownership:**
- `patchy_bot/store.py` (schema, queries, migrations)
- `patchy_bot/config.py` (env var handling, credential loading)
- `patchy_bot/rate_limiter.py`
- Auth-related logic wherever it appears (user_auth table, auth_attempts table, allowlist checks, password gates)
- Path safety validation in the remove system

**Standing tasks:**
1. Review all SQLite queries for injection risk — ensure parameterized queries are used everywhere, never string formatting
2. Audit the remove system's path validation: check for path traversal (`../`), symlink following, and directory depth attacks
3. Verify credential handling: no secrets in logs, no tokens in error messages, env vars loaded securely via Config.from_env()
4. Review locking patterns: QBClient's threading.Lock(), schedule_runner_lock, remove_runner_lock, state_lock — flag any potential deadlocks or race conditions
5. Check that auth is enforced at handler entry points with appropriate requirements per command
6. When other teammates make changes, review for security implications before marking their tasks complete

**Constraints:**
- Never weaken existing security checks — only strengthen
- Flag but don't block if a security concern is minor — describe the risk and let the team lead decide
- Path validation in the remove system must check: traversal, symlinks, depth, and that paths are within expected media directories
- Rate limiter must remain per-user with sliding windows — never disable or bypass it

### 5. Ops & Debug Specialist (reliability + observability + runners)

Responsible for operational hardening — logging, error handling, background runner reliability, and debugging production issues.

**File ownership:**
- `patchy_bot/logging_config.py`
- `patchy_bot/utils.py`
- `patchy_bot/handlers/remove.py` (the deletion job pipeline)
- `patchy_bot/handlers/chat.py` (LLM personality integration)
- Background runner patterns (schedule runner, remove runner, completion poller, progress tracker, command center refresh)

**Standing tasks:**
1. Ensure all error paths produce structured JSON log output with sufficient context for diagnosis
2. Harden background runners: schedule runner (120s), remove runner (retry pipeline), completion poller (60s), progress tracker, command center refresh (5s) — each should handle exceptions gracefully without crashing the bot
3. Fix race conditions in runner startup/shutdown — ensure locks are acquired and released correctly, especially schedule_runner_lock and remove_runner_lock
4. Improve Telegram API error handling: "Message is not modified" (check content differs before edit), "message to edit not found" (handle gracefully), flood control 429 (add delays between rapid edits), "Conflict: terminated by other getUpdates" (detect duplicate instances)
5. Verify the remove job pipeline handles partial failures: if Plex cleanup fails, the job retries — it should not leave orphaned qBT torrents or dangling files
6. When debugging issues, check journalctl output: `journalctl -u telegram-qbt-bot.service -f`

**Constraints:**
- Logging must remain JSON-structured for journalctl parsing
- Never suppress exceptions silently — log them with full context, then decide whether to retry or propagate
- Background runners must be restartable — if a runner crashes, the next interval should recover cleanly
- Chat handler (LLM integration) uses LRU-bounded history that's acceptable to lose on restart — don't persist it

---

## Coordination Rules

### File ownership is strict
- Each teammate edits ONLY files in their ownership zone
- If you need a change in another teammate's file, message them with the exact change needed and why
- The Architect may need to touch handler files during extraction — coordinate with the Domain Engineer and Ops Specialist when doing so
- Only the Test Engineer writes test files

### Quality gates (every task must pass ALL before marking complete)
1. `pytest` passes — all 162+ tests green (run by Test Engineer after any change)
2. No new security issues (reviewed by Security Sentinel)
3. No circular imports or broken module boundaries (verified by Architect)
4. Structured logging preserved for any modified code paths (verified by Ops Specialist)

### Communication expectations
- When you discover something that affects another teammate's domain, message them immediately — don't wait
- The Security Sentinel reviews ALL changes before tasks are marked complete
- The Test Engineer is notified of every code change so they can write/update tests
- If two teammates need to modify the same file, coordinate through the team lead

### Task granularity
- Aim for 5-6 tasks per teammate
- Each task should have a clear, verifiable deliverable
- Tasks can have dependencies (e.g., "Test the extracted search handler" depends on "Extract search callbacks from bot.py")
- Use the shared task list to track: pending → in_progress → completed

### Conflict resolution
- If teammates disagree on an approach, present both options to the team lead with trade-offs
- File ownership trumps — the owner of a file makes final decisions about its implementation
- Security concerns raised by the Security Sentinel take priority over feature velocity
