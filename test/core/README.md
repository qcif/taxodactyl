### Core test scenario

version: 1.0
date: 2026-08-04
taxonkit: 2026-05-08
blastdb: 2026-07-29/subset_core_nt
api-cache: 2026-11-26

This test runs the whole workflow once on a varied set of real samples, listed
in `metadata.csv`, and then checks every output file. The snapshot, flags and
`blast_result.xml` were made with the reference data versions above. The
`api-cache:` line names the frozen GBIF/NCBI responses that `nf-test.yml` uses
(see "API-cache fixture" below).

## In short

- **What it is for:** catching changes in what the workflow writes, whether a
  bug or new reference data.
- **What it checks:** two kinds of thing.
  - **Rule checks** must always hold: files are present, well formed and agree
    with each other, for example "the FASTA and the JSON list the same hits". A
    failure means something is broken. It can never be "accepted".
  - **Stored values** are compared with what a person reviewed and saved
    earlier, in `expected/<N>_<sample_id>.yaml`. A difference *may* be fine:
    GenBank, BOLD and GBIF change over time. After review, a person can accept
    it with `testkit.py promote`.
- **What it does not check:** anything the HTML report shows. That is the job
  of the Selenium tests (`test/selenium/`).
- **Where to look after a run:** the review page `nf-test-review.html`. It
  starts with a verdict and a list of what needs attention.

## Setting up

Follow `docs/nf-tests.md` to run tests, with these changes.

**Reference databases.** To match the versions above, download and extract:
- the subset BLAST database
  `https://daffstandard.blob.core.windows.net/test-data/taxodactyl/core/refdata/blastdb/2026-07-29.zip`
  to `test/core/refdata/blastdb/2026-07-29/`;
- Taxonkit
  `https://daffstandard.blob.core.windows.net/test-data/taxodactyl/core/refdata/taxdump/2026-05-08.zip`
  to `test/core/refdata/taxonkit/2026-05-08/`;
- optionally, the API-cache fixture (frozen GBIF/NCBI responses) named on the
  `api-cache:` line,
  `https://daffstandard.blob.core.windows.net/test-data/taxodactyl/core/refdata/api-cache/<version>.zip`.
  Copy `<version>/cache_db.sqlite` from the zip to
  `<params.temp_root_dir>/biosecurity/cache_db.sqlite` and check it against
  `API_CACHE_SHA256` in `.github/workflows/nf-test.yml` with `sha256sum`.
  **This overwrites any existing local API cache there**, so use a dedicated
  `temp_root_dir` for nf-test. Copy only `cache_db.sqlite`, never a
  `throttle_db.sqlite`. Without it, P4 and P5 query the live APIs.

Then set these in `test/core/nextflow.config`:
```
params.blastdb = "${projectDir}/test/core/refdata/blastdb/2026-07-29/subset_core_nt"
params.taxdb = "${projectDir}/test/core/refdata/taxonkit/2026-05-08/"
```

`test/core/nextflow.config` sets `env.CACHE_TIMEOUT_HOURS = '876000'`
(about 100 years) so the fixture's entries never expire.

**Configuration.** Set the `nf-test.config` scenario to `core`, and set
`params.mock_blast` to false so BLAST runs against the subset database.

The root `nf-test.config` selects scenario_04 and contains placeholders, so
naming a core test file is not enough to pick the core settings. Create a
config of your own:

```groovy
// /absolute/run/core.nf-test.config
config {
    workDir '/absolute/run/nf-test'
    testsDir 'test/core'
    configFile 'test/core/nextflow.config'
    profile 'singularity'
}
```

## Everyday tasks

### Run the test and open the review page

Run from the repository root:

```bash
mkdir -p /absolute/run/nf-test
export CORE_ASSERTIONS_OUTPUT=/absolute/run/nf-test/nf-test-assertions.json
nf-test test -c /absolute/run/core.nf-test.config \
  test/core/taxodactyl.assertions.nf.test --ci \
  --junitxml /absolute/run/nf-test/nf-test.xml
source scripts/venv/bin/activate
python test/core/testkit.py render \
  --junit /absolute/run/nf-test/nf-test.xml \
  --assertions /absolute/run/nf-test/nf-test-assertions.json \
  --output /absolute/run/nf-test/nf-test-review.html
```

Always name the test file. `nf-test test test/core/` would run *both* core
tests (see "Two core tests" below), and each one is a full workflow run.

The run writes `nf-test-assertions.json`, the **evidence**: one entry per check
and per value, with the expected and actual value and the files involved.
`render` turns it into the review page. Rendering never changes results or
stored values.

### Read the review page

From top to bottom:

- **Verdict:**
  - `PASSED`: everything matched.
  - `NEEDS BASELINE`: some values have nothing stored yet.
  - `DRIFT`: some stored values changed.
  - `FAILED`: a rule check failed.
  - `INCOMPLETE`: the workflow or the checks did not finish, or the JUnit XML
    is missing or invalid.
  - `INVALID EVIDENCE`: the evidence file is missing or unreadable.
- **Run health:** status of the workflow, the evaluation, the JUnit XML and the
  expectation files.
- **Needs attention:** one row per problem, most serious first, each linked to
  its sample. Changed values are grouped per sample and area. The **Comment**
  box next to "What went wrong" is for your notes (cause, ticket, "promote after
  checking GenBank"). It saves as you type, in this browser, for this run only.
  Use **Export comments** to keep them as a JSON file or share them, and
  **Import comments** to load a file, for example last run's notes into this
  run's page (they attach to the same sample and check). Comments never change
  results or stored values.
- **Failure analysis:** the same problems grouped across samples, such as
  "possible drift in Maps". This helps spot one cause behind many rows.
- **Samples × checks:** a grid of ✔ passed, ✖ failed and ? needs baseline.
- **Sample details:** for problem samples only. Each row has Check, Expected,
  Actual and Next step, links to the files that were read, and a ready-to-copy
  `promote` or `ingest` command.
- **All checks:** every check in the run, passed ones included, one collapsed
  block per sample, in the same Check / Expected / Actual / Next step table as
  "Sample details". For a passed rule check, Expected is the rule in plain words
  and Actual says the rule held (the evidence keeps no value for passed rules).
  For a stored value, both the stored and the produced value are shown.
- **Reference (collapsed):** commands; "What this test checks" (every check in
  plain words, from `schema.yaml`); a legend of channel letters; nf-test's own
  messages.

**"Rule failed" and "possible drift" are suggestions, not diagnoses.** The
label only says which *kind* of check broke, never why. A changed stored value
is often new reference data, but a regression looks exactly the same. Check
every change before you accept it.

Every message has the same shape: `<file>: <rule>`, then `Expected:` and
`Actual:`, plus `Difference:` for lists. Values are printed as they are:
strings in quotes, line breaks as `⏎`. For example:
`Expected: "rank,taxon⏎<rank>,Bruchophagus"` / `Actual: "rank,taxongenus,Bruchophagus"`.

### Accept a reviewed change (`promote`)

```bash
python test/core/testkit.py promote 16 \
  --assertions /absolute/run/nf-test/nf-test-assertions.json --dry-run
```

- **Choosing the target:** a file number (`16`), a file name without `.yaml`
  (`16_Scenario_04`) or a sample ID. `--all` targets every file.
- **Narrowing:** `--component maps`, or `--assertion <id or name>` (e.g.
  `maps/filenames`).
- **Answering:** `--dry-run` only shows the changes. Without it, answer each
  change with `y` (yes), `n` (no), `a` (yes to the rest of this sample) or `q`
  (stop). Then give a reason, which is saved in the file.
- **Afterwards:** run the test again.

`promote` changes or removes stored values; it never adds new ones. A value
stored in the file but no longer produced by the workflow is reported as
**stale**, and `promote` offers to remove it.

### Add a sample (`ingest`)

1. Add a row to `test/core/metadata.csv`. Nothing else needs changing.
2. Run the test. The new sample's rule checks run as usual. Its values have
   nothing stored yet ("needs baseline"), so the test fails.
3. Look at the sample on the review page.
4. Save its values:

   ```bash
   python test/core/testkit.py ingest --sample <sample_id> \
     --assertions /absolute/run/nf-test/nf-test-assertions.json --dry-run
   # Remove --dry-run, answer y / n / a / q, give a reason.
   ```

   This writes `test/core/expected/<N>_<sample_id>.yaml`.
5. Run the test again.

`ingest` only adds values that are missing. It never overwrites an existing
value (use `promote` for that). To remove a sample, delete its row in
`metadata.csv` and its file in `expected/`.

### When `ingest` or `promote` refuses

Both commands refuse rather than save something that cannot be trusted:

| Message starts with | Meaning | What to do |
|---|---|---|
| `Execution failure or incomplete evaluation` | The workflow failed, or some check could not run. | Fix the cause and run the test again. |
| `Stale assertion code` / `Stale schema` | `CoreAssertions.groovy` or `schema.yaml` changed after this run, even if only a comment changed. | Run the test again with the current code. |
| `Stale expectations for <sample>` | That sample's file in `expected/` changed after this run, perhaps from an earlier promote. | Run the test again. |
| `Invariant failures for <sample> … for <values> (<check>)` | A rule check failed in the same area as these values, so they cannot be trusted. Values in *other* areas of the sample are still offered. A failure that affects the whole run (sample `_run`) blocks every value. | Fix the cause of the rule failure. |
| `Existing key` / `Missing key` | You used `ingest` for a value that already exists, or `promote` for one that does not. | Use the other command. |
| `No matching promotable core observations` | Nothing matches the target and filters. | Check the target, `--component` and `--assertion`. |

Every write is all-or-nothing. The previous file is copied to
`expected/.backups/<name>.<timestamp>.yaml` (the last three per file are kept,
and the folder is not committed). `date:` and `provenance:` (which run, when,
and the reason given) are updated. These commands never touch Selenium
fixtures, flag files, `schema.yaml` or the check code.

## What the test checks

### Stored values (can be accepted with promote)

Only values the HTML report does *not* show are stored. That was a user
decision on 2026-11-26; everything the report shows is left to Selenium.

| Value | What it is | Why core keeps it |
|---|---|---|
| `blast_hits/sequence_fingerprints` | For each BLAST hit, a short code (the first 16 characters of the SHA-256 of its sequence). It changes whenever the sequence does. | The report does not show hit sequences. Because it is keyed by accession, a changed hit list also shows up here. |
| `maps/filenames` | The names of the coverage map images. | The report embeds the images without their names, and names that differ only in letter case have caused problems before. |

### Rule checks (must always hold; never accepted)

Each output folder of a sample is checked. The letters are the workflow's
output channels; the review page has a legend.

| Files | What is checked |
|---|---|
| H `all_hits.fasta`, `all_hits.json` | Each accession appears once; hits have the required fields; the sample ID matches; the FASTA is valid; each sequence matches its alignment in the JSON |
| C copies of the hit files, `query_title.txt` | Exact copies of the hit files |
| C `candidates.json`, `.csv`, `.fasta`, `_count.txt` | Well formed; species and accessions unique; the three files list the same hits; sequences match the hits; the count matches the species |
| C `1.flag`, `2.flag`, `7.flag` | One record, no target, an allowed value |
| C `assigned_taxonomy.csv` | Present only for flag 1A; same header and rows as the candidates CSV |
| C `preliminary_id_match.csv` | Present only for flag 7A; header `rank,taxon` and one row naming the sample's preliminary ID (see "Known problems") |
| C `taxa_of_concern_detected.csv` | Present only when the sample lists taxa of interest; one row per taxon, in input order; matches are candidate hits |
| C `candidates_phylogeny.fasta` | Valid; sequences match the hits |
| C `candidates_identity_boxplot.png` | Present only above the candidate limit; a readable image |
| S `4.flag`, `aggregated_sources.json` | Present only for 1 to max candidate species; one entry and one valid flag per species; sources are candidate hits and have the required fields |
| T `candidates_phylogeny.nwk` | A valid tree; its leaves are the selected sequences plus `QUERY`; empty only when nothing was selected |
| D `db_coverage.json` | Has candidate, taxon-of-interest and preliminary-ID sections; each taxon has target, related and country results; every count is a whole number or empty |
| F `5.1.flag`, `5.2.flag`, `5.3.flag` | Three files; exactly one record per taxon in `db_coverage.json`; every value allowed |
| M `map*.png` | Names are unique and look like `map*.png`; every map is a readable image |
| HTML reports | One per sample, correctly named. Their content is checked by Selenium |
| Versions, parameters, timestamp | One readable file each; BLAST, MAFFT and FastME are listed; required settings present; timestamp format `yyyyMMdd HHmmss` |
| Whole run | The workflow succeeded; every channel has one entry per sample (maps are optional); files sit in their sample's folder |

A candidate folder may contain only known file names; anything new fails so
that someone looks at it. Intermediate BLAST, taxonomy and alignment files are
not checked here. Exact BLAST numbers and parsing are tested in
`scripts/tests/test_blast_parser.py`, and hit selection in
`scripts/tests/test_phylogeny_sampling.py`.

Removed from core on 2026-11-26 because the report shows them: hit accession
lists; the values of flags 1, 2, 7, 4 and 5.x; selected tree sequences; source
accessions; and coverage taxa, states and species names. Record counts and
related-species names were already not compared. **Until Selenium fixtures
cover every sample, some of these are compared by neither suite** (spec
`TST-G-011`; task 12, Phase 12).

## Known problems

- **`C.pmi` fails for Scenario_04 and barcode_83_P59_Potyviridae_cluster_0_RC205.**
  `scripts/p3_assign_taxonomy.py` writes `preliminary_id_match.csv` without a
  line break between the header and the row (defect P3-D-008; nothing reads the
  file). By user decision it stays failing until a separate task fixes it, so
  core CI is red for this reason alone. It blocks only that sample's
  *candidates* values; map filenames and hit fingerprints can still be accepted.
- **Copying a run can lose files.** Zip archives and artifact downloads can drop
  symlinks and files whose names differ only in letter case. A retained copy
  lost `map_Bulimulus_sporadicus.png` that way. Copy runs with the tarball (see
  "In CI").

## Two core tests (for now)

The original snapshot test and the new assertion test run side by side (user
decision 2026-11-23). Retiring the original is a later decision.

| | Original | Assertions (task 12) |
|---|---|---|
| Test file | `taxodactyl.workflow.nf.test` + `.snap` | `taxodactyl.assertions.nf.test` + `expected/`, `schema.yaml` |
| CI workflow | `.github/workflows/nf-test.yml` | `.github/workflows/nf-test-core-assertions.yml` |
| Runs | Sunday 00:00 UTC, manual (callable from `build-pr.yml`, not used at present) | Pull requests to main via `build-pr.yml` (the PR's image, else `:main`), Sunday 12:00 UTC, manual |
| API responses | Pinned API-cache fixture (live with `use_cache` unticked) | Live APIs: the fixture is not installed yet |
| Flag check | "Test flags" against `flags/` | none (core checks that 5.x values are allowed; the values themselves are left to Selenium) |
| Review | snapshot error CSV, Selenium `review.html` | `nf-test-review` artifact and standalone `nf-test-review.html`, run-page summary, Selenium `review.html` |

The original files are byte-identical to commit `0f715e7`. Other scenarios and
the Selenium code, fixtures and tolerances are unchanged.

## In CI

`.github/workflows/nf-test-core-assertions.yml` (Actions →
nf-test-core-assertions → Run workflow, choosing the branch) runs
`taxodactyl.assertions.nf.test` with `CORE_REPO_ROOT` set. Then it:
- writes the verdict, needs-attention and failure-analysis tables to the run's
  summary page;
- uploads `nf-test-review-<runner>`, a self-contained folder. Open
  `nf-test-review.html` inside it. Its links go to copies of the files behind
  each failure, and the folder also holds the evidence JSON, the JUnit XML and
  the nf-test logs;
- uploads the same page on its own, unzipped, as the `nf-test-review.html`
  artifact. Browsers can block the zip on reputation alone (Firefox has called
  it a virus), but they don't check a plain `.html` file. Its file links only
  work inside the zip;
- on the self-hosted runner, keeps the run in
  `/var/runner/assertions-<run_id>-<run_attempt>/` together with
  `nf-test-run.tar.gz`, e.g. `/var/runner/assertions-12345678901-1/`. The run
  ID is unique across workflows; the `assertions-` prefix tells these runs
  apart from `nf-test.yml`'s `<run_id>-<run_attempt>` folders.

To build the same bundle locally:

```bash
python test/core/testkit.py render --junit <run>/nf-test.xml \
  --assertions <run>/nf-test-assertions.json --output <run>/nf-test-review.html \
  --summary <run>/nf-test-summary.md --bundle-dir <run>/nf-test-review
```

Links point only to files that exist inside the bundle. A page opened on its
own says which files are unavailable.

## API-cache fixture

These steps belong to the snapshot workflow, `nf-test.yml`. The assertion
workflow, `nf-test-core-assertions.yml`, does not install the fixture yet, so
it queries the live APIs.

### API-cache fixture in CI

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

### Refreshing the API-cache fixture

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
- `test/selenium/expected/`;
- `test/core/expected/` (assertion test) with `testkit.py promote`, once
  `nf-test-core-assertions.yml` installs the fixture. Until then the assertion
  test runs against the live APIs and its stored values are not tied to a
  fixture version.

Review the diff before accepting it (`spec/tests.md` §5.3), and update
`date:` at the top of this file.

**9. Clean up.** Delete your local copies of `cache_db.sqlite`,
`<version>/` and `<version>.zip`. They aren't git-ignored.

## How it works (for developers)

| File | Role |
|---|---|
| `metadata.csv` | The samples. One row per sample is all a new sample needs. |
| `taxodactyl.assertions.nf.test` | Runs the workflow once and passes its output channels to `CoreAssertions.groovy`. |
| `CoreAssertions.groovy` | Every check. Writes the evidence (`nf-test-assertions.json`) and gives nf-test one result per check. It contains no sample IDs. |
| `schema.yaml` | Declares every check and stored value: title, rule and plain-language text for the page. Groovy refuses anything undeclared. |
| `expected/<N>_<sample_id>.yaml` | Reviewed stored values, one file per sample, matched by `sample_id:`. `<N>` reuses the number of the Selenium fixture for the same sample, or else the next free number. Written only by `ingest`/`promote`; do not edit by hand. |
| `testkit.py` | Reads the evidence: `render`, `ingest`, `promote`. Never runs checks. |
| `contracts.test.groovy` | Synthetic scenarios for `CoreAssertions.groovy`. |

**Why the evidence file exists.** nf-test 0.9.5 reports only how many
assertions failed, not which ones, so each check also writes its result to the
JSON. No Python code re-checks workflow output. nf-test has no option to replay
only the checks, so after any change you need a new run.

**The `expected.files` check** fails, naming the file, for: a file whose sample
is not in `metadata.csv`; two files with the same `sample_id`; an unknown
component or value (including one core no longer compares); or an invalid
value. Stale values are not reported for an area whose rule check already
failed, so one broken file does not cause a cascade of failures.

**Expected file layout** is the same as the Selenium fixtures: `components` →
`assertions`, each with `id`, `type` and `value`. Grouped `{name, assertions}`
lists are supported but not used at present.

### Validation

```bash
source scripts/venv/bin/activate
PYTHONPATH=scripts python -m unittest discover -s scripts/tests -p 'test_nf_test_*.py' -b
# NFT_JAR is the jar shipped with nf-test 0.9.5:
java -cp "$NFT_JAR" groovy.ui.GroovyMain test/core/contracts.test.groovy "$PWD"
```

The 23 Groovy scenarios use disposable synthetic files. They cover:
- valid empty and skipped cases, and a new sample without a file (needs baseline);
- accepted synthetic data;
- missing, duplicate or wrongly placed samples, and malformed outputs;
- missing, extra or repeated 5.x records, and invalid flag values;
- changed flag values and coverage content, which must *not* fail core;
- a changed hit sequence failing only its fingerprint;
- a stored value core no longer compares, failing as unknown;
- orphan or duplicate files, unknown values, and independent failures.

The 43 Python tests cover:
- verdicts, the needs-attention order and rule text, and possible-drift labels;
- descriptions of list and fingerprint changes, a large passing run staying
  small, escaping, and portable links;
- schema labels, and that no sample ID appears in `CoreAssertions.groovy`;
- ingest and promote: file numbering, targets, `a`/`q` answers, per-sample
  freshness, blocking by rule failures (per sample and area), removal of stale
  values, other files left unchanged, backups, and quoting of fingerprints so
  that Groovy's YAML reader reads them as text.

## History and provenance

**Baseline.** The user explicitly validated and approved the supplied run on
2026-11-23. Its values are stored per sample in `expected/` (20 files), each
with a provenance block recording that approval. The same day they were moved
there from a single `expectations.json` (task 12, Phase 5). Following the
user's decisions:
- 12,390 per-species record counts were dropped;
- 8,190 full hit sequences became one fingerprint map per sample;
- on 2026-11-26, every value the report shows was deleted.

Approving the data did not approve failed rule checks or change any Selenium
fixtures.

**The supplied run.** The evidence is in
`/mnt/data/tests-wf-2/tests/2026-11-23_052042/tests/a6b58f1ab761dd04d3bfb3044ca4834`.
- `nf-test_results.txt` records nf-test 0.9.5 core **PASSED** in 2434.281
  seconds.
- `meta/workflow.json` records success (exit 0) and the workflow timestamp
  `20261123 043225`.
- The run's exact code revision is not recorded and must not be inferred from
  this branch, which starts at commit `0f715e7`.
- Input, reference and version hashes are in `evidence-provenance.json`. The
  BLAST and taxdump labels at the top of this file are names, not checksums.

The retained copy was missing the 60 symlinks of the candidate (C) folders.
The hit (H) originals were present and passed. For comparison only,
`.nf-test/task12-review/retained-view/` rebuilds those links from the recorded
staging commands, logged in `retained-view-manifest.json`, without changing the
original files. It found:
- the two malformed PMI files (P3-D-008, see "Known problems");
- the missing `query_020_512503_1_Andrew/map_Bulimulus_sporadicus.png` (the
  folder had only `map_Bulimulus_Sporadicus.png`).

No production code or stored values were changed to hide these.

Re-checking an old run's files is not a new workflow run and produces no JUnit
XML. Missing XML is shown as missing, never replaced. An old run without
evidence JSON needs a new run before anything can be accepted.

**Accepted baseline check, 2026-11-23.** After the move into per-sample files,
re-checking the retained run gave 1,021 results: 810 passed, 208 left to
Selenium, 0 needing a baseline, 0 stale, and three rule failures (the two PMI
files and the missing map). These counts are historical: since 2026-11-26 core
neither stores nor hands over values the report shows. Evidence:
`.nf-test/task12-review/phase5-assertions.json` and `phase5-review.html`.
