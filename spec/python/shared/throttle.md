# Spec: API throttling, retry and request coalescing (`src/utils/throttle.py`, `src/utils/coalesce.py`)

**Used by:** every external HTTP call — Entrez (P4, P5), GBIF (P5, BOLD
kingdom lookup), BOLD (P1-BOLD, P5).

## 1. Purpose

Keep many concurrent processes (one per query, several threads each,
possibly on several nodes) under each external service's rate limit;
retry transient failures; and avoid issuing the same cached request twice
(coalescing).

## 2. Endpoints

| Endpoint | Rate | Scope | Backoff on 429 | Service |
|---|---|---|---|---|
| `GBIF_SLOW` | 1 req/s | global (all users on the backend) | ÷2 per 30 s window, min 0.1 req/s, resets after 2 h | `gbif` |
| `GBIF_FAST` | 5 req/s | global | same | `gbif` |
| `ENTREZ` | 5 req/s with `NCBI_API_KEY`, else 2 req/s | per user (`USER_EMAIL` or `ANONYMOUS`) | none | `entrez` |
| `BOLD` | 5 req/s and 50 req/min | per user | none | `bold` |

## 3. Backends (`config.throttle_backend`)

### 3.1 `sqlite` (default)

| ID | Requirement |
|---|---|
| THR-001 | Timestamps are stored in table `throttle_<endpoint>` of `throttle_db.sqlite` in `tempdir` (global endpoints) or `user_tempdir` (per-user). The DB is created/WAL-enabled under an `fcntl` lock file. |
| THR-002 | `acquire()` loops: in an `IMMEDIATE` transaction, delete timestamps older than the window, count, and insert "now" iff within limits; otherwise sleep 0.1–2 s (random) and retry. Logs every ~15 s of waiting. |
| THR-003 | Window: 2 s when only a per-second limit exists (so at most `rps` requests per **2 s** — half the nominal rate); 12 s when a per-minute limit exists, with the per-second check over the last 2 s and the per-minute check over all rows in the 12 s window (THR-D-001). |
| THR-004 | Backoff (GBIF only): table `backoff_<endpoint>` holds `effective_rps`; a 429 divides it by `backoff_factor` at most once per 30 s, floored at 0.1; it resets to nominal 2 h after the last 429. State is per **endpoint**, not per service (THR-D-003). |
| THR-005 | The same `OperationalError` five times in a row inside `acquire()` is re-raised. |

Correct cross-node behaviour requires `tempdir` on a filesystem shared by
all nodes with working `fcntl` locks (see [../../nextflow/config-profiles.md](../../nextflow/config-profiles.md)).

### 3.2 `redis`

| ID | Requirement |
|---|---|
| THR-010 | Token buckets (`limiters.SyncTokenBucket`) named `throttle[:<email>]:<endpoint>:rps|rpm[:f<factor>]`, one per configured limit; `acquire()` takes one token from each. `max_sleep = 0` (unbounded wait). |
| THR-011 | Backoff state per **service**: key `…:<service>:BACKOFF_FACTOR` (TTL 2 h) multiplied by `backoff_factor` on a 429, debounced by `…:BACKOFF_DEBOUNCE` (30 s, `SET NX`); buckets are rebuilt when the factor changes. |
| THR-012 | Connection: `REDIS_HOST/PORT/PASSWORD`; TLS iff port 6380. A new client is created per `Throttle` instance. |

## 4. Retry (`Throttle.with_retry`)

| ID | Requirement |
|---|---|
| THR-020 | Each attempt acquires the throttle, then calls the function. |
| THR-021 | On an exception whose **string contains `429`**: notify backoff; sleep 10 s if the endpoint has a backoff factor, else **600 s**; reset the retry budget to `max_api_retries` (THR-D-002). |
| THR-022 | On any other exception: decrement the budget (initially `max_api_retries` = 3); when it reaches 0 raise `APIError("Failed to fetch data from API after 3 retries…")`; otherwise sleep 1 s and retry. Total attempts = 3. |
| THR-023 | With `with_cache=True`, the call goes through `coalesce(cache_key, …)` (§5); the default key is `cache.keyhash(func, args, kwargs)`. Exceptions are never cached; any non-`None` result (including empty lists) is cached. |

## 5. Coalescing (`coalesce`)

| ID | Requirement |
|---|---|
| THR-030 | Return the cached value on a hit. |
| THR-031 | If the throttle backend is not `redis` (or Redis is unreachable at first use), fetch, `cache.put`, return. |
| THR-032 | With Redis: `SET coalesce:lock:<key> NX EX 120`. The owner fetches, caches, deletes the lease. Others poll the cache every 1–1.5 s; if the lease disappears without a cached result, one waiter takes over; after 180 s a waiter fetches directly with a warning. |

## 6. Defects

| ID | Severity | Defect |
|---|---|---|
| THR-D-001 | Medium | SQLite per-minute limit is checked over a 12 s window (docstring says 90 s), allowing up to 5× the configured `requests_per_minute` (BOLD: 50/12 s instead of 50/min). |
| THR-D-002 | Medium | Rate-limit detection is `'429' in str(exc)`. Any error message containing "429" (URL, accession, taxid) is treated as rate limiting; for Entrez/BOLD this sleeps **10 min and resets the retry budget indefinitely**, so a persistent error can hang a task until its time limit (then the query loses its report). |
| THR-D-003 | Low | SQLite backoff is per endpoint, Redis backoff per service: a GBIF 429 slows both GBIF endpoints only with Redis. |
| THR-D-004 | Low | Entrez limits are per `USER_EMAIL`, but NCBI enforces per IP/key; several users on one host can exceed NCBI's limit together. |
| THR-D-005 | Low | A new Redis client per `Throttle()` (one per request) causes connection churn. |

## 7. Test mapping

`tests/test_cache.py`, `tests/test_coalesce.py` cover cache/coalescing.
No dedicated unit tests for the SQLite/Redis throttle windows or retry
policy.

---

## Provenance

**Initially derived from:** `throttle.py` (718), `coalesce.py` (212). v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
