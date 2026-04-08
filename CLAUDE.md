# Patchy Bot — Claude Code Project Memory

## Git Policy

Do not run git write commands in `/home/karson/Patchy_Bot` unless the user explicitly asks in the current message. Read-only git commands are fine. File edits are fine.

## Source Of Truth

- Prefer code over docs when they disagree.
- Most runtime code lives in [`telegram-qbt/`](/home/karson/Patchy_Bot/telegram-qbt).
- Repo-root `.claude/`, `.claude-plugin/`, and `skills/` define Claude Code behavior for this project.

## Runtime Map

- Entry point: [`telegram-qbt/patchy_bot/__main__.py`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/__main__.py)
- Config and startup: [`telegram-qbt/patchy_bot/config.py`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/config.py), [`telegram-qbt/telegram-qbt-bot.service`](/home/karson/Patchy_Bot/telegram-qbt/telegram-qbt-bot.service)
- Persistence: [`telegram-qbt/patchy_bot/store.py`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/store.py)
- Domain handlers: [`telegram-qbt/patchy_bot/handlers/`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/handlers)
- Telegram UI helpers: [`telegram-qbt/patchy_bot/ui/`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/ui)
- Clients: [`telegram-qbt/patchy_bot/clients/`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/clients)
- Back-compat test shim: [`telegram-qbt/qbt_telegram_bot.py`](/home/karson/Patchy_Bot/telegram-qbt/qbt_telegram_bot.py)

## Skill Policy

Use project-local skills selectively. Do not load the giant `skills/global/` library by default; treat it as reference-only unless the task clearly needs something the project-local skills do not cover.

### Default workflow guards

Use these automatically when beneficial:

- `scope-guard` for multi-step work, refactors, migrations, and before saying work is done.
- `reuse-check` before creating helpers, wrappers, abstractions, utilities, or new dependencies.
- `assumptions-audit` during planning, unfamiliar code, architecture choices, and external-system work.
- `diff-review` before handoff, commit, PR, or any “done” claim.

### Conditional project skills

Use these when the task matches:

- `telegram-ux-architect` before major Telegram flow design or structural UX changes.
- `telegram-chat-polisher` when editing user-facing message text, button labels, keyboard layout, or chat navigation wording.
- `env-check` for env vars, startup config, deployment config, service assumptions, or integration enablement.
- `test-bot` after Python or test changes when a full verification pass is warranted.
- `restart` after runtime/config/service changes when applying them locally is appropriate.
- `check-logs` for runtime diagnosis, restart failures, crashes, warnings, or “what happened?” questions.
- `db-inspect` for live SQLite state, schema reality, or persistence debugging.
- `debug-schedule` for schedule runner, due-track, metadata, or auto-download debugging.
- `sync-parity` after search/add-flow/UI changes that should stay aligned across movie and TV paths.

### Manual only

- `gh-issues-auto-fixer` is manual-only. Never invoke it automatically.

## Agent Routing

Use project agents when the task naturally fits their domain. Do not force subagents for trivial edits.

- `config-infra-agent`: config, `.env.example`, startup, service, logs, deployment.
- `database-agent`: `store.py`, schema, migrations, live DB inspection.
- `schedule-agent`: `handlers/schedule.py`, TV tracking, runner status, metadata flow.
- `search-download-agent`: search, add/download flow, qBittorrent, progress/completion tracking.
- `plex-agent`: Plex integration and organizer behavior.
- `remove-agent`: deletion flow, safety checks, Plex cleanup after delete.
- `ui-agent`: Telegram message rendering, keyboards, callbacks, navigation.
- `test-agent`: tests, pytest failures, coverage, test utilities.
- `security-agent`: auth, rate limits, path safety, validation, security review.
- `taskmaster-sync-agent`: only when the user wants Task Master kept in sync.
- `movie-tracking-agent`: movie release tracking, TMDB movie search, `msch:` callbacks, movie schedule features.
- `monitoring-metrics-agent`: health checks, alerting, log analysis, service monitoring, error rate tracking.
- `torrent-client-abstraction-agent`: Transmission/rTorrent support, torrent client interface design, multi-client architecture.
- `media-library-abstraction-agent`: Jellyfin/Emby support, media library interface design, multi-library architecture.
- `performance-optimization-agent`: SQLite optimization, query analysis, runner profiling, caching strategy.
- `release-manager-agent`: versioning, releases, changelogs, rollback procedures, deployment coordination.

## Known Pitfalls

- Always HTML-escape dynamic values (torrent names, paths, API responses) with `_h()` before inserting into Telegram messages with `parse_mode=HTML`. Raw `<`/`>` in release names break rendering.
- When adding parameters to a progress tracker code path, always update BOTH the immediate path and the pending (deferred-hash) path in `handlers/download.py`. The pending path is a separate async chain that is easy to forget.

## Working Rules

- Keep instructions concise and operational.
- Do not promote every skill into always-on context.
- Prefer the project-local skill when it overlaps a generic/global one.
- For Python changes in `telegram-qbt/`, run `pytest -q` from that project when tests cover the touched area.
- Keep `qbt_telegram_bot.py` import compatibility intact unless the user explicitly wants it changed.

---

## Memory System

### Session Start Protocol (MANDATORY)
At the start of every Claude Code session on Patchy Bot, before doing any work:
1. Read `.claude/memory/MEMORY.md` — loads current project context and quick reference
2. Read the last 2 entries in `.claude/memory/sessions.md` — loads recent handoff state

### During Work — Write to Memory Files
Write to the appropriate memory file whenever one of these events occurs:

| Event | File to update |
|-------|---------------|
| Architectural or design decision made | `.claude/memory/decisions.md` |
| Bug found and fixed | `.claude/memory/bugs.md` |
| Non-obvious pattern, convention, or gotcha discovered | `.claude/memory/patterns.md` |
| Wrapping up / about to stop work | `.claude/memory/sessions.md` |

After writing to any category file, also update the matching one-line summary in `.claude/memory/MEMORY.md`.

### Entry Format (all files)
```
## [YYYY-MM-DD HH:MM] Brief descriptive title
- **Context:** What was happening / what task was in progress
- **Finding/Decision:** What was decided, fixed, or discovered
- **Rationale:** Why this choice (for decisions only)
- **Files affected:** List of files changed
- **Impact:** What this affects going forward
```

### What the Hooks Do Automatically
- **PostToolUse** (`memory-recorder.sh`): Appends a JSON line to `.event-buffer.jsonl` after every tool use — full audit trail, no action needed
- **Stop** (`session-finalizer.sh`): Auto-writes a session-end entry to `sessions.md` from the event buffer if you didn't write one manually; rotates the buffer

### Memory File Locations
All memory files live in: `~/Patchy_Bot/.claude/memory/`
- `MEMORY.md` — master index (read first every session)
- `decisions.md` — design decisions + rationale
- `bugs.md` — bugs found + fixes
- `patterns.md` — conventions + gotchas
- `sessions.md` — session handoffs
