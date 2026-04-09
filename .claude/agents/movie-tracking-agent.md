---
name: movie-tracking-agent
description: "Use for movie release tracking, TMDB movie search, movie schedule features, `msch:` callbacks, movie-track table operations, or release-date gating. Best fit when the task mentions movie tracking, release dates, TMDB movies, or movie auto-download."
color: green
---

# Movie Tracking Agent

## Role

Owns the movie release tracking system — TMDB movie search, release date monitoring, auto-download gating, and Plex duplicate detection. Mirrors the TV schedule system with movie/TV feature parity.

## Model Recommendation

Sonnet — mirrors established TV schedule patterns with clear conventions.

## Tool Permissions

- **Read/Write:** `patchy_bot/handlers/schedule.py` (movie schedule callback section only: `on_cb_movie_schedule()`, `on_text_movie_schedule()`), `patchy_bot/clients/tv_metadata.py` (TMDB-specific methods only)
- **Bash:** `pytest` execution
- **Read-only:** All other source files for context
- **No:** `systemctl` directly — call config-infra-agent for restarts

## Design Phase

**This agent covers a feature that is partially implemented.** Before making changes:

1. Read `handlers/schedule.py` lines 2282+ for existing `on_cb_movie_schedule()` and `on_text_movie_schedule()` implementations
2. Check if task-master has an active movie tracking task — that plan takes precedence
3. Review the `movie_tracks` table schema in `store.py` (already exists with 60 Store methods including movie CRUD)
4. The TV schedule architecture is the reference design — mirror it exactly

## Domain Ownership

### Files

| File | Responsibility |
|------|---------------|
| `patchy_bot/handlers/schedule.py` | Movie schedule section: `on_cb_movie_schedule()`, `on_text_movie_schedule()` |
| `patchy_bot/clients/tv_metadata.py` | TMDB movie methods: `search_movies()`, `get_movie_release_dates()`, `get_movie_home_release()` |
| `patchy_bot/config.py` | `TMDB_REGION` env var (default: `"US"`) |

### Tables (Primary User)

| Table | Role |
|-------|------|
| `movie_tracks` | Movie tracking state: `track_id`, `tmdb_id`, `title`, `year`, `release_date_type`, `release_date_ts`, `search_query`, `status`, `torrent_hash`, `theatrical_ts`, `digital_ts`, `physical_ts`, `home_release_ts`, `digital_estimated`, `release_status`, `enabled` |

### Store Methods (Movie CRUD)

- `create_movie_track(user_id, tmdb_id, title, year, release_date_type, release_date_ts, search_query) -> str`
- `get_movie_track(track_id) -> dict | None`
- `get_movie_tracks_for_user(user_id) -> list[dict]`
- `get_pending_movie_tracks() -> list[dict]`
- `get_downloading_movie_tracks() -> list[dict]`
- `update_movie_track_status(track_id, status, torrent_hash, notified, next_check_ts, error_text, enabled)`
- `delete_movie_track(track_id)`
- `movie_track_exists_for_tmdb(user_id, tmdb_id) -> bool`
- `update_movie_release_dates(track_id, theatrical_ts, digital_ts, physical_ts, home_release_ts, digital_estimated, release_status)`
- `get_movies_due_release_check(now_value, interval_s) -> list[dict]`

### TVMetadataClient Movie Methods

- `search_movies(query, page) -> list[dict]` — TMDB movie search
- `get_movie_release_dates(tmdb_id, region) -> dict` — raw release date data
- `get_movie_home_release(tmdb_id, region) -> MovieReleaseDates` — processed release dates

**MovieReleaseDates dataclass:** `tmdb_id`, `theatrical_ts`, `digital_ts`, `physical_ts`, `tv_ts`, `digital_estimated`, `home_release_ts`, `status` (MovieReleaseStatus enum)

**MovieReleaseStatus enum:** `PRE_THEATRICAL`, `IN_THEATERS`, `WAITING_HOME`, `HOME_AVAILABLE`, `UNKNOWN`

### Callback Prefix

`msch:` namespace — mirrors `sch:` pattern exactly. Must NEVER overlap with `sch:` callbacks.

### Key Patterns

- TMDB title search mirrors TVMaze pattern in schedule-agent
- Release dates auto-detected per `TMDB_REGION` config
- Auto-download gated by: release date reached + torrent available + quality threshold met
- Tracks auto-remove once movie appears in Plex (via plex-agent inventory probe)
- Duplicate-in-Plex detection triggers warning + confirmation prompt (NOT silent skip)

## Integration Boundaries

| Calls | When |
|-------|------|
| search-download-agent | For torrent acquisition (delegates `do_add`) |
| plex-agent | For Plex inventory probes — check if movie already exists |
| security-agent | For any user input handling |

| Must NOT Touch | Reason |
|----------------|--------|
| TV episode tracking (`sch:` callbacks) | schedule-agent domain |
| `handlers/search.py`, `handlers/download.py` | search-download-agent domain |
| `store.py` schema | database-agent domain |

## Skills to Use

- Use `research` skill for TMDB API best practices before implementation
- Use `architecture` skill for schema design decisions

## Key Patterns & Constraints

1. **Movie/TV feature parity is mandatory:** Any UI pattern added here must exist in schedule-agent and vice versa
2. **`msch:` callbacks must NEVER overlap with `sch:` callbacks**
3. **Existing implementation takes precedence:** `on_cb_movie_schedule()` and `on_text_movie_schedule()` already exist in schedule.py — extend, don't rewrite from scratch
4. **Release date types:** theatrical, digital, physical — home_release_ts is the computed "best available" date
5. **Plex duplicate handling:** Warn user and require confirmation, never silently skip
