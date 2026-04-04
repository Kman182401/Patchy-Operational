"""Per-user sliding-window rate limiter."""

from __future__ import annotations

import collections
import threading
import time


class RateLimiter:
    """Per-user sliding-window rate limiter.

    Tracks command timestamps per user in a deque. On each call, flushes
    timestamps older than the window and checks against the limit.
    Thread-safe for the current sequential-update model; the lock also
    protects future concurrent_updates=True migration.
    """

    def __init__(self, limit: int = 20, window_s: float = 60.0) -> None:
        self.limit = limit
        self.window_s = window_s
        self._buckets: dict[int, collections.deque[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, user_id: int) -> bool:
        """Return True if the user is within their rate limit, False if exceeded."""
        now = time.monotonic()
        cutoff = now - self.window_s
        with self._lock:
            bucket = self._buckets.setdefault(user_id, collections.deque())
            # Remove timestamps outside the sliding window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    def _check_within_limit(self, user_id: int) -> bool:
        """Check if user is within limit WITHOUT recording a new request."""
        now = time.monotonic()
        cutoff = now - self.window_s
        with self._lock:
            bucket = self._buckets.get(user_id)
            if bucket is None:
                return True
            # Count non-expired entries
            count = sum(1 for ts in bucket if ts >= cutoff)
            return count < self.limit

    def reset(self, user_id: int) -> None:
        """Clear rate limit state for a user (e.g., after auth unlock)."""
        with self._lock:
            self._buckets.pop(user_id, None)

    def prune_stale(self) -> int:
        """Remove buckets where all timestamps have expired. Returns count removed."""
        now = time.monotonic()
        cutoff = now - self.window_s
        removed = 0
        with self._lock:
            stale_ids = [uid for uid, bucket in self._buckets.items() if not bucket or bucket[-1] < cutoff]
            for uid in stale_ids:
                del self._buckets[uid]
                removed += 1
        return removed

