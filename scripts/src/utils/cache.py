"""Cache module for storing data in SQLite database."""

import fcntl
import hashlib
import logging
import pickle
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)

KEY_COLUMN = 'key'
VALUE_COLUMN = 'value'
CREATED_AT_COLUMN = 'created_at'

config = Config()


class FileLock:
    """A file-based lock for cross-process synchronization."""

    def __init__(self, lock_file_path: Path):
        self.lock_file_path = lock_file_path
        self.lock_file = None

    def __enter__(self):
        """Acquire the file lock."""
        try:
            # Ensure lock directory exists
            self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
            # Open lock file for writing
            self.lock_file = open(self.lock_file_path, 'w')
            # Acquire exclusive lock with timeout
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX)
            return self
        except (OSError, IOError) as e:
            self._cleanup_lock_file()
            logger.warning(
                f"Failed to acquire file lock {self.lock_file_path}: {e}"
            )
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release the file lock."""
        self._cleanup_lock_file()

    def _cleanup_lock_file(self):
        """Clean up the lock file handle."""
        if self.lock_file:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            except (OSError, IOError) as e:
                logger.debug(f"Error unlocking file: {e}")
            try:
                self.lock_file.close()
            except (OSError, IOError) as e:
                logger.debug(f"Error closing lock file: {e}")
            finally:
                self.lock_file = None


def _serialize_cache_key_item(item):
    """Serialize individual cache key item to a consistent string."""
    if callable(item):
        # Functions use module.name to exclude memory address (ephemeral)
        return f"function:{item.__module__}.{item.__name__}"
    elif hasattr(item, 'serialize'):
        return item.serialize()
    elif hasattr(item, '__dict__'):
        # For other class objects use class name
        return f"object:{item.__class__.__module__}.{item.__class__.__name__}"
    else:
        return str(item)


def keyhash(*cache_key_items):
    """Convert cache key to a hashable string."""
    serialized_items = [
        _serialize_cache_key_item(item) for item in cache_key_items
    ]
    key_str = "|".join(serialized_items)
    return hashlib.sha256(key_str.encode()).hexdigest()


def _get_db_lock_file(sqlite_path: Path) -> Path:
    """Get the lock file path for a database."""
    return sqlite_path.with_suffix(sqlite_path.suffix + '.lock')


def _get_file_lock(sqlite_path: Path) -> FileLock:
    """Create a new file-based lock for cross-process synchronization."""
    lock_file_path = _get_db_lock_file(sqlite_path)
    return FileLock(lock_file_path)


def cleanup_lock_files(sqlite_path: Path):
    """Clean up stale lock files for a database."""
    lock_file_path = _get_db_lock_file(sqlite_path)
    try:
        if lock_file_path.exists():
            # Try to acquire lock briefly to check if it's stale
            with open(lock_file_path, 'w') as lock_file:
                try:
                    # Non-blocking lock attempt
                    fcntl.flock(
                        lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                    )
                    # If we got the lock, file was stale - remove it
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file_path.unlink()
                    logger.debug(
                        f"Cleaned up stale lock file: {lock_file_path}"
                    )
                except (OSError, IOError):
                    # Lock is held by another process - leave it alone
                    pass
    except (OSError, IOError) as e:
        logger.debug(f"Could not clean lock file {lock_file_path}: {e}")


def _get_connection(
    sqlite_path: Path,
    timeout: float = 30.0,
    setup_wal: bool = True,
) -> sqlite3.Connection:
    """Get a thread-safe database connection with proper configuration."""
    conn = sqlite3.connect(
        sqlite_path,
        timeout=timeout,
        check_same_thread=False
    )

    if setup_wal:
        # Set up WAL mode under file lock to prevent race conditions
        # Only the first process to access the database should set WAL mode
        wal_setup_lock = _get_file_lock(sqlite_path)
        try:
            with wal_setup_lock:
                # Check current journal mode
                cursor = conn.execute("PRAGMA journal_mode")
                current_mode = cursor.fetchone()[0]

                # Only set WAL mode if not already set
                if current_mode.upper() != 'WAL':
                    conn.execute("PRAGMA journal_mode=WAL")

                # Set other pragmas (these are safe to set multiple times)
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=10000")
                conn.execute("PRAGMA temp_store=memory")
        except (OSError, IOError):
            # If file locking fails, fall back to setting pragmas without lock
            # This maintains backwards compatibility but may have race
            # conditions
            logger.warning(
                "File locking failed, setting WAL mode without lock"
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=memory")
    else:
        # Skip WAL setup when called from within another locked context
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=memory")

    return conn


def _ensure_cache_table(sqlite_path: Path):
    """Ensure the cache table exists in the database (cross-process
    safe)."""
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    # Use file-based lock to prevent concurrent schema modifications
    # across processes
    schema_lock = _get_file_lock(sqlite_path)
    try:
        with schema_lock:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with _get_connection(sqlite_path, setup_wal=False) as conn:
                        conn.execute(f"""
CREATE TABLE IF NOT EXISTS cache (
    {KEY_COLUMN} TEXT PRIMARY KEY,
    {VALUE_COLUMN} BLOB,
    {CREATED_AT_COLUMN} TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

                        # Check if created_at column exists, add it if missing
                        cursor = conn.execute("PRAGMA table_info(cache)")
                        columns = [row[1] for row in cursor.fetchall()]
                        if CREATED_AT_COLUMN not in columns:
                            conn.execute(
                                (
                                    f"ALTER TABLE cache ADD COLUMN "
                                    f"{CREATED_AT_COLUMN} TIMESTAMP"
                                )
                            )
                            current_time = datetime.now().isoformat()
                            conn.execute(
                                (
                                    f"UPDATE cache SET "
                                    f"{CREATED_AT_COLUMN} = ? WHERE "
                                    f"{CREATED_AT_COLUMN} IS NULL"
                                ),
                                (current_time,)
                            )

                        conn.commit()
                        break
                except sqlite3.OperationalError as e:
                    if (
                        "database is locked" in str(e)
                        and attempt < max_retries - 1
                    ):
                        time.sleep(0.1 * (2 ** attempt))
                        continue
                    else:
                        logger.warning(f"Failed to ensure cache table: {e}")
                        raise
    except (OSError, IOError) as e:
        # If file locking fails, fall back to non-locked schema operations
        logger.warning(
            f"File locking failed for schema operations: {e}"
        )
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with _get_connection(sqlite_path) as conn:
                    conn.execute(f"""
CREATE TABLE IF NOT EXISTS cache (
    {KEY_COLUMN} TEXT PRIMARY KEY,
    {VALUE_COLUMN} BLOB,
    {CREATED_AT_COLUMN} TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

                    # Check if created_at column exists, add it if missing
                    cursor = conn.execute("PRAGMA table_info(cache)")
                    columns = [row[1] for row in cursor.fetchall()]
                    if CREATED_AT_COLUMN not in columns:
                        conn.execute(
                            (
                                f"ALTER TABLE cache ADD COLUMN "
                                f"{CREATED_AT_COLUMN} TIMESTAMP"
                            )
                        )
                        current_time = datetime.now().isoformat()
                        conn.execute(
                            (
                                f"UPDATE cache SET {CREATED_AT_COLUMN} = ? "
                                f"WHERE {CREATED_AT_COLUMN} IS NULL"
                            ),
                            (current_time,)
                        )

                    conn.commit()
                    break
            except sqlite3.OperationalError as e:
                if (
                    "database is locked" in str(e)
                    and attempt < max_retries - 1
                ):
                    time.sleep(0.1 * (2 ** attempt))
                    continue
                else:
                    logger.warning(f"Failed to ensure cache table: {e}")
                    raise


def get(key_hash: str):
    """Get cached data by key (thread-safe).

    Args:
        key_hash: Cache key hash

    Returns:
        Cached data if found, None otherwise
    """
    sqlite_path = config.cache_sqlite_path
    if not sqlite_path.exists():
        return None

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with _get_connection(sqlite_path) as conn:
                cutoff_time = datetime.now() - timedelta(
                    hours=config.cache_timeout_hours
                )

                # Use atomic transaction to avoid race conditions
                with conn:
                    cursor = conn.execute(
                        (
                            f"SELECT {VALUE_COLUMN}, {CREATED_AT_COLUMN} "
                            f"FROM cache WHERE {KEY_COLUMN} = ?"
                        ),
                        (key_hash,)
                    )
                    row = cursor.fetchone()

                    if row:
                        created_at = datetime.fromisoformat(row[1])
                        if created_at >= cutoff_time:
                            return pickle.loads(row[0])
                        else:
                            # Atomically remove expired entry
                            conn.execute(
                                f"DELETE FROM cache WHERE {KEY_COLUMN} = ?",
                                (key_hash,)
                            )

                return None
        except sqlite3.OperationalError as e:
            if (
                "database is locked" in str(e)
                and attempt < max_retries - 1
            ):
                time.sleep(0.05 * (2 ** attempt))
                continue
            else:
                logger.warning(f"Database error in get(): {e}")
                return None
        except (sqlite3.Error, pickle.PickleError) as e:
            logger.warning(f"Cache get error: {e}")
            return None
    return None


def put(key_hash, value):
    """Set cached data by key (thread-safe).

    Args:
        key_hash: Cache key hash
        value: Data to cache
    """
    config = Config()
    sqlite_path = config.cache_sqlite_path

    try:
        _ensure_cache_table(sqlite_path)
    except Exception as e:
        logger.warning(f"Failed to ensure cache table: {e}")
        return

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with _get_connection(sqlite_path) as conn:
                with conn:  # Use transaction for atomic operation
                    conn.execute(
                        (
                            f"INSERT OR REPLACE INTO cache "
                            f"({KEY_COLUMN}, {VALUE_COLUMN}, "
                            f"{CREATED_AT_COLUMN}) VALUES (?, ?, ?)"
                        ),
                        (
                            key_hash,
                            pickle.dumps(value),
                            datetime.now().isoformat()
                        )
                    )
                return  # Success, exit retry loop
        except sqlite3.OperationalError as e:
            if (
                "database is locked" in str(e)
                and attempt < max_retries - 1
            ):
                time.sleep(0.05 * (2 ** attempt))
                continue
            else:
                logger.warning(f"Database error in put(): {e}")
                return
        except (sqlite3.Error, pickle.PickleError) as e:
            logger.warning(f"Cache put error: {e}")
            return
