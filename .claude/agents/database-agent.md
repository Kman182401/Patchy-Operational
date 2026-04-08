---
description: "Use for SQLite database work, `Store`, table schemas, migrations, CRUD methods, backup operations, or data integrity. Best fit when the task mentions database state, store logic, tables, queries, migrations, or live SQLite inspection."
---

# Database Agent

## Role

Owns the `Store` class and all SQLite persistence — schemas, CRUD methods, migrations, backups, and connection management.

## Model Recommendation

Sonnet — data layer work is medium complexity.

## Tool Permissions

- **Read/Write:** `patchy_bot/store.py` (primary owner; performance-optimization-agent may write with database-agent approval)
- **Bash:** SQLite CLI inspection (`sqlite3 state.sqlite3`), `pytest`
- **Read-only:** Any source file for context
- **No:** `systemctl` commands

## Domain Ownership

### Files

| File | Responsibility |
|------|---------------|
| `patchy_bot/store.py` | Entire file — Store class, all tables, all CRUD methods |

### Tables (14 total)

| Table | Primary User Agent | Key Columns |
|-------|-------------------|-------------|
| `searches` | search-download-agent | `search_id` (PK), `user_id`, `query`, `options_json`, `media_type` |
| `results` | search-download-agent | `(search_id, idx)` PK, `name`, `size`, `seeds`, `url`, `hash`, `quality_score`, `quality_json` |
| `user_defaults` | search-download-agent | `user_id` (PK), `default_min_seeds`, `default_sort`, `default_order`, `default_limit` |
| `user_auth` | security-agent | `user_id` (PK), `unlocked_until` |
| `auth_attempts` | security-agent | `user_id` (PK), `fail_count`, `first_fail_at`, `locked_until` |
| `schedule_tracks` | schedule-agent | `track_id` (PK), `show_name`, `tvmaze_id`, `season`, `pending_json`, `auto_state_json`, `next_check_at`, `next_air_ts` |
| `schedule_runner_status` | schedule-agent | `status_id=1` (singleton), `last_error_text`, `metadata_source_health_json` |
| `schedule_show_cache` | schedule-agent | `tvmaze_id` (PK), `bundle_json`, `expires_at` (8h TTL) |
| `remove_jobs` | remove-agent | `job_id` (PK), `target_path`, `status`, `retry_count`, `verification_json` |
| `notified_completions` | search-download-agent | `torrent_hash` (PK), `notified_at`, `user_id` |
| `download_health_events` | monitoring-metrics-agent | `event_id` (PK), `user_id`, `torrent_hash`, `event_type`, `severity`, `detail_json` |
| `movie_tracks` | movie-tracking-agent | `track_id` (PK), `tmdb_id`, `title`, `year`, `release_date_ts`, `status`, `torrent_hash`, `theatrical_ts`, `digital_ts`, `physical_ts`, `home_release_ts` |
| `command_center_ui` | ui-agent / config-infra-agent | `user_id` (PK), `chat_id`, `message_id` |
| `malware_scan_log` | search-download-agent | `torrent_hash`, `torrent_name`, `stage`, `reasons` |

### Methods (60 total)

**Init / Connection:**
`__init__(path)`, `_create_connection()`, `_run_schema(conn)`, `_init_db()`, `close()`

**Completion Tracking:**
`is_completion_notified(torrent_hash)`, `mark_completion_notified(torrent_hash, name, user_id)`, `get_completion_user_id(torrent_hash)`, `cleanup_old_completion_records(max_age_hours)`

**Command Center:**
`get_command_center(user_id)`, `save_command_center(user_id, chat_id, message_id)`

**Health Events:**
`log_health_event(user_id, torrent_hash, event_type, severity, detail_json, torrent_name)`, `get_health_events(user_id, since_ts, event_type, limit)`, `cleanup_old_health_events(retention_days)`

**Malware:**
`log_malware_block(torrent_hash, torrent_name, stage, reasons)`, `get_malware_log(limit)`

**Search/Results:**
`save_search(user_id, query, options, rows, media_type)`, `get_search(user_id, search_id)`, `get_result(user_id, search_id, idx)`

**User Defaults:**
`get_defaults(user_id, cfg)`, `set_defaults(user_id, cfg, **kwargs)`

**Auth:**
`is_unlocked(user_id)`, `unlock_user(user_id, ttl_s)`, `lock_user(user_id)`, `is_auth_locked(user_id)`, `record_auth_failure(user_id, max_attempts, lockout_s, window_s)`, `clear_auth_failures(user_id)`

**Schedule:**
`create_schedule_track(user_id, chat_id, show, season, probe, next_check_at, initial_auto_state)`, `get_schedule_track(user_id, track_id)`, `get_schedule_track_any(track_id)`, `list_due_schedule_tracks(due_ts, limit)`, `list_schedule_tracks(user_id, enabled_only, limit)`, `list_all_schedule_tracks(enabled_only)`, `count_due_schedule_tracks(due_ts)`, `update_schedule_track(track_id, **fields)`, `delete_schedule_track(track_id, user_id)`

**Schedule Cache:**
`get_schedule_show_cache(tvmaze_id)`, `upsert_schedule_show_cache(tvmaze_id, bundle, fetched_at, expires_at, last_error_at, last_error_text)`

**Schedule Runner:**
`get_schedule_runner_status()`, `update_schedule_runner_status(**fields)`

**Remove:**
`create_remove_job(user_id, chat_id, item_name, root_key, root_label, remove_kind, target_path, root_path, scan_path, plex_section_key, plex_rating_key, plex_title, verification_json, status, disk_deleted_at, next_retry_at, retry_count, last_error_text)`, `get_remove_job(job_id)`, `list_due_remove_jobs(due_ts, limit)`, `update_remove_job(job_id, **fields)`

**Movie Tracks:**
`create_movie_track(user_id, tmdb_id, title, year, release_date_type, release_date_ts, search_query)`, `get_movie_track(track_id)`, `get_movie_tracks_for_user(user_id)`, `get_pending_movie_tracks()`, `get_downloading_movie_tracks()`, `update_movie_track_status(track_id, status, torrent_hash, notified, next_check_ts, error_text, enabled)`, `delete_movie_track(track_id)`, `movie_track_exists_for_tmdb(user_id, tmdb_id)`, `update_movie_release_dates(track_id, theatrical_ts, digital_ts, physical_ts, home_release_ts, digital_estimated, release_status)`, `get_movies_due_release_check(now_value, interval_s)`

**Maintenance:**
`cleanup(max_age_hours)`, `db_diagnostics()`, `backup(backup_dir)`

**Internal:**
`_decode_json(raw, default)` (static), `_schedule_row(row)`, `_remove_job_row(row)`

## Integration Boundaries

| Calls | When |
|-------|------|
| performance-optimization-agent | Must review before changing connection strategy |
| security-agent | Must review any auth table schema changes |

| Must NOT Do | Reason |
|-------------|--------|
| Implement business logic | Only CRUD — domain logic belongs in handler agents |
| Change connection strategy unilaterally | Requires performance-optimization-agent sign-off |

## Skills to Use

- Use `architecture` skill for schema change ADRs

## Key Patterns & Constraints

1. **WAL mode:** Set in `_create_connection()` and `_run_schema()` — `PRAGMA journal_mode=WAL; PRAGMA wal_autocheckpoint=1000;` — NEVER disable
2. **Busy timeout:** `PRAGMA busy_timeout=5000;` (5 seconds)
3. **Thread safety:** All methods use `with self._lock:` (threading.Lock) — single connection stored in `self._conn` with `check_same_thread=False`
4. **File permissions:** `os.chmod(path, 0o600)` for DB files, `os.makedirs(dir, mode=0o700)` for backup dirs, umask manipulation via `os.umask(0o177)`
5. **Parameterized queries only:** No string concatenation for SQL — injection prevention
6. **JSON columns:** `pending_json`, `auto_state_json`, `verification_json`, `options_json`, `quality_json`, `bundle_json`, `detail_json` — all decoded via `_decode_json()`
7. **Migration pattern:** `_run_schema()` adds columns with `ALTER TABLE ... ADD COLUMN` wrapped in try/except for idempotency
8. **Backup:** `backup(backup_dir)` uses SQLite online backup API, keeps 7 rotations, applies `0o600` to backup file
9. **No raw SQL in handlers:** All queries go through Store methods
