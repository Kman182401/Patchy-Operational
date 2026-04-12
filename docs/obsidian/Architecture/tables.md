# SQLite Tables

> Generated from `patchy_bot/store.py` on 2026-04-11. 14 tables, WAL mode, busy_timeout=5000.

## Database Config

- **Journal mode:** WAL (`PRAGMA journal_mode=WAL; PRAGMA wal_autocheckpoint=1000;`)
- **Busy timeout:** 5,000 ms
- **File permissions:** `0o600` (owner-only)
- **Thread safety:** `threading.Lock()`, single connection with `check_same_thread=False`
- **Parameterized queries only** — no string concatenation (injection prevention)

---

## searches

Stores active search sessions per user.

| Column | Type | Notes |
|--------|------|-------|
| `search_id` | TEXT | PK |
| `user_id` | INTEGER | NOT NULL |
| `created_at` | INTEGER | NOT NULL |
| `query` | TEXT | NOT NULL |
| `options_json` | TEXT | NOT NULL |

**Primary user:** search-download-agent

## results

Individual torrent results linked to a search session.

| Column | Type | Notes |
|--------|------|-------|
| `search_id` | TEXT | PK (composite), FK → searches |
| `idx` | INTEGER | PK (composite) |
| `name` | TEXT | NOT NULL |
| `size` | INTEGER | NOT NULL |
| `seeds` | INTEGER | NOT NULL |
| `leechers` | INTEGER | NOT NULL |
| `site` | TEXT | |
| `url` | TEXT | |
| `file_url` | TEXT | |
| `descr_link` | TEXT | |
| `hash` | TEXT | |
| `uploader` | TEXT | |

**Primary user:** search-download-agent

## user_defaults

Per-user search preference overrides.

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | INTEGER | PK |
| `default_min_seeds` | INTEGER | |
| `default_sort` | TEXT | |
| `default_order` | TEXT | |
| `default_limit` | INTEGER | |

**Primary user:** search-download-agent

## user_auth

Password-based session unlocking.

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | INTEGER | PK |
| `unlocked_until` | INTEGER | NOT NULL |
| `updated_at` | INTEGER | NOT NULL |

**Primary user:** security-agent

## auth_attempts

Brute-force protection — tracks failed login attempts and lockouts.

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | INTEGER | PK |
| `fail_count` | INTEGER | NOT NULL, DEFAULT 0 |
| `first_fail_at` | INTEGER | NOT NULL |
| `locked_until` | INTEGER | NOT NULL, DEFAULT 0 |

**Primary user:** security-agent

## schedule_tracks

TV episode auto-tracking state.

| Column | Type | Notes |
|--------|------|-------|
| `track_id` | TEXT | PK |
| `user_id` | INTEGER | NOT NULL |
| `chat_id` | INTEGER | NOT NULL |
| `created_at` | INTEGER | NOT NULL |
| `updated_at` | INTEGER | NOT NULL |
| `enabled` | INTEGER | NOT NULL, DEFAULT 1 |
| `show_name` | TEXT | NOT NULL |
| `year` | INTEGER | |
| `season` | INTEGER | NOT NULL |
| `tvmaze_id` | INTEGER | NOT NULL |
| `tmdb_id` | INTEGER | |
| `imdb_id` | TEXT | |
| `show_json` | TEXT | NOT NULL |
| `pending_json` | TEXT | NOT NULL, DEFAULT '[]' |
| `auto_state_json` | TEXT | NOT NULL, DEFAULT '{}' |
| `next_check_at` | INTEGER | |
| `next_air_ts` | INTEGER | |

**Indexes:** `idx_schedule_due(enabled, next_check_at)`, `idx_schedule_user_enabled(user_id, enabled, updated_at DESC)`
**Primary user:** schedule-agent

## schedule_runner_status

Singleton row tracking schedule runner health.

| Column | Type | Notes |
|--------|------|-------|
| `status_id` | INTEGER | PK, CHECK (= 1) |
| `created_at` | INTEGER | NOT NULL |
| `updated_at` | INTEGER | NOT NULL |
| `last_started_at` | INTEGER | |
| `last_finished_at` | INTEGER | |
| `last_success_at` | INTEGER | |
| `last_error_at` | INTEGER | |
| `last_error_text` | TEXT | |
| `last_due_count` | INTEGER | NOT NULL, DEFAULT 0 |
| `last_processed_count` | INTEGER | NOT NULL, DEFAULT 0 |
| `metadata_source_health_json` | TEXT | NOT NULL, DEFAULT '{}' |
| `inventory_source_health_json` | TEXT | NOT NULL, DEFAULT '{}' |

**Primary user:** schedule-agent

## schedule_show_cache

TVMaze bundle cache with 8-hour TTL.

| Column | Type | Notes |
|--------|------|-------|
| `tvmaze_id` | INTEGER | PK |
| `bundle_json` | TEXT | NOT NULL |
| `fetched_at` | INTEGER | NOT NULL |
| `expires_at` | INTEGER | NOT NULL |
| `last_error_at` | INTEGER | |
| `last_error_text` | TEXT | |
| `updated_at` | INTEGER | NOT NULL |

**Primary user:** schedule-agent

## remove_jobs

Media removal job tracking.

| Column | Type | Notes |
|--------|------|-------|
| `job_id` | TEXT | PK |
| `created_at` | INTEGER | NOT NULL |
| `updated_at` | INTEGER | NOT NULL |
| `user_id` | INTEGER | NOT NULL |
| `chat_id` | INTEGER | NOT NULL |
| `item_name` | TEXT | NOT NULL |
| `root_key` | TEXT | NOT NULL |
| `root_label` | TEXT | NOT NULL |
| `remove_kind` | TEXT | NOT NULL |
| `target_path` | TEXT | NOT NULL |
| `root_path` | TEXT | NOT NULL |
| `scan_path` | TEXT | |
| `plex_section_key` | TEXT | |
| `plex_rating_key` | TEXT | |
| `plex_title` | TEXT | |
| `verification_json` | TEXT | |
| `status` | TEXT | NOT NULL |
| `disk_deleted_at` | INTEGER | |
| `next_retry_at` | INTEGER | |
| `retry_count` | INTEGER | NOT NULL, DEFAULT 0 |
| `last_error_text` | TEXT | |

**Indexes:** `idx_remove_jobs_due(status, next_retry_at)`
**Primary user:** remove-agent

## notified_completions

Dedup tracker for download completion notifications.

| Column | Type | Notes |
|--------|------|-------|
| `torrent_hash` | TEXT | PK |
| `name` | TEXT | NOT NULL |
| `notified_at` | INTEGER | NOT NULL |
| `user_id` | INTEGER | NOT NULL, DEFAULT 0 (migration) |

**Primary user:** search-download-agent

## download_health_events

Health event log for download pipeline monitoring.

| Column | Type | Notes |
|--------|------|-------|
| `event_id` | INTEGER | PK, AUTOINCREMENT |
| `created_at` | REAL | NOT NULL |
| `user_id` | INTEGER | NOT NULL |
| `torrent_hash` | TEXT | |
| `event_type` | TEXT | NOT NULL |
| `severity` | TEXT | NOT NULL |
| `detail_json` | TEXT | NOT NULL |
| `torrent_name` | TEXT | |

**Indexes:** `idx_health_events_user(user_id, created_at DESC)`, `idx_health_events_type(event_type, created_at DESC)`
**Primary user:** monitoring-metrics-agent

## movie_tracks

Movie release tracking and auto-download scheduling.

| Column | Type | Notes |
|--------|------|-------|
| `track_id` | TEXT | PK |
| `user_id` | INTEGER | NOT NULL |
| `tmdb_id` | INTEGER | Nullable |
| `title` | TEXT | NOT NULL |
| `year` | INTEGER | |
| `release_date_type` | TEXT | NOT NULL |
| `release_date_ts` | INTEGER | NOT NULL |
| `search_query` | TEXT | NOT NULL |
| `status` | TEXT | NOT NULL, DEFAULT 'pending' |
| `torrent_hash` | TEXT | |
| `last_checked_ts` | INTEGER | |
| `next_check_ts` | INTEGER | |
| `error_text` | TEXT | |
| `notified` | INTEGER | NOT NULL, DEFAULT 0 |
| `enabled` | INTEGER | NOT NULL, DEFAULT 1 |
| `theatrical_ts` | INTEGER | |
| `digital_ts` | INTEGER | |
| `physical_ts` | INTEGER | |
| `home_release_ts` | INTEGER | |
| `digital_estimated` | INTEGER | |
| `release_status` | TEXT | |

**Primary user:** movie-tracking-agent

## command_center_ui

Per-user command center message tracking.

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | INTEGER | PK |
| `chat_id` | INTEGER | NOT NULL |
| `message_id` | INTEGER | NOT NULL |
| `updated_at` | INTEGER | NOT NULL |

**Primary user:** ui-agent / config-infra-agent

## malware_scan_log

Audit trail for blocked torrents.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER | PK, AUTOINCREMENT |
| `torrent_hash` | TEXT | NOT NULL |
| `torrent_name` | TEXT | NOT NULL |
| `stage` | TEXT | NOT NULL, CHECK('search' or 'download') |
| `reasons` | TEXT | NOT NULL |
| `blocked_at` | INTEGER | NOT NULL |

**Indexes:** `idx_malware_hash(torrent_hash)`, `idx_malware_blocked_at(blocked_at)`
**Primary user:** search-download-agent
