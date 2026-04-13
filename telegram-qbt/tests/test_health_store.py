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


# ---------------------------------------------------------------------------
# Session 5: malware stats aggregation queries
# ---------------------------------------------------------------------------


class TestMalwareStats:
    """Session 5: get_malware_stats, get_malware_block_count, get_user_malware_blocks."""

    def test_get_malware_stats_empty(self) -> None:
        """Empty store → zero totals, empty dicts/lists."""
        s = Store(":memory:")
        stats = s.get_malware_stats()
        assert stats["total_blocks"] == 0
        assert stats["by_stage"] == {}
        assert stats["by_tier"] == {}
        assert stats["top_signals"] == []
        assert stats["recent"] == []
        s.close()

    def test_get_malware_stats_with_data(self) -> None:
        """3 heterogeneous blocks → correct totals, counts, ordered recent."""
        s = Store(":memory:")
        sig_a = [
            {"signal_id": "ext.executable", "points": 100, "detail": "x"},
            {"signal_id": "fname.suspicious", "points": 25, "detail": "y"},
        ]
        sig_b = [{"signal_id": "kw.codec", "points": 20, "detail": "codec"}]
        sig_c = [{"signal_id": "uploader.anon", "points": 15, "detail": "anon"}]
        s.log_malware_block(
            "a" * 40,
            "First.Movie.mkv",
            "search",
            ["r1"],
            risk_score=90,
            tier="blocked",
            signals=sig_a,
        )
        s.log_malware_block(
            "b" * 40,
            "Second.Movie.mkv",
            "download",
            ["r2"],
            risk_score=55,
            tier="caution",
            signals=sig_b,
        )
        s.log_malware_block(
            "c" * 40,
            "Third.Movie.mkv",
            "pre_add",
            ["r3"],
            risk_score=30,
            tier="clean",
            signals=sig_c,
        )

        stats = s.get_malware_stats()
        assert stats["total_blocks"] == 3
        assert stats["by_stage"] == {"search": 1, "download": 1, "pre_add": 1}
        assert stats["by_tier"] == {"blocked": 1, "caution": 1, "clean": 1}

        recent = stats["recent"]
        assert len(recent) == 3
        # Ordered DESC by blocked_at — since all three share now_ts(),
        # SQLite will return them by id DESC (inserted last → first).
        # At minimum, the set of names must match.
        names = {row["torrent_name"] for row in recent}
        assert names == {"First.Movie.mkv", "Second.Movie.mkv", "Third.Movie.mkv"}
        s.close()

    def test_get_malware_stats_time_filter(self) -> None:
        """since_ts filter excludes backdated rows."""
        s = Store(":memory:")
        s.log_malware_block("1" * 40, "Recent", "search", ["r"])
        s.log_malware_block("2" * 40, "Ancient", "search", ["r"])
        now = now_ts()
        with s._lock:
            s._conn.execute(
                "UPDATE malware_scan_log SET blocked_at = ? WHERE torrent_hash = ?",
                (now - 1000 * 86400, "2" * 40),
            )
            s._conn.commit()
        # Filter for anything in the last day → only "Recent".
        stats = s.get_malware_stats(since_ts=now - 86400)
        assert stats["total_blocks"] == 1
        assert stats["recent"][0]["torrent_name"] == "Recent"
        s.close()

    def test_get_malware_stats_stage_filter(self) -> None:
        """stage filter returns only exact matches."""
        s = Store(":memory:")
        s.log_malware_block("1" * 40, "M1", "search", ["r"])
        s.log_malware_block("2" * 40, "M2", "pre_add", ["r"])
        s.log_malware_block("3" * 40, "M3", "pre_add", ["r"])
        s.log_malware_block("4" * 40, "M4", "download", ["r"])

        stats = s.get_malware_stats(stage="pre_add")
        assert stats["total_blocks"] == 2
        assert stats["by_stage"] == {"pre_add": 2}
        names = {row["torrent_name"] for row in stats["recent"]}
        assert names == {"M2", "M3"}
        s.close()

    def test_top_signals_aggregation(self) -> None:
        """Overlapping signal_ids aggregate and sort desc by count."""
        s = Store(":memory:")
        # ext.executable appears 3x, fname.suspicious 2x, kw.codec 1x.
        s.log_malware_block(
            "1" * 40,
            "M1",
            "search",
            ["r"],
            signals=[
                {"signal_id": "ext.executable", "points": 100, "detail": "x"},
                {"signal_id": "fname.suspicious", "points": 25, "detail": "y"},
            ],
        )
        s.log_malware_block(
            "2" * 40,
            "M2",
            "search",
            ["r"],
            signals=[
                {"signal_id": "ext.executable", "points": 100, "detail": "x"},
                {"signal_id": "fname.suspicious", "points": 25, "detail": "y"},
                {"signal_id": "kw.codec", "points": 20, "detail": "z"},
            ],
        )
        s.log_malware_block(
            "3" * 40,
            "M3",
            "search",
            ["r"],
            signals=[{"signal_id": "ext.executable", "points": 100, "detail": "x"}],
        )

        stats = s.get_malware_stats()
        top = stats["top_signals"]
        # Must be sorted descending by count.
        counts = [count for _, count in top]
        assert counts == sorted(counts, reverse=True)
        as_dict = dict(top)
        assert as_dict["ext.executable"] == 3
        assert as_dict["fname.suspicious"] == 2
        assert as_dict["kw.codec"] == 1
        # First entry must be the highest-count signal.
        assert top[0][0] == "ext.executable"
        assert top[0][1] == 3
        s.close()

    def test_top_signals_malformed_json_skipped(self) -> None:
        """Malformed signals_json rows are defensively skipped; valid rows still counted."""
        s = Store(":memory:")
        s.log_malware_block(
            "1" * 40,
            "Good",
            "search",
            ["r"],
            signals=[{"signal_id": "ext.executable", "points": 100, "detail": "x"}],
        )
        # Now insert a row with garbage signals_json via raw SQL.
        with s._lock:
            s._conn.execute(
                "INSERT INTO malware_scan_log "
                "(torrent_hash, torrent_name, stage, reasons, blocked_at, signals_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("2" * 40, "Broken", "search", json.dumps(["r"]), now_ts(), "{not valid json"),
            )
            # Also insert one with a non-list JSON payload (defensive path).
            s._conn.execute(
                "INSERT INTO malware_scan_log "
                "(torrent_hash, torrent_name, stage, reasons, blocked_at, signals_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("3" * 40, "WrongShape", "search", json.dumps(["r"]), now_ts(), '{"not":"a list"}'),
            )
            s._conn.commit()

        # Query must not raise.
        stats = s.get_malware_stats()
        assert stats["total_blocks"] == 3  # all 3 rows counted
        top = dict(stats["top_signals"])
        # Only the valid row's signal counts.
        assert top == {"ext.executable": 1}
        s.close()

    def test_top_signals_null_tier_bucketed_unknown(self) -> None:
        """Rows with tier=NULL bucket into by_tier['unknown']."""
        s = Store(":memory:")
        s.log_malware_block("1" * 40, "NoTier", "search", ["r"])  # tier defaults to None
        s.log_malware_block(
            "2" * 40,
            "Tiered",
            "search",
            ["r"],
            tier="blocked",
        )
        stats = s.get_malware_stats()
        assert stats["by_tier"]["unknown"] == 1
        assert stats["by_tier"]["blocked"] == 1
        s.close()

    def test_get_user_malware_blocks(self) -> None:
        """user_id filter isolates rows to the specified user."""
        s = Store(":memory:")
        s.log_malware_block("1" * 40, "User1-A", "search", ["r"], user_id=1)
        s.log_malware_block("2" * 40, "User1-B", "search", ["r"], user_id=1)
        s.log_malware_block("3" * 40, "User2-A", "search", ["r"], user_id=2)
        s.log_malware_block("4" * 40, "NoUser", "search", ["r"])  # user_id=None

        user1_rows = s.get_user_malware_blocks(1)
        assert len(user1_rows) == 2
        assert {r["torrent_name"] for r in user1_rows} == {"User1-A", "User1-B"}

        user2_rows = s.get_user_malware_blocks(2)
        assert len(user2_rows) == 1
        assert user2_rows[0]["torrent_name"] == "User2-A"

        # No rows for an unknown user.
        assert s.get_user_malware_blocks(999) == []
        s.close()

    def test_get_malware_block_count(self) -> None:
        """Count respects since_ts filter; future cutoff returns 0."""
        s = Store(":memory:")
        s.log_malware_block("1" * 40, "M1", "search", ["r"])
        s.log_malware_block("2" * 40, "M2", "download", ["r"])
        s.log_malware_block("3" * 40, "M3", "pre_add", ["r"])
        assert s.get_malware_block_count() == 3
        # since_ts in the future → nothing matches.
        assert s.get_malware_block_count(since_ts=now_ts() + 10_000) == 0
        # since_ts in the past → all match.
        assert s.get_malware_block_count(since_ts=now_ts() - 10_000) == 3
        s.close()
