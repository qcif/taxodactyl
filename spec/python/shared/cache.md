# Spec: API response cache (`src/utils/cache.py`)

**Derived from:** `cache.py` (697), `tests/test_cache.py`,
`tests/test_cache_azure.py`. v1.5.0.
**Used by:** `Throttle.with_retry(with_cache=True)` via `coalesce`
([throttle.md](throttle.md)).

## 1. Purpose

Avoid repeating expensive, idempotent external requests across threads,
processes, queries and runs.

## 2. Requirements

| ID | Requirement |
|---|---|
| CCH-001 | Public API: `keyhash(*items) -> sha256 hex`, `get(key) -> value or None`, `put(key, value)`. If `cache_disabled`, `get` returns `None` and `put` does nothing. |
| CCH-002 | Key serialisation per item: callable → `function:<module>.<name>`; object with `serialize()` → its result; other object with `__dict__` → `object:<module>.<class>` (**instance data ignored**); anything else → `str(item)`. Items joined with `|`. |
| CCH-003 | Values are pickled. A cached `None` is indistinguishable from a miss. |
| CCH-004 | Entries older than `cache_timeout_hours` (168) are treated as misses and deleted best-effort on read. |
| CCH-005 | Every backend error (I/O, lock, SDK, unpickling) MUST be logged and treated as a miss / no-op; the cache never fails an analysis. |
| CCH-006 | The backend is selected once per process from `cache_backend`: `sqlite` or `azure_blob`; anything else raises at first use (then logged, cache inactive). |

### 2.1 `sqlite`

| ID | Requirement |
|---|---|
| CCH-010 | Database `tempdir/cache_db.sqlite`, table `cache(key TEXT PK, value BLOB, created_at TIMESTAMP)`; WAL mode set under an `fcntl` lock (`.lock` file); `database is locked` retried 3× with exponential sleep. Legacy tables without `created_at` are migrated. |

### 2.2 `azure_blob`

| ID | Requirement |
|---|---|
| CCH-020 | One blob per key named `[<prefix>/]<keyhash>` in container `cache_azure_container`; client from `cache_azure_connection_string`, else `cache_azure_account_url` + `DefaultAzureCredential`; connection pool 50. |
| CCH-021 | `created_at` stored in blob metadata (fallback: last-modified converted to local time); writes use `overwrite=True` (last writer wins). The container is created if missing (permission errors ignored). |
| CCH-022 | Authoritative expiry is the storage lifecycle policy (`deployment/azure/storage-policy.json`), not application code. |

## 3. Defects

| ID | Severity | Defect |
|---|---|---|
| CCH-D-001 | Low | CCH-002 keys objects by class only; two calls differing only in an object argument share a cache entry. Current callers pass strings/dicts, so latent. |
| CCH-D-002 | Low (security) | Values are unpickled from shared storage (Azure container, shared temp dir): anyone able to write there can execute code in analysis tasks. |
| CCH-D-003 | Low | Transient empty API responses are cached for 7 days. |
| CCH-D-004 | Low | `fcntl` makes the package Linux/macOS-only. |
