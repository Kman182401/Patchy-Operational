---
description: Dump current state of TV/movie scheduler runners and tracking
allowed-tools: Bash, Read
---

Read-only snapshot of Patchy's scheduler state — TV tracks, movie tracks, removal queue, recent runner activity.

Known references (verified from `patchy_bot/store.py`):
- DB: `/home/karson/Patchy_Bot/telegram-qbt/patchy_bot.db`
- Tables: `schedule_tracks` (TV), `movie_tracks`, `remove_jobs`, `schedule_runner_status`
- TV: `enabled INTEGER`, `next_check_at INTEGER` (epoch), `updated_at INTEGER`
- Movies: `status TEXT`, `release_status TEXT`, `enabled INTEGER`, `next_check_ts INTEGER`, `last_release_check_ts INTEGER`
- Remove jobs: `status TEXT`, `next_retry_at INTEGER`

Use `sqlite3` in read-only mode (`-readonly` flag) on the WAL DB. Format epoch timestamps with `datetime(<col>, 'unixepoch', 'localtime')`.

### Section 1 — TV tracks (`schedule_tracks`)
!`sqlite3 -readonly /home/karson/Patchy_Bot/telegram-qbt/patchy_bot.db "SELECT COUNT(*) AS total, SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END) AS enabled FROM schedule_tracks;" 2>&1`
!`sqlite3 -readonly -header -column /home/karson/Patchy_Bot/telegram-qbt/patchy_bot.db "SELECT track_id, user_id, enabled, datetime(next_check_at,'unixepoch','localtime') AS next_check, datetime(updated_at,'unixepoch','localtime') AS updated FROM schedule_tracks ORDER BY updated_at DESC LIMIT 5;" 2>&1`

### Section 2 — Movie tracks (`movie_tracks`)
!`sqlite3 -readonly /home/karson/Patchy_Bot/telegram-qbt/patchy_bot.db "SELECT COUNT(*) AS total, SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END) AS enabled, GROUP_CONCAT(DISTINCT status) AS statuses FROM movie_tracks;" 2>&1`
!`sqlite3 -readonly -header -column /home/karson/Patchy_Bot/telegram-qbt/patchy_bot.db "SELECT track_id, user_id, status, release_status, datetime(next_check_ts,'unixepoch','localtime') AS next_check, datetime(last_release_check_ts,'unixepoch','localtime') AS last_check FROM movie_tracks ORDER BY COALESCE(last_release_check_ts,0) DESC LIMIT 5;" 2>&1`

### Section 3 — Removal queue (`remove_jobs`)
!`sqlite3 -readonly /home/karson/Patchy_Bot/telegram-qbt/patchy_bot.db "SELECT status, COUNT(*) AS n FROM remove_jobs GROUP BY status;" 2>&1`
!`sqlite3 -readonly -header -column /home/karson/Patchy_Bot/telegram-qbt/patchy_bot.db "SELECT job_id, status, datetime(next_retry_at,'unixepoch','localtime') AS next_retry FROM remove_jobs WHERE status NOT IN ('done','succeeded','complete') ORDER BY next_retry_at LIMIT 10;" 2>&1`

### Section 4 — Recent runner activity (last hour)
!`journalctl -u telegram-qbt-bot.service --since "1 hour ago" --no-pager 2>/dev/null | grep -iE 'schedul|runner|track' | tail -20`

### Section 5 — Stuck items (>24h in non-terminal state)
For TV: tracks where `next_check_at < strftime('%s','now') - 86400` AND `enabled=1`:
!`sqlite3 -readonly -header -column /home/karson/Patchy_Bot/telegram-qbt/patchy_bot.db "SELECT track_id, user_id, datetime(next_check_at,'unixepoch','localtime') AS overdue_since FROM schedule_tracks WHERE enabled=1 AND next_check_at < strftime('%s','now') - 86400 ORDER BY next_check_at LIMIT 10;" 2>&1`

For movies: tracks where `next_check_ts < strftime('%s','now') - 86400` AND `enabled=1` AND `status NOT IN ('completed','cancelled')`:
!`sqlite3 -readonly -header -column /home/karson/Patchy_Bot/telegram-qbt/patchy_bot.db "SELECT track_id, status, datetime(next_check_ts,'unixepoch','localtime') AS overdue_since FROM movie_tracks WHERE enabled=1 AND COALESCE(next_check_ts,0) < strftime('%s','now') - 86400 AND status NOT IN ('completed','cancelled') ORDER BY next_check_ts LIMIT 10;" 2>&1`

For removal: jobs where `next_retry_at < strftime('%s','now') - 86400` AND status non-terminal — covered in Section 3.

Output four numbered sections (TV / Movies / Removal queue / Recent runner activity) with the counts and sample rows above. Then under "⚠️ Stuck items" list anything from Section 5. If a query fails (`unable to open` or `no such column`) name the failure and suggest re-checking schema in `patchy_bot/store.py` — do not fabricate results.
