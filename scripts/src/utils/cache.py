"""Cache module for storing data in SQLite database."""

import sqlite3
import pickle
import hashlib
from datetime import datetime, timedelta

from .config import Config


def _serialize_cache_key_item(item):
    """Serialize individual cache key item to a consistent string."""
    if callable(item):
        # For functions, use module + name instead of memory address
        return f"function:{item.__module__}.{item.__name__}"
    elif hasattr(item, '__dict__'):
        # For objects with attributes, use class name
        return f"object:{item.__class__.__module__}.{item.__class__.__name__}"
    else:
        # For simple types, use string representation
        return str(item)


def _get_cache_key_hash(cache_key):
    """Convert cache key to a hashable string."""
    if isinstance(cache_key, tuple):
        # Serialize each item in the tuple consistently
        serialized_items = [
            _serialize_cache_key_item(item) for item in cache_key
        ]
        key_str = "|".join(serialized_items)
    else:
        key_str = _serialize_cache_key_item(cache_key)

    # Create a hash to ensure consistent key length
    return hashlib.sha256(key_str.encode()).hexdigest()


def _ensure_cache_table(sqlite_path):
    """Ensure the cache table exists in the database."""
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(sqlite_path) as conn:
        # Create table with new schema
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Check if created_at column exists, add it if missing (migration)
        cursor = conn.execute("PRAGMA table_info(cache)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'created_at' not in columns:
            # Add column without default, then update existing rows
            conn.execute("ALTER TABLE cache ADD COLUMN created_at TIMESTAMP")
            # Set current timestamp for existing entries
            current_time = datetime.now().isoformat()
            conn.execute(
                "UPDATE cache SET created_at = ? WHERE created_at IS NULL",
                (current_time,)
            )

        conn.commit()


def get(cache_key):
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

    key_hash = _get_cache_key_hash(cache_key)

    try:
        with sqlite3.connect(sqlite_path) as conn:
            # Calculate cutoff time for expired entries
            config = Config()
            cutoff_time = datetime.now() - timedelta(
                hours=config.CACHE_TIMEOUT_HOURS
            )

            cursor = conn.execute(
                "SELECT value, created_at FROM cache WHERE key = ?",
                (key_hash,)
            )
            row = cursor.fetchone()
            if row:
                created_at = datetime.fromisoformat(row[1])
                if created_at >= cutoff_time:
                    return pickle.loads(row[0])
                else:
                    # Remove expired entry
                    conn.execute(
                        "DELETE FROM cache WHERE key = ?", (key_hash,)
                    )
                    conn.commit()
            return None
    except (sqlite3.Error, pickle.PickleError):
        return None


def set(cache_key, value):
    """Set cached data by key.

    Args:
        cache_key: Cache key (can be tuple or other hashable type)
        value: Data to cache
    """
    config = Config()
    sqlite_path = config.cache_sqlite_path

    _ensure_cache_table(sqlite_path)
    key_hash = _get_cache_key_hash(cache_key)

    try:
        with sqlite3.connect(sqlite_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, created_at) "
                "VALUES (?, ?, ?)",
                (key_hash, pickle.dumps(value), datetime.now().isoformat())
            )
            conn.commit()
    except (sqlite3.Error, pickle.PickleError):
        # Silently fail if we can't cache the data
        pass
