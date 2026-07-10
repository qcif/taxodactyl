"""Unit tests for src.utils.coalesce.

Tests use ``fakeredis`` to avoid a real Redis dependency. The polling
interval is monkey-patched short so concurrent tests run in seconds.
"""

import threading
import time
import unittest
from unittest.mock import patch

import fakeredis

from src.utils import cache, coalesce as coalesce_module
from src.utils.coalesce import coalesce


def _unique_key(suffix: str) -> str:
    """Return a cache key unique to this test invocation."""
    return cache.keyhash('test_coalesce', suffix, time.monotonic_ns())


class TestCoalesceFallback(unittest.TestCase):
    """Fallback behaviour when Redis is not available."""

    def setUp(self):
        coalesce_module.reset_connection()

    def test_no_redis_runs_fetch_directly(self):
        """With no Redis, coalesce still caches and returns."""
        with patch.object(coalesce_module, '_get_redis', return_value=None):
            key = _unique_key('no_redis')
            calls = []

            def fetch():
                calls.append(1)
                return 'result'

            self.assertEqual(coalesce(key, fetch), 'result')
            self.assertEqual(len(calls), 1)
            self.assertEqual(cache.get(key), 'result')

    def test_cache_hit_skips_fetch(self):
        """Cache hits return without invoking fetch_fn or Redis."""
        with patch.object(coalesce_module, '_get_redis', return_value=None):
            key = _unique_key('cache_hit')
            cache.put(key, 'pre-cached')

            def fetch():
                self.fail("fetch_fn must not be called on cache hit")

            self.assertEqual(coalesce(key, fetch), 'pre-cached')

    def test_redis_set_failure_falls_back(self):
        """If Redis raises during SET, coalesce still fetches directly."""
        fake = fakeredis.FakeRedis()

        def boom(*args, **kwargs):
            raise ConnectionError("simulated Redis outage")

        with patch.object(fake, 'set', side_effect=boom), \
                patch.object(coalesce_module, '_get_redis', return_value=fake):
            key = _unique_key('redis_outage')
            calls = []

            def fetch():
                calls.append(1)
                return 42

            self.assertEqual(coalesce(key, fetch), 42)
            self.assertEqual(len(calls), 1)


class TestCoalesceWithRedis(unittest.TestCase):
    """Coalescing behaviour with a (fake) Redis backend."""

    def setUp(self):
        coalesce_module.reset_connection()
        self.fake_redis = fakeredis.FakeRedis()
        self._get_redis_patch = patch.object(
            coalesce_module, '_get_redis', return_value=self.fake_redis,
        )
        self._get_redis_patch.start()
        # Speed up the wait loop for concurrent tests.
        self._poll_patch = patch.object(
            coalesce_module, 'WAIT_POLL_INTERVAL_SECONDS', 0.02,
        )
        self._poll_patch.start()
        self._jitter_patch = patch.object(
            coalesce_module, 'WAIT_POLL_JITTER_SECONDS', 0.0,
        )
        self._jitter_patch.start()

    def tearDown(self):
        self._get_redis_patch.stop()
        self._poll_patch.stop()
        self._jitter_patch.stop()
        coalesce_module.reset_connection()

    def test_leader_fetches_and_releases_lease(self):
        """Single caller: fetch runs, result cached, lease cleared."""
        key = _unique_key('leader_only')

        def fetch():
            return {'value': 1}

        self.assertEqual(coalesce(key, fetch), {'value': 1})
        self.assertEqual(cache.get(key), {'value': 1})
        # Lease key should be deleted after release.
        self.assertFalse(
            self.fake_redis.exists(
                f"{coalesce_module.LEASE_KEY_PREFIX}{key}"
            )
        )

    def test_concurrent_callers_share_one_fetch(self):
        """N concurrent callers should invoke fetch_fn exactly once."""
        key = _unique_key('shared_fetch')
        call_count = 0
        call_lock = threading.Lock()
        fetch_started = threading.Event()
        fetch_release = threading.Event()

        def fetch():
            nonlocal call_count
            with call_lock:
                call_count += 1
            fetch_started.set()
            # Block until waiters are queued so they truly coalesce.
            fetch_release.wait(timeout=5)
            return 'shared'

        results = []
        results_lock = threading.Lock()

        def worker():
            r = coalesce(key, fetch)
            with results_lock:
                results.append(r)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        self.assertTrue(fetch_started.wait(timeout=2),
                        "leader's fetch never started")
        # Give late waiters time to enqueue.
        time.sleep(0.1)
        fetch_release.set()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(call_count, 1,
                         "fetch_fn should run exactly once across waiters")
        self.assertEqual(results, ['shared'] * 5)

    def test_waiter_takes_over_when_lease_expires(self):
        """If the leader's lease vanishes without a cached result, a"""
        """waiter promotes itself and runs fetch."""
        key = _unique_key('lease_expiry')
        lease_key = f"{coalesce_module.LEASE_KEY_PREFIX}{key}"
        # Simulate a dead leader: lease present, no cached result yet.
        self.fake_redis.set(lease_key, b'1', ex=120)

        calls = []

        def fetch():
            calls.append(1)
            return 'taken-over'

        def kill_lease():
            time.sleep(0.05)
            self.fake_redis.delete(lease_key)

        threading.Thread(target=kill_lease).start()
        result = coalesce(key, fetch)
        self.assertEqual(result, 'taken-over')
        self.assertEqual(len(calls), 1)
        self.assertEqual(cache.get(key), 'taken-over')

    def test_leader_exception_propagates_and_releases_lease(self):
        """A failing fetch must release the lease so the next caller"""
        """can retry, and the exception must bubble up."""
        key = _unique_key('leader_fails')
        lease_key = f"{coalesce_module.LEASE_KEY_PREFIX}{key}"

        def boom():
            raise RuntimeError("upstream failed")

        with self.assertRaises(RuntimeError):
            coalesce(key, boom)
        self.assertFalse(self.fake_redis.exists(lease_key))
        self.assertIsNone(cache.get(key))


if __name__ == '__main__':
    unittest.main()
