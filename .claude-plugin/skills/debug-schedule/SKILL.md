---
name: debug-schedule
description: Diagnose Patchy's schedule runner and TV auto-tracking state. Use when schedule checks, due tracks, metadata refresh, or episode auto-download behavior looks wrong. Trigger automatically for schedule-specific debugging; do not use for unrelated DB inspection.
---

# TV Schedule Diagnostics

Inspect the full state of the TV schedule system and report what's happening, what's stuck, and what needs attention.

## Agent Delegation

This skill delegates to the following agents during execution. Always use these agents — do not implement inline what an agent can handle.

- **Primary:** Delegate schedule state inspection, runner health analysis, and diagnosis to the `implementer` (sequential with database queries).
- **Secondary:** Delegate SQLite queries (Steps 1-2) to the `explorer` if the implementer needs raw query support.

Use Python's stdlib `sqlite3` module so this works without the `sqlite3` CLI.

## Step 1 — Read the schedule database tables

Run these SQLite queries against `/home/karson/Patchy_Bot/telegram-qbt/state.sqlite3`:

### Runner status (is the schedule engine running?)
```bash
cd /home/karson/Patchy_Bot/telegram-qbt && python - <<'PY'
import sqlite3
conn = sqlite3.connect("state.sqlite3")
for row in conn.execute("""
SELECT status_id, datetime(last_started_at, 'unixepoch'), datetime(last_finished_at, 'unixepoch'),
       datetime(last_success_at, 'unixepoch'), datetime(last_error_at, 'unixepoch'),
       last_error_text, last_due_count, last_processed_count,
       metadata_source_health_json, inventory_source_health_json
FROM schedule_runner_status
"""):
    print(row)
PY
```

### Active tracks (what shows are being monitored?)
```bash
cd /home/karson/Patchy_Bot/telegram-qbt && python - <<'PY'
import sqlite3
conn = sqlite3.connect("state.sqlite3")
for row in conn.execute("""
SELECT track_id, user_id, show_name, season, tvmaze_id, enabled,
       datetime(next_check_at, 'unixepoch'), datetime(next_air_ts, 'unixepoch'),
       datetime(updated_at, 'unixepoch'), pending_json, auto_state_json
FROM schedule_tracks
ORDER BY next_check_at
"""):
    print(row)
PY
```

### Pending episodes (stored inside `schedule_tracks.pending_json`)
```bash
cd /home/karson/Patchy_Bot/telegram-qbt && python - <<'PY'
import json, sqlite3
conn = sqlite3.connect("state.sqlite3")
for row in conn.execute("SELECT track_id, show_name, season, pending_json FROM schedule_tracks ORDER BY updated_at DESC"):
    pending = json.loads(row[3] or "[]")
    if pending:
        print(row[0], row[1], row[2], pending[:5])
PY
```

### Show cache (is metadata fresh?)
```bash
cd /home/karson/Patchy_Bot/telegram-qbt && python - <<'PY'
import sqlite3
conn = sqlite3.connect("state.sqlite3")
for row in conn.execute("SELECT tvmaze_id, datetime(fetched_at, 'unixepoch'), datetime(expires_at, 'unixepoch'), last_error_text FROM schedule_show_cache"):
    print(row)
PY
```

## Step 2 — Analyze the state

For each tracked show, determine:
1. **Is the track enabled?** If disabled, note it.
2. **Is next_check_at in the past?** If so, the runner may be stuck or not running.
3. **Is next_air_ts set?** If null, metadata may have failed.
4. **Is `pending_json` populated?** If so, what episode codes or retries are waiting?
5. **Is the show cache expired?** Stale metadata means wrong air dates.

For the runner:
1. **When did it last run?** If `last_started > last_finished`, it may still be running or crashed mid-run.
2. **Any errors?** Check `last_error_text` for clues.
3. **Health status?** Parse `metadata_source_health_json` and `inventory_source_health_json` for degraded sources.

## Step 3 — Cross-reference with code if needed

If the database state doesn't explain the issue, read:
- `/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/handlers/schedule.py` — the main schedule logic
- `/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/bot.py` — runner wiring and bootstrap
- Look for the runner loop, check timing, grace windows, backoff logic

## Report format

### Runner Health
- Status: Running / Idle / Stuck / Error
- Last successful run: [timestamp]
- Last error: [text or "none"]
- Metadata health: [OK / degraded]
- Inventory health: [OK / degraded]

### Tracked Shows
Table showing: Show Name | Season | Enabled | Next Check | Next Air | Status

Where status is one of:
- **Healthy** — next_check is in the future, metadata is fresh
- **Overdue** — next_check is in the past, runner should have processed it
- **No metadata** — next_air_ts is null, TVMaze lookup may have failed
- **Disabled** — user turned it off
- **Stale cache** — show cache expired, metadata needs refresh

### Pending Episodes
List any non-empty `pending_json` state and summarize what it implies.

### Diagnosis
Plain-English explanation of what's wrong (if anything) and what to do about it.
