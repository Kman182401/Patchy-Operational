---
name: download_health_events schema
description: Table added to store.py for download health monitoring, including columns, indexes, and CRUD methods
type: project
---

Table `download_health_events` was added to `_run_schema()` in `patchy_bot/store.py` between `notified_completions` and `command_center_ui`.

Columns: event_id (PK AUTOINCREMENT), created_at REAL, user_id INTEGER, torrent_hash TEXT (nullable), event_type TEXT, severity TEXT, detail_json TEXT, torrent_name TEXT (nullable).

Indexes: idx_health_events_user (user_id, created_at DESC), idx_health_events_type (event_type, created_at DESC).

CRUD methods added after `cleanup_old_completion_records`:
- `log_health_event(user_id, torrent_hash, event_type, severity, detail_json, torrent_name=None) -> int` — inserts a row, returns event_id
- `get_health_events(user_id, *, since_ts=None, event_type=None, limit=50) -> list[dict]` — filtered query, f-string WHERE clause with dynamic params list
- `cleanup_old_health_events(retention_days=30) -> int` — deletes rows older than cutoff, returns rowcount

**Why:** Added to support future download health monitoring and stall-detection features.
**How to apply:** When adding health event calls elsewhere in the codebase, use these three methods. `detail_json` must be a valid JSON string — serialize dicts with `json.dumps()` before passing.
