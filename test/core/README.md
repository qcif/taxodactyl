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

Updating the fixture is a deliberate, reviewed change, like bumping the
taxdump or BLAST DB. Do it in a PR, and re-baseline in the same PR.

**When to refresh**

- "Report API cache" warns about cache misses on every cached run. This
  usually means a code change altered API request parameters, so the
  requests have new cache keys that aren't in the fixture.
- A transient empty or bad response was captured in the fixture
  (CCH-D-003). It stays until the next version.
- You deliberately want the tests to reflect newer GBIF/NCBI data.

**Never change or delete a published version.** Older commits pin their
version and hash, so each refresh is a new dated version.

**1. Live run.** Run `nf-test.yml` in live mode on the self-hosted runner,
from the branch that will carry the new pin:

```
gh workflow run nf-test.yml \
  --repo qcif/taxodactyl \
  --ref <branch> \
  -f use_cache=false
```

A PR run also works while no version is pinned. Pushing to a PR cancels its
running nf-test job, so don't push until the live run has finished. When it
finishes:

- `run_info.txt` should show `api_cache: live`.
- Note the SHA-256 printed by the "Save API cache" step.
- The copy is saved at
  `/var/runner/<run_id>-<attempt>/api_cache/cache_db.sqlite` on
  `daff-runner`. `<run_id>` is the run ID in the run's URL. For a PR run,
  that's the calling `build-pr` run.

**2. Fetch the copy** and check that it's the file from that run:

```
scp daff-runner:/var/runner/<run_id>-<attempt>/api_cache/cache_db.sqlite .
ssh daff-runner cat /var/runner/<run_id>-<attempt>/run_info.txt
sha256sum cache_db.sqlite
```

`run_info.txt` should show your run's `run_url` and `api_cache: live`. The
hash should match the one from step 1.

**3. Inspect it.** The fixture is published in a public container, and its
values are Python pickles that the workflow unpickles (CCH-D-002). Check it
before publishing, and **don't unpickle it**: read it with `sqlite3` only.

```
python3 - cache_db.sqlite <<'EOF'
import re, sqlite3, sys
db = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro&immutable=1", uri=True)
print("integrity:", db.execute("pragma integrity_check").fetchone()[0])
print("objects:", db.execute("select type, name from sqlite_master").fetchall())
print("rows, oldest, newest:",
      db.execute("select count(*), min(created_at), max(created_at) from cache").fetchone())
bad = db.execute("select count(*) from cache where length(key) != 64 or value is null").fetchone()[0]
print("bad keys or empty values:", bad)
raw = open(sys.argv[1], "rb").read()
print("NCBI-key-shaped tokens:", len(re.findall(rb"(?<![0-9a-fA-F])[0-9a-f]{36}(?![0-9a-fA-F])", raw)))
EOF
```

Expect:

- **integrity:** `ok`.
- **objects:** only the `cache` table and its index
  (`sqlite_autoindex_cache_1`). There must be no throttle or backoff
  tables.
- **rows:** a few thousand (3,156 for `2026-11-26`), all created during the
  live run.
- **bad keys or empty values, and NCBI-key-shaped tokens:** both `0`.

Then search the raw file for the NCBI API key and email used in CI (the
repository secrets `NCBI_API_KEY` and `NCBI_USER_EMAIL`). Both counts must
be `0`:

```
grep -c -a -F "<NCBI_API_KEY>" cache_db.sqlite
grep -c -a -F "<NCBI user email>" cache_db.sqlite
```

Other email addresses inside the data are expected: GenBank comments and
GBIF annotations contain public contact addresses.

**4. Package.** Choose `<version>`, today's date as `YYYY-MM-DD`. The zip
contains `<version>/cache_db.sqlite`, the same layout as the taxdump and
BLAST DB zips:

```
mkdir <version>
cp cache_db.sqlite <version>/
zip -X -9 <version>.zip <version>/cache_db.sqlite
sha256sum <version>/cache_db.sqlite
sha256sum <version>.zip
```

The workflow pins the hash of the **database**, not of the zip. Keep the
zip hash too, to check the upload.

**5. Upload** to the `test-data` container of the `daffstandard` storage
account (see `docs/azure`), then check that it downloads anonymously with
the same zip hash:

```
az storage blob upload \
  --account-name daffstandard \
  --container-name test-data \
  --name taxodactyl/core/refdata/api-cache/<version>.zip \
  --file <version>.zip \
  --auth-mode login
wget -q https://daffstandard.blob.core.windows.net/test-data/taxodactyl/core/refdata/api-cache/<version>.zip
sha256sum <version>.zip
```

**6. Pin.** In the PR, update these together:

- `API_CACHE_VERSION` and `API_CACHE_SHA256` (the database hash) in
  `.github/workflows/nf-test.yml`;
- the `api-cache:` line at the top of this file.

Pushing the pin starts a cached PR run.

**7. Check two cached runs.** Use the PR run from step 6, plus a re-run of
the same job (`gh run rerun <run_id>`, saved as attempt 2). In each run:

- "Install API cache fixture" passes and logs
  `Fixture <version>: <n> cached responses`;
- `run_info.txt` shows `api_cache: cached` and the new version;
- "Report API cache" shows the same count before and after, i.e. 0 cache
  misses.

Then compare the two saved runs on `daff-runner`. They should be
identical, apart from timestamps and durations:

- `flags_results.txt`;
- `flags/evaluated/`;
- `nf-test_errors*.csv`;
- `review.html`.

Investigate any other difference before going on: a reported cache miss,
something not API-related, or a live request that wasn't reported.

**8. Re-baseline** against the new fixture in the same PR:

- `taxodactyl.workflow.nf.test.snap` (`--update-snapshot`);
- `flags/` (`bin/collect_flags.sh` over the reviewed run);
- `test/selenium/expected/`.

Review the diff before accepting it (`spec/tests.md` §5.3), and update
`date:` at the top of this file.

**9. Clean up.** Delete your local copies of `cache_db.sqlite`,
`<version>/` and `<version>.zip`. They aren't git-ignored.
