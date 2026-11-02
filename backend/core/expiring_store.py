"""Thread-safe TTL mapping for per-process game sessions.

The previous plain ``dict`` grew without bound: every visitor created an entry
that stayed until the process restarted.  Entries now expire after a period of
inactivity and the store evicts the least recently seen entry when it is full.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Iterator


class ExpiringStore:
    def __init__(
        self,
        ttl_seconds: float,
        max_entries: int = 5000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._ttl = float(ttl_seconds)
        self._max = int(max_entries)
        self._clock = clock
        self._items: dict[str, tuple[Any, float]] = {}
        self._lock = threading.RLock()

    def _now(self) -> float:
        return self._clock()

    def _alive(self, key: str, now: float) -> bool:
        entry = self._items.get(key)
        if entry is None:
            return False
        if now - entry[1] >= self._ttl:
            del self._items[key]
            return False
        return True

    def _evict_oldest(self) -> None:
        if not self._items:
            return
        oldest = min(self._items, key=lambda key: self._items[key][1])
        del self._items[oldest]

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            now = self._now()
            if not self._alive(key, now):
                return default
            value, _seen = self._items[key]
            self._items[key] = (value, now)
            return value

    def __getitem__(self, key: str) -> Any:
        with self._lock:
            now = self._now()
            if not self._alive(key, now):
                raise KeyError(key)
            value, _seen = self._items[key]
            self._items[key] = (value, now)
            return value

    def __setitem__(self, key: str, value: Any) -> None:
        with self._lock:
            now = self._now()
            if key not in self._items:
                while len(self._items) >= self._max:
                    self._evict_oldest()
            self._items[key] = (value, now)

    def __contains__(self, key: str) -> bool:
        with self._lock:
            return self._alive(key, self._now())

    def pop(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if not self._alive(key, self._now()):
                return default
            return self._items.pop(key)[0]

    def __delitem__(self, key: str) -> None:
        with self._lock:
            if not self._alive(key, self._now()):
                raise KeyError(key)
            del self._items[key]

    def __len__(self) -> int:
        with self._lock:
            now = self._now()
            return sum(1 for key in list(self._items) if self._alive(key, now))

    def __iter__(self) -> Iterator[str]:
        with self._lock:
            now = self._now()
            return iter([key for key in list(self._items) if self._alive(key, now)])

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
