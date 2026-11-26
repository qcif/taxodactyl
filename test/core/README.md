### Core test scenario

version: 1.0
date: 2026-08-04
taxonkit: 2026-05-08
blastdb: 2026-07-29/subset_core_nt
api-cache: 2026-11-26

This test scenario consists of a diverse set of samples as described by `metadata.csv`.

The nf-test snapshot, flags and blast_result.xml have been generated using reference data versions noted above. 

Follow the instructions in `${projectDir}/docs/nf-tests.md` to run this test, changing steps:

#### 3. Required databases

To run this test with the same versions as the snapshot, download and extract:
- Subset blast database from `https://daffstandard.blob.core.windows.net/test-data/taxodactyl/core/refdata/blastdb/2026-07-29.zip` to `${projectDir}/test/core/refdata/blastdb/2026-07-29/`
- Taxonkit from `https://daffstandard.blob.core.windows.net/test-data/taxodactyl/core/refdata/taxdump/2026-05-08.zip` to `${projectDir}/test/core/refdata/taxonkit/2026-05-08/`
- API-cache fixture (frozen GBIF/NCBI responses, when a version is pinned
  above) from
  `https://daffstandard.blob.core.windows.net/test-data/taxodactyl/core/refdata/api-cache/<version>.zip`.
  Copy `<version>/cache_db.sqlite` from the zip to
  `<params.temp_root_dir>/biosecurity/cache_db.sqlite`. Check it against
  `API_CACHE_SHA256` in `.github/workflows/nf-test.yml` with `sha256sum`.
  **This overwrites any existing local API cache there**, so use a dedicated
  `temp_root_dir` for nf-test. Copy only `cache_db.sqlite`, never a
  `throttle_db.sqlite`.

In `${projectDir}$/test/core/nextflow.config`, set the following parameters:
```
params.blastdb = "${projectDir}/test/core/refdata/blastdb/2026-07-29/subset_core_nt"
params.taxdb = "${projectDir}/test/core/refdata/taxonkit/2026-05-08/"
```

`test/core/nextflow.config` sets `env.CACHE_TIMEOUT_HOURS = '876000'`
(about 100 years) so the fixture's entries never expire.

#### Configuration

- Set `nf-test.config` scenario to `core`.
- Set `params.mock_blast` to false to run blast using the subset database.

#### API-cache fixture in CI

P4 and P5 query the live GBIF and NCBI APIs, which change from week to week.
To keep runs comparable, `.github/workflows/nf-test.yml` installs a pinned,
versioned copy of the API cache (`API_CACHE_VERSION`, `API_CACHE_SHA256`)
into the job's temp root before nf-test runs:

- The job fails if the SHA-256 doesn't match, or if the database holds any
  table other than `cache`.
- After the run, "Report API cache" warns if the run added rows. Each added
  row is a cache miss: a request that wasn't in the fixture and went to the
  live API. Empty (`None`) results and errors are never cached, so they go
  live on every run.
- When `API_CACHE_VERSION` is empty, or the run is dispatched with
  "Use cached API responses" (`use_cache`) unticked, the run queries the
  live APIs.
- `run_info.txt` records `api_cache: cached|live` and `api_cache_version`.
- Every run saves a compacted copy of its final cache to
  `/var/runner/<run_id>-<attempt>/api_cache/cache_db.sqlite` on the
  self-hosted runner. It's never uploaded as a GitHub artifact.

#### Refreshing the API-cache fixture

Updating the fixture is a deliberate change. Bump the version and
re-baseline in the same PR.

1. **Live run.** Dispatch `nf-test.yml` with `use_cache` unticked (or with no
   version pinned) on the self-hosted runner, using the refdata versions
   above. Its cache is saved at
   `/var/runner/<run_id>-<attempt>/api_cache/cache_db.sqlite`.
2. **Check for secrets** before publishing (the container is public).
   These should both print `0`:
   ```
   grep -c -a -F "<NCBI_API_KEY>" cache_db.sqlite
   grep -c -a -F "<NCBI user email>" cache_db.sqlite
   ```
   `sqlite3 cache_db.sqlite .tables` should print only `cache` (no throttle
   or backoff tables). Also check the file size.
3. **Package.** Choose `<version>` (today's date, `YYYY-MM-DD`). Put the file
   at `<version>/cache_db.sqlite`, zip it as `<version>.zip`, and run
   `sha256sum <version>/cache_db.sqlite`.
4. **Upload** the zip to
   `test-data/taxodactyl/core/refdata/api-cache/<version>.zip` in the
   `daffstandard` storage account, and check that it downloads anonymously.
5. **Pin.** Set `API_CACHE_VERSION` and `API_CACHE_SHA256` in
   `.github/workflows/nf-test.yml`, and the `api-cache:` line above.
6. **Check.** Run two cached runs back to back. Both should show
   `api_cache: cached`, pass the hash check and report few or no cache
   misses, and agree with each other.
7. **Re-baseline** `taxodactyl.workflow.nf.test.snap`, `flags/` and
   `test/selenium/expected/` against the new fixture in the same PR, and
   update `date:` above.
