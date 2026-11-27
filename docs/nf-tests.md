# How to Run nf-test from test/scenario_01

This document provides step-by-step instructions for running nf-test with the scenario_01 test case in the Taxodactyl workflow.

## Prerequisites

### 1. Install nf-test

Follow the installation instructions at: https://www.nf-test.com/installation/

```bash
# Example installation using curl
curl -fsSL https://get.nf-test.com | bash
```

After installation, ensure nf-test is accessible from your PATH:

```bash
# Option 1: Move nf-test to a directory already in PATH
sudo mv nf-test /usr/local/bin/

# Option 2: Add the nf-test installation directory to PATH
# Add this line to your ~/.bashrc or ~/.bash_profile
export PATH="$PATH:/path/to/nf-test/installation/dir"

# Then reload your shell configuration
source ~/.bashrc
```

Verify the installation:

```bash
nf-test version
```

### 2. Clone the Taxodactyl Repository

Clone the Taxodactyl workflow from GitHub:

```bash
git clone https://github.com/qcif/taxodactyl.git /path/to/taxodactyl_github_repo_dir
cd /path/to/taxodactyl_github_repo_dir
```

Alternatively, clone a specific version or branch:

```bash
# Clone a specific branch
git clone -b <branch_name> https://github.com/qcif/taxodactyl.git /path/to/taxodactyl_github_repo_dir

# Or checkout a specific tag/version after cloning
git clone https://github.com/qcif/taxodactyl.git /path/to/taxodactyl_github_repo_dir
cd /path/to/taxodactyl_github_repo_dir
git checkout <tag_or_version>
```

### 3. Required Databases

Ensure the following databases are available:

- **BLAST database**: `/path/to/blastdb/core_nt` 
- **Taxonomy database**: `/path/to/taxonkit_db`
- **Singularity cache**: `/path/to/singularity_cache`

### 4. Working Directory

Create the test working directory:

```bash
mkdir -p /path/to/test_execution_dir
```

## Configuration

### nf-test.config

The `nf-test.config` file in the workflow root directory `/path/to/taxodactyl_github_repo_dir` controls which test scenario to run:

```nextflow
config {
    workDir "/path/to/test_execution_dir"
    testsDir "test/scenario_01"
    configFile "test/scenario_01/nextflow.config"
    profile "singularity"
}
```

**Configuration parameters:**
- `workDir`: Where nf-test stores execution artifacts and work directories
- `testsDir`: Directory containing the test scenarios (currently set to scenario_01)
- `configFile`: Test-specific Nextflow configuration
- `profile`: Execution profile (singularity, docker, etc.)

### Test Configuration (test/scenario_01/nextflow.config)

Test-specific parameters are defined in `test/scenario_01/nextflow.config`:

```nextflow
params.metadata = "${projectDir}/test/scenario_01/metadata.csv" 
params.sequences = "${projectDir}/test/scenario_01/query.fasta" 
params.blast_xml = "${projectDir}/test/scenario_01/blast_result.xml"
params.mock_blast = true 
params.db_type = "blast_core_nt"
params.blastdb = "/path/to/blastdb"
params.taxdb = "/path/to/taxonkit_db"

// Optional: NCBI API credentials for faster execution (recommended)
// params.ncbi_api_key = "your_ncbi_api_key_here"  // Get from https://www.ncbi.nlm.nih.gov/account/settings/
// params.ncbi_user_email = "your_email@example.com"  // Alternative to API key

singularity {
    cacheDir = "/path/to/singularity_cache"
}
```

### API response cache

P4 (source diversity) and P5 (database coverage) cache GBIF and NCBI API
responses in `<params.temp_root_dir>/biosecurity/cache_db.sqlite`. Live API
data changes from week to week, so the `core` scenario uses a versioned
**API-cache fixture**: a frozen copy of that database, pinned by version and
SHA-256. See [test/core/README.md](../test/core/README.md) for how to
download, install and refresh it.

- `test/core/nextflow.config` sets `env.CACHE_TIMEOUT_HOURS = '876000'`
  (about 100 years) so the fixture's entries never expire.
- Empty (`None`) results and errors are never cached, so those requests go
  to the live API on every run, and may drift.
- In CI (`.github/workflows/nf-test.yml`), the fixture is installed into
  the job's temp root before nf-test runs. Untick the dispatch input
  "Use cached API responses" (`use_cache`) to query the live APIs instead.
  The run also uses the live APIs while no fixture version is pinned.
- After the run, CI warns if any responses were added to the cache. These
  are cache misses: requests that weren't in the fixture and were fetched
  live, so the results may drift.
- Each CI run saves a copy of its final cache with the run files on the
  self-hosted runner (`/var/runner/<run_id>-<attempt>/api_cache/`). A live
  run's copy is the starting point for a new fixture version.

**Updating the fixture** is a deliberate, reviewed change: a live run, an
inspection and secrets check of its saved cache, a new dated version
uploaded to `daffstandard/test-data`, the version and SHA-256 pinned in
`nf-test.yml`, two matching cached runs, and a re-baseline in the same PR.
Never change a published version. The step-by-step process, with commands,
is in [test/core/README.md](../test/core/README.md#refreshing-the-api-cache-fixture).

## Test Input Files

The scenario_01 test includes the following input files in `test/scenario_01/`:

- `metadata.csv` - Sample metadata
- `query.fasta` - Query sequences
- `blast_result.xml` - Pre-generated BLAST results (used with mock_blast=true)
- `nextflow.config` - Test-specific configuration
- `taxodactyl.workflow.nf.test` - Test definition file
- `taxodactyl.workflow.nf.test.snap` - Snapshot file for comparison

## Running the Test

### Navigate to Workflow Directory

```bash
cd /path/to/taxodactyl_github_repo_dir
```

### Set Environment Variables (Optional)

For better diff output in snapshot comparisons:

```bash
export NFT_DIFF_ARGS="--suppress-common-lines"
```

### Run the Test

Execute the test with:

```bash
nf-test test test/scenario_01/taxodactyl.workflow.nf.test \
  > /path/to/test_execution_dir/tests/scenario_01/nf-test_results.txt \
  2> /path/to/test_execution_dir/tests/scenario_01/nf-test_errors.txt
```

## Understanding Test Results

### Test Execution

When you run the test:
1. nf-test reads `nf-test.config` to determine execution parameters
2. It loads the test configuration from `test/scenario_01/nextflow.config`
3. The test executes the workflow defined in `workflows/taxodactyl.nf`
4. Outputs are compared against the snapshot file

### Test Hash

The test generates a unique hash (`NF_TEST_HASH`, e.g., `9550e06b15180ad4857afa5ae5d07ed3`) used to organize test artifacts.

### Test Artifacts Location

After running the test, artifacts are stored in:

```
/path/to/test_execution_dir/tests/[NF_TEST_HASH]/
```

For example:
```
/path/to/test_execution_dir/tests/9550e06b15180ad4857afa5ae5d07ed3/
├── meta/
│   ├── trace.csv          # Execution trace
│   └── [other logs]       # Pipeline logs
└── work/                  # Nextflow work directory
```

### Assertions

The test validates:

- Snapshot comparison of key output channels:
  - `ch_hits_for_report`
  - `ch_candidates_for_report`
  - `ch_db_coverage_flags`
  - `ch_source_diversity_for_report`
  - `ch_homology_trees`
  
- Output file counts:
  - 6 HTML reports
  - 1 collated versions file
  - 1 params JSON file
  - 1 workflow timestamp
  - 6 database coverage maps
  - 11 total database coverage map files (flattened)
  - 6 database coverage JSON files
  - 6 database coverage flag groups
  - 18 total flag files (flattened)

## Flag Comparison Test (baseline vs evaluated)

In addition to nf-test assertions, a post-run flag comparison can be performed using
`collect_flags.sh` and `test_flags.py`. These scripts can be found in `/path/to/taxodactyl_github_repo_dir/test`.

This compares:
- baseline flags in `test/<scenario>/flags`
- evaluated flags collected from a specific nf-test run hash

### Variables used for flag comparison

Example variables:

```bash
test_case=scenario_01
NF_TEST_HASH=<nf_test_run_hash>

taxo_fold=/path/to/taxodactyl_github_repo_dir
tests_fold=/path/to/test_execution_dir

baseline_dir=${taxo_fold}/test/${test_case}/flags
evaluated_dir=${tests_fold}/tests/${NF_TEST_HASH}
```

### Flag comparison commands

```bash
mkdir -p ${tests_fold}/tests/${test_case}/flags/evaluated
bash collect_flags.sh "$evaluated_dir" "${tests_fold}/tests/${test_case}/flags/evaluated"

python3 test_flags.py "$baseline_dir" "${tests_fold}/tests/${test_case}/flags/evaluated" \
  > "${tests_fold}/tests/${test_case}/flags_results.txt" \
  2> "${tests_fold}/tests/${test_case}/flags_errors.txt"
```

### Output files from flag comparison

- `${tests_fold}/tests/${test_case}/flags_results.txt`
- `${tests_fold}/tests/${test_case}/flags_errors.txt`

### Check Test Results

After the test completes, review the execution logs:

```bash
# View standard output
cat /path/to/test_execution_dir/tests/scenario_01/nf-test_results.txt

# View errors (if any)
cat /path/to/test_execution_dir/tests/scenario_01/nf-test_errors.txt

# Or tail the logs during execution
tail -f /path/to/test_execution_dir/tests/scenario_01/nf-test_results.txt
```

A successful test will show all assertions passing with output similar to:
```
✅ Test [NF_TEST_HASH] scenario_01 PASSED
```

## Updating Snapshots

If you intentionally change the workflow behavior and need to update test expectations:

```bash
nf-test test test/scenario_01/taxodactyl.workflow.nf.test --update-snapshot
```

This will regenerate the `.snap` file with new expected outputs.

For the `core` scenario, regenerate the snapshot, flag baselines and
Selenium expected reports from a **cached** run against the pinned
API-cache fixture (see [API response cache](#api-response-cache)), never
from a live run. Otherwise the baselines contain live API data and the
next cached run drifts. A new fixture version always needs a re-baseline
in the same PR.

## Running Different Scenarios

To run a different test scenario (e.g., scenario_02):

1. Edit `nf-test.config`:
   ```nextflow
   config {
       workDir "/path/to/test_execution_dir"
       testsDir "test/scenario_02"
       configFile "test/scenario_02/nextflow.config"
       profile "singularity"
   }
   ```

2. Run the test:
   ```bash
   nf-test test test/scenario_02/taxodactyl.workflow.nf.test
   ```

3. If you need to validate generated flags against baseline files, set `NF_TEST_HASH`
  to the produced test hash and run the flag comparison commands above.

## Troubleshooting

### Test Fails

1. Check the execution logs in the test artifacts directory
2. Review the trace file: `[workDir]/tests/[NF_TEST_HASH]/meta/trace.csv`
3. Examine the work directory for process-level outputs

## Additional Resources

- nf-test documentation: https://www.nf-test.com/
- Snapshot assertions: https://www.nf-test.com/docs/assertions/snapshots/
- Taxodactyl documentation: See `docs/` directory in the workflow

## Database coverage mode scenario

`test/coverage` tests database coverage mode (`--coverage_taxa`) with `workflows/coverage.nf`.
Point `nf-test.config` at it (`testsDir "test/coverage"`, `configFile "test/coverage/nextflow.config"`)
and see `test/coverage/README.md`. It needs the taxdump but no BLAST database.

## Core assertion review (task 12)

Core now uses named workflow/file contracts and a structured assertion sidecar.
Use the explicit core configuration and `--ci --junitxml` invocation in
[test/core/README.md](../test/core/README.md#run-review-ingest-rerun); the root
configuration currently selects scenario_04 and has unresolved placeholders.
Other scenarios retain their existing snapshots and legacy post-processing.

`python test/core/testkit.py render --junit <run>/nf-test.xml --assertions
<run>/nf-test-assertions.json --output <run>/nf-test-review.html` renders an offline
review from retained evidence. Use a single shell line or explicit backslash
continuations. Missing XML/sidecar is reported as missing, not a successful test.
The self-hosted job retains native XML, JSON, HTML and logs even after failure.
`bin/collect_artifacts.py --assertions <sidecar>` routes core P5 and other failed
checks to their producing tasks; `--nft_errors` remains for legacy scenarios.
The frozen mock workflow predates this evidence and only validates legacy
post-processing when it is missing.

Expected values are stored per sample in `test/core/expected/<N>_<sample_id>.yaml`
(matched by `sample_id`; `<N>` reuses the Selenium fixture number), like
`test/selenium/expected/`. Check titles, rules and value types are declared in
`test/core/schema.yaml`. The review page opens with a verdict and a "Needs
attention" table, a failure-analysis table grouping the same problems across
samples by kind and area (e.g. possible drift in Database coverage), then a sample × check
matrix and cards only for samples with problems.

"Rule failed" and "possible drift" are suggestions, not diagnoses. A failed rule
check (structure, routing, valid values) is labelled a rule failure and probably
means a workflow bug; a stored value that differs from `test/core/expected/` is
labelled possible drift and may be new reference data or a regression. The tool
only knows which kind of check broke, so review every change before promoting it.
Core compares only values the HTML report does not show: hit sequence
fingerprints and coverage map filenames. Values the report shows (flags, coverage
taxa, states and species, source accessions, tree sequences) are left to Selenium
(user decision 2026-11-26). Core still checks that every flag value is valid and
that the files agree with each other, in every sample. Until the Selenium
fixtures cover every sample, some of these values are not compared by either
suite; see `spec/tests.md` TST-G-011.

To add a sample: add its row to `test/core/metadata.csv`, run core, render, then
`python test/core/testkit.py ingest --sample <sample_id> --assertions <run>/nf-test-assertions.json`
and rerun. Accept reviewed changes later with
`python test/core/testkit.py promote <N|sample_id> --assertions <run>/nf-test-assertions.json`.
Both support `--dry-run`, `--component`/`--assertion` selection and explicit
review reasons.

Two core pipelines run side by side for now. The original snapshot test,
`test/core/taxodactyl.workflow.nf.test`, runs in `.github/workflows/nf-test.yml`
with its flag check (weekly and by hand). The assertion test,
`test/core/taxodactyl.assertions.nf.test`, runs in
`.github/workflows/nf-test-core-assertions.yml`: on pull requests to main
(called by `build-pr.yml`, with the PR's image), weekly, and from Actions →
nf-test-core-assertions → Run workflow. Its run page shows
a short summary; the `nf-test-review-<runner>` artifact holds the full page with
copies of the files behind each failure, and the `nf-test-review.html` artifact
holds the page alone, unzipped (browsers may block the zip on reputation alone). The page explains each check in plain
words. Ordinary tests, rendering and CI never accept data. Read the core
README for exact commands, what core compares and unresolved migration review; do not
regenerate the core snapshot to accept drift.
