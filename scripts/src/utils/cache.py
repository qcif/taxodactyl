"""Cache module with pluggable backends.

Provides a module-level ``get``/``put`` API that delegates to a configured
:class:`CacheBackend`. Two backends are shipped:

- :class:`SqliteCacheBackend` - stores entries in a local SQLite database
  and uses ``fcntl`` file locks to coordinate concurrent access from
  multiple processes on the same host.
- :class:`AzureBlobCacheBackend` - stores each entry as a blob in an
  Azure Blob Storage container. Intended for use when running across
  ephemeral nodes (e.g. Azure Batch) where a shared filesystem is not
  available. Azure Blob Storage provides atomic last-writer-wins
  semantics for ``PUT`` which is sufficient for a cache.

Backends subclass :class:`CacheBackend` and may optionally implement a
``lock`` context manager for cross-process synchronization around
internal setup operations. Backends that don't need locking can rely on
the default no-op implementation.
"""

import fcntl
import hashlib
import logging
import pickle
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from contextlib import nullcontext
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .config import Config

logger = logging.getLogger(__name__)

KEY_COLUMN = 'key'
VALUE_COLUMN = 'value'
CREATED_AT_COLUMN = 'created_at'

BACKEND_SQLITE = 'sqlite'
BACKEND_AZURE_BLOB = 'azure_blob'

CREATED_AT_METADATA_KEY = 'created_at'

# Size of the urllib3 connection pool used by the Azure Blob SDK. The
# default (10) is too small for our worker-pool workloads and causes
# "Connection pool is full, discarding connection" warnings plus extra
# TLS handshakes. Set comfortably above the expected concurrent worker
# count.
AZURE_BLOB_POOL_MAXSIZE = 50

_backend_lock = threading.Lock()
_backend: Optional['CacheBackend'] = None


# ---------------------------------------------------------------------------
# Key hashing
# ---------------------------------------------------------------------------

def _serialize_cache_key_item(item):
    """Serialize individual cache key item to a consistent string."""
    if callable(item):
        # Functions use module.name to exclude memory address (ephemeral)
        return f"function:{item.__module__}.{item.__name__}"
    elif hasattr(item, 'serialize'):
        return item.serialize()
    elif hasattr(item, '__dict__'):
        # For other class objects use class name
        return (
            f"object:{item.__class__.__module__}."
            f"{item.__class__.__name__}"
        )
    else:
        return str(item)


def keyhash(*cache_key_items):
    """Convert cache key to a hashable string."""
    serialized_items = [
        _serialize_cache_key_item(item) for item in cache_key_items
    ]
    key_str = "|".join(serialized_items)
    return hashlib.sha256(key_str.encode()).hexdigest()


# ---------------------------------------------------------------------------
# File lock (used by the SQLite backend)
# ---------------------------------------------------------------------------

class FileLock:
    """A file-based lock for cross-process synchronization."""

    def __init__(self, lock_file_path: Path):
        self.lock_file_path = lock_file_path
        self.lock_file = None

    def __enter__(self):
        """Acquire the file lock."""
        try:
            self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.lock_file = open(self.lock_file_path, 'w')
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


def _get_db_lock_file(sqlite_path: Path) -> Path:
    """Get the lock file path for a database."""
    return sqlite_path.with_suffix(sqlite_path.suffix + '.lock')


def cleanup_lock_files(sqlite_path: Path):
    """Clean up stale lock files for a database."""
    lock_file_path = _get_db_lock_file(sqlite_path)
    try:
        if lock_file_path.exists():
            with open(lock_file_path, 'w') as lock_file:
                try:
                    fcntl.flock(
                        lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                    )
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


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------

class CacheBackend(ABC):
    """Abstract base class for cache backends.

    Subclasses must implement :meth:`get` and :meth:`put`. Backends may
    optionally override :meth:`lock` to provide a cross-process lock
    context manager (keyed by an arbitrary string) for internal setup
    operations. The default implementation is a no-op ``nullcontext``,
    which is appropriate for backends whose underlying storage already
    serializes concurrent access (e.g. Azure Blob Storage).
    """

    def lock(self, name: str = 'default'):
        """Optional cross-process lock context manager.

        Backends that need to coordinate setup or schema operations
        across processes should override this to return a real lock
        context manager. The default is a no-op.
        """
        return nullcontext()

    @abstractmethod
    def get(self, key_hash: str):
        """Return the cached value for ``key_hash`` or ``None``."""

    @abstractmethod
    def put(self, key_hash: str, value) -> None:
        """Store ``value`` under ``key_hash``."""


# ---------------------------------------------------------------------------
# SQLite backend
# ---------------------------------------------------------------------------

class SqliteCacheBackend(CacheBackend):
    """Local SQLite-backed cache with ``fcntl`` file locking.

    Suitable for a single host with many threads/processes sharing a
    local filesystem. Uses WAL mode for concurrent readers and writers
    and retries on transient ``database is locked`` errors.
    """

    MAX_RETRIES = 3

    def __init__(self, sqlite_path: Path, timeout_hours: int):
        self.sqlite_path = sqlite_path
        self.timeout_hours = timeout_hours
        self._table_ready = False
        self._table_ready_lock = threading.Lock()

    def lock(self, name: str = 'default') -> FileLock:
        lock_file_path = _get_db_lock_file(self.sqlite_path)
        return FileLock(lock_file_path)

    def _get_connection(
        self,
        timeout: float = 30.0,
        setup_wal: bool = True,
    ) -> sqlite3.Connection:
        """Get a thread-safe database connection."""
        conn = sqlite3.connect(
            self.sqlite_path,
            timeout=timeout,
            check_same_thread=False,
        )

        if setup_wal:
            # Set up WAL mode under file lock to prevent race conditions.
            # Only the first process to access the database should set
            # WAL mode.
            try:
                with self.lock():
                    cursor = conn.execute("PRAGMA journal_mode")
                    current_mode = cursor.fetchone()[0]
                    if current_mode.upper() != 'WAL':
                        conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")
                    conn.execute("PRAGMA cache_size=10000")
                    conn.execute("PRAGMA temp_store=memory")
            except (OSError, IOError):
                # If file locking fails, fall back to setting pragmas without lock
                # This maintains backwards compatibility but may have race
                # conditions - we use a retry to de-risk
                logger.warning(
                    "File locking failed, setting WAL mode without lock"
                )
                retries = 0
                while True:
                    try:
                        conn.execute("PRAGMA journal_mode=WAL")
                        conn.execute("PRAGMA synchronous=NORMAL")
                        conn.execute("PRAGMA cache_size=10000")
                        conn.execute("PRAGMA temp_store=memory")
                    except sqlite3.OperationalError as exc:
                        if retries < 5:
                            time.sleep(0.1 * (2 ** retries))
                            retries += 1
                            continue
                        raise exc
                    break

        else:
            # Skip WAL setup when called from within another locked context
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=memory")

        return conn

    def _create_or_migrate_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(f"""
CREATE TABLE IF NOT EXISTS cache (
    {KEY_COLUMN} TEXT PRIMARY KEY,
    {VALUE_COLUMN} BLOB,
    {CREATED_AT_COLUMN} TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

        cursor = conn.execute("PRAGMA table_info(cache)")
        columns = [row[1] for row in cursor.fetchall()]
        if CREATED_AT_COLUMN not in columns:
            conn.execute(
                f"ALTER TABLE cache ADD COLUMN "
                f"{CREATED_AT_COLUMN} TIMESTAMP"
            )
            current_time = datetime.now().isoformat()
            conn.execute(
                (
                    f"UPDATE cache SET {CREATED_AT_COLUMN} = ? "
                    f"WHERE {CREATED_AT_COLUMN} IS NULL"
                ),
                (current_time,),
            )

        conn.commit()

    def _ensure_cache_table(self) -> None:
        """Ensure the cache table exists (cross-process safe)."""
        if self._table_ready:
            return
        with self._table_ready_lock:
            if self._table_ready:
                return
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with self.lock():
                    self._run_ensure_table_with_retries()
            except (OSError, IOError) as e:
                logger.warning(
                    f"File locking failed for schema operations: {e}"
                )
                self._run_ensure_table_with_retries()
            self._table_ready = True

    def _run_ensure_table_with_retries(self) -> None:
        for attempt in range(self.MAX_RETRIES):
            try:
                with self._get_connection(setup_wal=False) as conn:
                    self._create_or_migrate_table(conn)
                return
            except sqlite3.OperationalError as e:
                if (
                    "database is locked" in str(e)
                    and attempt < self.MAX_RETRIES - 1
                ):
                    time.sleep(0.1 * (2 ** attempt))
                    continue
                logger.warning(f"Failed to ensure cache table: {e}")
                raise

    def get(self, key_hash: str):
        if not self.sqlite_path.exists():
            return None

        for attempt in range(self.MAX_RETRIES):
            try:
                with self._get_connection() as conn:
                    cutoff_time = datetime.now() - timedelta(
                        hours=self.timeout_hours
                    )
                    with conn:
                        cursor = conn.execute(
                            (
                                f"SELECT {VALUE_COLUMN}, "
                                f"{CREATED_AT_COLUMN} "
                                f"FROM cache WHERE {KEY_COLUMN} = ?"
                            ),
                            (key_hash,),
                        )
                        row = cursor.fetchone()

                        if row:
                            created_at = datetime.fromisoformat(row[1])
                            if created_at >= cutoff_time:
                                return pickle.loads(row[0])
                            conn.execute(
                                (
                                    f"DELETE FROM cache "
                                    f"WHERE {KEY_COLUMN} = ?"
                                ),
                                (key_hash,),
                            )
                    return None
            except sqlite3.OperationalError as e:
                if (
                    "database is locked" in str(e)
                    and attempt < self.MAX_RETRIES - 1
                ):
                    time.sleep(0.05 * (2 ** attempt))
                    continue
                logger.warning(f"Database error in get(): {e}")
                return None
            except (sqlite3.Error, pickle.PickleError) as e:
                logger.warning(f"Cache get error: {e}")
                return None
        return None

    def put(self, key_hash: str, value) -> None:
        try:
            self._ensure_cache_table()
        except Exception as e:
            logger.warning(f"Failed to ensure cache table: {e}")
            return

        for attempt in range(self.MAX_RETRIES):
            try:
                with self._get_connection() as conn:
                    with conn:
                        conn.execute(
                            (
                                f"INSERT OR REPLACE INTO cache "
                                f"({KEY_COLUMN}, {VALUE_COLUMN}, "
                                f"{CREATED_AT_COLUMN}) VALUES (?, ?, ?)"
                            ),
                            (
                                key_hash,
                                pickle.dumps(value),
                                datetime.now().isoformat(),
                            ),
                        )
                return
            except sqlite3.OperationalError as e:
                if (
                    "database is locked" in str(e)
                    and attempt < self.MAX_RETRIES - 1
                ):
                    time.sleep(0.05 * (2 ** attempt))
                    continue
                logger.warning(f"Database error in put(): {e}")
                return
            except (sqlite3.Error, pickle.PickleError) as e:
                logger.warning(f"Cache put error: {e}")
                return


# ---------------------------------------------------------------------------
# Azure Blob backend
# ---------------------------------------------------------------------------

class AzureBlobCacheBackend(CacheBackend):
    """Cache backend backed by an Azure Blob Storage container.

    Each cache entry is stored as a single blob whose name is derived
    from the key hash. The creation timestamp is stored in blob
    metadata so that expiry can be checked without relying on service
    clock skew.

    Azure Blob Storage serializes concurrent writes to the same blob
    (last writer wins) and concurrent readers always see a consistent
    snapshot, so no additional locking is required for correct cache
    semantics across nodes. The default no-op ``lock()`` inherited from
    :class:`CacheBackend` is therefore appropriate.
    """

    def __init__(
        self,
        container_name: str,
        timeout_hours: int,
        account_url: Optional[str] = None,
        connection_string: Optional[str] = None,
        blob_prefix: str = '',
    ):
        if not account_url and not connection_string:
            raise ValueError(
                "AzureBlobCacheBackend requires either account_url "
                "(with DefaultAzureCredential) or connection_string."
            )
        logging.getLogger(
            "azure.core.pipeline.policies.http_logging_policy"
        ).setLevel(logging.WARNING)
        self.container_name = container_name
        self.timeout_hours = timeout_hours
        self.account_url = account_url
        self.connection_string = connection_string
        self.blob_prefix = blob_prefix
        self._client_lock = threading.Lock()
        self._container_client = None
        self._container_ready = False

    def _get_container_client(self):
        """Return a thread-safe ContainerClient, creating it on demand."""
        if self._container_client is not None:
            return self._container_client
        with self._client_lock:
            if self._container_client is not None:
                return self._container_client
            try:
                from azure.core.pipeline.transport import RequestsTransport
                from azure.storage.blob import BlobServiceClient
            except ImportError as e:
                raise ImportError(
                    "azure-storage-blob is required for the "
                    "'azure_blob' cache backend. Install it via "
                    "`pip install azure-storage-blob`."
                ) from e

            # Enlarge the urllib3 connection pool so that concurrent
            # workers don't discard sockets on return.
            transport = RequestsTransport(
                connection_pool_maxsize=AZURE_BLOB_POOL_MAXSIZE,
            )

            if self.connection_string:
                service_client = BlobServiceClient.from_connection_string(
                    self.connection_string,
                    transport=transport,
                )
            else:
                try:
                    from azure.identity import DefaultAzureCredential
                except ImportError as e:
                    raise ImportError(
                        "azure-identity is required for the "
                        "'azure_blob' cache backend when using "
                        "account_url. Install it via "
                        "`pip install azure-identity`."
                    ) from e
                service_client = BlobServiceClient(
                    account_url=self.account_url,
                    credential=DefaultAzureCredential(),
                    transport=transport,
                )

            container_client = service_client.get_container_client(
                self.container_name
            )
            self._ensure_container(container_client)
            self._container_client = container_client
            return self._container_client

    def _ensure_container(self, container_client) -> None:
        if self._container_ready:
            return
        try:
            from azure.core.exceptions import ResourceExistsError
        except ImportError:
            ResourceExistsError = Exception  # type: ignore
        try:
            container_client.create_container()
        except ResourceExistsError:
            pass
        except Exception as e:
            # The container may already exist and we may not have
            # permission to create it - that's fine as long as reads
            # and writes work.
            logger.debug(
                f"Could not ensure Azure cache container exists: {e}"
            )
        self._container_ready = True

    def _blob_name(self, key_hash: str) -> str:
        if self.blob_prefix:
            return f"{self.blob_prefix.rstrip('/')}/{key_hash}"
        return key_hash

    def get(self, key_hash: str):
        try:
            from azure.core.exceptions import ResourceNotFoundError
        except ImportError:
            ResourceNotFoundError = Exception  # type: ignore

        try:
            container = self._get_container_client()
            blob_client = container.get_blob_client(
                self._blob_name(key_hash)
            )
            try:
                downloader = blob_client.download_blob()
            except ResourceNotFoundError:
                return None

            properties = downloader.properties
            created_at = self._extract_created_at(properties)
            cutoff_time = datetime.now() - timedelta(
                hours=self.timeout_hours
            )
            if created_at is not None and created_at < cutoff_time:
                # Expired - best-effort delete and return None.
                try:
                    blob_client.delete_blob()
                except Exception as e:
                    logger.debug(
                        f"Failed to delete expired cache blob "
                        f"{key_hash}: {e}"
                    )
                return None

            data = downloader.readall()
            return pickle.loads(data)
        except pickle.PickleError as e:
            logger.warning(f"Cache get unpickle error: {e}")
            return None
        except Exception as e:
            logger.warning(f"Azure blob cache get error: {e}")
            return None

    def put(self, key_hash: str, value) -> None:
        try:
            container = self._get_container_client()
            blob_client = container.get_blob_client(
                self._blob_name(key_hash)
            )
            data = pickle.dumps(value)
            metadata = {
                CREATED_AT_METADATA_KEY: datetime.now().isoformat(),
            }
            # overwrite=True gives us last-writer-wins semantics, which
            # is what we want for a cache.
            blob_client.upload_blob(
                data,
                overwrite=True,
                metadata=metadata,
            )
        except pickle.PickleError as e:
            logger.warning(f"Cache put pickle error: {e}")
        except Exception as e:
            logger.warning(f"Azure blob cache put error: {e}")

    @staticmethod
    def _extract_created_at(properties) -> Optional[datetime]:
        """Extract the cached creation time from blob properties."""
        metadata = getattr(properties, 'metadata', None) or {}
        raw = metadata.get(CREATED_AT_METADATA_KEY)
        if raw:
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                logger.debug(
                    f"Invalid {CREATED_AT_METADATA_KEY} metadata: {raw}"
                )
        # Fall back to the blob's last modified time. Note this is in
        # UTC while datetime.now() is naive local time, so we convert.
        last_modified = getattr(properties, 'last_modified', None)
        if last_modified is not None:
            try:
                if last_modified.tzinfo is not None:
                    return last_modified.astimezone().replace(tzinfo=None)
                return last_modified
            except Exception:
                return None
        return None


# ---------------------------------------------------------------------------
# Backend selection and public API
# ---------------------------------------------------------------------------

def _create_backend(config: Config) -> CacheBackend:
    backend_name = (config.cache_backend or BACKEND_SQLITE).lower()
    if backend_name == BACKEND_SQLITE:
        return SqliteCacheBackend(
            sqlite_path=config.cache_sqlite_path,
            timeout_hours=config.cache_timeout_hours,
        )
    if backend_name == BACKEND_AZURE_BLOB:
        return AzureBlobCacheBackend(
            container_name=config.cache_azure_container,
            timeout_hours=config.cache_timeout_hours,
            account_url=config.cache_azure_account_url,
            connection_string=config.cache_azure_connection_string,
            blob_prefix=config.cache_azure_blob_prefix,
        )
    raise ValueError(
        f"Unknown cache backend: {backend_name!r}. "
        f"Expected one of: {BACKEND_SQLITE}, {BACKEND_AZURE_BLOB}."
    )


def get_backend() -> CacheBackend:
    """Return the (lazily-initialized) configured cache backend."""
    global _backend
    if _backend is not None:
        return _backend
    with _backend_lock:
        if _backend is None:
            _backend = _create_backend(Config())
    return _backend


def reset_backend() -> None:
    """Clear the cached backend instance. Intended for tests."""
    global _backend
    with _backend_lock:
        _backend = None


def get(key_hash: str):
    """Get cached data by key (thread-safe).

    Delegates to the configured :class:`CacheBackend`.
    """
    config = Config()
    if config.cache_disabled:
        return None
    try:
        backend = get_backend()
    except Exception as e:
        logger.warning(f"Failed to initialize cache backend: {e}")
        return None
    return backend.get(key_hash)


def put(key_hash: str, value) -> None:
    """Set cached data by key (thread-safe).

    Delegates to the configured :class:`CacheBackend`.
    """
    config = Config()
    if config.cache_disabled:
        return
    try:
        backend = get_backend()
    except Exception as e:
        logger.warning(f"Failed to initialize cache backend: {e}")
        return
    backend.put(key_hash, value)
