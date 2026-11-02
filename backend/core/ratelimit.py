"""In-memory sliding-window limiter for login and other cheap-to-abuse routes."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Deque


class SlidingWindowLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._limit = int(limit)
        self._window = float(window_seconds)
        self._clock = clock
        self._events: dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def _trim(self, key: str, now: float) -> Deque[float]:
        events = self._events.setdefault(key, deque())
        cutoff = now - self._window
        while events and events[0] <= cutoff:
            events.popleft()
        return events

    def is_limited(self, key: str) -> bool:
        with self._lock:
            return len(self._trim(key, self._clock())) >= self._limit

    def record(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            self._trim(key, now).append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)
