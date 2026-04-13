# Patchy Bot Runtime Notes

Apply the repo-root project rules in [`../CLAUDE.md`](/home/karson/Patchy_Bot/CLAUDE.md) first. This file adds `telegram-qbt/` runtime context. See the [`patchy-bot` skill](/home/karson/Patchy_Bot/skills/patchy-bot/reference.md) for the full architecture map.

## Project Overview

**Patchy Bot** — Telegram bot managing qBittorrent downloads and Plex media library organization.

- **Stack:** Python 3.12+, python-telegram-bot (polling mode), SQLite WAL, asyncio
- **Entry:** `patchy_bot/__main__.py` → `bot.py` (~4,752 lines)
- **Service:** `telegram-qbt-bot.service` (systemd, `python -m patchy_bot`)
- **Shim:** `qbt_telegram_bot.py` is a backward-compat import shim — do not edit for runtime changes

## Architecture

- **Handlers:** `handlers/` — commands, search, schedule, download, remove, chat
- **UI:** `ui/` — flow state, keyboards, rendering, text templates
- **Clients:** `clients/` — qBittorrent (thread-safe), Plex XML, TVMaze/TMDB, LLM
- **Routing:** `CallbackDispatcher` in `dispatch.py` — 2 exact + 12 prefix registrations
- **State:** `HandlerContext` dataclass in `types.py` — injected into all handlers
- **Persistence:** `store.py` — 14 tables, 56+ CRUD methods, WAL mode, busy_timeout=5000
- **18 slash commands**, 760 tests across 23 test files

## Coding Conventions

### Telegram Messages
- **HTML parse mode** for all messages — never switch to Markdown
- **Escape dynamic values** with `_h(text)` from `utils.py` (wraps `html.escape`)
- **Callback data format:** colon-delimited `prefix:param1:param2` (e.g., `sch:track:12345`)
- **Selected items:** `✅` prefix; unselected items: plain text (never use ⬜)
- **Navigation:** Use "↩️ Back" or "🏠 Home" — never "Cancel"
- **Inline buttons** for all navigation — never require text input when buttons work

### Code Patterns
- `Config.from_env()` — all settings from `.env`
- `build_requests_session()` — use for all HTTP clients (retry/backoff built in)
- `human_size()` — format byte counts
- `now_ts()` — current Unix timestamp
- `episode_code(season, episode)` — format as `S01E01`
- `quality_tier(name)` — torrent quality scoring
- `user_flow` state machine via `ui/flow.py` — `set_flow()`, `get_flow()`, `clear_flow()`
- Type hints required on all new function signatures
- Scoring functions should penalize (score -= N), not hard-reject (return -9999)
- In-memory caching for hot polling loops; DB as restart-safe fallback

### Parity Rule
Any change to Movie Search must also be applied to TV Search and vice versa. Check both paths after modifying either.

### Download Paths
If a download/progress change touches both the immediate path and the deferred-hash pending path, update both paths. The pending path is a separate async chain in `handlers/download.py`.

### EMA Variables
When using multiple related EMA smoothing variables (smooth_progress_pct, smooth_dls, smooth_uls), initialize and check all of them together.

## Safety Rules

### Path Safety
- All file operations must pass traversal guard, symlink rejection, depth validation
- Use `PurePosixPath.is_relative_to()` for containment checks — never `str.startswith()`
- Validate file extensions before moving into Plex library dirs (VIDEO_EXTS for movies, KEEP_EXTS for TV)
- Never use `os.path.exists()` before `shutil.move()` — TOCTOU race; use try/except

### SQLite
- File permissions: owner-only `0o600`
- WAL mode with `busy_timeout=5000` — don't hold transactions open unnecessarily

### Thread Safety
- `QBClient` uses `threading.Lock()` — preserve this; keep lock scope minimal
- Never hold lock across awaits in async code

### VPN & Network
- Never set `current_network_interface` in qBT preferences to the VPN interface
- OS-level Surfshark kill-switch handles VPN routing (ip rule 31565 → table 300000)
- Interface binding breaks libtorrent DNS (can't reach 127.0.0.1:53)

### Secrets
- Never expose secrets, `.env` contents, or API keys
- Never commit `.env` files

## Service Operations

```bash
# Restart (required after any patchy_bot/ code change)
sudo systemctl restart telegram-qbt-bot.service

# Logs
journalctl -u telegram-qbt-bot.service -f

# Status
systemctl status telegram-qbt-bot.service
```

- **DB file:** `telegram-qbt/patchy_bot.db`
- **Backup:** Daily at 03:00 if `BACKUP_DIR` configured
- **Dependencies:** `network-online.target`, `qbittorrent.service`
- **Security hardening:** `ProtectSystem=strict`, `NoNewPrivileges=true`, `PrivateTmp=true`
- **ReadWritePaths:** `telegram-qbt/`, `~/Downloads`, `~/MySSD/Plex Videos`, `~/MySSD/Plex Movies`

### Background Runners
| Runner | Interval | Purpose |
|--------|----------|---------|
| schedule-runner | 60s | Check due TV episodes + movie releases, trigger auto-downloads |
| remove-runner | 60s | Process pending media removal jobs |
| completion-poller | 60s | Detect completed torrents → organize → notify |
| command center refresh | 3s | Per-user async loop updating command center message |
| qbt-health-check | 300s | Periodic qBT connectivity check |

## Hooks

| Script | Event | Purpose |
|--------|-------|---------|
| `pre-bash-guard.sh` | PreToolUse (Bash) | Blocks destructive deletes and secret file reads |
| `post-edit-format.sh` | PostToolUse (Write\|Edit) | Auto-runs ruff format on edited Python files |
| `memory-recorder.sh` | PostToolUse (Write\|Edit\|Bash) | Logs write/edit/bash events to `.event-buffer.jsonl` |
| `session-finalizer.sh` | Stop | Records session end from event buffer, rotates archives |
| `auto-approve.sh` | PermissionRequest | Auto-allows all permission prompts |
| `session-start-context.sh` | SessionStart | Injects task-master list output at session start |
| `stop-audit-trigger.sh` | Stop | Detects change size, recommends post-changes-audit mode |

All hooks use `type: "command"` only. Never use `type: "prompt"` — prompt hooks cause mid-process halts or infinite loops.

## Post-Changes Audit

Auto-triggered by the Stop hook after code changes. Three modes based on change size:

| Mode | Trigger | What It Does |
|------|---------|--------------|
| quick | <5 lines changed | Inline correctness scan, lint check, domain rule check |
| standard | 5–49 lines | audit-correctness-agent + security-agent |
| deep | 50+ lines | 4 subagents + scope-guard + diff-review |

Invoke manually: `/post-changes-audit [quick|standard|deep]`

## Subagent Routing

25 agents in `.claude/agents/`:

| Agent | Domain |
|-------|--------|
| `database-agent` | SQLite store, table schemas, migrations, CRUD |
| `schedule-agent` | TV/movie tracking, TVMaze/TMDB, schedule runner |
| `search-download-agent` | Torrent search, add flow, qBT, progress tracking |
| `remove-agent` | Media removal, Plex cleanup, path safety |
| `plex-agent` | Plex integration, library scans, organizer |
| `ui-agent` | Telegram keyboards, messages, flow state |
| `test-agent` | Tests, pytest, coverage, mocking |
| `security-agent` | Auth, rate limiting, input validation, path safety |
| `lint-type-agent` | Ruff, mypy, static quality |
| `config-infra-agent` | Config, env vars, systemd, deployment |
| `performance-optimization-agent` | SQLite connections, caching, profiling |
| `movie-tracking-agent` | TMDB movies, `msch:` callbacks, movie-track table |
| `monitoring-metrics-agent` | Health, alerting, log analysis |
| `coverage-analysis-agent` | Test coverage reports, gap analysis |
| `audit-correctness-agent` | Post-changes correctness, completeness, efficiency review |
| `audit-performance-agent` | Post-changes performance, resource use, verbosity review |
| `dependency-audit-agent` | Dependency vulnerabilities, CVE scanning |
| `secret-scanner-agent` | Secrets scanning, credential detection |
| `static-analysis-agent` | AST scanning, Bandit, Semgrep |
| `security-scan-orchestrator` | Full security scan pipeline |
| `supply-chain-scan-agent` | OS-level CVEs, Trivy, SBOM |
| `release-manager-agent` | Versioning, changelogs, deployment |
| `taskmaster-sync-agent` | Task Master reconciliation |
| `media-library-abstraction-agent` | Jellyfin/Emby abstraction planning |
| `torrent-client-abstraction-agent` | Transmission/rTorrent abstraction planning |

**Model routing:** Audit/review agents use Opus. Implementation agents use Sonnet (project default). Do not hardcode `model` in Agent tool calls — let `settings.json` control it unless the agent definition specifies otherwise.

## Subagent-Driven Development

ALL Patchy Bot work must use subagent-driven development:
1. Dispatch each task to the matching domain subagent
2. Review subagent output before applying
3. Never implement domain logic inline — always delegate

## Task Master

Run `task-master list` to see current project tasks. Auto-injected at session start by the SessionStart hook. Use `/tm:*` skills for task management.

## Settings

- **Extended thinking:** Enabled (`alwaysThinkingEnabled: true`)
- **Model:** Sonnet (project default); Opus for audit agents
- **Plugins:** pyright-lsp, context7

## Verification

- Default test command: `.venv/bin/python -m pytest -q`
- Ruff + mypy config in [`pyproject.toml`](/home/karson/Patchy_Bot/telegram-qbt/pyproject.toml)
- Use targeted tests first when debugging, then run the broader suite before handoff
- **Fix pre-existing issues, never ignore them.** When fresh pyright/pytest runs surface diagnostics — even ones unrelated to the current task — triage and fix them in the same session. Tractable ones (unused imports, deprecated APIs, missing None-checks, stale event strings) must be patched directly. Structural test-fixture type gaps get minimal `cast()` / `# type: ignore[arg-type]` rather than rewrites. Never report "done" with known errors still present. Dispatch `lint-type-agent` for non-trivial backlogs.
