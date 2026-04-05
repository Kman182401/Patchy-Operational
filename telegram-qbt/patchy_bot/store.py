"""SQLite-backed persistent state store."""

from __future__ import annotations

import json
import logging
import os
import secrets
import sqlite3
import threading
from datetime import UTC, datetime
from typing import Any

from .quality import quality_label, score_torrent
from .utils import now_ts

LOG = logging.getLogger("qbtg")


class Store:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._init_db()
        # Lock down permissions on pre-existing database files too
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass  # Path may not exist yet (e.g. :memory: during tests)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        # Ensure the database file is created with owner-only permissions (0600).
        # sqlite3.connect() creates the file with mode 0666 modified by umask;
        # temporarily set umask=0o177 so the result is 0600.
        old_mask = os.umask(0o177)
        try:
            with self._connect() as conn:
                conn.executescript(
                    """
                PRAGMA journal_mode=WAL;
                PRAGMA wal_autocheckpoint=1000;

                CREATE TABLE IF NOT EXISTS searches (
                    search_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    options_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS results (
                    search_id TEXT NOT NULL,
                    idx INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    seeds INTEGER NOT NULL,
                    leechers INTEGER NOT NULL,
                    site TEXT,
                    url TEXT,
                    file_url TEXT,
                    descr_link TEXT,
                    hash TEXT,
                    PRIMARY KEY (search_id, idx),
                    FOREIGN KEY (search_id) REFERENCES searches(search_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS user_defaults (
                    user_id INTEGER PRIMARY KEY,
                    default_min_seeds INTEGER,
                    default_sort TEXT,
                    default_order TEXT,
                    default_limit INTEGER
                );

                CREATE TABLE IF NOT EXISTS user_auth (
                    user_id INTEGER PRIMARY KEY,
                    unlocked_until INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS auth_attempts (
                    user_id INTEGER PRIMARY KEY,
                    fail_count INTEGER NOT NULL DEFAULT 0,
                    first_fail_at INTEGER NOT NULL,
                    locked_until INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS schedule_tracks (
                    track_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    show_name TEXT NOT NULL,
                    year INTEGER,
                    season INTEGER NOT NULL,
                    tvmaze_id INTEGER NOT NULL,
                    tmdb_id INTEGER,
                    imdb_id TEXT,
                    show_json TEXT NOT NULL,
                    pending_json TEXT NOT NULL DEFAULT '[]',
                    auto_state_json TEXT NOT NULL DEFAULT '{}',
                    skipped_signature TEXT,
                    last_missing_signature TEXT,
                    last_probe_json TEXT NOT NULL DEFAULT '{}',
                    last_probe_at INTEGER,
                    next_check_at INTEGER NOT NULL,
                    next_air_ts INTEGER,
                    UNIQUE(user_id, tvmaze_id, season)
                );

                CREATE TABLE IF NOT EXISTS schedule_runner_status (
                    status_id INTEGER PRIMARY KEY CHECK (status_id = 1),
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    last_started_at INTEGER,
                    last_finished_at INTEGER,
                    last_success_at INTEGER,
                    last_error_at INTEGER,
                    last_error_text TEXT,
                    last_due_count INTEGER NOT NULL DEFAULT 0,
                    last_processed_count INTEGER NOT NULL DEFAULT 0,
                    metadata_source_health_json TEXT NOT NULL DEFAULT '{}',
                    inventory_source_health_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS schedule_show_cache (
                    tvmaze_id INTEGER PRIMARY KEY,
                    bundle_json TEXT NOT NULL,
                    fetched_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    last_error_at INTEGER,
                    last_error_text TEXT,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS remove_jobs (
                    job_id TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    root_key TEXT NOT NULL,
                    root_label TEXT NOT NULL,
                    remove_kind TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    scan_path TEXT,
                    plex_section_key TEXT,
                    plex_rating_key TEXT,
                    plex_title TEXT,
                    verification_json TEXT NOT NULL DEFAULT '{}',
                    disk_deleted_at INTEGER,
                    plex_cleanup_started_at INTEGER,
                    verified_at INTEGER,
                    next_retry_at INTEGER,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    last_error_text TEXT
                );

                CREATE TABLE IF NOT EXISTS notified_completions (
                    torrent_hash TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    notified_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS command_center_ui (
                    user_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_schedule_due ON schedule_tracks(enabled, next_check_at);
                CREATE INDEX IF NOT EXISTS idx_schedule_user_enabled ON schedule_tracks(user_id, enabled, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_remove_jobs_due ON remove_jobs(status, next_retry_at);
                """
                )
            results_cols = {row[1] for row in conn.execute("PRAGMA table_info(results)")}
            if "quality_score" not in results_cols:
                conn.execute("ALTER TABLE results ADD COLUMN quality_score INTEGER DEFAULT 0")
            if "quality_json" not in results_cols:
                conn.execute("ALTER TABLE results ADD COLUMN quality_json TEXT")

            schedule_track_cols = {row[1] for row in conn.execute("PRAGMA table_info(schedule_tracks)")}
            if "auto_state_json" not in schedule_track_cols:
                conn.execute("ALTER TABLE schedule_tracks ADD COLUMN auto_state_json TEXT NOT NULL DEFAULT '{}'")
                schedule_track_cols.add("auto_state_json")
            if "auto_state_json" in schedule_track_cols:
                conn.execute(
                    "UPDATE schedule_tracks SET auto_state_json = '{}' WHERE auto_state_json IS NULL OR trim(auto_state_json) = ''"
                )
            now_value = now_ts()
            conn.execute(
                """
                INSERT INTO schedule_runner_status(
                    status_id, created_at, updated_at, last_due_count, last_processed_count,
                    metadata_source_health_json, inventory_source_health_json
                ) VALUES(1, ?, ?, 0, 0, '{}', '{}')
                ON CONFLICT(status_id) DO NOTHING
                """,
                (now_value, now_value),
            )
            conn.execute("PRAGMA optimize;")
            conn.commit()
        finally:
            os.umask(old_mask)

    def is_completion_notified(self, torrent_hash: str) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM notified_completions WHERE torrent_hash = ?",
                (torrent_hash.lower(),),
            ).fetchone()
            return row is not None

    def mark_completion_notified(self, torrent_hash: str, name: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO notified_completions(torrent_hash, name, notified_at) VALUES(?, ?, ?)",
                (torrent_hash.lower(), name, now_ts()),
            )
            conn.commit()

    def get_command_center(self, user_id: int) -> dict[str, int] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT chat_id, message_id FROM command_center_ui WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                return None
            return {"chat_id": int(row["chat_id"]), "message_id": int(row["message_id"])}

    def save_command_center(self, user_id: int, chat_id: int, message_id: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO command_center_ui(user_id, chat_id, message_id, updated_at) "
                "VALUES(?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
                "chat_id=excluded.chat_id, message_id=excluded.message_id, updated_at=excluded.updated_at",
                (user_id, chat_id, message_id, now_ts()),
            )
            conn.commit()

    def cleanup_old_completion_records(self, max_age_hours: int = 168) -> None:
        """Remove completion records older than 7 days to prevent table bloat."""
        cutoff = now_ts() - max_age_hours * 3600
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM notified_completions WHERE notified_at < ?", (cutoff,))
            conn.commit()

    def cleanup(self, max_age_hours: int = 24) -> None:
        cutoff = now_ts() - max_age_hours * 3600
        with self._lock, self._connect() as conn:
            old_ids = [
                r[0] for r in conn.execute("SELECT search_id FROM searches WHERE created_at < ?", (cutoff,)).fetchall()
            ]
            for sid in old_ids:
                conn.execute("DELETE FROM results WHERE search_id = ?", (sid,))
                conn.execute("DELETE FROM searches WHERE search_id = ?", (sid,))
            conn.commit()

    def save_search(self, user_id: int, query: str, options: dict[str, Any], rows: list[dict[str, Any]]) -> str:
        search_id = secrets.token_hex(8)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO searches(search_id, user_id, created_at, query, options_json) VALUES(?,?,?,?,?)",
                (search_id, user_id, now_ts(), query, json.dumps(options)),
            )
            for idx, row in enumerate(rows, start=1):
                name = str(row.get("fileName") or row.get("name") or "unknown")
                size = int(row.get("fileSize") or row.get("size") or 0)
                seeds = int(row.get("nbSeeders") or row.get("seeders") or 0)
                ts = score_torrent(name, size, seeds)
                q_json = json.dumps(
                    {
                        "resolution": ts.parsed.resolution,
                        "source": ts.parsed.quality,
                        "codec": ts.parsed.codec,
                        "audio": list(ts.parsed.audio or []),
                        "hdr": list(ts.parsed.hdr or []),
                        "group": ts.parsed.group,
                        "tier": ts.resolution_tier,
                        "label": quality_label(ts.parsed),
                    }
                )
                conn.execute(
                    """
                    INSERT INTO results(search_id, idx, name, size, seeds, leechers, site, url, file_url, descr_link, hash,
                                        quality_score, quality_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        search_id,
                        idx,
                        name,
                        size,
                        seeds,
                        int(row.get("nbLeechers") or row.get("leechers") or 0),
                        str(row.get("siteUrl") or row.get("site") or ""),
                        str(row.get("fileUrl") or row.get("file_url") or row.get("url") or ""),
                        str(row.get("fileUrl") or row.get("file_url") or ""),
                        str(row.get("descrLink") or row.get("descr_link") or ""),
                        str(row.get("fileHash") or row.get("hash") or ""),
                        ts.format_score,
                        q_json,
                    ),
                )
            conn.commit()
        return search_id

    def get_search(self, user_id: int, search_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        with self._lock, self._connect() as conn:
            s = conn.execute(
                "SELECT search_id, query, options_json FROM searches WHERE search_id = ? AND user_id = ?",
                (search_id, user_id),
            ).fetchone()
            if not s:
                return None
            opts = json.loads(s["options_json"])
            rows = conn.execute("SELECT * FROM results WHERE search_id = ? ORDER BY idx ASC", (search_id,)).fetchall()
            return ({"search_id": s["search_id"], "query": s["query"], "options": opts}, [dict(r) for r in rows])

    def get_result(self, user_id: int, search_id: str, idx: int) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            s = conn.execute(
                "SELECT 1 FROM searches WHERE search_id = ? AND user_id = ?", (search_id, user_id)
            ).fetchone()
            if not s:
                return None
            row = conn.execute("SELECT * FROM results WHERE search_id = ? AND idx = ?", (search_id, idx)).fetchone()
            return dict(row) if row else None

    def get_defaults(self, user_id: int, cfg: Config) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM user_defaults WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                return {
                    "default_min_seeds": cfg.default_min_seeds,
                    "default_sort": cfg.default_sort,
                    "default_order": cfg.default_order,
                    "default_limit": cfg.default_limit,
                }
            return {
                "default_min_seeds": int(row["default_min_seeds"] or 0),
                "default_sort": row["default_sort"] or cfg.default_sort,
                "default_order": row["default_order"] or cfg.default_order,
                "default_limit": int(row["default_limit"] or cfg.default_limit),
            }

    def set_defaults(self, user_id: int, cfg: Config, **kwargs: Any) -> None:
        current = self.get_defaults(user_id, cfg)
        current.update(kwargs)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_defaults(user_id, default_min_seeds, default_sort, default_order, default_limit)
                VALUES(?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                  default_min_seeds=excluded.default_min_seeds,
                  default_sort=excluded.default_sort,
                  default_order=excluded.default_order,
                  default_limit=excluded.default_limit
                """,
                (
                    user_id,
                    int(current.get("default_min_seeds") or 0),
                    str(current.get("default_sort") or "seeds"),
                    str(current.get("default_order") or "desc"),
                    int(current.get("default_limit") or 10),
                ),
            )
            conn.commit()

    def is_unlocked(self, user_id: int) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT unlocked_until FROM user_auth WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                return False
            until = int(row["unlocked_until"] or 0)
            if until <= 0:
                return True  # indefinite unlock sentinel
            return until > now_ts()

    def unlock_user(self, user_id: int, ttl_s: int) -> int:
        ttl = int(ttl_s)
        until = 0 if ttl <= 0 else now_ts() + max(60, ttl)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_auth(user_id, unlocked_until, updated_at)
                VALUES(?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                  unlocked_until=excluded.unlocked_until,
                  updated_at=excluded.updated_at
                """,
                (user_id, until, now_ts()),
            )
            conn.commit()
        return until

    def lock_user(self, user_id: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM user_auth WHERE user_id = ?", (user_id,))
            conn.commit()

    def is_auth_locked(self, user_id: int) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT locked_until FROM auth_attempts WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                return False
            return int(row["locked_until"] or 0) > now_ts()

    def record_auth_failure(
        self, user_id: int, max_attempts: int = 5, lockout_s: int = 900, window_s: int = 3600
    ) -> bool:
        now_value = now_ts()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT fail_count, first_fail_at, locked_until FROM auth_attempts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row and int(row["locked_until"] or 0) > now_value:
                return True  # already locked
            # Reset counter if the first failure is older than the window
            if row and (now_value - int(row["first_fail_at"] or 0)) > window_s:
                count = 1
            elif row:
                count = int(row["fail_count"] or 0) + 1
            else:
                count = 1
            locked_until = (now_value + lockout_s) if count >= max_attempts else 0
            conn.execute(
                """
                INSERT INTO auth_attempts(user_id, fail_count, first_fail_at, locked_until)
                VALUES(?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                  fail_count=excluded.fail_count,
                  locked_until=excluded.locked_until
                """,
                (user_id, count, now_value, locked_until),
            )
            conn.commit()
            return locked_until > 0

    def clear_auth_failures(self, user_id: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM auth_attempts WHERE user_id = ?", (user_id,))
            conn.commit()

    @staticmethod
    def _decode_json(raw: str | None, default: Any) -> Any:
        if not raw:
            return default
        try:
            return json.loads(raw)
        except Exception:
            return default

    def _schedule_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["enabled"] = bool(data.get("enabled"))
        data["show_json"] = self._decode_json(data.get("show_json"), {})
        data["pending_json"] = self._decode_json(data.get("pending_json"), [])
        data["auto_state_json"] = self._decode_json(data.get("auto_state_json"), {})
        data["last_probe_json"] = self._decode_json(data.get("last_probe_json"), {})
        return data

    def _remove_job_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["verification_json"] = self._decode_json(data.get("verification_json"), {})
        return data

    def create_schedule_track(
        self,
        *,
        user_id: int,
        chat_id: int,
        show: dict[str, Any],
        season: int,
        probe: dict[str, Any],
        next_check_at: int,
        initial_auto_state: dict[str, Any] | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM schedule_tracks WHERE user_id = ? AND tvmaze_id = ? AND season = ?",
                (user_id, int(show.get("id") or 0), int(season)),
            ).fetchone()
            if existing:
                return False, self._schedule_row(existing)

            track_id = secrets.token_hex(8)
            now_value = now_ts()
            initial_auto_state = initial_auto_state or {"enabled": True, "next_auto_retry_at": None}
            conn.execute(
                """
                INSERT INTO schedule_tracks(
                    track_id, user_id, chat_id, created_at, updated_at, enabled, show_name, year, season,
                    tvmaze_id, tmdb_id, imdb_id, show_json, pending_json, auto_state_json, skipped_signature,
                    last_missing_signature, last_probe_json, last_probe_at, next_check_at, next_air_ts
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    track_id,
                    int(user_id),
                    int(chat_id),
                    now_value,
                    now_value,
                    1,
                    str(show.get("name") or "Unknown show"),
                    int(show.get("year") or 0) or None,
                    int(season),
                    int(show.get("id") or 0),
                    int(show.get("tmdb_id") or 0) or None,
                    str(show.get("imdb_id") or "").strip() or None,
                    json.dumps(show),
                    json.dumps(list(probe.get("pending_codes") or [])),
                    json.dumps(initial_auto_state),
                    None,
                    str(probe.get("signature") or "") or None,
                    json.dumps(probe),
                    now_value,
                    int(next_check_at),
                    int(probe.get("next_air_ts") or 0) or None,
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM schedule_tracks WHERE track_id = ?", (track_id,)).fetchone()
            if row is None:
                raise RuntimeError(f"Schedule track {track_id} was inserted but could not be read back")
            return True, self._schedule_row(row)

    def get_schedule_track(self, user_id: int, track_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM schedule_tracks WHERE track_id = ? AND user_id = ?",
                (track_id, int(user_id)),
            ).fetchone()
            return self._schedule_row(row) if row else None

    def get_schedule_track_any(self, track_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM schedule_tracks WHERE track_id = ?", (track_id,)).fetchone()
            return self._schedule_row(row) if row else None

    def list_due_schedule_tracks(self, due_ts: int, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schedule_tracks WHERE enabled = 1 AND next_check_at <= ? ORDER BY next_check_at ASC LIMIT ?",
                (int(due_ts), int(limit)),
            ).fetchall()
            return [self._schedule_row(row) for row in rows]

    def list_schedule_tracks(self, user_id: int, enabled_only: bool = True, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            query = "SELECT * FROM schedule_tracks WHERE user_id = ?"
            params: list[Any] = [int(user_id)]
            if enabled_only:
                query += " AND enabled = 1"
            query += " ORDER BY updated_at DESC, created_at DESC LIMIT ?"
            params.append(int(limit))
            rows = conn.execute(query, params).fetchall()
            return [self._schedule_row(row) for row in rows]

    def list_all_schedule_tracks(self, enabled_only: bool = True) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            query = "SELECT * FROM schedule_tracks"
            if enabled_only:
                query += " WHERE enabled = 1"
            query += " ORDER BY updated_at DESC, created_at DESC"
            rows = conn.execute(query).fetchall()
            return [self._schedule_row(row) for row in rows]

    def count_due_schedule_tracks(self, due_ts: int) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM schedule_tracks WHERE enabled = 1 AND next_check_at <= ?",
                (int(due_ts),),
            ).fetchone()
            return int((row["c"] if row is not None else 0) or 0)

    def update_schedule_track(self, track_id: str, **fields: Any) -> None:
        if not fields:
            return
        allowed = {
            "chat_id",
            "enabled",
            "show_name",
            "year",
            "season",
            "tvmaze_id",
            "tmdb_id",
            "imdb_id",
            "show_json",
            "pending_json",
            "auto_state_json",
            "skipped_signature",
            "last_missing_signature",
            "last_probe_json",
            "last_probe_at",
            "next_check_at",
            "next_air_ts",
        }
        json_fields = {"show_json", "pending_json", "auto_state_json", "last_probe_json"}
        parts: list[str] = []
        values: list[Any] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in json_fields:
                value = json.dumps(value)
            if key == "enabled":
                value = 1 if value else 0
            parts.append(f"{key} = ?")
            values.append(value)
        if not parts:
            return
        parts.append("updated_at = ?")
        values.append(now_ts())
        values.append(track_id)
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE schedule_tracks SET {', '.join(parts)} WHERE track_id = ?", values)
            conn.commit()

    def delete_schedule_track(self, track_id: str, user_id: int) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM schedule_tracks WHERE track_id = ? AND user_id = ?",
                (track_id, int(user_id)),
            )
            conn.commit()
            return cur.rowcount > 0

    def get_schedule_show_cache(self, tvmaze_id: int) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM schedule_show_cache WHERE tvmaze_id = ?",
                (int(tvmaze_id),),
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            data["bundle_json"] = self._decode_json(data.get("bundle_json"), {})
            return data

    def upsert_schedule_show_cache(
        self,
        tvmaze_id: int,
        bundle: dict[str, Any],
        fetched_at: int,
        expires_at: int,
        *,
        last_error_at: int | None = None,
        last_error_text: str | None = None,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO schedule_show_cache(
                    tvmaze_id, bundle_json, fetched_at, expires_at, last_error_at, last_error_text, updated_at
                ) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(tvmaze_id) DO UPDATE SET
                  bundle_json=excluded.bundle_json,
                  fetched_at=excluded.fetched_at,
                  expires_at=excluded.expires_at,
                  last_error_at=excluded.last_error_at,
                  last_error_text=excluded.last_error_text,
                  updated_at=excluded.updated_at
                """,
                (
                    int(tvmaze_id),
                    json.dumps(bundle),
                    int(fetched_at),
                    int(expires_at),
                    int(last_error_at) if last_error_at else None,
                    str(last_error_text or "").strip() or None,
                    now_ts(),
                ),
            )
            conn.commit()

    def get_schedule_runner_status(self) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM schedule_runner_status WHERE status_id = 1").fetchone()
            if not row:
                return {
                    "status_id": 1,
                    "last_due_count": 0,
                    "last_processed_count": 0,
                    "metadata_source_health_json": {},
                    "inventory_source_health_json": {},
                }
            data = dict(row)
            data["metadata_source_health_json"] = self._decode_json(data.get("metadata_source_health_json"), {})
            data["inventory_source_health_json"] = self._decode_json(data.get("inventory_source_health_json"), {})
            return data

    def update_schedule_runner_status(self, **fields: Any) -> None:
        allowed = {
            "last_started_at",
            "last_finished_at",
            "last_success_at",
            "last_error_at",
            "last_error_text",
            "last_due_count",
            "last_processed_count",
            "metadata_source_health_json",
            "inventory_source_health_json",
        }
        json_fields = {"metadata_source_health_json", "inventory_source_health_json"}
        parts: list[str] = []
        values: list[Any] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in json_fields:
                value = json.dumps(value or {})
            parts.append(f"{key} = ?")
            values.append(value)
        if not parts:
            return
        parts.append("updated_at = ?")
        updated_at = now_ts()
        values.append(updated_at)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO schedule_runner_status(status_id, created_at, updated_at)
                VALUES(1, ?, ?)
                ON CONFLICT(status_id) DO NOTHING
                """,
                (updated_at, updated_at),
            )
            conn.execute(f"UPDATE schedule_runner_status SET {', '.join(parts)} WHERE status_id = 1", values)
            conn.commit()

    def create_remove_job(
        self,
        *,
        user_id: int,
        chat_id: int,
        item_name: str,
        root_key: str,
        root_label: str,
        remove_kind: str,
        target_path: str,
        root_path: str,
        scan_path: str | None,
        plex_section_key: str | None,
        plex_rating_key: str | None,
        plex_title: str | None,
        verification_json: dict[str, Any] | None = None,
        status: str,
        disk_deleted_at: int | None = None,
        next_retry_at: int | None = None,
        retry_count: int = 0,
        last_error_text: str | None = None,
    ) -> dict[str, Any]:
        job_id = secrets.token_hex(8)
        now_value = now_ts()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO remove_jobs(
                    job_id, created_at, updated_at, user_id, chat_id, item_name, root_key, root_label,
                    remove_kind, target_path, root_path, scan_path, plex_section_key, plex_rating_key,
                    plex_title, verification_json, disk_deleted_at, plex_cleanup_started_at, verified_at,
                    next_retry_at, retry_count, status, last_error_text
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    job_id,
                    now_value,
                    now_value,
                    int(user_id),
                    int(chat_id),
                    str(item_name),
                    str(root_key),
                    str(root_label),
                    str(remove_kind),
                    str(target_path),
                    str(root_path),
                    str(scan_path or "").strip() or None,
                    str(plex_section_key or "").strip() or None,
                    str(plex_rating_key or "").strip() or None,
                    str(plex_title or "").strip() or None,
                    json.dumps(verification_json or {}),
                    int(disk_deleted_at) if disk_deleted_at else None,
                    None,
                    None,
                    int(next_retry_at) if next_retry_at else None,
                    int(retry_count),
                    str(status),
                    str(last_error_text or "").strip() or None,
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM remove_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise RuntimeError(f"Remove job {job_id} was inserted but could not be read back")
            return self._remove_job_row(row)

    def get_remove_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM remove_jobs WHERE job_id = ?", (str(job_id),)).fetchone()
            return self._remove_job_row(row) if row else None

    def list_due_remove_jobs(self, due_ts: int, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM remove_jobs
                WHERE status = 'plex_pending' AND next_retry_at IS NOT NULL AND next_retry_at <= ?
                ORDER BY next_retry_at ASC, created_at ASC
                LIMIT ?
                """,
                (int(due_ts), int(limit)),
            ).fetchall()
            return [self._remove_job_row(row) for row in rows]

    def update_remove_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        allowed = {
            "item_name",
            "root_key",
            "root_label",
            "remove_kind",
            "target_path",
            "root_path",
            "scan_path",
            "plex_section_key",
            "plex_rating_key",
            "plex_title",
            "verification_json",
            "disk_deleted_at",
            "plex_cleanup_started_at",
            "verified_at",
            "next_retry_at",
            "retry_count",
            "status",
            "last_error_text",
        }
        json_fields = {"verification_json"}
        parts: list[str] = []
        values: list[Any] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in json_fields:
                value = json.dumps(value or {})
            parts.append(f"{key} = ?")
            values.append(value)
        if not parts:
            return
        parts.append("updated_at = ?")
        values.append(now_ts())
        values.append(str(job_id))
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE remove_jobs SET {', '.join(parts)} WHERE job_id = ?", values)
            conn.commit()

    def db_diagnostics(self) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            busy_timeout = int(conn.execute("PRAGMA busy_timeout;").fetchone()[0] or 0)
            return {
                "journal_mode": str(journal_mode),
                "busy_timeout_ms": busy_timeout,
                "sqlite_runtime": sqlite3.sqlite_version,
            }

    def backup(self, backup_dir: str) -> str:
        """Create a timestamped backup of the database using SQLite's online backup API.

        Uses sqlite3.Connection.backup() which holds a shared read lock and copies
        page-by-page, making it safe to run against a live database in WAL mode.
        Keeps the last 7 backups and deletes older ones.

        Args:
            backup_dir: Directory where backup files will be written.

        Returns:
            Path of the backup file created.

        Raises:
            RuntimeError: If backup_dir cannot be created or backup fails.
        """
        import sqlite3 as _sqlite3

        try:
            os.makedirs(backup_dir, mode=0o700, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"Cannot create backup directory {backup_dir}: {e}") from e

        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"state_{ts}.sqlite3")

        with self._lock:
            src = self._connect()
            try:
                dst = _sqlite3.connect(backup_path)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
            finally:
                src.close()

        # Set restrictive permissions on backup file
        try:
            os.chmod(backup_path, 0o600)
        except OSError:
            pass

        # Rotate: keep only the most recent 7 backups
        try:
            existing = sorted(
                (f for f in os.listdir(backup_dir) if f.startswith("state_") and f.endswith(".sqlite3")),
                reverse=True,
            )
            for old_file in existing[7:]:
                try:
                    os.unlink(os.path.join(backup_dir, old_file))
                except OSError:
                    pass
        except OSError:
            pass

        return backup_path
