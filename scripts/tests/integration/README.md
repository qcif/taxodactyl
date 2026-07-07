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

## Managing fixtures with `toolkit.py`

Each case directory may contain an `expected/db_coverage.json` fixture. When
present, the suite walks the produced `db_coverage.json` against the fixture
using tiered rules (structural key-set at the analysis-target layer,
type-only leaves, non-null propagation). Cases without a fixture are skipped
cleanly.

`toolkit.py` is the fixture-management CLI. It is **not** wired into
`run_tests.sh` — invoke the executable directly:

```bash
scripts/tests/integration/toolkit.py <subcommand> [options]
```

By default the toolkit reads from the most recent `integration_test_*`
directory under the system temp dir. Pass `--from PATH` to override.

### Sub-commands

- **`seed --case NAME`** — write a first-time fixture for a case that has
  none. Refuses if `expected/db_coverage.json` already exists.
- **`promote --case NAME | --all | --all-failed`** — update an existing
  fixture. Renders a semantic diff (colour-coded `WOULD_FAIL` vs
  `TOLERATED`), prompts for confirmation, and warns before dropping species
  keys. Refuses cases whose last run raised an exception (no produced
  `db_coverage.json`). Use `--all-failed` after intentional algorithm
  changes to bulk-promote every currently failing case.
- **`harvest`** — scaffold a new case dir from a Nextflow output
  (planned — Phase 5).

### Shared flags

- `--yes` / `-y` — skip confirmation prompts.
- `--dry-run` — report actions without writing files.

### Typical workflow

1. Run the suite: `scripts/tests/integration/run_tests.sh --keep`.
2. For a new case: `toolkit.py seed --case NAME`.
3. For an existing case whose fixture needs updating after an intentional
   change: `toolkit.py promote --case NAME` and review the diff.
4. `git add` the printed fixture path and commit.
