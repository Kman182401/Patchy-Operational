---
name: db-inspect
description: Query and summarize the Patchy Bot SQLite database state. Use when the user says "db inspect", "check database", "show db", "database state", "what's in the db", "check state", or needs to understand what the bot's persistence layer currently holds.
---

# Database State Inspector

Query the bot's SQLite database and present a clean, human-readable summary of all tables.

Database path: `/home/karson/Patchy_Bot/telegram-qbt/state.sqlite3`

## Step 1 — Get table overview

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && sqlite3 state.sqlite3 -header -column \
  "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
```

## Step 2 — Get row counts for all tables

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && sqlite3 state.sqlite3 \
  "SELECT 'searches', COUNT(*) FROM searches UNION ALL \
   SELECT 'results', COUNT(*) FROM results UNION ALL \
   SELECT 'user_defaults', COUNT(*) FROM user_defaults UNION ALL \
   SELECT 'user_auth', COUNT(*) FROM user_auth UNION ALL \
   SELECT 'auth_attempts', COUNT(*) FROM auth_attempts UNION ALL \
   SELECT 'schedule_tracks', COUNT(*) FROM schedule_tracks UNION ALL \
   SELECT 'schedule_runner_status', COUNT(*) FROM schedule_runner_status UNION ALL \
   SELECT 'schedule_pending', COUNT(*) FROM schedule_pending UNION ALL \
   SELECT 'schedule_show_cache', COUNT(*) FROM schedule_show_cache UNION ALL \
   SELECT 'plex_remove_jobs', COUNT(*) FROM plex_remove_jobs;"
```

## Step 3 — Show recent data for active tables

Only query tables that have rows. For each non-empty table, show the most recent entries:

### searches (recent 5)
```bash
sqlite3 state.sqlite3 -header -column \
  "SELECT search_id, user_id, query, datetime(created_at, 'unixepoch') as created FROM searches ORDER BY created_at DESC LIMIT 5;"
```

### results (count per search)
```bash
sqlite3 state.sqlite3 -header -column \
  "SELECT search_id, COUNT(*) as result_count FROM results GROUP BY search_id ORDER BY search_id DESC LIMIT 5;"
```

### user_auth (all entries)
```bash
sqlite3 state.sqlite3 -header -column \
  "SELECT user_id, datetime(unlocked_until, 'unixepoch') as unlocked_until, datetime(updated_at, 'unixepoch') as updated FROM user_auth;"
```

### auth_attempts (all entries)
```bash
sqlite3 state.sqlite3 -header -column \
  "SELECT user_id, fail_count, datetime(first_fail_at, 'unixepoch') as first_fail, datetime(locked_until, 'unixepoch') as locked_until FROM auth_attempts;"
```

### schedule_tracks (all entries)
```bash
sqlite3 state.sqlite3 -header -column \
  "SELECT track_id, show_name, season, enabled, datetime(next_check_at, 'unixepoch') as next_check FROM schedule_tracks;"
```

### plex_remove_jobs (recent 5)
```bash
sqlite3 state.sqlite3 -header -column \
  "SELECT * FROM plex_remove_jobs ORDER BY rowid DESC LIMIT 5;"
```

## Step 4 — Check for anomalies

Look for:
- **Orphaned results**: results whose search_id doesn't exist in searches
- **Stale searches**: searches older than 24 hours (should be auto-cleaned)
- **Locked users**: auth_attempts with locked_until in the future
- **Stale pending**: schedule_pending entries older than 48 hours
- **Expired cache**: schedule_show_cache entries past their expires_at

```bash
sqlite3 state.sqlite3 \
  "SELECT 'orphaned_results', COUNT(*) FROM results WHERE search_id NOT IN (SELECT search_id FROM searches) UNION ALL \
   SELECT 'stale_searches', COUNT(*) FROM searches WHERE created_at < unixepoch('now', '-1 day') UNION ALL \
   SELECT 'locked_users', COUNT(*) FROM auth_attempts WHERE locked_until > unixepoch('now') UNION ALL \
   SELECT 'expired_cache', COUNT(*) FROM schedule_show_cache WHERE expires_at < unixepoch('now');"
```

## Report format

### Table Summary
| Table | Rows | Notes |
|-------|------|-------|
| searches | N | oldest: X ago |
| results | N | across M searches |
| ... | ... | ... |

### Recent Activity
Show the recent searches and their result counts.

### Anomalies
List any issues found, or "None — database is clean."

### Storage
Report the file size of `state.sqlite3`.
