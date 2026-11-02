"""Unit tests for the in-memory session store and login limiter."""

import unittest

from core.expiring_store import ExpiringStore
from core.ratelimit import SlidingWindowLimiter


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class ExpiringStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = ExpiringStore(ttl_seconds=10, max_entries=3, clock=self.clock)

    def test_values_expire_after_ttl(self):
        self.store["a"] = "game"
        self.assertEqual(self.store["a"], "game")
        self.clock.now = 9
        self.assertIn("a", self.store)
        self.clock.now = 10
        self.assertNotIn("a", self.store)
        self.assertIsNone(self.store.get("a"))

    def test_reads_refresh_the_idle_timer(self):
        self.store["a"] = "game"
        self.clock.now = 9
        self.assertEqual(self.store.get("a"), "game")
        self.clock.now = 15
        self.assertIn("a", self.store)

    def test_capacity_evicts_least_recently_set(self):
        for key in ("a", "b", "c"):
            self.clock.now += 1
            self.store[key] = key
        self.clock.now += 1
        self.store["d"] = "d"
        self.assertNotIn("a", self.store)
        self.assertEqual(len(self.store), 3)

    def test_pop_and_delete(self):
        self.store["a"] = 1
        self.assertEqual(self.store.pop("a"), 1)
        self.assertIsNone(self.store.pop("a"))
        with self.assertRaises(KeyError):
            del self.store["a"]


class SlidingWindowLimiterTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.limiter = SlidingWindowLimiter(limit=2, window_seconds=60, clock=self.clock)

    def test_limit_is_reached_after_recording(self):
        key = "ip:user"
        self.assertFalse(self.limiter.is_limited(key))
        self.limiter.record(key)
        self.assertFalse(self.limiter.is_limited(key))
        self.limiter.record(key)
        self.assertTrue(self.limiter.is_limited(key))

    def test_window_slides(self):
        key = "ip:user"
        self.limiter.record(key)
        self.limiter.record(key)
        self.assertTrue(self.limiter.is_limited(key))
        self.clock.now = 61
        self.assertFalse(self.limiter.is_limited(key))

    def test_clear_resets_key(self):
        self.limiter.record("k")
        self.limiter.record("k")
        self.limiter.clear("k")
        self.assertFalse(self.limiter.is_limited("k"))


if __name__ == "__main__":
    unittest.main()
