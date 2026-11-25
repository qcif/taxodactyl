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
## Task 12 assertion migration (awaiting review)
## Task 12 assertion migration

The core test now runs `CoreAssertions.groovy` once over the emitted channels.
Each independent invariant records a diagnostic before aggregation with native
`assertAll`. Native nf-test **0.9.5** JUnit retains the aggregate failure count,
not individual power assertions (verified with two deliberate failures). The
JSON sidecar therefore retains every check's sample, stable ID, field, owner,
expected/observed values, diagnostic and artifact paths. No Python code evaluates
workflow contracts.

**Baseline status:** the user explicitly validated and approved the supplied run
on 2026-11-23. Its core-owned values are stored per sample in
`expected/<N>_<sample_id>.yaml` (20 files), each with provenance quoting that
authorization. On the same day they were moved there from the former single
`expectations.json` (task 12 Phase 5). Following the user's decisions, the
12,390 per-species related/in-country record counts were dropped, and the 8,190
full hit sequences became one fingerprint map per sample. The 208 Selenium-owned
fields are excluded. This approval accepts the data,
not failed integrity checks or changed Selenium fixtures.

**Two core pipelines run side by side for now (user decision 2026-11-23):**

| | Original | Assertions (task 12) |
|---|---|---|
| Test file | `taxodactyl.workflow.nf.test` + `.snap` | `taxodactyl.assertions.nf.test` + `expected/`, `schema.yaml` |
| CI workflow | `.github/workflows/nf-test.yml` | `.github/workflows/nf-test-core-assertions.yml` |
| Triggers | Sunday 00:00 UTC, manual (callable from `build-pr.yml`, currently not used) | PRs to main via `build-pr.yml` (PR's image, else `:main`), Sunday 12:00 UTC, manual |
| Flag check | "Test flags" against `flags/` | none (core/Selenium own 5.x values) |
| Review | snapshot error CSV, Selenium `review.html` | `nf-test-review` artifact and standalone `nf-test-review.html`, run-page summary, Selenium `review.html` |

The original files are byte-identical to commit `0f715e7`. Retiring them is a
later decision, after comparing the two. Always name the test file explicitly:
`nf-test test test/core/` would run both full workflows. Other scenarios and
Selenium code/fixtures/tolerances are unchanged.

**Known defect:** the `C.pmi` check fails for Scenario_04 and
barcode_83_P59_Potyviridae_cluster_0_RC205. `scripts/p3_assign_taxonomy.py`
writes `preliminary_id_match.csv` without a line break between header and row
(P3-D-008; nothing reads the file). By user decision it stays failing until a
separate task fixes the writer; core CI is red for that reason alone. The page
does not label it; tracking stays in the task brief and `tasks/todo.md`.

### Coverage ownership

| Artifact | Core checks | Existing Selenium owner / limits |
|---|---|---|
| H `all_hits.fasta`, `all_hits.json` | Unique accession membership, essential hit/HSP schema, input sample identity, FASTA validity, last subject-HSP sequence agreement; reviewed accession list and per-accession sequence fingerprints (first 16 hex characters of SHA-256) | Selected BLAST modal values; no duplicate core statistics expectations |
| H/C `query_title.txt`, copied hit files | Input identity and byte-preserving copy through emitted C paths | Input popup identity is a presentation check |
| C `candidates.json`, `.csv`, `.fasta`, `_count.txt` | Schema, species/accession uniqueness, CSV/JSON/FASTA membership agreement, sequence agreement with H, integer count agrees with species | Candidate table owns displayed species/statistics; core does not baseline those statistics |
| C `1.flag`, `2.flag`, `7.flag` | One raw record, required fields, configured value domains; uncovered values only | Populated `overview_tab.conclusion_flag`, `toi_flag`, `preliminary_flag`; blank expectations are not owners |
| C `assigned_taxonomy.csv` | Required iff 1A; header and records agree with candidate CSV | Displayed identified candidate |
| C `preliminary_id_match.csv` | Required iff 7A; rank/taxon header and single matching input PMI | Raw file is unused by Selenium/P6; known P3-D-008 produces malformed CSV and remains a visible invariant failure |
| C `taxa_of_concern_detected.csv` | Required iff input TOIs; header, input-order membership and match accessions belong to candidates | Existing TOI table owns displayed match values |
| C `candidates_phylogeny.fasta` | Valid records, sequences agree with H, reviewed selected accession membership | Tree minimum-node check is only a lower bound |
| C `candidates_identity_boxplot.png` | Presence iff candidate count exceeds run limit; decoded PNG, positive dimensions | No pixel baseline |
| S `4.flag`, `aggregated_sources.json` | Exact assessed/skipped channel shape from 1..max candidate rule; candidate/flag/source relationships, publication record structure, reviewed raw source accessions and flag values | Publication modal owns displayed titles/source/count fields; core does not baseline publication text |
| T `candidates_phylogeny.nwk` | Valid Newick grammar, unique leaves equal selected FASTA plus QUERY; empty only for empty selected FASTA | Tree title/minimum nodes; branching/lengths are deliberately not frozen |
| D `db_coverage.json` | Per-role taxon membership; in-country **species names**; assessed/not-assessed/null/NA states; count structure (whole numbers or null). **No record count is a core expectation** (user decision 2026-11-23): target counts not owned by Selenium appear on the review page as "not checked". **Related-species names are not compared for any role** (user decision 2026-11-25); the related list is still checked for structure and its state (NA/null) is still compared | Populated database-coverage `record_count`, species count/total and bars. Existing substring/list comparison and ±10% tolerance remain authoritative |
| F `5.1.flag`, `5.2.flag`, `5.3.flag` | Three filenames per sample; unique `(flag,role,target)` records agree with D membership; uncovered values only | Populated `flag_text1/2` for the exact role and taxon. Country `final_text` is explanatory text, not an assertion of raw 5.3 value |
| M `map*.png` | Per-sample reviewed map filenames; unique names; decoded PNG dimensions | Country messages do not cover raw images |
| HTML | Reject unknown/duplicate/misassociated emitted paths | Per-sample report presence and browser contents remain exclusively Selenium |
| Versions, parameters, timestamp | Singleton/readable; required tools, database/analysis limit, valid emitted `yyyyMMdd HHmmss` time | No exact version/time baseline. Parameters are never embedded in review output |
| Workflow / all tuple channels | Success, tuple shape, complete keyed membership (except optional maps), multiplicity, path/sample association | Independent workflow integrity |

`coverage-ownership.tsv` records concrete populated Selenium owners from the
supplied run, by sample/role/taxon/field. It contains **ownership**, not accepted
expected data. All other promotable fields shown in the sidecar belong to core.
Delegated fields cannot be ingested or promoted. Changing Selenium fixtures can
change ownership and requires rerunning the coverage audit.

Every candidate directory's emitted filenames are checked against an explicit
allowlist; unknown additions fail for review. Copied H files are checked for
preservation rather than given second independent baselines. Intermediate BLAST,
taxonomy, alignment and accession-list files outside the emitted channels remain
outside this test. Precise BLAST calculations/records remain covered by `scripts/tests/test_blast_parser.py` (including exact identities, scores, alignment fields and sequence output); selection boundaries remain in `scripts/tests/test_phylogeny_sampling.py`.

### Supplied run provenance and limitations

Evidence source:
`/mnt/data/tests-wf-2/tests/2026-11-23_052042/tests/a6b58f1ab761dd04d3bfb3044ca4834`.
The parent `nf-test_results.txt` records nf-test 0.9.5 core **PASSED** in
2434.281 seconds. `meta/workflow.json` records success/exit 0; workflow timestamp
is `20261123 043225`. The implementation branch starts at `nf-test-sh-runner`
commit `0f715e7`; the historical run's exact checkout revision is not recorded in
that metadata and must not be inferred from today's branch. Input/reference and
version hashes gathered from retained evidence are in `evidence-provenance.json`.
BLAST/taxdump labels documented above are not content digests of those databases.

The retained channel paths use the original runner prefix. An explicit prefix
mapping was used for diagnostics, without searching for substitute files. The
H originals under `work/54/6614…` are present. Candidate `.command.run` stages them
as symlinks under `hits_files/`; `.command.sh` moves those links into the candidate
folder. The retained copy has **none of those 60 C symlinks**. Content validation
of H is possible; preservation at C's emitted paths is not established by this
copy. For retained-data comparison, `.nf-test/task12-review/retained-view/` reconstructs
these links from the exact recorded staging commands, with every mapping logged
in `retained-view-manifest.json`. This disposable view leaves original files
unchanged and is distinguished from verification of the original retained paths.

Two PMI-match files expose existing P3-D-008 (missing newline between header and
record), for Scenario_04 and barcode_83_P59_Potyviridae_cluster_0_RC205. The emitted
map `query_020_512503_1_Andrew/map_Bulimulus_sporadicus.png` is absent; the folder
contains only `map_Bulimulus_Sporadicus.png`. No production code or expected values
have been changed to hide these findings.

A diagnostic evaluation of retained channels is **not a new workflow execution**
and does not create native JUnit. Old runs without the sidecar need a new core
execution/evaluation before manual acceptance. Missing XML is shown as missing,
never replaced by synthetic passing XML. Ordinary toolkit ingestion remains blocked while invariant failures or incomplete
evaluation remain. The initial baseline was authored explicitly under the user’s
validated-data authorization, retaining the original failed evidence and recording
its integrity findings in the baseline provenance. No ingest safety checks were
relaxed.

### Run, review, ingest, rerun

Keep core reference paths and credentials configured as described above. The
root `nf-test.config` selects scenario_04 by default and has placeholders; a core
filename alone does not select core configuration. Create an explicit config:

```groovy
// /absolute/run/core.nf-test.config
config {
    workDir '/absolute/run/nf-test'
    testsDir 'test/core'
    configFile 'test/core/nextflow.config'
    profile 'singularity'
}
```

Run from the repository root, after resolving `test/core/nextflow.config` paths:

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

A sample without expectations **fails** ("needs baseline") while still collecting
all observations and running every rule check.

### Expected files

`expected/<N>_<sample_id>.yaml` holds one sample's reviewed values, laid out like
the Selenium fixtures (`components` → `assertions` with `id`, `type`, `value`;
grouped components list `{name, assertions}` per role or candidate). The file is
matched by its `sample_id:` key; `<N>` reuses the number of the Selenium fixture
for the same sample (`test/selenium/expected/<N>_<sample_id>.yaml`), otherwise
the next unused number. Components, value types, titles and the rule text shown
on the review page are declared once in `schema.yaml`. Groovy refuses to emit a
check or value that is not declared there. `CoreAssertions.groovy` contains no
sample IDs. Only `ingest`/`promote` write these files; do not hand-edit values.

The `expected.files` check fails, naming the file, for an orphan file (sample not
in `metadata.csv`), two files with the same `sample_id`, an unknown component or
assertion, or an invalid value. A stored value that is no longer observed (a
taxon vanished, or Selenium now owns it) fails as **stale**; `promote` offers to
remove it. Stale reporting is suppressed for a component whose rule check
already failed, so one broken file does not cascade into many failures.

### Adding a sample

1. Add a row to `test/core/metadata.csv`. Nothing else changes.
2. Run core (commands above). The new sample's rule checks run; its values are
   "needs baseline", so the test fails.
3. Render the review page and check the sample under **Needs attention**.
4. Ingest after review:

   ```bash
   python test/core/testkit.py ingest --sample <sample_id> \
     --assertions /absolute/run/nf-test/nf-test-assertions.json --dry-run
   # Remove --dry-run; answer y / n / a (all in this sample) / q; give a reason.
   ```

   This writes `test/core/expected/<N>_<sample_id>.yaml`.
5. Rerun core. To remove a sample, delete its `metadata.csv` row and its file.

### Accepting later changes

```bash
python test/core/testkit.py promote 16 \
  --assertions /absolute/run/nf-test/nf-test-assertions.json --dry-run
# Target by number (16), file stem (16_Scenario_04) or sample_id; or --all.
# Narrow with --component database_coverage or --assertion <id or name>.
```

Ingest adds missing values and never overwrites an existing one; promote changes
or removes existing values and never invents one. Both preview each value (lists
as `+added / −removed`, fingerprints by accession), require acceptance and a
reason, and refuse: incomplete or errored evaluations; stale assertion code,
schema or Selenium ownership; a sample file edited since the evaluation; and
samples with rule failures (with `--all` such samples are skipped and named).
Writes are atomic and update `date:`/`provenance:`. The previous file is kept
in ignored `expected/.backups/<stem>.<timestamp>.yaml` (last three per file).
Selenium fixtures, flag files, assertion code and the schema are never written.
Rendering and CI are read-only. After any acceptance, rerun the core invocation
above. nf-test 0.9.5 has no documented assertion-only replay flag in its CLI;
no replay is promised. Original failure records stay unchanged.

### Reading the review page

- **Verdict:** `PASSED`, `NEEDS BASELINE` (values without expectations), `DRIFT`
  (stored values changed), `FAILED` (a rule check failed), `INCOMPLETE` (workflow
  or evaluation error, or missing/invalid JUnit), or `INVALID EVIDENCE`.
- **Drift vs failure is a suggestion.** The label depends only on which kind of
  check broke, never on why. A *rule check* (structure, routing, valid values;
  declared under `checks:` in `schema.yaml`) must always hold, so its failure is
  shown as **rule failed** and a workflow bug is the likely cause. A *stored
  value* (declared under `assertions:`) that differs from
  `expected/<N>_<sample_id>.yaml` is shown as **possible drift**: new reference
  data (GenBank, BOLD, GBIF) is a common cause, but a regression looks exactly
  the same. Check every change before promoting. The page and CI summary say
  this next to the tables.
- **Run health:** workflow, evaluation, JUnit and expectation-file status.
- **Needs attention:** one row per problem, most serious first, linking to the
  sample card. Changed values are grouped per sample and component.
- **Failure analysis:** the same problems grouped across samples by kind (error,
  rule failed, possible drift, needs baseline) and area (e.g. drift in Database coverage, drift
  in Coverage flags), most serious first and then by how many samples share them.
  Each row lists the affected samples (linked), the checks involved with counts,
  and one example. Use it to spot one cause behind many rows above.
- **Samples × checks:** ✔ passed, ✖ failed, ? needs baseline.
- **Sample details:** only samples with problems. Columns: **Check | Expected |
  Actual | Next step**. Every message has the same shape, built by helpers in
  `CoreAssertions.groovy`: `<file>: <rule>`, `Expected: <value>`, `Actual: <value>`,
  and for lists `Difference: missing …; unexpected …`. Values are printed as they
  are (strings quoted, line breaks as `⏎`), with no interpretation, e.g.
  `Expected: "rank,taxon⏎<rank>,Bruchophagus"` / `Actual: "rank,taxongenus,Bruchophagus"`.
  Links go to the files that check read, followed by a copyable
  `promote`/`ingest` command.
- **Reference (collapsed):** commands; **What this test checks**, a static list
  per area of the files read, the step writing them, each rule check and stored
  value in one line (from `schema.yaml`, no per-run results); channel legend;
  native nf-test diagnostics.

Values owned by Selenium (208 in the baseline) are not shown on this page. They
stay in the evidence JSON and `coverage-ownership.tsv`; the Selenium review shows
their results. A value is Selenium's for a sample when that sample's fixture has a
non-empty expected value for it. Core then also skips re-checking that the value
exists and is valid: `C.flag.1/2/7` run only for unowned flags (baseline: flag 2
of FungusB_Btub), and 5.x record values are validated only where unowned. The
5.x record structure (one record per taxon in `db_coverage.json`, none missing,
extra or repeated) is always checked. A test enforces that every assertion goes
through the Expected/Actual helpers.

### In CI

`.github/workflows/nf-test-core-assertions.yml` (Actions →
nf-test-core-assertions → Run workflow, choosing the branch) runs
`taxodactyl.assertions.nf.test` with `CORE_REPO_ROOT` set and then:
- writes the verdict, needs-attention and failure-analysis tables to the run's
  summary page;
- uploads the `nf-test-review-<runner>` artifact, a self-contained folder.
  Open `nf-test-review.html` inside it; links point to copies of the files behind
  each failure, plus the evidence JSON, JUnit XML and nf-test logs;
- uploads the same page on its own, unzipped, as the `nf-test-review.html`
  artifact. Browsers can block the zipped artifact on reputation alone (Firefox
  reported it as a virus); a plain `.html` is not checked. Its links to evidence
  files only work inside the zipped bundle;
- on the self-hosted runner, keeps `/var/runner/<timestamp>/` and
  `nf-test-run.tar.gz` there. Copy runs elsewhere with the tarball: zip archives
  and artifact downloads can drop symlinks and files whose names differ only in
  case. A retained copy lost `map_Bulimulus_sporadicus.png` that way.

Render a local bundle the same way:

```bash
python test/core/testkit.py render --junit <run>/nf-test.xml \
  --assertions <run>/nf-test-assertions.json --output <run>/nf-test-review.html \
  --summary <run>/nf-test-summary.md --bundle-dir <run>/nf-test-review
```

HTML and JSON/XML should stay together in the retained bundle. Links point only
to existing files within that bundle, using relative paths. A standalone uploaded
review still shows unavailable artifact links explicitly. Self-hosted retention
continues under `/var/runner/<timestamp>/`.

### Focused validation

```bash
source scripts/venv/bin/activate
PYTHONPATH=scripts python -m unittest discover -s scripts/tests -p 'test_nf_test_*.py' -b
# NFT_JAR is the jar shipped with nf-test 0.9.5:
java -cp "$NFT_JAR" groovy.ui.GroovyMain test/core/contracts.test.groovy "$PWD"
```

The Groovy scenarios (27) use disposable synthetic files. They cover:
- valid empty and skipped cases, and a new sample without a file (needs baseline);
- accepted synthetic data;
- missing, duplicate or wrongly associated samples, and malformed outputs;
- missing, extra or duplicated P5 records, and changed flag values;
- record-count and related-species-name changes that must not fail core;
- a changed hit sequence failing only its fingerprint;
- Selenium-owned values, including a stored core value that Selenium now owns;
- stale entries, orphan or duplicate files, unknown assertions, and independent failures.

The Python tests (37) cover:
- verdicts, the needs-attention order and rule text;
- list and fingerprint change descriptions, a large passing run staying small,
  escaping, and portable links;
- schema labels, and that no sample ID appears in `CoreAssertions.groovy`;
- per-sample ingest/promote: numbering, target resolution, `a`/`q` answers,
  per-sample freshness, blocking by rule failures, removal of stale entries,
  unchanged other files, backups, and quoting of fingerprints for SnakeYAML.
The real baseline was accepted through explicit user validation, independently
of these synthetic tests. Baseline data acceptance does not relabel failed
invariants as passing.


### Accepted baseline verification — 2026-11-23

All values come from the user-validated run (provenance in each file's
`provenance:` block). After the Phase 5 move into per-sample files, re-evaluating
the retained run (disposable reconstructed staging view) gives 1,021 rows:
810 passed, 208 owned by Selenium, 0 needing a baseline, 0 stale, and three rule
failures. Those are the two malformed PMI CSVs (P3-D-008) and the missing
lowercase map `map_Bulimulus_sporadicus.png`, now a failure rather than an
evaluation error. Evidence: `.nf-test/task12-review/phase5-assertions.json`
and `phase5-review.html` (62 KB; the former page was 17 MB). The PMI CSV and map
findings remain failures; accepting values does not disable those checks. The
standalone review remains explicit about absent historical native JUnit.
