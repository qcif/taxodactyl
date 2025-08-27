"""Cache module for storing data in SQLite database."""

import hashlib
import logging
import pickle
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)

KEY_COLUMN = 'key'
VALUE_COLUMN = 'value'
CREATED_AT_COLUMN = 'created_at'

# Thread-safe database operations
_db_locks = {}
_db_locks_lock = threading.Lock()


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


def _get_db_lock(sqlite_path: Path) -> threading.Lock:
    """Get or create a database-specific lock."""
    path_str = str(sqlite_path)
    with _db_locks_lock:
        if path_str not in _db_locks:
            _db_locks[path_str] = threading.Lock()
        return _db_locks[path_str]


def _get_connection(
    sqlite_path: Path, timeout: float = 30.0
) -> sqlite3.Connection:
    """Get a thread-safe database connection with proper configuration."""
    conn = sqlite3.connect(
        sqlite_path,
        timeout=timeout,
        check_same_thread=False
    )
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    conn.execute("PRAGMA temp_store=memory")
    return conn


def _ensure_cache_table(sqlite_path: Path):
    """Ensure the cache table exists in the database (thread-safe)."""
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    # Use database-specific lock to prevent concurrent schema modifications
    db_lock = _get_db_lock(sqlite_path)
    with db_lock:
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


def get(key_hash):
    """Get cached data by key (thread-safe).

    Args:
        key_hash: Cache key hash

    Returns:
        Cached data if found, None otherwise
    """
    config = Config()
    sqlite_path = config.cache_sqlite_path

    if not sqlite_path.exists():
        return None

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with _get_connection(sqlite_path) as conn:
                cutoff_time = datetime.now() - timedelta(
                    hours=config.CACHE_TIMEOUT_HOURS
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
