---
name: debug-schedule
description: Diagnose TV show schedule issues by inspecting database state, runner status, and pending episodes. Use when the user says "debug schedule", "schedule not working", "show not downloading", "check schedule", "schedule status", or reports any issue with TV show auto-tracking.
---

# TV Schedule Diagnostics

Inspect the full state of the TV schedule system and report what's happening, what's stuck, and what needs attention.

## Agent Delegation

This skill delegates to the following agents during execution. Always use these agents — do not implement inline what an agent can handle.

- **Primary:** Delegate schedule state inspection, runner health analysis, and diagnosis to the `schedule-agent` (sequential with database queries).
- **Secondary:** Delegate SQLite queries (Steps 1-2) to the `database-agent` if the schedule-agent needs raw query support.

## Step 1 — Read the schedule database tables

Run these SQLite queries against `/home/karson/Patchy_Bot/telegram-qbt/state.sqlite3`:

### Runner status (is the schedule engine running?)
```bash
cd /home/karson/Patchy_Bot/telegram-qbt && sqlite3 state.sqlite3 -header -column \
  "SELECT status_id, datetime(last_started_at, 'unixepoch') as last_started, datetime(last_finished_at, 'unixepoch') as last_finished, datetime(last_success_at, 'unixepoch') as last_success, datetime(last_error_at, 'unixepoch') as last_error, last_error_text, last_due_count, last_processed_count, metadata_source_health_json, inventory_source_health_json FROM schedule_runner_status;"
```

### Active tracks (what shows are being monitored?)
```bash
cd /home/karson/Patchy_Bot/telegram-qbt && sqlite3 state.sqlite3 -header -column \
  "SELECT track_id, user_id, show_name, season, tvmaze_id, enabled, datetime(next_check_at, 'unixepoch') as next_check, datetime(next_air_ts, 'unixepoch') as next_air, datetime(updated_at, 'unixepoch') as updated FROM schedule_tracks ORDER BY next_check_at;"
```

### Pending episodes (what's queued for download?)
```bash
cd /home/karson/Patchy_Bot/telegram-qbt && sqlite3 state.sqlite3 -header -column \
  "SELECT * FROM schedule_pending ORDER BY rowid DESC LIMIT 20;"
```

### Show cache (is metadata fresh?)
```bash
cd /home/karson/Patchy_Bot/telegram-qbt && sqlite3 state.sqlite3 -header -column \
  "SELECT tvmaze_id, datetime(fetched_at, 'unixepoch') as fetched, datetime(expires_at, 'unixepoch') as expires FROM schedule_show_cache;"
```

## Step 2 — Analyze the state

For each tracked show, determine:
1. **Is the track enabled?** If disabled, note it.
2. **Is next_check_at in the past?** If so, the runner may be stuck or not running.
3. **Is next_air_ts set?** If null, metadata may have failed.
4. **Are there pending episodes?** What state are they in?
5. **Is the show cache expired?** Stale metadata means wrong air dates.

For the runner:
1. **When did it last run?** If `last_started > last_finished`, it may still be running or crashed mid-run.
2. **Any errors?** Check `last_error_text` for clues.
3. **Health status?** Parse `metadata_source_health_json` and `inventory_source_health_json` for degraded sources.

## Step 3 — Cross-reference with code if needed

If the database state doesn't explain the issue, read:
- `/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/schedule.py` — the main schedule logic
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
List any pending downloads with their state.

### Diagnosis
Plain-English explanation of what's wrong (if anything) and what to do about it.
