import logging
import random
import sqlite3
import time
from dataclasses import dataclass
from abc import ABC, abstractmethod
from pprint import pformat
from typing import Optional

from .cache import FileLock
from .config import Config
from .errors import APIError
from src.utils import cache

config = Config()
logger = logging.getLogger(__name__)

MAX_THROTTLE_WAIT_SECONDS = 120


@dataclass(frozen=True)
class Endpoint:
    """Configuration for a throttled API endpoint."""

    name: str
    requests_per_second: Optional[int] = None
    requests_per_minute: Optional[int] = None
    backoff_factor: Optional[int] = None
    global_rate_limit: bool = False

    def __post_init__(self):
        if not (self.requests_per_second or self.requests_per_minute):
            raise ValueError(
                "Endpoint must specify either 'requests_per_second'"
                " or 'requests_per_minute'."
            )


class ENDPOINTS:
    GBIF_SLOW = Endpoint(
        name='gbif_slow',
        requests_per_second=1,
        backoff_factor=2,
        global_rate_limit=True,
    )
    GBIF_FAST = Endpoint(
        name='gbif_fast',
        requests_per_second=10,
        backoff_factor=2,
        global_rate_limit=True,
    )
    ENTREZ = Endpoint(
        name='entrez',
        requests_per_second=10,
    )
    BOLD = Endpoint(
        name='bold',
        requests_per_second=5,
        requests_per_minute=50,
    )


class AbstractQueueBackend(ABC):
    """Abstract base class for throttle queue backends.

    This is necessary to avoid hitting API rate limits, or overwhelming the
    server. Each endpoint (identified by name) is throttled independently to
    allow for request rates to be set per-service, and to for throttles to be
    managed independently.

    To be conservative, the throttle will limit per-second requests in 2-second
    blocks and per-minute requests in 90-second blocks.

    Backends are responsible for coordinating request timestamps across
    processes to enforce rate limits. Each backend must support atomic
    check-and-insert operations to prevent race conditions.
    """

    @abstractmethod
    def initialize(
        self,
        name: str,
        rps: int | None,
        rpm: int | None,
    ):
        """Initialize the backend for the given endpoint name."""

    @abstractmethod
    def acquire(self):
        """Block until a request is allowed, then record it."""


class SqliteQueueBackend(AbstractQueueBackend):
    """SQLite-based throttle backend for single-node concurrency."""

    FIELD_NAME = 'timestamp'
    PER_SECOND_BLOCK_MS = 2000
    PER_MINUTE_BLOCK_MS = 12000
    BACKOFF_DEBOUNCE_MS = 30_000  # 30s
    BACKOFF_EXPIRY_MS = 7_200_000  # 2 hours
    BACKOFF_MIN_RPS = 0.1
    _await_exception_count = 0
    _await_exception_msg = ""

    def __init__(
        self,
        endpoint: Endpoint,
    ):
        self.rps = endpoint.requests_per_second
        self.rpm = endpoint.requests_per_minute
        self.per_second_limit = bool(self.rps)
        self.per_minute_limit = bool(self.rpm)
        self.window_length_ms = (
            self.PER_MINUTE_BLOCK_MS
            if self.rpm
            else self.PER_SECOND_BLOCK_MS
        )
        self.backoff_factor = endpoint.backoff_factor
        self.db_path = (
            config.throttle_sqlite_global_path
            if endpoint.global_rate_limit
            else config.throttle_sqlite_path
        )
        self.name = endpoint.name
        self.table_name = f"throttle_{self.name}"
        self.backoff_table = f"backoff_{self.name}"
        self._initialize_db()

    def __enter__(self):
        self._await_release()

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def _get_file_lock(self) -> FileLock:
        """Create a file-based lock for cross-process synchronization."""
        lock_path = self.db_path.with_suffix(
            self.db_path.suffix + '.lock'
        )
        return FileLock(lock_path)

    def _get_connection(
        self,
        timeout: float = 30.0,
        setup_wal: bool = True,
    ) -> sqlite3.Connection:
        """Get a database connection with proper configuration."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=timeout,
            check_same_thread=False,
        )
        if setup_wal:
            try:
                with self._get_file_lock():
                    cursor = conn.execute("PRAGMA journal_mode")
                    current_mode = cursor.fetchone()[0]
                    if current_mode.upper() != 'WAL':
                        conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")
            except (OSError, IOError):
                logger.warning(
                    "File locking failed, setting WAL mode without lock"
                )
                retries = 0
                while True:
                    try:
                        conn.execute("PRAGMA journal_mode=WAL")
                        conn.execute("PRAGMA synchronous=NORMAL")
                    except sqlite3.OperationalError as exc:
                        if retries < 5:
                            time.sleep(0.1 * (2 ** retries))
                            retries += 1
                            continue
                        raise exc
                    break
        else:
            conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _initialize_db(self):
        """Create tables for tracking request timestamps and backoff."""
        if not self.db_path.exists():
            logger.info(
                f"Creating throttle SQLite DB file: {self.db_path}"
            )
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._get_file_lock():
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        with self._get_connection(
                            setup_wal=False,
                        ) as conn:
                            self._create_db_tables(conn)
                            break
                    except sqlite3.OperationalError as e:
                        if (
                            "database is locked" in str(e)
                            and attempt < max_retries - 1
                        ):
                            time.sleep(0.1 * (2 ** attempt))
                            continue
                        raise
        except (OSError, IOError):
            logger.warning(
                "File locking failed for schema operations"
            )
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with self._get_connection() as conn:
                        self._create_db_tables(conn)
                        break
                except sqlite3.OperationalError as e:
                    if (
                        "database is locked" in str(e)
                        and attempt < max_retries - 1
                    ):
                        time.sleep(0.1 * (2 ** attempt))
                        continue
                    raise

    def _create_db_tables(self, conn):
        """Create necessary tables for throttling and backoff."""
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                {self.FIELD_NAME} INTEGER
            )
        """)
        if self.backoff_factor:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.backoff_table} (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    effective_rps REAL NOT NULL,
                    last_429_timestamp INTEGER NOT NULL
                )
            """)
            conn.execute(
                f"INSERT OR IGNORE INTO {self.backoff_table}"
                " (id, effective_rps, last_429_timestamp)"
                " VALUES (1, ?, 0)",
                (self.rps,)
            )
        conn.commit()

    def acquire(self):
        """Poll SQLite DB until a request slot is available."""
        started_waiting = time.time()
        while True:
            if not self.db_path.exists():
                raise FileNotFoundError(
                    f"Throttle SQLite DB file not found: {self.db_path}"
                )
            try:
                with sqlite3.connect(
                    self.db_path,
                    isolation_level=None,
                    timeout=30.0,
                ) as conn:
                    try:
                        conn.execute("BEGIN IMMEDIATE")
                        now = int(time.time() * 1000)
                        if self._within_request_limits(now, conn):
                            conn.execute(
                                f"INSERT INTO {self.table_name}"
                                f" ({self.FIELD_NAME})"
                                " VALUES (?)",
                                (now,)
                            )
                            conn.commit()
                            return

                        # The request limit has been exceeded
                        conn.rollback()

                    except sqlite3.OperationalError as e:
                        self._consider_await_exception(e)
                        logger.warning(
                            "OperationalError during throttle check:"
                            f" {e}. Retrying..."
                        )

            except sqlite3.OperationalError as e:
                raise sqlite3.OperationalError(
                    str(e) + f"\nDB path: {self.db_path}"
                )

            time.sleep(round(random.uniform(0.1, 2), 3))
            seconds_waited = int(time.time() - started_waiting)
            if seconds_waited and seconds_waited % 15 == 0:
                logger.info(
                    f"Awaiting throttle release for endpoint"
                    f" {self.name} for >{seconds_waited} seconds..."
                )

    def _consider_await_exception(self, exception):
        """Raise if the same exception has occurred 5 times in a row."""
        if self._await_exception_msg != str(exception):
            self._await_exception_msg = str(exception)
            self._await_exception_count = 0
        self._await_exception_count += 1
        if self._await_exception_count >= 5:
            raise exception

    def _notify_429(self):
        """Record a 429 response and apply backoff if debounce has elapsed.

        All 429s within BACKOFF_DEBOUNCE_MS are lumped together so that the
        backoff factor is applied only once per debounce window.
        """
        if not self.backoff_factor:
            return
        try:
            with sqlite3.connect(
                self.db_path,
                isolation_level=None,
            ) as conn:
                conn.execute("BEGIN IMMEDIATE")
                now = int(time.time() * 1000)
                row = conn.execute(
                    f"SELECT effective_rps, last_429_timestamp"
                    f" FROM {self.backoff_table}"
                    " WHERE id = 1"
                ).fetchone()
                effective_rps, last_429_ts = row

                if now - last_429_ts < self.BACKOFF_DEBOUNCE_MS:
                    conn.rollback()
                    return

                new_rps = max(
                    effective_rps / self.backoff_factor,
                    self.BACKOFF_MIN_RPS,
                )
                conn.execute(
                    f"UPDATE {self.backoff_table}"
                    " SET effective_rps = ?,"
                    " last_429_timestamp = ?"
                    " WHERE id = 1",
                    (new_rps, now),
                )
                conn.commit()
                logger.warning(
                    f"429 backoff applied for endpoint {self.name}:"
                    f" RPS reduced from {effective_rps} to {new_rps}"
                )
        except sqlite3.OperationalError:
            pass

    def _get_effective_rps(self, conn):
        """Read effective RPS from backoff table, resetting if expired."""
        row = conn.execute(
            f"SELECT effective_rps, last_429_timestamp"
            f" FROM {self.backoff_table}"
            " WHERE id = 1"
        ).fetchone()
        effective_rps, last_429_ts = row
        now = int(time.time() * 1000)

        if last_429_ts and now - last_429_ts > self.BACKOFF_EXPIRY_MS:
            conn.execute(
                f"UPDATE {self.backoff_table}"
                " SET effective_rps = ?,"
                " last_429_timestamp = 0"
                " WHERE id = 1",
                (self.rps,),
            )
            logger.info(
                f"Backoff expired for endpoint {self.name}:"
                f" RPS reset to {self.rps}"
            )
            return self.rps

        return effective_rps

    def _within_request_limits(self, now, conn):
        """Check if the request limits are within the allowed range.
        This method uses a sliding window of timestamps to determine
        if the number of requests in the last second or minute exceeds the
        limits specified for the endpoint.
        """
        window_start = now - self.window_length_ms

        conn.execute(
            f"DELETE FROM {self.table_name}"
            f" WHERE {self.FIELD_NAME} < ?",
            (window_start,),
        )

        rps_observed = None
        rpm_observed = None

        if self.rps:
            args = [
                f"SELECT COUNT(*) FROM {self.table_name}",
            ]
            if self.rpm:
                args[0] += f" WHERE {self.FIELD_NAME} >= ?"
                rps_window_start = now - self.PER_SECOND_BLOCK_MS
                args.append((rps_window_start,))
            rps_observed = conn.execute(*args).fetchone()[0]

        if self.rpm:
            rpm_observed = conn.execute(
                f"SELECT COUNT(*) FROM {self.table_name}"
            ).fetchone()[0]

        rps_limit = self.rps
        if self.backoff_factor and self.per_second_limit:
            rps_limit = self._get_effective_rps(conn)

        within_per_second_limit = (
            not self.per_second_limit
            or rps_observed < rps_limit
        )
        within_per_minute_limit = (
            not self.per_minute_limit
            or rpm_observed < self.rpm
        )

        return within_per_second_limit and within_per_minute_limit


class RedisQueueBackend(AbstractQueueBackend):
    """Redis-based throttle backend for distributed multi-node concurrency.

    Uses SyncTokenBucket from redis-rate-limiters for atomic rate
    limiting with Lua scripts. Supports both per-second and per-minute
    limits via separate token buckets.
    """

    def __init__(self):
        import redis as redis_lib
        self._connection = redis_lib.Redis(
            host=config.REDIS_HOST,
            port=int(config.REDIS_PORT),
            password=config.REDIS_PASSWORD,
            ssl=config.REDIS_SSL,
        )
        self._user_email = config.USER_EMAIL or 'ANONYMOUS'

    def initialize(
        self,
        name: str,
        rps: int | None,
        rpm: int | None,
    ):
        from limiters import SyncTokenBucket

        self._buckets = []
        key_prefix = f"throttle:{self._user_email}:{name}"

        for key, capacity, refill_n in [
            ('rps', rps, 1),
            ('rpm', rpm, 60),
        ]:
            if capacity:
                self._buckets.append(SyncTokenBucket(
                    name=f"{key_prefix}:{key}",
                    capacity=capacity,
                    refill_frequency=refill_n,
                    refill_amount=capacity,
                    max_sleep=MAX_THROTTLE_WAIT_SECONDS,
                    connection=self._connection,
                ))

        logger.debug(
            f"Redis throttle backend initialized for key: {key_prefix}"
        )

    def acquire(self):
        """Acquire a token from all configured rate limit buckets."""
        for bucket in self._buckets:
            with bucket:
                pass


BACKENDS = {
    'sqlite': SqliteQueueBackend,
    'redis': RedisQueueBackend,
}


def _get_backend() -> AbstractQueueBackend:
    """Select the throttle backend based on environment configuration."""
    backend_class = BACKENDS.get(config.throttle_backend)
    if not backend_class:
        raise ValueError(
            f"Unknown throttle backend '{config.throttle_backend}'."
            f" Available backends: {', '.join(BACKENDS.keys())}"
        )
    return backend_class()


class Throttle:
    """Coordinate throttling of API requests across processes.

    Uses a pluggable backend (SQLite or Redis) to track request timestamps
    and enforce rate limits. The backend is selected via the
    THROTTLE_BACKEND environment variable (default: 'sqlite').
    """

    def __init__(
        self,
        endpoint: Endpoint,
    ):
        self.rps = endpoint.requests_per_second
        self.rpm = endpoint.requests_per_minute
        self.name = endpoint.name
        self.backoff_factor = endpoint.backoff_factor
        self.backend = _get_backend()
        self.backend.initialize(self.name, self.rps, self.rpm)

    def __enter__(self):
        self.backend.acquire()

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def _notify_429(self):
        if hasattr(self.backend, '_notify_429'):
            self.backend._notify_429()

    def with_retry(self, func, args=[], kwargs={}, with_cache=False):
        retries = config.max_api_retries
        if with_cache:
            cache_key = cache.keyhash(func, args, kwargs)
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                logger.debug(
                    f"Cache hit for {func.__module__}.{func.__name__}"
                    " request"
                )
                return cached_data

        while True:
            try:
                with self:
                    logger.debug(
                        "Throttle released. Sending request to"
                        f" {self.name}..."
                    )
                res = func(*args, **kwargs)
                if with_cache:
                    cache.put(cache_key, res)
                return res

            except Exception as exc:
                sleep_seconds = 1
                retries -= 1
                if '429' in str(exc):
                    self._notify_429()
                    if self.backoff_factor:
                        sleep_seconds = 10
                        logger.warning(
                            "API rate limit exceeded for endpoint"
                            f" {self.name}. Backoff applied,"
                            " retrying in 10 seconds.")
                    else:
                        sleep_seconds = 600
                        logger.warning(
                            "API rate limit exceeded. Waiting"
                            " 10 minutes before next retry.")
                    retries = config.max_api_retries
                elif retries <= 0:
                    raise APIError(
                        'Failed to fetch data from API after'
                        f' {config.max_api_retries} retries. Please'
                        f' try resuming this job at a later time.'
                        f'\nException: {exc}'
                    )
                logger.warning(
                    "Exception encountered in call to endpoint"
                    f" {self.name} Retrying {retries} more times."
                    f" Exception: {exc}\n"
                    f" Args:\n{pformat(args)}"
                )
                time.sleep(sleep_seconds)
