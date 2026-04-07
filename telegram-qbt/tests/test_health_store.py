"""Tests for Store health event CRUD methods."""

from __future__ import annotations

import json

from patchy_bot.store import Store


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
        from patchy_bot.utils import now_ts

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
