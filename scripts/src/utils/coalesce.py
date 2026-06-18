"""Cross-process request coalescing for cached API calls.

The cache + throttle stack has a stampede failure mode: when N concurrent
callers (across threads, processes, or Nextflow tasks on different nodes)
all check the blob cache for the same key, all miss, and all join the
throttle queue, the first request to complete writes to the cache long
after the rest have committed to making the same request. Every duplicate
holds a throttle slot, multiplying queue depth and wall-clock latency.

``coalesce`` adds a Redis "fetch lease" in front of ``fetch_fn``: the
first requester per cache key acquires the lease and runs the fetch;
others poll the cache until the leader's result lands. Only the leader
ever enters the throttle for a given key.

Activates automatically when ``config.throttle_backend == 'redis'``.
With any other backend, or if Redis is unreachable, ``coalesce`` falls
back to a plain ``cache.get`` / ``fetch_fn`` / ``cache.put`` so behaviour
is unchanged from a fresh cache miss.
"""

import logging
import random
import threading
import time
from typing import Callable, TypeVar

from . import cache
from .config import Config

logger = logging.getLogger(__name__)

T = TypeVar('T')

LEASE_KEY_PREFIX = 'coalesce:lock:'
LEASE_TTL_SECONDS = 120
WAIT_POLL_INTERVAL_SECONDS = 1.0
WAIT_POLL_JITTER_SECONDS = 0.5
WAIT_TIMEOUT_SECONDS = 180.0

_redis_conn = None
_redis_init_lock = threading.Lock()
_redis_init_attempted = False


def _get_redis():
    """Return a Redis connection if the redis throttle backend is in use.

    Returns ``None`` (and logs once) if Redis is unconfigured or the
    initial connection attempt fails, so callers can fall back to a
    direct fetch.
    """
    global _redis_conn, _redis_init_attempted
    if _redis_init_attempted:
        return _redis_conn
    with _redis_init_lock:
        if _redis_init_attempted:
            return _redis_conn
        _redis_init_attempted = True
        config = Config()
        if config.throttle_backend != 'redis':
            return None
        try:
            import redis as redis_lib
            _redis_conn = redis_lib.Redis(
                host=config.redis_host,
                port=config.redis_port,
                password=config.redis_password,
                ssl=config.redis_ssl,
                socket_connect_timeout=10,
                socket_timeout=10,
            )
        except Exception as exc:
            logger.warning(
                f"Request coalescing disabled - Redis unavailable: {exc}"
            )
            _redis_conn = None
        return _redis_conn


def reset_connection():
    """Reset the lazy Redis singleton. Intended for tests."""
    global _redis_conn, _redis_init_attempted
    with _redis_init_lock:
        _redis_conn = None
        _redis_init_attempted = False


def coalesce(
    cache_key: str,
    fetch_fn: Callable[[], T],
    task_description: str | None = None,
) -> T:
    """Run ``fetch_fn`` at most once per ``cache_key`` across processes.

    Flow:

    1. Check the cache; return on hit.
    2. Try to acquire a Redis lease ``coalesce:lock:{cache_key}`` with
       ``SET NX EX 120``. The first caller per key wins.
    3. Leader runs ``fetch_fn()``, writes the result via ``cache.put``,
       releases the lease, and returns. Other callers poll the cache
       until the leader's result appears.
    4. If the lease expires while waiters are still polling (i.e. the
       leader crashed before writing), a waiter promotes itself to leader.
    5. Hard timeout (``WAIT_TIMEOUT_SECONDS``) falls back to running
       ``fetch_fn()`` directly with a warning, to bound worst-case latency.

    ``task_description`` is a human-readable label included in HIT/MISS log
    messages. Pass something like ``"Entrez esearch: term=txid7240..."``
    so logs explain which request was cached/coalesced. Defaults to a
    short cache_key prefix.

    Falls back to a plain ``cache.get`` / ``fetch_fn`` / ``cache.put`` if
    Redis is not configured or unreachable.
    """
    label = task_description or f"key={cache_key[:12]}"

    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache HIT: {label}")
        return cached

    redis_conn = _get_redis()
    if redis_conn is None:
        logger.debug(f"Cache MISS, fetching directly: {label}")
        return _run_and_cache(cache_key, fetch_fn)

    lease_key = f"{LEASE_KEY_PREFIX}{cache_key}"
    try:
        owner = redis_conn.set(lease_key, b'1', nx=True, ex=LEASE_TTL_SECONDS)
    except Exception as exc:
        logger.warning(
            f"Coalesce lease acquire failed for {label}: {exc}."
            " Proceeding with direct fetch."
        )
        return _run_and_cache(cache_key, fetch_fn)

    if owner:
        logger.debug(f"Cache MISS, fetching as leader: {label}")
        return _run_and_cache(cache_key, fetch_fn, redis_conn, lease_key)

    logger.debug(f"Cache MISS, awaiting coalesced fetch: {label}")
    return _wait_for_leader(
        cache_key, fetch_fn, redis_conn, lease_key, label,
    )


def _run_and_cache(
    cache_key: str,
    fetch_fn: Callable[[], T],
    redis_conn=None,
    lease_key: str | None = None,
) -> T:
    """Run ``fetch_fn``, populate the cache, then release the lease."""
    try:
        result = fetch_fn()
        cache.put(cache_key, result)
        return result
    finally:
        if redis_conn is not None and lease_key is not None:
            try:
                redis_conn.delete(lease_key)
            except Exception as exc:
                logger.debug(
                    f"Coalesce lease release failed for {cache_key[:12]}..."
                    f": {exc}"
                )


def _wait_for_leader(
    cache_key: str,
    fetch_fn: Callable[[], T],
    redis_conn,
    lease_key: str,
    label: str,
) -> T:
    """Poll the cache until the leader's result lands, or take over."""
    deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        time.sleep(
            WAIT_POLL_INTERVAL_SECONDS
            + random.uniform(0, WAIT_POLL_JITTER_SECONDS)
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        # Lease gone but no result - leader probably crashed; try to take over
        try:
            lease_exists = redis_conn.exists(lease_key)
        except Exception:
            lease_exists = True  # Be conservative; keep waiting
        if not lease_exists:
            try:
                owner = redis_conn.set(
                    lease_key, b'1', nx=True, ex=LEASE_TTL_SECONDS,
                )
            except Exception:
                owner = False
            if owner:
                logger.info(
                    f"Coalesce leader appears to have died; taking over"
                    f" fetch for {label}"
                )
                return _run_and_cache(
                    cache_key, fetch_fn, redis_conn, lease_key,
                )

    logger.warning(
        f"Coalesce wait timed out for {label} after"
        f" {WAIT_TIMEOUT_SECONDS:.0f}s; falling back to direct fetch."
    )
    return _run_and_cache(cache_key, fetch_fn)
