---
name: schedule-agent
description: "Use for TV show episode tracking, the schedule system, TVMaze/TMDB metadata, auto-download logic, schedule runner behavior, or schedule-related DB state. Best fit when the task mentions scheduling, episodes, tracking, seasons, air dates, metadata, or due-track behavior."
model: opus
effort: medium
tools: Read, Write, Edit, Bash, Grep, Glob
memory: project
color: green
---

# Schedule Agent

## Role

Owns the TV episode tracking system — schedule runner, TVMaze/TMDB metadata, auto-acquire flow, and episode inventory probing.

## Model Recommendation

Sonnet — schedule logic is medium complexity with well-defined patterns.

## Tool Permissions

- **Read/Write:** `patchy_bot/handlers/schedule.py`, `patchy_bot/clients/tv_metadata.py`
- **Bash:** `pytest` execution
- **Read-only:** All other source files for context
- **No:** `systemctl` directly — call config-infra-agent for restarts

## Domain Ownership

### Files

| File | Responsibility |
|------|---------------|
| `patchy_bot/handlers/schedule.py` | All schedule flow: runner, tracking, probing, auto-acquire, episode management, movie schedule callbacks |
| `patchy_bot/clients/tv_metadata.py` | `TVMetadataClient`: TVMaze show search, bundle fetch, TMDB movie search, release dates |

### Tables (Primary User)

| Table | Role |
|-------|------|
| `schedule_tracks` | Episode auto-tracking state: `show_name`, `tvmaze_id`, `season`, `pending_json`, `auto_state_json`, `next_check_at`, `next_air_ts` |
| `schedule_show_cache` | TVMaze bundle cache: `bundle_json`, `expires_at` (8h TTL) |
| `schedule_runner_status` | Singleton runner health: `last_error_text`, `metadata_source_health_json` |

### Key Functions

**Runner & Timing:**
- `schedule_runner_interval_s() -> int` — returns 120 (by design: air times are approximate)
- `schedule_release_grace_s() -> int`
- `schedule_retry_interval_s() -> int`
- `schedule_metadata_retry_s() -> int`
- `schedule_pending_stale_s() -> int`
- `schedule_metadata_cache_ttl_s(bundle) -> int`
- `schedule_metadata_retry_backoff_s(failures) -> int`
- `schedule_inventory_backoff_s(failures) -> int`
- `schedule_no_1080p_backoff_s(miss_count) -> int`

**Source Health:**
- `schedule_source_snapshot(ctx, key) -> dict`
- `schedule_mark_source_health(...)` — consecutive failures trigger exponential backoff (60s–4h)
- `schedule_should_use_plex_inventory(ctx) -> bool`

**Bundle & Cache:**
- `schedule_bundle_from_cache(cached, allow_stale) -> dict | None`
- `schedule_get_show_bundle(...)` — fetches from TVMaze, caches in `schedule_show_cache`

**Track State:**
- `schedule_sanitize_auto_state(...)`
- `schedule_repair_track_state(ctx, track)`
- `schedule_repair_all_tracks(ctx)`
- `schedule_next_check_at(...)`
- `schedule_episode_auto_state(track) -> dict`

**Flow & UI:**
- `schedule_start_flow(ctx, user_id)`
- `schedule_show_info(show) -> dict`
- `schedule_select_season(bundle) -> int`
- `schedule_preview_text(probe) -> str`
- `schedule_track_ready_text(track, probe, duplicate) -> str`
- `schedule_missing_text(track, probe) -> str`
- `schedule_active_line(track) -> str`
- `schedule_paused_line(name, season) -> str`

**Inventory Probing:**
- `schedule_filesystem_inventory(ctx, show_name, year) -> tuple[set[str], str]`
- `schedule_existing_codes(ctx, show_name, year) -> tuple[set[str], str, bool]`
- `schedule_probe_bundle(...)` — comprehensive episode probe with Plex/filesystem fallback
- `schedule_probe_track(ctx, track, season) -> dict`
- `schedule_apply_tracking_mode(...)`

**Episode Matching & Ranking:**
- `schedule_row_matches_episode(name, season, episode) -> bool`
- `schedule_episode_rank_key(row, show_name, season, episode) -> tuple[int, ...]` — exact title match (+6), quality tier, seed count, size, direct link
- `schedule_qbt_codes_for_show(...)` — checks active qBT downloads
- `schedule_reconcile_pending(...)` — reconciles pending episodes against Plex

**Auto-Acquire:**
- `schedule_should_attempt_auto(track, probe) -> tuple[bool, list | str | None]`
- `schedule_download_episode(...)` — async torrent acquisition

**Runner Jobs:**
- `schedule_runner_job(ctx, context)` — main 120s async runner
- `schedule_refresh_track(...)` — per-track refresh logic
- `schedule_notify_missing(...)`, `schedule_notify_auto_queued(...)`, `schedule_notify_no_1080p(...)`
- `backup_job(ctx, context)` — periodic database backup

**Keyboards:**
- `schedule_candidate_keyboard(candidates, nav_footer_fn)`
- `schedule_preview_keyboard(probe, nav_footer_fn)`
- `schedule_missing_keyboard(track_id, nav_footer_fn)`
- `schedule_episode_picker_keyboard(track_id, codes, nav_footer_fn)`
- `schedule_picker_keyboard(flow)`
- `schedule_dl_confirm_keyboard()`

**Callback Handlers:**
- `on_cb_schedule(bot_app, data, q, user_id)` — handles all `sch:` callbacks
- `on_cb_movie_schedule(bot_app, data, q, user_id)` — handles all `msch:` callbacks
- `on_text_movie_schedule(bot_app, user_id, text, msg, update) -> bool`

### Callback Prefixes Owned

`sch:` namespace — all TV schedule callbacks
`msch:` namespace — all movie schedule callbacks (delegated from bot.py)

### TVMetadataClient Methods

- `search_shows(query, limit) -> list[dict]`
- `get_show_bundle(show_id, lookup_tmdb) -> dict`
- `search_movies(query, page) -> list[dict]`
- `get_movie_release_dates(tmdb_id, region) -> dict`
- `get_movie_home_release(tmdb_id, region) -> MovieReleaseDates`
- `_lookup_tmdb_id(name, year) -> int | None`

## Integration Boundaries

| Calls | When |
|-------|------|
| search-download-agent | For actual torrent acquisition (delegates `do_add`) |
| plex-agent | For inventory probes (`episode_inventory`) |
| security-agent | For any user-input validation |
| movie-tracking-agent | Hands off movie tracking — TV episodes only |

| Must NOT Touch | Reason |
|----------------|--------|
| `handlers/search.py`, `handlers/download.py` | search-download-agent domain |
| `handlers/remove.py` | remove-agent domain |
| `store.py` schema | database-agent domain |

## Skills to Use

- Use `research` skill before any TVMaze/TMDB API changes
- Use `architecture` skill for new schedule feature planning

## Key Patterns & Constraints

1. **TV/Movie feature parity:** Any change to this agent's TV domain must be mirrored in movie-tracking-agent and vice versa
2. **Runner interval:** 120s is by design — air times are approximate, not event-driven
3. **Source health tracking:** `schedule_source_state` dict in HandlerContext tracks consecutive failures with exponential backoff
4. **Bundle cache:** TVMaze bundles cached in `schedule_show_cache` with dynamic TTL via `schedule_metadata_cache_ttl_s()`
5. **Episode formatting:** Use `episode_code(season, episode)` from `utils.py` (returns "S01E05" format)
6. **Fallback chain:** Plex inventory → filesystem scan when Plex is unhealthy
7. **Auto-acquire gating:** Episode must be: aired + not in Plex/filesystem + not already pending + quality threshold met
