# Integration tests

These are thin tests, in that they run the entire Python-side workflow without
making any assertions - only ensuring that each test case runs without error.
The strength of these tests is that each test case covers a different scenario
that has raised errors in the past.

It's a long test that requires some internet bandwidth for API calls, so be
aware of that before running.

Requirements of running this suite:

- Virtual environment at $project_root/venv with requirements installed
- NCBI Taxdump data dir must be available (set in launch.json):
  ftp://ftp.ncbi.nih.gov/pub/taxonomy/taxdump.tar.gz
- taxonkit binary must be available in PATH

## Managing fixtures with `testkit.py`

Each case directory may contain an `expected/db_coverage.json` fixture. When
present, the suite walks the produced `db_coverage.json` against the fixture
using tiered rules (structural key-set at the analysis-target layer,
type-only leaves, non-null propagation). Cases without a fixture are skipped
cleanly.

`testkit.py` is the fixture-management CLI. It is **not** wired into
`run_tests.sh` — invoke the executable directly:

```bash
scripts/tests/integration/testkit.py <subcommand> [options]
```

By default, testkit reads from the most recent `integration_test_*`
directory under the system temp dir. Pass `--from PATH` to override.

### Sub-commands

#### `seed --case NAME`

Write a first-time fixture from prior test output for a case that has none.
Refuses if `expected/db_coverage.json` already exists — use `promote` in that
case.

#### `promote --case NAME | --all | --all-failed`

Update an existing fixture from prior test output.
Renders a semantic diff (colour-coded `WOULD_FAIL` vs `TOLERATED`),
prompts for confirmation, and warns before
dropping species keys. Refuses cases whose last run raised an exception
(no produced `db_coverage.json`). Use `--all-failed` after intentional
algorithm changes to bulk-promote every currently failing case.

#### `harvest LOG --query SAMPLE_ID --name NAME`

Scaffold a new case dir from a completed Nextflow run. What it does:

- Reads the run's profile + outdir from line 1 of `LOG` (`.nextflow.log`).
- Resolves per-task workdirs via
  `pipeline_info/execution_trace_*.txt` (with a log-scan fallback for
  when the trace has no `workdir` column or is empty).
- Copies the six required case files into
  `test-data/integration/blast/<NAME>/`:
    - `blast_result.xml`, `query.fasta` (from `sequences.fasta`) and
      `metadata.csv` are filtered down to just `--query <SAMPLE_ID>`.
    - `candidates.nwk`, `taxids.csv`, `taxonomy.csv` are copied
      verbatim.
- Refuses if `<NAME>` already exists.

Overrides for when the log's inline paths are stale or non-standard:
`--outdir`, `--trace`, `--work-dir` (local only).

> Note: if there is a github issue for the case, --name should be the issue
> number e.g. --name 123

**Local run** (workflow ran locally with `-profile local|singularity`):

```bash
scripts/tests/integration/testkit.py harvest \
    output/local_example/.nextflow.log \
    --query LC438549.1 \
    --name my_new_case \
    --work-dir output/local_example/work
```

`--work-dir` is only needed when the run was copied off its original
machine — the log's `workDir` paths are absolute so a fresh local run
usually needs no overrides.

**Cloudgene job dir** (`.nextflow.log` under `logs/`, outdir in
params-file):

```bash
scripts/tests/integration/testkit.py harvest \
    cloudgene_job/logs/step1-nextflow.log \
    --query SME26-173 \
    --name my_new_case \
    --outdir cloudgene_job/outdir \
    --work-dir cloudgene_job/work
```

**Azure run** (workflow ran with `-profile azure`; work dirs live in
blob storage):

```bash
# Azure env vars are required:
source deployment/azure/batch-helpers.sh && az_load_env

scripts/tests/integration/testkit.py harvest \
    .nextflow.log \
    --query VE24-1351_COI \
    --name my_new_case
```

Each required file is fetched via a single `az storage blob download`. `AZURE_STORAGE_ACCOUNT_KEY` must be set in the shell — `az_load_env` from
`batch-helpers.sh` handles that.

**Remote run over SSH/SCP** (run lives on another machine reachable via
`ssh`; no need to rsync the whole job dir down first):

```bash
scripts/tests/integration/testkit.py harvest \
    daff-admin:/mnt/data/tests-wf-2/tests/…/meta/nextflow.log \
    --query 008 \
    --name my_new_case
```

Any of `--outdir`, `--trace`, `--work-dir` can also be `host:path`, but
plain paths inherit the log's host by default — so `--outdir
/mnt/data/…/output` alongside a `daff-admin:` log is treated as
`daff-admin:/mnt/data/…/output`. Requires non-interactive `ssh <host>`
(agent forwarding or key auth). Each of the six required files is
fetched with a single `scp` (never a whole-workdir mirror), with three
retries on transient failures.

### Shared flags

- `--yes` / `-y` — skip confirmation prompts.
- `--dry` — report actions without writing files.

### Typical workflow

1. Run the suite: `scripts/tests/integration/run_tests.sh --keep`.
2. For a new case: `testkit.py seed --case NAME`.
3. For an existing case whose fixture needs updating after an intentional
   change: `testkit.py promote --case NAME` and review the diff.
4. `git add` the printed fixture path and commit.

### Adding a new case

`harvest` builds the case dir; the fixture is seeded from a first passing
suite run.

1. Identify a completed Nextflow run and note its `.nextflow.log` path
   and the `sample_id` of the query you want to snapshot.
2. `scripts/tests/integration/testkit.py harvest PATH/TO/.nextflow.log
   --query SAMPLE_ID --name NAME` — optionally add `--dry` first to
   preview the resolution plan.
   - Azure runs: `source deployment/azure/batch-helpers.sh && az_load_env`
     first so per-file blob downloads authenticate.
3. `RUN_TEST_CASE=NAME scripts/tests/integration/run_tests.sh --keep` —
   confirms the harvested inputs run end-to-end through the Python
   phases. No fixture assertion yet.
4. Inspect the produced `db_coverage.json` under
   `/tmp/integration_test_*/NAME/query_001*/`; if it looks right,
   `testkit.py seed --case NAME` to write the fixture.
5. Re-run the suite without `--keep` to confirm the case passes the walker.
6. `git add scripts/tests/test-data/integration/blast/NAME/` and commit.
