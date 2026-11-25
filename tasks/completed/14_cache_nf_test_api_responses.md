# Task 14 — Versioned API-cache fixture for deterministic nf-test runs

**Status:** done
**Priority:** high (nf-test fails on almost every run from live-API drift)
**Scope:** `.github/workflows/nf-test.yml`, `test/core/nextflow.config`,
`test/core/README.md`, `docs/nf-tests.md`, `spec/tests.md`,
`spec/python/modules/cache.md` (one sentence). No Python, module or
workflow-channel changes.
**Source material:**
- Issue qcif/taxodactyl#369 "Cache API responses for deterministic nf-test runs"
- `spec/python/modules/cache.md` (CCH-001…CCH-010, CCH-D-002, CCH-D-003)
- `spec/tests.md` (TST-023, TST-024, TST-G-005, TST-G-009)
- Existing frozen refdata pattern: the "Download taxonkit" and "Download
  subset blastdb" steps in `.github/workflows/nf-test.yml`, and the version
  block in `test/core/README.md`.
- No Spec Kit feature directory and no `.specify/extensions.yml` exist; this
  brief is based on the `spec/` documents and the code directly.
- No `tasks/todo.md` item covers this work.

**Implementation authorization:** given by the user (`/speckit-implement 14`, 2026-11-25).

## Overview

**The problem.** The core nf-test runs the whole workflow. Two of its steps,
P4 (source diversity) and P5 (database coverage), ask the live GBIF and NCBI
GenBank APIs for data. That data changes from week to week, so the nf-test
snapshot, the flag baselines and the Selenium reports almost never match. A
failure tells us nothing.

**What already exists.** The Python code already caches every API response in
a SQLite file, `<temp_root>/biosecurity/cache_db.sqlite`. Each entry expires
after `cache_timeout_hours`, which defaults to 168 (7 days). In CI,
`temp_root` is `$RUNNER_TEMP/taxodactyl`, which is deleted after every job,
so every run starts with an empty cache.

**The fix.** Treat a filled cache database as a **test fixture**, exactly
like the frozen taxdump and subset BLAST DB:

- It is a dated zip, `api-cache/<version>.zip`, in DAFF's public
  `daffstandard/test-data` blob container. The version and a SHA-256 of the
  database are pinned in the workflow and in `test/core/README.md`, next to
  the other refdata versions.
- Before each run, CI downloads it, checks the hash, and copies it into the
  job's throwaway temp root. The run reads from that copy, so the published
  fixture never changes. This works on any runner, self-hosted or
  GitHub-hosted.
- `CACHE_TIMEOUT_HOURS=876000` (about 100 years) stops the fixture's entries
  from expiring.
- After the run, CI reports how many entries were added. Any growth is a
  **cache miss**: a request that wasn't in the fixture and went to the live
  API. It's a warning, not a failure.
- A dispatch input **"Use cached API responses"** (`use_cache`, default on)
  can be turned off to skip the fixture and run against the live APIs.
- Every run saves a clean copy of its cache database with the saved run files
  on the self-hosted runner. A live run's copy is the candidate for the next
  fixture version.

Updating the fixture is a deliberate, user-owned change: make a new version,
upload it, bump the pinned version and hash, and re-baseline in the same PR.

The issue suggests a `TAXODACTYL_TEMP` env var, but nothing in the repo reads
one. The real setting is the Nextflow parameter `params.temp_root_dir`. The
workflow already fills it in with `sed`, and the two API-calling modules
already pass it on (`--temp-root`) and bind it into the container. So only the
CI wiring needs to change.

**Only the API cache, never the throttle state.** The temp root also holds
the request-throttle databases. These are separate files, checked
2026-11-25:

| File (under `<temp_root>/biosecurity/`) | Written by | Tables | In fixture? |
|---|---|---|---|
| `cache_db.sqlite` | `config.cache_sqlite_path` (`scripts/src/utils/config/config.py:523`), `SqliteCacheBackend` (`scripts/src/utils/cache.py:273`) | `cache` | **yes, only this** |
| `cache_db.sqlite.lock` | `_get_db_lock_file` (`scripts/src/utils/cache.py:132`) | – (lock file) | no |
| `throttle_db.sqlite` | `config.throttle_sqlite_global_path` (`config.py:515`), `scripts/src/utils/throttle.py:144` | throttle + backoff | no |
| `<email or ANONYMOUS>/throttle_db.sqlite` | `config.throttle_sqlite_path` (`config.py:511`) | throttle + backoff | no (and the directory name may be the NCBI email) |

The steps below only ever read or write `cache_db.sqlite`. The install and
save steps also check that the database holds exactly one table, `cache`, and
refuse anything else.

**Known catch.** Empty (`None`) results and errors are not cached (CCH-003,
CCH-005), so those requests still go to the live API on every run. They show
up in the miss count. If one of them later succeeds, that run drifts.

**Bootstrapping.** No fixture exists yet. The workflow must keep working until
the user uploads the first one, so an empty pinned version means live mode,
with a warning.

**Decisions made (2026-11-25):**
- The cache is a versioned fixture hosted with the public refdata in
  `daffstandard/test-data`, not committed to git and not kept as state on
  `daff-runner`. This replaces the earlier `/var/cache/taxodactyl` and
  `reset_cache` design. `/var/cache/taxodactyl` is no longer used.
- Keep the `use_cache` dispatch input (default true). When it's false, the
  run uses the live APIs.
- The user creates, checks and uploads fixture versions and owns all testing
  (see below).

## Preconditions

- Start from `main`. Check the current branch first (`AGENTS.md`).
- The user has write access to the `daffstandard` storage account's
  `test-data` container (see `docs/azure`). The implementer doesn't upload
  anything.
- Fixture versions must be uploaded under
  `test-data/taxodactyl/core/refdata/api-cache/<version>.zip`, readable at
  `https://daffstandard.blob.core.windows.net/test-data/taxodactyl/core/refdata/api-cache/<version>.zip`.
  `<version>` is a date, `YYYY-MM-DD`, like the other refdata. The zip
  contains `<version>/cache_db.sqlite`, the same layout as the blastdb and
  taxdump zips.

## Objective

When a fixture version is pinned and `use_cache` isn't false, every
`nf-test.yml` run (scheduled, PR via `workflow_call`, dispatch) gets a fresh,
hash-checked copy of the pinned fixture at
`$RUNNER_TEMP/taxodactyl/biosecurity/cache_db.sqlite` before nf-test runs, and
its entries never expire. Two runs with the same code, refdata and fixture
give the same snapshot, flags and Selenium results, apart from cache misses,
which are reported. Every run saves a compacted copy of its final cache to
`$RUNNER_TEMP/nf-test/api_cache/cache_db.sqlite`. That folder is kept on the
self-hosted runner and never uploaded as a GitHub artifact.

## Implementation

### Phase 1 — Pinned version and input (`.github/workflows/nf-test.yml`)

1. Add top-level `env` entries next to `NFT_VER`/`MOCK_BLAST`:
   ```yaml
   # Frozen GBIF/NCBI API responses (SQLite cache) used as a test fixture so
   # runs don't drift with live API data (#369). Empty = no fixture yet: run
   # against live APIs. Bump both together; see test/core/README.md
   API_CACHE_VERSION: ""
   API_CACHE_SHA256: ""
   ```
   Leave both empty. The user fills them in after uploading the first
   fixture (see the hand-off).
2. Add to `on.workflow_dispatch.inputs`, after `image`:
   ```yaml
   use_cache:
     description: Use cached API responses (untick to query live GBIF/NCBI APIs)
     type: boolean
     required: false
     default: true
   ```
   Don't add it to `on.workflow_call.inputs`. `inputs.use_cache` is empty on
   `schedule` and `workflow_call` events, so only the literal string `false`
   may select live mode.

### Phase 2 — Select mode (`.github/workflows/nf-test.yml`)

1. Insert a step **"Select API cache mode"** immediately before
   "Record run info". Pass the input through `env`, not inline:
   ```yaml
   # cached: install the pinned API-cache fixture before the run.
   # live: start from an empty cache (use_cache=false, or no fixture pinned)
   - name: Select API cache mode
     env:
       USE_CACHE: ${{ inputs.use_cache }}
     run: |
       if [[ "$USE_CACHE" == "false" ]]; then
         mode=live
       elif [[ -z "$API_CACHE_VERSION" ]]; then
         mode=live
         echo "::warning::No API cache fixture pinned (API_CACHE_VERSION is empty); querying live APIs"
       else
         mode=cached
       fi
       echo "API_CACHE_MODE=$mode" >> "$GITHUB_ENV"
       echo "API cache mode: $mode"
   ```
2. In "Record run info", add these to the block that writes `run_info.txt`:
   `echo "api_cache: $API_CACHE_MODE"` and
   `echo "api_cache_version: ${API_CACHE_VERSION:-none}"`.

The temp root stays `$RUNNER_TEMP/taxodactyl` in both modes. Leave the
"Resolve core scenario CUSTOMISE placeholders" step's `temp_root_dir`
sed and `mkdir -p` as they are.

### Phase 3 — Install the fixture (`.github/workflows/nf-test.yml`)

Add a step **"Install API cache fixture"** right after "Resolve core scenario
CUSTOMISE placeholders" (which creates `$RUNNER_TEMP/taxodactyl`):

```yaml
# Copy the pinned fixture into this job's temp root. The run may add
# entries (cache misses) to this copy; the published fixture is unchanged
- name: Install API cache fixture
  if: env.API_CACHE_MODE == 'cached'
  run: |
    wget -q "https://daffstandard.blob.core.windows.net/test-data/taxodactyl/core/refdata/api-cache/$API_CACHE_VERSION.zip"
    mkdir -p "$RUNNER_TEMP/api-cache" "$RUNNER_TEMP/taxodactyl/biosecurity"
    unzip -q "$API_CACHE_VERSION.zip" -d "$RUNNER_TEMP/api-cache"
    fixture="$RUNNER_TEMP/api-cache/$API_CACHE_VERSION/cache_db.sqlite"
    echo "$API_CACHE_SHA256  $fixture" | sha256sum -c -
    # The fixture must hold the API cache only (no throttle tables)
    python3 -c "import sqlite3,sys; t=[r[0] for r in sqlite3.connect(sys.argv[1]).execute(\"select name from sqlite_master where type='table'\")]; sys.exit(0 if t==['cache'] else 'Unexpected tables in API cache fixture: %s' % t)" "$fixture"
    cp "$fixture" "$RUNNER_TEMP/taxodactyl/biosecurity/cache_db.sqlite"
```

- Copy only `cache_db.sqlite`. Never copy any `throttle_*` file or the
  `biosecurity/` directory as a whole. Each run starts with fresh throttle
  state.

- The hash check must fail the job on a mismatch or an empty
  `API_CACHE_SHA256`. Values are unpickled on read (CCH-D-002), so only the
  reviewed file may be loaded. `sha256sum -c` already fails in both cases.
  Don't add `continue-on-error`.
- Put the URL base in the same style as the taxonkit/blastdb steps. Don't
  invent a new variable for it.

### Phase 4 — Never-expiring entries (`test/core/nextflow.config`)

1. Add, after the `env.USER_EMAIL` line:
   ```groovy
   // ~100 years: entries in the API-cache fixture (see README.md) never
   // expire, so runs reuse the same GBIF/NCBI data (#369)
   env.CACHE_TIMEOUT_HOURS = '876000'
   ```
   `CACHE_TIMEOUT_HOURS` is read by `scripts/src/utils/config/mappings.py:137`.
   Nextflow's `env` scope exports it into each task, and Singularity passes the
   host environment into the container. It does no harm in live mode.
2. Don't add a `CUSTOMISE` placeholder for it, and don't touch the `sed` list.
3. `datetime.now() - timedelta(hours=876000)` (`scripts/src/utils/cache.py:339`)
   lands in about 1926, which is valid. No code change is needed.

### Phase 5 — Miss report and saved copy (`.github/workflows/nf-test.yml`)

All `python3` calls below run before `actions/setup-python` and use the
runner's `python3` with the standard-library `sqlite3`. That is CI-only and
outside the venv rule, which covers local development.

1. At the end of "Install API cache fixture", record the starting row count:
   ```bash
   rows=$(python3 -c "import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute('select count(*) from cache').fetchone()[0])" "$RUNNER_TEMP/taxodactyl/biosecurity/cache_db.sqlite")
   echo "API_CACHE_ROWS_BEFORE=$rows" >> "$GITHUB_ENV"
   echo "Fixture $API_CACHE_VERSION: $rows cached responses"
   ```
2. Add a step **"Report API cache"** after "Run core nf-test", with
   `if: always()` and `continue-on-error: true`. It must only read. It prints
   `API_CACHE_MODE`, `API_CACHE_VERSION`, the row count now
   (`ROWS_AFTER`, same query; treat a missing file as 0) and
   `API_CACHE_ROWS_BEFORE` (default 0). In cached mode, if
   `ROWS_AFTER > ROWS_BEFORE`, emit
   `::warning::<n> API responses were not in fixture <version> and were fetched live; results may drift. Consider a new fixture version`.
   It never fails the job.
3. Add a step **"Save API cache"** right after "Report API cache", with
   `if: always()` and `continue-on-error: true`. It writes a compacted,
   WAL-free copy into the saved run files:
   ```bash
   src="$RUNNER_TEMP/taxodactyl/biosecurity/cache_db.sqlite"
   dest="$RUNNER_TEMP/nf-test/api_cache/cache_db.sqlite"
   if [[ -f "$src" ]]; then
     mkdir -p "$(dirname "$dest")"
     python3 -c "import sqlite3,sys; sqlite3.connect(sys.argv[1]).execute('VACUUM INTO ?', (sys.argv[2],))" \
       "$src" "$dest"
     # Keep the copy only if it holds the API cache table and nothing else
     if python3 -c "import sqlite3,sys; t=[r[0] for r in sqlite3.connect(sys.argv[1]).execute(\"select name from sqlite_master where type='table'\")]; sys.exit(0 if t==['cache'] else 'Unexpected tables: %s' % t)" "$dest"; then
       sha256sum "$dest"
     else
       rm -f "$dest"
       echo "::warning::Saved API cache had unexpected tables; copy discarded"
     fi
   fi
   ```
   The source is `cache_db.sqlite` only. Don't glob `biosecurity/*`, and
   don't save any `throttle_*` database or the per-user directory.
   "Save run files on self-hosted runner" already copies `$RUNNER_TEMP/nf-test`
   to `/var/runner/<run_id>-<attempt>/`, so the copy ends up in
   `/var/runner/<run_id>-<attempt>/api_cache/cache_db.sqlite`. **Don't** upload it
   as a GitHub artifact: the repository is public, and the file hasn't been
   checked for secrets yet. Check that no `upload-artifact` step's `path`
   includes `$RUNNER_TEMP/nf-test` or `api_cache`.

### Phase 6 — Polish

- `git diff` must touch only the files listed under **Scope**. Strip trailing
  whitespace from edited lines; one existing line in `nf-test.yml` has
  trailing spaces, but leave lines you don't edit as they are.

## Documentation and configuration

- `test/core/README.md`:
  - Add `api-cache: none (pending first fixture)` to the version block (the
    `version/date/taxonkit/blastdb` lines). The user changes it when pinning a
    fixture.
  - Under "3. Required databases", add the fixture download: from
    `https://daffstandard.blob.core.windows.net/test-data/taxodactyl/core/refdata/api-cache/<version>.zip`,
    copy `<version>/cache_db.sqlite` to
    `<params.temp_root_dir>/biosecurity/cache_db.sqlite`. Warn that this
    overwrites any existing local cache there, so use a dedicated
    `temp_root_dir` for nf-test.
  - Add a "Refreshing the API-cache fixture" subsection that follows the
    fixture-creation steps of the hand-off below (live run → saved copy →
    secrets check → zip → upload → bump `API_CACHE_VERSION`/`API_CACHE_SHA256`
    and the README version → re-baseline in the same PR).
- `docs/nf-tests.md`: add a short "API response cache" subsection under
  "Configuration". It says P4/P5 cache GBIF/NCBI responses in
  `<temp_root_dir>/biosecurity/cache_db.sqlite`, the `core` scenario uses a
  versioned fixture (link to `test/core/README.md`),
  `CACHE_TIMEOUT_HOURS=876000`, `None`/error results aren't cached, and CI has
  the `use_cache` dispatch input and the cache-miss warning.
- `spec/tests.md` (the user agreed to this behaviour change on 2026-11-25):
  - TST-024: add the API-cache fixture (pinned version + SHA-256, downloaded
    from `daffstandard/test-data`, copied into the job temp root), the
    `use_cache` input, live mode when no version is pinned, the miss warning,
    and the saved compacted copy. Don't rewrite the parts of TST-024 about
    triggers or the runner, even though they are out of date. Record that
    staleness as a spin-off in `tasks/todo.md` if it's still there when you
    finish.
  - TST-G-005 / TST-G-009: say that the `core` scenario reads frozen API
    responses when a fixture is pinned. Drift now comes only from cache
    misses (uncached `None`/error results, or code that changes request
    parameters and so creates new cache keys), live-mode runs, or a fixture
    version bump.
- `spec/python/modules/cache.md`: the cache behaviour itself doesn't change.
  Add one sentence to CCH-D-003: in the nf-test fixture, a cached transient
  empty response stays until the next fixture version.

## Testing decision

Decided by the user on 2026-11-25, for this task (#369) only. The switch to a
fixture adds user-owned steps (creating and uploading fixture versions) but
leaves ownership as it was:

- **Affected suites:** core nf-test snapshot
  (`test/core/taxodactyl.workflow.nf.test.snap`), flag baselines
  (`test/core/flags/*.flag`), Selenium expected reports
  (`test/selenium/expected/*.yaml`, as exercised by
  `test/selenium/test_reports.py`). Unit tests (`scripts/tests/test_cache.py`
  etc.) aren't affected: no Python changes.
- **New automated assertions:** none. The user owns all testing.
- **Who runs checks:** the user triggers `nf-test.yml` runs and inspects
  results. The implementer only runs static/lint checks (see Validation).
- **Who reviews drift:** the user.
- **Who may update expected results and the fixture:** the user only. The
  implementer must not change snapshots, flag baselines or Selenium fixtures,
  must not run `--update-snapshot`, must not upload to blob storage, and must
  not set `API_CACHE_VERSION`/`API_CACHE_SHA256` unless the user supplies
  the values.

## Validation

Implementer (automated, static only):

1. Check that `.github/workflows/nf-test.yml` is valid YAML:
   `. /home/cameron/.local/envs/claude/bin/activate && python -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" .github/workflows/nf-test.yml`.
   Use `actionlint` too if it's installed. Report it as unavailable if not.
2. Run `grep -n 'CACHE_TIMEOUT_HOURS' test/core/nextflow.config` and show
   the line. (`nextflow config` won't resolve with `CUSTOMISE` placeholders.)
3. Dry-run the mode selection in the scratchpad with `GITHUB_ENV` pointed at a
   scratch file. Try these combinations and show the selected mode for each:
   - `USE_CACHE=` (empty) and `API_CACHE_VERSION=` (empty): expect `live` plus
     the warning.
   - `USE_CACHE=` and `API_CACHE_VERSION=2026-01-01`: expect `cached`.
   - `USE_CACHE=true` and `API_CACHE_VERSION=2026-01-01`: expect `cached`.
   - `USE_CACHE=false` and `API_CACHE_VERSION=2026-01-01`: expect `live`.
4. Dry-run the install, report and save logic offline in the scratchpad. Build
   a tiny SQLite DB with a `cache(key TEXT PRIMARY KEY, value BLOB,
   created_at TIMESTAMP)` table and two rows. Zip it as
   `2026-01-01/cache_db.sqlite`. Then run the step bodies with the `wget`
   line replaced by a local copy, and with `RUNNER_TEMP` pointing at the
   scratchpad. Show that:
   - the hash check passes with the right hash and fails with a wrong or
     empty one;
   - the row count is `2`, and after you insert one row the miss warning
     reports `1`;
   - `VACUUM INTO` writes a single file with no `-wal`.
   - the table check rejects a database with an extra table: add a
     `throttle` table to a copy, then show that install fails and that save
     discards the copy with the warning;
   - a `throttle_db.sqlite` and a `<email>/throttle_db.sqlite` placed under
     the scratch `taxodactyl/biosecurity/` end up in neither the installed
     temp root nor `nf-test/api_cache/`.
   Use `/home/cameron/.local/envs/claude/bin/python` if the system `python3`
   is off-limits locally.
5. Record every check you ran and its result in the hand-off message,
   including any that were unavailable.

User (manual, pending): see the hand-off below.

## Test impact and manual review

**Expected changes:** none to any checked-in expected file from this task.
Until a fixture is pinned, runs are live, so they behave as they do today.
The baselines were generated from live data on 2026-08-04
(`test/core/README.md`), so they will need a user-owned re-baseline against
the first fixture.

**Possible changes (need evidence):** a fixture only freezes successful
responses. How much of the run is still live (misses) is unknown until run B
below reports it.

**Hand-off to the user (fixture creation, runs and review are user-owned):**

1. **Create fixture candidate.** Push the branch and dispatch `nf-test.yml`
   (`use_cache` either way, since no version is pinned yet) on the
   self-hosted runner. Reference data: taxdump `2026-05-08`, subset BLAST DB
   `2026-07-29`. Image: `neoformit/taxodactyl:main` unless a PR image is under
   test. This is run A. Its cache is saved at
   `/var/runner/<run_id>-<attempt>/api_cache/cache_db.sqlite`.
2. **Check it for secrets before publishing** (the container is public):
   `grep -c -a -F "<NCBI_API_KEY>" cache_db.sqlite` and the same for the
   NCBI user email should both print `0`. Keys are hashes, and values are
   GBIF/NCBI responses. Confirm it holds only the API cache:
   `sqlite3 cache_db.sqlite .tables` should print only `cache` (no throttle
   or backoff tables). Also check its size.
3. **Package and upload.** Choose `<version>` (today's date). Put the file at
   `<version>/cache_db.sqlite` and zip it as `<version>.zip`. Run
   `sha256sum <version>/cache_db.sqlite`. Upload the zip to
   `test-data/taxodactyl/core/refdata/api-cache/<version>.zip`, and check it
   downloads anonymously.
4. **Pin.** Set `API_CACHE_VERSION`/`API_CACHE_SHA256` in
   `.github/workflows/nf-test.yml` and the `api-cache:` line in
   `test/core/README.md`. You can also give the values to the implementer to
   apply.
5. **Run B and C** (cached, default inputs), back to back. In each, check:
   - the "Install API cache fixture" hash check passed;
   - `run_info.txt` shows `api_cache: cached` and the version;
   - the "Report API cache" miss count (ideally 0; whatever remains should be
     requests that returned `None` or an error in run A).
6. **Compare C with B** on `daff-runner` (`/var/runner/<run_id>-<attempt>/`):
   `nf-test_errors_summary.csv`, `flags_results.txt`, Selenium
   `test-report.json`/`review.html`. They should show the same differences
   against the old baselines. Use the `investigate-runner` and
   `selenium-report` skills to triage. Classify every B-vs-C difference as:
   (a) a reported cache miss (expected), (b) something not API-related
   (timestamps, ordering, a regression), or (c) a live request with no miss
   reported (an uncached code path). (b) and (c) need a new issue.
7. **Run D** with `use_cache=false`. It should show `api_cache: live` and
   no install step, and it drifts as before. This confirms the live path
   still works.
8. **Re-baseline.** Once B and C agree, re-baseline
   `test/core/taxodactyl.workflow.nf.test.snap`, `test/core/flags/` and
   `test/selenium/expected/` against fixture `<version>` in the same PR that
   pins it, and update the `date:` in `test/core/README.md`.

Status tracking: report implementation status apart from manual validation.
Each manual step above stays **pending** until the user provides evidence.

## Completion criteria

- [x] Phases 1–5 done in `.github/workflows/nf-test.yml` and
      `test/core/nextflow.config`, with `API_CACHE_VERSION`/`API_CACHE_SHA256`
      empty unless the user supplied the values, and nothing outside Scope
      changed.
- [x] Docs and spec updates listed above are done.
- [x] Static validation steps 1–4 run, with results reported, including any
      that were unavailable.
- [x] No snapshot, flag baseline, Selenium fixture or blob-storage object
      changed by the implementer.
- [ ] **Manual (user):** fixture created, checked for secrets, uploaded and
      pinned; runs B, C and D done; B and C agree apart from class (a)
      differences; baselines re-generated against the fixture. Pending until
      the user provides evidence.

## Risks

- **Cache misses:** `None`/error results (CCH-003/005), and requests whose
  cache keys change because the code changed, go live on every run. These
  are now reported, not silent. If misses persist, think about caching
  negative results in a follow-up. That's not in scope here.
- **Frozen bad data:** a transient empty response captured in the fixture
  stays until the next version (CCH-D-003). The fix is a new fixture version
  plus a re-baseline.
- **Pickles from a public URL:** values are unpickled (CCH-D-002). The pinned
  SHA-256 means only the reviewed file is loaded. Changing the hash is a
  reviewed code change.
- **Secrets in a public fixture:** the hand-off's secrets check is a
  required, manual step before every upload.
- **Throttle state leaking into the fixture:** prevented three ways. The
  steps handle `cache_db.sqlite` by exact name. Install and save both check
  that the database's only table is `cache`. The manual `.tables` check runs
  before upload. If a future code change puts the throttle tables into the
  cache file, these checks fail loudly rather than publishing them.
- **Live-API canary is manual:** scheduled and PR runs no longer exercise the
  live APIs once a fixture is pinned. API breakage only shows up in a
  `use_cache=false` dispatch run.
- **Fixture staleness vs code:** a PR that changes request parameters
  produces misses and drift for that PR. That is real, expected and visible
  in the miss warning. The fix is a fixture bump in that PR.

## Outcomes

Implemented 2026-11-25 on branch `task-14-cache-nf-test-api-responses`.

### Completed work

- `.github/workflows/nf-test.yml`:
  - Top-level `API_CACHE_VERSION: ""` and `API_CACHE_SHA256: ""`, left
    empty (no user-supplied values yet).
  - `workflow_dispatch` input `use_cache` (boolean, default true). It isn't
    added to `workflow_call`.
  - "Select API cache mode" step before "Record run info". `run_info.txt`
    now records `api_cache` and `api_cache_version`.
  - "Install API cache fixture" step after "Resolve core scenario CUSTOMISE
    placeholders". It downloads, checks the SHA-256 and table list, copies
    only `cache_db.sqlite`, and records `API_CACHE_ROWS_BEFORE`.
  - "Report API cache" and "Save API cache" steps after "Run core nf-test"
    (`if: always()`, `continue-on-error: true`).
- `test/core/nextflow.config`: `env.CACHE_TIMEOUT_HOURS = '876000'`.
- `test/core/README.md`: `api-cache:` version line, fixture download under
  "3. Required databases" (with the overwrite warning), a CI fixture
  summary, and "Refreshing the API-cache fixture".
- `docs/nf-tests.md`: "API response cache" subsection under Configuration.
- `spec/tests.md`: TST-024 (fixture behaviour appended; trigger/runner text
  left as is), TST-G-005, TST-G-009, and the suite table row 3 note.
- `spec/python/modules/cache.md`: one sentence added to CCH-D-003.

### Deviations

- "Report API cache" uses the same plain `sqlite3.connect` row-count query
  as the install step. A read-only (`mode=ro`) connection was considered
  and dropped: the cache is in WAL mode, and a read-only open can fail when
  the `-shm` file is missing. A plain `SELECT` doesn't modify the data.
- "Save API cache" prints `No API cache at <path>; nothing to save` when
  the source file is missing (the brief's snippet was silent).
- The install step has a short comment explaining the hash check (CCH-D-002).
- Rebased onto `origin/main` after #370, which names the saved-run folder
  `/var/runner/${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}` instead of the run
  number. The README and this brief now say `<run_id>-<attempt>`.
- `spec/tests.md` row 3 of the suite table now says P4/P5 use live APIs
  "unless an API-cache fixture is pinned (TST-024)", for consistency.

### Validation (implementer, static/offline)

1. YAML: valid (PyYAML via `scripts/venv`; the claude venv has no PyYAML).
   Step order confirmed. `actionlint`: **unavailable** (not installed).
2. `grep -n CACHE_TIMEOUT_HOURS test/core/nextflow.config` →
   `18:env.CACHE_TIMEOUT_HOURS = '876000'`.
3. Mode selection (step body extracted from the YAML, run with
   `GITHUB_ENV` in the scratchpad):
   - `USE_CACHE=''`, `API_CACHE_VERSION=''` → `live` plus the warning
   - `USE_CACHE=''`, `2026-01-01` → `cached`
   - `USE_CACHE=true`, `2026-01-01` → `cached`
   - `USE_CACHE=false`, `2026-01-01` → `live`
4. Install/report/save (step bodies extracted from the YAML, run with
   `bash --noprofile --norc -eo pipefail` as Actions does, `wget` replaced
   by a local copy, `python3` shimmed to the claude venv):
   - Hash check: the right hash passes; a wrong hash and an empty hash both
     exit 1, and nothing is installed.
   - Row count `2`. One inserted row → warning "1 API responses were not in
     fixture 2026-01-01…", exit 0. Live mode: no warning. Missing DB: 0
     rows, exit 0.
   - With a writer holding uncheckpointed WAL rows (`-wal`/`-shm` present),
     the report counted them (4 rows, 2 misses). `VACUUM INTO` saved a
     single file (`journal_mode` `delete`, no `-wal`) holding all 4 rows.
   - A fixture with an extra `throttle` table: install exits 1 ("Unexpected
     tables in API cache fixture: ['cache', 'throttle']") and nothing is
     installed. Save discards the copy with the warning, exit 0.
   - Throttle files: with `throttle_db.sqlite` and
     `user@example.org/throttle_db.sqlite` shipped inside the fixture zip,
     only `cache_db.sqlite` reaches the temp root. With them placed in the
     temp root (as a run creates them), only `cache_db.sqlite` is saved to
     `nf-test/api_cache/`.
   - No `upload-artifact` path includes `$RUNNER_TEMP/nf-test` or
     `api_cache` (paths: `review.html`, `test-report.json`,
     `$TEST_DIR/output/reports`).
- `git diff` touches only the Scope files plus the task lifecycle files.
  No trailing whitespace on added lines. No snapshot, flag baseline or
  Selenium fixture changed, and nothing was uploaded.

### Manual validation (user-owned): pending

Hand-off steps 1–8 (fixture run A, secrets check, upload, pin, runs B/C/D,
re-baseline) are **pending** until the user provides evidence. Until a
version is pinned, every run is in live mode with a warning, so CI behaves
as it does today. Tracked in `tasks/todo.md`.

### Spin-offs

- TST-024's trigger and runner text in `spec/tests.md` is out of date
  (it says manual-only on a GitHub-hosted runner; the workflow runs weekly,
  on PRs via `build-pr.yml`, and on the self-hosted runner). Added to
  `tasks/todo.md`.
- The fixture creation, pinning and re-baseline above. Added to
  `tasks/todo.md`.
