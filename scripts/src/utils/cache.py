"""Cache module for storing data in SQLite database."""

import hashlib
import logging
import pickle
import sqlite3
from datetime import datetime, timedelta

from .config import Config

logger = logging.getLogger(__name__)

KEY_COLUMN = 'key'
VALUE_COLUMN = 'value'
CREATED_AT_COLUMN = 'created_at'


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


def _ensure_cache_table(sqlite_path):
    """Ensure the cache table exists in the database."""
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(sqlite_path) as conn:
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
                f"ALTER TABLE cache ADD COLUMN {CREATED_AT_COLUMN} TIMESTAMP"
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


def get(key_hash):
    """Get cached data by key.

    Args:
        cache_key: Cache key (can be tuple or other hashable type)

    Returns:
        Cached data if found, None otherwise
    """
    config = Config()
    sqlite_path = config.cache_sqlite_path

    if not sqlite_path.exists():
        return None

    try:
        with sqlite3.connect(sqlite_path) as conn:
            config = Config()
            cutoff_time = datetime.now() - timedelta(
                hours=config.CACHE_TIMEOUT_HOURS
            )
            cursor = conn.execute(
                (
                    f"SELECT {VALUE_COLUMN}, {CREATED_AT_COLUMN} FROM cache "
                    f"WHERE {KEY_COLUMN} = ?"
                ),
                (key_hash,)
            )
            row = cursor.fetchone()
            if row:
                created_at = datetime.fromisoformat(row[1])
                if created_at >= cutoff_time:
                    return pickle.loads(row[0])
                else:
                    # Remove expired entries
                    conn.execute(
                        f"DELETE FROM cache WHERE {KEY_COLUMN} = ?",
                        (key_hash,)
                    )
                    conn.commit()
            return None
    except (sqlite3.Error, pickle.PickleError):
        return None


def put(key_hash, value):
    """Set cached data by key.

    Args:
        cache_key: Cache key (can be tuple or other hashable type)
        value: Data to cache
    """
    config = Config()
    sqlite_path = config.cache_sqlite_path
    _ensure_cache_table(sqlite_path)
    try:
        with sqlite3.connect(sqlite_path) as conn:
            conn.execute(
                (
                    f"INSERT OR REPLACE INTO cache "
                    f"({KEY_COLUMN}, {VALUE_COLUMN}, {CREATED_AT_COLUMN}) "
                    "VALUES (?, ?, ?)"
                ),
                (key_hash, pickle.dumps(value), datetime.now().isoformat())
            )
            conn.commit()
    except (sqlite3.Error, pickle.PickleError):
        # Silently fail if we can't cache the data
        pass
