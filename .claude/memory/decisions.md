# Patchy Bot — Decisions Log (ARCHIVED 2026-04-08)

> **FROZEN ARCHIVE — do not append.** New decisions go in the live auto-memory
> store at `~/.claude/projects/-home-karson-Patchy-Bot/memory/` as `project_*`
> entries. See this directory's `MEMORY.md` for the archive rationale.

## Entry Format
```
## [YYYY-MM-DD HH:MM] Brief descriptive title
- **Context:** What was happening / what task was in progress
- **Decision:** What was decided
- **Rationale:** Why this choice over alternatives
- **Files affected:** List any files changed
- **Impact:** What this affects going forward
```

---

## [2026-04-07] CAM/TS/SCR sources penalized instead of hard-rejected
- **Context:** Movie schedule tracks for movies still in theaters needed available sources
- **Decision:** Changed `parsed.trash` from hard rejection (-9999) to heavy penalty (score -= 200)
- **Rationale:** Movie scheduling feature needs trash sources as last-resort fallback for in-theater movies
- **Files affected:** `patchy_bot/quality.py`, `patchy_bot/store.py`
- **Impact:** Trash sources will only be selected if no better source exists; `trash` field persisted in scored results

## [2026-04-07] Malware/fake-content scanning gate added
- **Context:** No pre-download content validation existed — users could add obviously fake torrents
- **Decision:** New `patchy_bot/malware.py` module with `scan_search_result()` and `scan_download()` heuristics
- **Rationale:** Search results silently filtered; downloads blocked with user-facing error; blocks logged to SQLite
- **Files affected:** `patchy_bot/malware.py` (new), `patchy_bot/handlers/search.py`, `patchy_bot/handlers/download.py`, `patchy_bot/store.py`
- **Impact:** All search results and downloads now pass malware heuristics before proceeding

## [2026-04-07] Season navigation changed from text input to arrow buttons
- **Context:** Schedule preview required typing a season number — fragile, left garbage messages, broke inline flow
- **Decision:** Replaced with left/right arrow buttons (`sch:nav:<season>`) and removed `await_season_pick` stage
- **Rationale:** Text input creates validation burden and breaks the callback-driven UX pattern used everywhere else
- **Files affected:** `patchy_bot/bot.py`, `patchy_bot/handlers/schedule.py`
- **Impact:** Season navigation is now fully inline-button driven; no text input stages remain in schedule flow

## [2026-04-07] No git in Patchy_Bot — direct file edits only
- **Context:** User removed all git infrastructure on 2026-04-03 after a git reset incident caused production downtime
- **Decision:** No git commands, commits, branches, or version control in ~/Patchy_Bot
- **Rationale:** Nested repo / submodule / gitlink complexity caused a production incident with lost uncommitted work
- **Files affected:** All — workflow change, not code change
- **Impact:** Edit files directly and restart service. No staging, committing, or branching.

## [2026-04-07] qBT interface binding removed — OS kill-switch handles VPN
- **Context:** Binding qBittorrent's `current_network_interface` to `surfshark_wg` broke libtorrent DNS
- **Decision:** Removed interface binding; rely on OS-level Surfshark kill-switch (ip rule 31565 → table 300000)
- **Rationale:** Sockets bound to VPN IP can't reach DNS stub at 127.0.0.1:53; OS routing already forces VPN
- **Files affected:** `patchy_bot/__main__.py` (startup prefs), `patchy_bot/bot.py` (health check auto-clear)
- **Impact:** Never re-introduce interface binding. Health check auto-clears stale bindings if found.

## [2026-04-06] Plex autoEmptyTrash=1 + purge_deleted_path in download handler
- **Context:** Replaced media files left ghost entries in Plex (red unavailable icons) because autoEmptyTrash was disabled
- **Decision:** Enabled autoEmptyTrash in Plex Preferences.xml; changed download handler from `refresh_for_path()` to `purge_deleted_path()`
- **Rationale:** `purge_deleted_path()` triggers scan + wait + emptyTrash — belt-and-suspenders cleanup
- **Files affected:** Plex Preferences.xml, `patchy_bot/handlers/download.py`
- **Impact:** Ghost entries from replaced files are always cleaned up automatically

## [2026-04-04] Package restructure — monolith to patchy_bot/ package
- **Context:** Bot was a single large file; needed modularization for maintainability
- **Decision:** Split into `patchy_bot/` package with domain modules; `qbt_telegram_bot.py` kept as compat shim
- **Rationale:** Enables domain-specific editing, cleaner imports, and better test isolation
- **Files affected:** All `patchy_bot/*.py` modules (new), `qbt_telegram_bot.py` (shim)
- **Impact:** Service now runs `python -m patchy_bot`. All runtime edits go to package modules.
