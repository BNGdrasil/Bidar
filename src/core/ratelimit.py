# --------------------------------------------------------------------------
# Minimal in-process rate limiter
#
# This is a brute-force mitigation for the login endpoint only. It is per
# worker process and resets on restart, so it is not a quota mechanism. A
# shared limiter at the edge remains the durable control.
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import time
from collections import OrderedDict, deque
from threading import Lock
from typing import Deque

# Keys older than this are dropped so the dictionary cannot grow without bound.
WINDOW_SECONDS = 60.0

# Hard ceiling on tracked keys. Once reached, the least recently touched keys
# are evicted, so a flood of distinct source addresses cannot grow the map
# without bound. Eviction forgives the evicted key's earlier attempts, which
# is acceptable for a mitigation: the durable control is the edge limiter.
MAX_TRACKED_KEYS = 10000


class SlidingWindowLimiter:
    """Count events per key inside a fixed sliding window."""

    def __init__(
        self,
        window_seconds: float = WINDOW_SECONDS,
        max_tracked_keys: int = MAX_TRACKED_KEYS,
    ) -> None:
        """Create a limiter tracking events over the given window."""
        self._window = window_seconds
        self._max_tracked_keys = max_tracked_keys
        # Ordered by last touch: the oldest entry is the first one.
        self._events: "OrderedDict[str, Deque[float]]" = OrderedDict()
        self._lock = Lock()

    def _prune(self, now: float) -> None:
        stale = [
            key
            for key, events in self._events.items()
            if not events or now - events[-1] > self._window
        ]
        for key in stale:
            self._events.pop(key, None)

    def _enforce_capacity(self) -> None:
        while len(self._events) > self._max_tracked_keys:
            self._events.popitem(last=False)

    def hit(self, key: str, limit: int) -> bool:
        """Record an event and report whether it is still within the limit.

        Args:
            key: Identity of the caller, usually the client IP.
            limit: Maximum number of events per window. Zero or less disables
                the limiter.

        Returns:
            bool: True when the call is allowed, False when the limit is hit.
        """
        if limit <= 0:
            return True

        now = time.monotonic()
        with self._lock:
            if len(self._events) >= self._max_tracked_keys:
                # Cheap pass first: drop everything that has already expired.
                self._prune(now)

            events = self._events.setdefault(key, deque())
            self._events.move_to_end(key)

            while events and now - events[0] > self._window:
                events.popleft()

            allowed = len(events) < limit
            if allowed:
                events.append(now)

            # Runs after the insert so the ceiling holds even when every key
            # is still fresh and _prune could not free anything.
            self._enforce_capacity()
            return allowed

    def reset(self) -> None:
        """Drop all tracked state. Used by tests."""
        with self._lock:
            self._events.clear()


# Applied to POST /auth/token only, so /health and /metrics are never limited.
login_limiter = SlidingWindowLimiter()
