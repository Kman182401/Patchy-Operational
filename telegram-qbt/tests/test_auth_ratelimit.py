"""
Tests for the authentication system and rate limiter.

Covers:
- RateLimiter sliding window behavior
- Store auth: unlock, lock, session TTL
- Store brute-force: failure counting, lockout, time-window reset
- Store auth failure clearing
"""

from __future__ import annotations

import time
from typing import Any

from qbt_telegram_bot import RateLimiter, Store, now_ts

# ---------------------------------------------------------------------------
# RateLimiter tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_allows_requests_under_limit(self) -> None:
        rl = RateLimiter(limit=5, window_s=60.0)
        for _ in range(5):
            assert rl.is_allowed(user_id=1) is True

    def test_blocks_requests_over_limit(self) -> None:
        rl = RateLimiter(limit=3, window_s=60.0)
        for _ in range(3):
            assert rl.is_allowed(user_id=1) is True
        assert rl.is_allowed(user_id=1) is False

    def test_different_users_have_independent_limits(self) -> None:
        rl = RateLimiter(limit=2, window_s=60.0)
        assert rl.is_allowed(user_id=1) is True
        assert rl.is_allowed(user_id=1) is True
        assert rl.is_allowed(user_id=1) is False
        # User 2 should still have their full quota
        assert rl.is_allowed(user_id=2) is True
        assert rl.is_allowed(user_id=2) is True

    def test_window_expires_and_allows_again(self) -> None:
        rl = RateLimiter(limit=2, window_s=0.1)  # 100ms window
        assert rl.is_allowed(user_id=1) is True
        assert rl.is_allowed(user_id=1) is True
        assert rl.is_allowed(user_id=1) is False
        time.sleep(0.15)  # Wait for window to expire
        assert rl.is_allowed(user_id=1) is True

    def test_check_within_limit_does_not_consume_quota(self) -> None:
        rl = RateLimiter(limit=2, window_s=60.0)
        # Check without consuming
        assert rl._check_within_limit(user_id=1) is True
        assert rl._check_within_limit(user_id=1) is True
        # Still have full quota
        assert rl.is_allowed(user_id=1) is True
        assert rl.is_allowed(user_id=1) is True
        # Now exhausted
        assert rl.is_allowed(user_id=1) is False
        assert rl._check_within_limit(user_id=1) is False

    def test_reset_clears_user_quota(self) -> None:
        rl = RateLimiter(limit=2, window_s=60.0)
        assert rl.is_allowed(user_id=1) is True
        assert rl.is_allowed(user_id=1) is True
        assert rl.is_allowed(user_id=1) is False
        rl.reset(user_id=1)
        assert rl.is_allowed(user_id=1) is True

    def test_reset_does_not_affect_other_users(self) -> None:
        rl = RateLimiter(limit=1, window_s=60.0)
        assert rl.is_allowed(user_id=1) is True
        assert rl.is_allowed(user_id=2) is True
        assert rl.is_allowed(user_id=1) is False
        assert rl.is_allowed(user_id=2) is False
        rl.reset(user_id=1)
        assert rl.is_allowed(user_id=1) is True
        assert rl.is_allowed(user_id=2) is False


# ---------------------------------------------------------------------------
# Store: unlock / lock / session tests
# ---------------------------------------------------------------------------


class TestStoreAuthSessions:
    def test_unlock_then_is_unlocked(self, tmp_path: Any) -> None:
        store = Store(str(tmp_path / "auth.sqlite3"))
        assert store.is_unlocked(99) is False
        store.unlock_user(99, ttl_s=0)  # permanent
        assert store.is_unlocked(99) is True

    def test_lock_removes_session(self, tmp_path: Any) -> None:
        store = Store(str(tmp_path / "auth.sqlite3"))
        store.unlock_user(33, ttl_s=0)
        assert store.is_unlocked(33) is True
        store.lock_user(33)
        assert store.is_unlocked(33) is False

    def test_expired_session_is_not_unlocked(self, tmp_path: Any) -> None:
        """A session with unlocked_until in the past should return False."""
        store = Store(str(tmp_path / "auth.sqlite3"))
        # Directly insert an already-expired record
        with store._create_connection() as conn:
            expired_ts = now_ts() - 1
            conn.execute(
                "INSERT INTO user_auth(user_id, unlocked_until, updated_at) VALUES(?,?,?)",
                (7, expired_ts, now_ts()),
            )
            conn.commit()
        assert store.is_unlocked(7) is False

    def test_permanent_unlock_uses_zero_sentinel(self, tmp_path: Any) -> None:
        store = Store(str(tmp_path / "auth.sqlite3"))
        until = store.unlock_user(42, ttl_s=0)
        assert until == 0  # sentinel for permanent
        assert store.is_unlocked(42) is True

    def test_timed_unlock_sets_future_timestamp(self, tmp_path: Any) -> None:
        store = Store(str(tmp_path / "auth.sqlite3"))
        until = store.unlock_user(42, ttl_s=3600)
        assert until > now_ts()
        assert store.is_unlocked(42) is True


# ---------------------------------------------------------------------------
# Store: brute-force lockout tests
# ---------------------------------------------------------------------------


class TestStoreBruteForce:
    def test_failures_below_max_do_not_lock(self, tmp_path: Any) -> None:
        store = Store(str(tmp_path / "auth.sqlite3"))
        for _ in range(4):
            locked = store.record_auth_failure(user_id=55, max_attempts=5, lockout_s=900)
            assert locked is False
        assert store.is_auth_locked(55) is False

    def test_fifth_failure_triggers_lockout(self, tmp_path: Any) -> None:
        store = Store(str(tmp_path / "auth.sqlite3"))
        for _ in range(4):
            store.record_auth_failure(user_id=55, max_attempts=5, lockout_s=900)
        locked = store.record_auth_failure(user_id=55, max_attempts=5, lockout_s=900)
        assert locked is True
        assert store.is_auth_locked(55) is True

    def test_already_locked_returns_true_immediately(self, tmp_path: Any) -> None:
        store = Store(str(tmp_path / "auth.sqlite3"))
        # Lock the user
        for _ in range(5):
            store.record_auth_failure(user_id=55, max_attempts=5, lockout_s=900)
        # Additional failure on locked user returns True without incrementing
        assert store.record_auth_failure(user_id=55, max_attempts=5, lockout_s=900) is True

    def test_clear_auth_failures_resets_counter(self, tmp_path: Any) -> None:
        store = Store(str(tmp_path / "auth.sqlite3"))
        for _ in range(3):
            store.record_auth_failure(user_id=55, max_attempts=5, lockout_s=900)
        store.clear_auth_failures(55)
        # Counter should be reset — 4 more failures should NOT trigger lockout
        for _ in range(4):
            locked = store.record_auth_failure(user_id=55, max_attempts=5, lockout_s=900)
            assert locked is False

    def test_time_window_resets_counter_for_stale_failures(self, tmp_path: Any) -> None:
        """Failures older than window_s should not count toward lockout."""
        store = Store(str(tmp_path / "auth.sqlite3"))
        # Insert 4 failures with first_fail_at far in the past
        with store._create_connection() as conn:
            old_ts = now_ts() - 7200  # 2 hours ago — outside default 1h window
            conn.execute(
                "INSERT INTO auth_attempts(user_id, fail_count, first_fail_at, locked_until) VALUES(?,?,?,?)",
                (77, 4, old_ts, 0),
            )
            conn.commit()
        # The 5th failure should RESET the counter (window expired), not trigger lockout
        locked = store.record_auth_failure(user_id=77, max_attempts=5, lockout_s=900, window_s=3600)
        assert locked is False
        assert store.is_auth_locked(77) is False

    def test_failures_within_window_accumulate_normally(self, tmp_path: Any) -> None:
        """Failures within the time window should still accumulate to lockout."""
        store = Store(str(tmp_path / "auth.sqlite3"))
        # Insert 4 failures with first_fail_at within the window
        with store._create_connection() as conn:
            recent_ts = now_ts() - 60  # 1 minute ago — inside default 1h window
            conn.execute(
                "INSERT INTO auth_attempts(user_id, fail_count, first_fail_at, locked_until) VALUES(?,?,?,?)",
                (88, 4, recent_ts, 0),
            )
            conn.commit()
        # The 5th failure should trigger lockout (within window)
        locked = store.record_auth_failure(user_id=88, max_attempts=5, lockout_s=900, window_s=3600)
        assert locked is True
        assert store.is_auth_locked(88) is True

    def test_lockout_does_not_affect_other_users(self, tmp_path: Any) -> None:
        store = Store(str(tmp_path / "auth.sqlite3"))
        for _ in range(5):
            store.record_auth_failure(user_id=55, max_attempts=5, lockout_s=900)
        assert store.is_auth_locked(55) is True
        assert store.is_auth_locked(99) is False

    def test_unlock_after_successful_auth_clears_failures(self, tmp_path: Any) -> None:
        """Simulates the real flow: user fails 3 times, then succeeds."""
        store = Store(str(tmp_path / "auth.sqlite3"))
        for _ in range(3):
            store.record_auth_failure(user_id=10, max_attempts=5, lockout_s=900)
        # Successful auth clears failures
        store.clear_auth_failures(10)
        store.unlock_user(10, ttl_s=0)
        assert store.is_unlocked(10) is True
        assert store.is_auth_locked(10) is False
        # 4 more failures should NOT lock (counter was cleared)
        for _ in range(4):
            locked = store.record_auth_failure(user_id=10, max_attempts=5, lockout_s=900)
            assert locked is False
