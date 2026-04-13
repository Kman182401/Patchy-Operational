---
name: db-inspect
description: Query and summarize the live Patchy Bot SQLite database state. Use for schema reality, persistent-state debugging, or “what is in the DB right now?” questions. Trigger automatically when DB state is central to the task; do not use for code-only refactors.
---

# Database State Inspector

Query the bot's SQLite database and present a clean, human-readable summary of the actual current schema and table contents.

Database path: `/home/karson/Patchy_Bot/telegram-qbt/state.sqlite3`

## Agent Delegation

This skill delegates to the following agents during execution. Always use these agents — do not implement inline what an agent can handle.

- **Primary:** Delegate all database queries, anomaly detection, and schema inspection to the `explorer`.

Use Python's stdlib `sqlite3` module so this skill works even when the `sqlite3` CLI is not installed.

## Step 1 — Get table overview

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && python - <<'PY'
import sqlite3
conn = sqlite3.connect("state.sqlite3")
for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
    print(name)
PY
```

## Step 2 — Get row counts for the live tables

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && python - <<'PY'
import sqlite3
conn = sqlite3.connect("state.sqlite3")
tables = [
    "searches", "results", "user_defaults", "user_auth", "auth_attempts",
    "schedule_tracks", "schedule_runner_status", "schedule_show_cache",
    "remove_jobs", "notified_completions", "download_health_events",
    "movie_tracks", "command_center_ui", "pending_downloads",
    "notification_outbox", "active_trackers",
]
for table in tables:
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}\t{count}")
    except sqlite3.OperationalError:
        pass
PY
```

## Step 3 — Show recent data for active tables

Only query tables that have rows. For each non-empty table, show the most recent entries:

### searches (recent 5)
```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect("state.sqlite3")
for row in conn.execute("SELECT search_id, user_id, query, datetime(created_at, 'unixepoch') FROM searches ORDER BY created_at DESC LIMIT 5"):
    print(row)
PY
```

### results (count per search)
```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect("state.sqlite3")
for row in conn.execute("SELECT search_id, COUNT(*) FROM results GROUP BY search_id ORDER BY search_id DESC LIMIT 5"):
    print(row)
PY
```

### user_auth (all entries)
```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect("state.sqlite3")
for row in conn.execute("SELECT user_id, datetime(unlocked_until, 'unixepoch'), datetime(updated_at, 'unixepoch') FROM user_auth"):
    print(row)
PY
```

### auth_attempts (all entries)
```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect("state.sqlite3")
for row in conn.execute("SELECT user_id, fail_count, datetime(first_fail_at, 'unixepoch'), datetime(locked_until, 'unixepoch') FROM auth_attempts"):
    print(row)
PY
```

### schedule_tracks (all entries)
```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect("state.sqlite3")
for row in conn.execute("SELECT track_id, show_name, season, enabled, datetime(next_check_at, 'unixepoch') FROM schedule_tracks"):
    print(row)
PY
```

### remove_jobs (recent 5)
```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect("state.sqlite3")
for row in conn.execute("SELECT job_id, item_name, remove_kind, status, retry_count, datetime(updated_at, 'unixepoch') FROM remove_jobs ORDER BY updated_at DESC LIMIT 5"):
    print(row)
PY
```

## Step 4 — Check for anomalies

Look for:
- **Orphaned results**: results whose search_id doesn't exist in searches
- **Stale searches**: searches older than 24 hours (should be auto-cleaned)
- **Locked users**: auth_attempts with locked_until in the future
- **Stale schedule pending state**: schedule tracks whose `pending_json` is still populated long after `next_check_at`
- **Expired cache**: schedule_show_cache entries past their expires_at
- **Retrying remove jobs**: `remove_jobs` rows stuck in retry states

```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect("state.sqlite3")
queries = {
    "orphaned_results": "SELECT COUNT(*) FROM results WHERE search_id NOT IN (SELECT search_id FROM searches)",
    "stale_searches": "SELECT COUNT(*) FROM searches WHERE created_at < unixepoch('now', '-1 day')",
    "locked_users": "SELECT COUNT(*) FROM auth_attempts WHERE locked_until > unixepoch('now')",
    "expired_cache": "SELECT COUNT(*) FROM schedule_show_cache WHERE expires_at < unixepoch('now')",
    "remove_jobs_retrying": "SELECT COUNT(*) FROM remove_jobs WHERE status IN ('plex_pending', 'retry', 'failed')",
}
for name, query in queries.items():
    print(name, conn.execute(query).fetchone()[0])
PY
```

## Report format

### Table Summary
| Table | Rows | Notes |
|-------|------|-------|
| searches | N | oldest: X ago |
| results | N | across M searches |
| ... | ... | ... |

### Recent Activity
Show the recent searches, active schedule tracks, and recent remove jobs when those tables are non-empty.

### Anomalies
List any issues found, or "None — database is clean."

### Storage
Report the file size of `state.sqlite3`.
