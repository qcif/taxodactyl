import logging
import random
import sqlite3
import time
from pprint import pformat

from .config import Config
from .errors import APIError

config = Config()
logger = logging.getLogger(__name__)


class ENDPOINTS:
    GBIF_SLOW = {
        'requests_per_second': 1,
        'name': 'gbif_slow',
    }
    GBIF_FAST = {
        'requests_per_second': 10,
        'name': 'gbif_fast',
    }
    ENTREZ = {
        'requests_per_second': 10,
        'name': 'entrez',
    }
    BOLD = {
        'requests_per_second': 5,
        'requests_per_minute': 50,
        'name': 'bold',
    }


class Throttle:
    """Use SQLite3 database to coordinate throttling of API requests.

    This is necessary to avoid hitting API rate limits, or overwhelming the
    server. Each endpoint (identified by name) is throttled independently to
    allow for request rates to be set per-service, and to for throttles to be
    managed independently.

    The endpoint arg should be a dict of:
        {
          'requests_per_second': int,  # Max requests per second
          // AND/OR
          'requests_per_minute': int,  # Max requests per minute
          'name': str,                 # Name to identify this endpoint
        }

    To be conservative, the throttle will limit per-second requests in 2-second
    blocks and per-minute requests in 90-second blocks.
    """

    FIELD_NAME = 'timestamp'
    PER_SECOND_BLOCK_MS = 2000
    PER_MINUTE_BLOCK_MS = 12000

    def __init__(
        self,
        endpoint: dict,
    ):
        self.rps = endpoint.get('requests_per_second')
        self.rpm = endpoint.get('requests_per_minute')
        if not (self.rps or self.rpm):
            raise ValueError(
                "Endpoint must specify either 'requests_per_second' or"
                " 'requests_per_minute'."
            )
        self.per_second_limit = bool(self.rps)
        self.per_minute_limit = bool(self.rpm)
        self.window_length_ms = (
            self.PER_MINUTE_BLOCK_MS
            if self.rpm
            else self.PER_SECOND_BLOCK_MS
        )
        self.db_path = config.throttle_sqlite_path
        self.name = endpoint['name']
        self._initialize_db()

    def __enter__(self):
        self._await_release()

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def _initialize_db(self):
        """Create table for tracking request timestamps."""
        if not self.db_path.exists():
            logger.info(
                f"Creating throttle SQLite DB file: {self.db_path}"
            )
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.name} (
                    {self.FIELD_NAME} INTEGER
                )
            """)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.commit()

    def _await_release(self):
        """Query sqlite DB for permission to send a request.

        The DB table keeps track of requests sent across processes by writing
        a timestamp for each request sent. This is used to determine if we are
        within the allowed request limits before sendind the next request.
        """
        started_waiting = time.time()
        while True:
            try:
                if not self.db_path.exists():
                    raise FileNotFoundError(
                        "Throttle SQLite DB file not found:"
                        f" {self.db_path}"
                    )
                with sqlite3.connect(
                    self.db_path,
                    isolation_level=None,
                ) as conn:
                    try:
                        # Lock the database for writing
                        conn.execute("BEGIN IMMEDIATE")
                        now = int(time.time() * 1000)
                        if self._within_request_limits(now, conn):
                            # Insert current timestamp atomically
                            conn.execute(
                                f"INSERT INTO {self.name} ({self.FIELD_NAME})"
                                " VALUES (?)",
                                (now,)
                            )
                            conn.commit()
                            return

                        # Rollback if the request limit is exceeded
                        conn.rollback()

                    except sqlite3.OperationalError:
                        # Handle potential lock contention gracefully
                        pass

            except sqlite3.OperationalError as e:
                raise sqlite3.OperationalError(
                    str(e) + f"\nDB path: {self.db_path}"
                )

            # Sleep for a random interval to reduce race conditions
            time.sleep(round(random.uniform(0.1, 2), 3))
            seconds_waited = int(time.time() - started_waiting)
            if seconds_waited and seconds_waited % 15 == 0:
                logger.info(
                    f"Awaiting throttle release for endpoint {self.name}"
                    f" for >{seconds_waited} seconds..."
                )

    def _within_request_limits(self, now, conn):
        """Check if the request limits are within the allowed range.
        This method uses a sliding window of timestamps to determine
        if the number of requests in the last second or minute exceeds the
        limits specified for the endpoint.
        """
        window_start = now - self.window_length_ms

        # Remove expired timestamps older than window length
        conn.execute(
            f"DELETE FROM {self.name}"
            f" WHERE {self.FIELD_NAME} < ?",
            (window_start,))

        # Count requests in the window
        rps_observed = None
        rpm_observed = None

        if self.per_second_limit:
            args = [
                f"SELECT COUNT(*) FROM {self.name}",
            ]
            if self.per_minute_limit:
                # The window is for rpm, so need to narrow
                # query to RPS window size
                args[0] += f" WHERE {self.FIELD_NAME} >= ?"
                rps_window_start = (
                    now - self.PER_SECOND_BLOCK_MS
                )
                args.append((rps_window_start,))
            rps_observed = conn.execute(*args).fetchone()[0]

        if self.per_minute_limit:
            rpm_observed = conn.execute(
                f"SELECT COUNT(*) FROM {self.name}"
            ).fetchone()[0]

        within_per_second_limit = (
            not self.per_second_limit
            or rps_observed < self.rps
        )
        within_per_minute_limit = (
            not self.per_minute_limit
            or rpm_observed < self.rpm
        )

        return within_per_second_limit and within_per_minute_limit

    def with_retry(self, func, args=[], kwargs={}):
        retries = config.MAX_API_RETRIES
        while True:
            try:
                with self:
                    logger.debug("Throttle released. Sending request to"
                                 f" {self.name}...")
                    return func(*args, **kwargs)
            except Exception as exc:
                sleep_seconds = 1
                retries -= 1
                if '429' in str(exc):
                    sleep_seconds = 600
                    logger.warning(
                        "API rate limit exceeded. Waiting 10 minutes before"
                        " next retry.")
                    retries = config.MAX_API_RETRIES
                elif retries <= 0:
                    raise APIError(
                        'Failed to fetch data from API after'
                        f' {config.MAX_API_RETRIES} retries. Please try'
                        f' resuming this job at a later time.'
                        f'\nException: {exc}'
                    )
                logger.warning(
                    "Exception encountered in call to endpoint"
                    f" {self.name} Retrying {retries} more times."
                    f" Exception: {exc}\n"
                    f" Args:\n{pformat(args)}")
                time.sleep(sleep_seconds)
