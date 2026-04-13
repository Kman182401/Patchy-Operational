"""Tests for Store health event CRUD methods."""

from __future__ import annotations

import json
import sqlite3

import pytest

from patchy_bot.store import Store
from patchy_bot.utils import now_ts


class TestHealthEvents:
    def test_log_and_retrieve(self):
        s = Store(":memory:")
        eid = s.log_health_event(123, "abc", "stall_detected", "warn", json.dumps({"test": True}), "MyTorrent")
        assert isinstance(eid, int) and eid > 0
        events = s.get_health_events(123)
        assert len(events) == 1
        assert events[0]["event_type"] == "stall_detected"
        assert events[0]["severity"] == "warn"
        assert events[0]["torrent_name"] == "MyTorrent"
        assert events[0]["torrent_hash"] == "abc"
        s.close()

    def test_log_without_hash(self):
        s = Store(":memory:")
        eid = s.log_health_event(1, None, "preflight_fail", "error", "{}", "Test")
        assert eid > 0
        events = s.get_health_events(1)
        assert len(events) == 1
        assert events[0]["torrent_hash"] is None
        s.close()

    def test_filter_by_type(self):
        s = Store(":memory:")
        s.log_health_event(1, "a", "stall_detected", "warn", "{}", "T1")
        s.log_health_event(1, "b", "preflight_fail", "error", "{}", "T2")
        s.log_health_event(1, "c", "stall_detected", "warn", "{}", "T3")
        events = s.get_health_events(1, event_type="preflight_fail")
        assert len(events) == 1
        assert events[0]["event_type"] == "preflight_fail"
        all_events = s.get_health_events(1)
        assert len(all_events) == 3
        s.close()

    def test_filter_by_since_ts(self):
        s = Store(":memory:")
        s.log_health_event(1, "a", "stall_detected", "warn", "{}", "T1")
        future_ts = now_ts() + 100
        events = s.get_health_events(1, since_ts=future_ts)
        assert len(events) == 0
        events = s.get_health_events(1, since_ts=0)
        assert len(events) == 1
        s.close()

    def test_limit(self):
        s = Store(":memory:")
        for i in range(10):
            s.log_health_event(1, f"h{i}", "stall_detected", "warn", "{}", f"T{i}")
        events = s.get_health_events(1, limit=3)
        assert len(events) == 3
        s.close()

    def test_cleanup_retains_recent(self):
        s = Store(":memory:")
        s.log_health_event(1, "recent", "stall_detected", "warn", "{}", "Recent")
        count = s.cleanup_old_health_events(30)
        assert count == 0
        events = s.get_health_events(1)
        assert len(events) == 1
        s.close()

    def test_user_isolation(self):
        s = Store(":memory:")
        s.log_health_event(1, "a", "stall_detected", "warn", "{}", "User1")
        s.log_health_event(2, "b", "stall_detected", "warn", "{}", "User2")
        assert len(s.get_health_events(1)) == 1
        assert len(s.get_health_events(2)) == 1
        assert len(s.get_health_events(999)) == 0
        s.close()


# ---------------------------------------------------------------------------
# Session 4 Task 11: malware_scan_log v2 + cleanup
# ---------------------------------------------------------------------------


class TestMalwareScanLogEnhanced:
    """Session 4 data-layer upgrade: risk_score/tier/signals_json columns,
    'pre_add' stage, and retention-based cleanup."""

    def _query_all(self, store: Store) -> list[sqlite3.Row]:
        with store._lock:
            cur = store._conn.execute(
                "SELECT torrent_hash, torrent_name, stage, reasons, blocked_at, "
                "risk_score, tier, signals_json FROM malware_scan_log ORDER BY id"
            )
            return cur.fetchall()

    def test_log_with_scoring_data(self) -> None:
        """log_malware_block with risk_score, tier, signals stores all three in DB."""
        s = Store(":memory:")
        signals = [{"signal_id": "kw.codec", "points": 20, "detail": "codec keyword"}]
        s.log_malware_block(
            "a" * 40,
            "Bad.Movie.2024.mkv",
            "search",
            ["codec keyword", "suspicious uploader"],
            risk_score=75,
            tier="blocked",
            signals=signals,
        )
        rows = self._query_all(s)
        assert len(rows) == 1
        row = rows[0]
        assert row["torrent_hash"] == "a" * 40
        assert row["stage"] == "search"
        assert row["risk_score"] == 75
        assert row["tier"] == "blocked"
        assert row["signals_json"] is not None
        assert json.loads(row["signals_json"]) == signals
        assert json.loads(row["reasons"]) == ["codec keyword", "suspicious uploader"]
        s.close()

    def test_log_without_scoring_data(self) -> None:
        """Legacy 4-arg call stores NULL in the three new columns (backward compat)."""
        s = Store(":memory:")
        s.log_malware_block("b" * 40, "Legacy.Movie.mkv", "download", ["reason1"])
        rows = self._query_all(s)
        assert len(rows) == 1
        row = rows[0]
        assert row["risk_score"] is None
        assert row["tier"] is None
        assert row["signals_json"] is None
        s.close()

    def test_pre_add_stage_allowed(self) -> None:
        """stage='pre_add' passes the CHECK constraint (v2 migration)."""
        s = Store(":memory:")
        s.log_malware_block("c" * 40, "Pending.Movie.mkv", "pre_add", ["heuristic reject"])
        rows = self._query_all(s)
        assert len(rows) == 1
        assert rows[0]["stage"] == "pre_add"
        s.close()

    def test_invalid_stage_rejected(self) -> None:
        """stage='bogus' raises IntegrityError from CHECK constraint."""
        s = Store(":memory:")
        with pytest.raises(sqlite3.IntegrityError):
            s.log_malware_block("d" * 40, "Evil.Movie.mkv", "bogus", ["nope"])
        s.close()

    def test_cleanup_old_malware_logs_removes_old(self) -> None:
        """cleanup_old_malware_logs(1) deletes all aged entries, returns count."""
        s = Store(":memory:")
        s.log_malware_block("e" * 40, "M1", "search", ["r1"])
        s.log_malware_block("f" * 40, "M2", "download", ["r2"])
        s.log_malware_block("0" * 40, "M3", "pre_add", ["r3"])
        # Force every row's blocked_at into the far past so retention strips all.
        with s._lock:
            s._conn.execute("UPDATE malware_scan_log SET blocked_at = 0")
            s._conn.commit()
        deleted = s.cleanup_old_malware_logs(retention_days=1)
        assert deleted == 3
        assert self._query_all(s) == []
        s.close()

    def test_cleanup_old_malware_logs_keeps_recent(self) -> None:
        """cleanup_old_malware_logs(90) keeps yesterday entries, drops 100d-old."""
        s = Store(":memory:")
        # Insert two rows then rewrite blocked_at to simulate age.
        s.log_malware_block("1" * 40, "Recent", "search", ["r"])
        s.log_malware_block("2" * 40, "Ancient", "search", ["r"])
        now = now_ts()
        yesterday = now - 86400
        hundred_days = now - 100 * 86400
        with s._lock:
            s._conn.execute(
                "UPDATE malware_scan_log SET blocked_at = ? WHERE torrent_hash = ?",
                (yesterday, "1" * 40),
            )
            s._conn.execute(
                "UPDATE malware_scan_log SET blocked_at = ? WHERE torrent_hash = ?",
                (hundred_days, "2" * 40),
            )
            s._conn.commit()
        deleted = s.cleanup_old_malware_logs(retention_days=90)
        assert deleted == 1
        remaining = self._query_all(s)
        assert len(remaining) == 1
        assert remaining[0]["torrent_hash"] == "1" * 40
        s.close()

    def test_cleanup_old_malware_logs_retention_days(self) -> None:
        """Boundary test: 30-day retention keeps 29d-old, removes 31d-old."""
        s = Store(":memory:")
        s.log_malware_block("3" * 40, "Under", "search", ["r"])
        s.log_malware_block("4" * 40, "Over", "search", ["r"])
        now = now_ts()
        with s._lock:
            s._conn.execute(
                "UPDATE malware_scan_log SET blocked_at = ? WHERE torrent_hash = ?",
                (now - 29 * 86400, "3" * 40),
            )
            s._conn.execute(
                "UPDATE malware_scan_log SET blocked_at = ? WHERE torrent_hash = ?",
                (now - 31 * 86400, "4" * 40),
            )
            s._conn.commit()
        deleted = s.cleanup_old_malware_logs(retention_days=30)
        assert deleted == 1
        remaining = self._query_all(s)
        assert len(remaining) == 1
        assert remaining[0]["torrent_hash"] == "3" * 40
        s.close()

    def test_signals_json_roundtrip(self) -> None:
        """signals list round-trips through JSON storage without data loss."""
        s = Store(":memory:")
        signals = [
            {"signal_id": "kw.cam", "points": 30, "detail": "CAM source"},
            {"signal_id": "uploader.anon", "points": 10, "detail": "anonymous uploader"},
            {"signal_id": "size.small", "points": 15, "detail": "under 300 MB"},
        ]
        s.log_malware_block(
            "5" * 40,
            "Complex.Movie.mkv",
            "search",
            ["multi"],
            risk_score=55,
            tier="caution",
            signals=signals,
        )
        rows = self._query_all(s)
        assert len(rows) == 1
        roundtripped = json.loads(rows[0]["signals_json"])
        assert roundtripped == signals
        assert roundtripped[0]["signal_id"] == "kw.cam"
        assert roundtripped[2]["points"] == 15
        s.close()
