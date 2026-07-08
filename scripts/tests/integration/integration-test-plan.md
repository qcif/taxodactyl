# Integration test suite: narrow assertions + tooling

Forked from [testing.md](testing.md). Scope is the Python-side integration
suite only ([scripts/tests/integration/](scripts/tests/integration/)) —
Selenium and the pre-push runner live in the parent plan.

Goal: add narrow, low-maintenance assertions on `db_coverage.json` and the
tooling needed to keep them cheap.

## Design summary

- Optional per-case `expected/db_coverage.json` — a **literal JSON document**
  captured from a verified run.
- Tandem walker enforces tiered rules:
  - Exact key-set match for `coverage.<target_type>` and `ncbi_urls` keys
    (analysis-target layer) and top-level `coverage` categories.
  - Type-only match for leaf values.
  - Non-null propagation: if expected leaf is truthy, actual must be too.
  - Sub-object keys below the analysis layer (e.g. `country`, `related`)
    tolerated to differ — recurse with type-only rules.
- Cases without a fixture keep today's "no exception raised" behaviour.
- One tooling entrypoint, separate from the test runner:
  - `scripts/tests/integration/testkit.py` — sub-command CLI (`harvest`,
    `promote`, `seed`).
  - Kept out of `run_tests.sh`, which stays scoped to running tests
    ([run_tests.sh:16-39](scripts/tests/integration/run_tests.sh#L16-L39)).
    Test-execution flags and non-test tooling shouldn't share an
    entrypoint — different mental model, different arg surface, and it
    keeps `run_tests.sh --help` honest.
  - Sub-commands:
    - `testkit.py harvest` — scaffold a new case dir from a completed NF
      run, scoped to a single query. Takes the run's `.nextflow.log` as
      the sole source arg; profile (`local`/`azure`) and outdir are
      parsed from it, and any per-task work files are resolved via
      `pipeline_info/execution_trace_*.txt`.
    - `testkit.py promote` — copy a `--keep` output into `expected/`
      after a semantic-diff review.
    - `testkit.py seed` — like `promote` but for a case that has no
      fixture yet (no diff step).

## Checklist

### Phase 1 — Assertion walker

- [ ] Create `scripts/tests/integration/kit/coverage_assert.py` with two entry
      points:
    - `assert_matches(expected: dict, actual: dict) -> None` — raises
      `AssertionError` with a path-qualified message on any tier violation.
    - `semantic_diff(expected: dict, actual: dict) -> list[Change]` — returns
      a structured diff labelling each change as `WOULD_FAIL` (rule-tier
      violation) or `TOLERATED` (value drift within same type). Used by both
      the test failure message and the promote CLI.
- [ ] Encode the four rule tiers:
    - Structural key-set match: `coverage` top-level, `coverage.<cat>`,
      `ncbi_urls`.
    - Sub-object recursion with type-only leaf rules (`country`, `related`,
      etc.).
    - Leaf `type(actual) == type(expected)`.
    - Non-null propagation on truthy expected leaves.
- [ ] Unit-test the walker in `scripts/tests/test_coverage_assert.py` with
      hand-crafted expected/actual pairs covering each rule (matching pair,
      lost species key, extra species key, int→str, non-null→null, tolerated
      value drift, extra country key allowed).
- [ ] Run `flake8` on the new files.

### Phase 2 — Wire assertions into the suite

- [ ] Modify
      [scripts/tests/integration/test_integration.py](scripts/tests/integration/test_integration.py)
      to check for `expected/db_coverage.json` in each case dir after the
      module run; if present, call `assert_matches` on the produced JSON.
- [ ] Skip cleanly with a clear log line when a case has no fixture — do
      **not** fail. Rollout must be incremental.
- [ ] Surface the walker's path-qualified assertion messages in the
      unittest failure output (no swallowing).
- [ ] Verify existing cases without fixtures still pass green.

### Phase 3 — Seed initial fixtures

- [ ] Pick 3–5 seed cases
- [ ] For each: run with `run_tests.sh --keep --test_case <case>`, review
      the produced `db_coverage.json` by eye, copy it to
      `expected/db_coverage.json`, commit.
- [ ] Re-run the suite; confirm all seeded cases pass.

### Phase 4 — `testkit.py` skeleton + `promote` sub-command

- [ ] Create `scripts/tests/integration/testkit.py` with an argparse
      sub-command dispatcher. Sub-commands: `harvest` (Phase 5), `promote`,
      `seed`. Shared flags: `--yes`, `--dry-run`, TTY-only colour.
- [ ] Do **not** wire testkit into `run_tests.sh`. It's a separate
      entrypoint — invoked as
      `python -m scripts.tests.integration.testkit <subcommand> …` or via
      the `venv` script alias.
- [ ] Implement `testkit.py promote`:
    - Args: `--case <name>` | `--all` | `--all-failed`; `--from <path>`.
    - Locate the most recent `integration_test_*` tmp dir when `--from`
      is not given (mirror the existing `TEMPDIR_PREFIX` convention in
      [test_integration.py:27](scripts/tests/integration/test_integration.py#L27)).
    - Render the semantic diff from `coverage_assert.semantic_diff`,
      colour-coding `WOULD_FAIL` vs `TOLERATED`.
    - Confirmation prompt before write. `--yes` bypass.
    - Guardrails:
      - Refuse if the case's last run raised an exception.
      - Warn (not refuse) if promotion would drop species keys — confirm
        intent.
    - Print the resolved fixture path so the dev can `git add` it
      directly.
    - Exit non-zero if no changes were promoted.
- [ ] Implement `testkit.py seed`:
    - Args: `--case <name>`; `--from <path>` (optional, same discovery
      rule as `promote`).
    - Refuses to run if `expected/db_coverage.json` already exists
      (use `promote` to update).
    - Skips the diff step; just writes the fixture and prints the git
      path.
- [ ] Extend
      [scripts/tests/integration/README.md](scripts/tests/integration/README.md)
      with a "Managing fixtures with testkit.py" section.

### Phase 5 — `testkit.py harvest` sub-command

Scaffold a new test case dir from a completed NF workflow output, scoped to
a single chosen query. The case dir must end up looking like an existing
one (see [scripts/tests/test-data/integration/blast/A/](scripts/tests/test-data/integration/blast/A/))
— a single-query snapshot suitable as `query_001` when the suite re-runs
the Python phases against it.

#### Required inputs and where they come from

The suite's expected files for a case:

| Case file          | NF source (per query dir unless noted) | Handling                      |
| ------------------ | -------------------------------------- | ----------------------------- |
| `blast_result.xml` | run-level `blast_result.xml`           | filter to the target query `<Iteration>`   |
| `query.fasta`      | run-level `sequences.fasta`            | filter to the target query record   |
| `metadata.csv`     | run-level `metadata.csv`               | filter to the target query row      |
| `candidates.nwk`   | per-query `candidates_phylogeny.nwk`   | copy verbatim                 |
| `taxids.csv`       | per-query `taxids.csv`                 | copy verbatim                 |
| `taxonomy.csv`     | per-query `taxonomy.csv`               | copy verbatim                 |

Rename on copy: `sequences.fasta` → `query.fasta`;
`candidates_phylogeny.nwk` → `candidates.nwk`.

Filtering rules:

- `blast_result.xml`: keep only the `<Iteration>` whose
  `<Iteration_query-def>` matches the chosen query id (prefix match on the
  first whitespace-delimited token), implicitly making our target query the
  first iteration.
- `query.fasta`: keep only the FASTA record whose header starts with the
  chosen query id.
- `metadata.csv`: keep the header row plus the single row whose
  `sample_id` matches the chosen query id.

#### Single entrypoint: the `.nextflow.log`

Rather than expose separate `--from` / `--from-azure` flags, harvest takes
one required source arg: the run's `.nextflow.log`. Everything else is
derived from it.

- **Line 1** of `.nextflow.log` is the `nextflow.cli.Launcher` debug line
  containing the full `nextflow run …` invocation. Parse it for:
  - `-profile <name>` — determines local vs Azure retrieval mode.
  - `--outdir <path>` — the run's published output directory (contains
    `blast_result.xml`, per-query dirs, `pipeline_info/`).
- `<outdir>/pipeline_info/execution_trace_*.txt` — a TSV with one row per
  Nextflow task. The `workdir` column is a local path for the local
  profile and an `az://<container>/work/<hash-prefix>/<hash-tail>` URI for
  the Azure profile. Used to locate task-scratch files that are not
  published (e.g. the per-query `metadata.csv`, `taxids.csv`,
  `taxonomy.csv` which may live only in the corresponding task workdir).
- For files that are published to `<outdir>` or `<outdir>/query_*/`
  directly (e.g. `blast_result.xml`, `sequences.fasta`,
  `candidates_phylogeny.nwk`), read them from there without touching the
  trace.
- For files only present in a task workdir, look up the relevant task by
  process name in the trace (e.g. `TAXODACTYL:VALIDATE_INPUT` for
  `metadata.csv`, the per-query taxid/taxonomy processes for the chosen
  query), then:
  - **Local profile**: read directly from the local workdir path.
  - **Azure profile**: fetch via `deployment/azure/batch-helpers.sh`
    helpers (already available in the dev shell — see project CLAUDE.md)
    into a temp dir, then read from there.

Behaviour is otherwise identical across profiles — the same filter/copy
core runs on a materialised local view of the required files.

#### CLI shape

```
testkit.py harvest <nextflow-log> --query <query-id> --name <case>
```

- Positional: path to the run's `.nextflow.log`.
- Required flags: `--query <query-id>`, `--name <case>`.
- Shared testkit flags apply: `--yes`, `--dry-run`.

#### Checklist

- [ ] Parse `.nextflow.log` line 1 to extract `-profile` and `--outdir`.
      Refuse cleanly if either is missing.
- [ ] Load the newest `pipeline_info/execution_trace_*.txt` from the
      outdir; index rows by process name (and by per-query tag where
      applicable) so per-query task workdirs can be resolved from the
      chosen `--query`.
- [ ] Extract the filter/copy core so it operates on a materialised local
      source view (a dir or dict-of-paths containing every required
      file). Local and Azure paths both funnel into this core.
- [ ] Implement `blast_result.xml` iteration filter (prefix match on
      `<Iteration_query-def>`; rewrite `<Iteration_iter-num>` to 1).
- [ ] Implement `query.fasta` record filter (header prefix match) on the
      run's `sequences.fasta`.
- [ ] Implement `metadata.csv` row filter (`sample_id` == query id).
- [ ] Copy `candidates_phylogeny.nwk` → `candidates.nwk`;
      `taxids.csv` and `taxonomy.csv` verbatim.
- [ ] Local profile: read published files from `<outdir>` and
      `<outdir>/query_*/`; for any file only present in a task workdir,
      read it directly from the workdir path listed in the trace.
- [ ] Azure profile: for each required file, resolve its source (published
      → `<outdir>`, otherwise task workdir `az://…` URI via the trace),
      and fetch it into a temp dir using
      `deployment/azure/batch-helpers.sh` helpers before dispatching to
      the shared core. **Fetch each required file individually** (e.g. by
      appending the known filename to the workdir URI) — never mirror the
      whole workdir. Task workdirs can be large (multi-GB BLAST outputs,
      scratch DBs, staged inputs), so a whole-dir pull would be
      prohibitively slow and expensive.
- [ ] Validate `--name` for uniqueness against existing case dirs under
      `scripts/tests/test-data/integration/blast/`. Refuse with a clear
      error if a case of that name already exists — harvest never
      overwrites an existing case, even with `--yes` (updates go through
      manual edits or a fresh name).
- [ ] Print a summary: files harvested (with source → dest paths), any
      warnings, and the git paths to `git add`.
- [ ] Extend the integration README with an "Adding a new case" section
      that walks: `testkit.py harvest` → `run_tests.sh --test_case` →
      `testkit.py seed`.
- [ ] Add a lint helper (invoked by the test suite in `setUpClass`) that
      flags any case dir missing a required file — catches hand-created
      cases that were half-set-up.

### Phase 6 — End-to-end verification

- [ ] Baseline: `run_tests.sh` on `main` — record pass count and wall time.
- [ ] Regression injection (in
      [scripts/src/coverage/assess.py](scripts/src/coverage/assess.py)),
      one at a time, each reverted before the next:
    - Structural: emit `target` as a string → walker reports type mismatch.
    - Missing key: omit `related` sub-object for a species → walker reports
      missing key at the correct path.
    - Analysis coverage: silently drop a candidate species → walker reports
      exact-key-set failure.
    - Non-null: emit `target: 0` where fixture has `target: 59` → walker
      reports non-null-propagation failure.
    - Pure value drift: bump `target: 59` → `60` → walker reports as
      `TOLERATED`, test still passes.
- [ ] Historical bug replay: pick a recent phase-2 coverage bug from git
      log; add a case reproducing it; confirm the assertion we'd have
      added would have caught it pre-hand-off.
- [ ] CLI round trip:
    - `testkit.py harvest --from <past-run-dir> --query <query-id>
      --name smoke-harvest` — verify manifest coverage, portability
      rewrites, summary output.
    - `run_tests.sh --test_case smoke-harvest` — case runs end-to-end.
    - `run_tests.sh --keep --test_case smoke-harvest` then
      `testkit.py seed --case smoke-harvest` — fixture written.
    - Re-run without `--keep` — passes cleanly.
    - Change a value in the fixture to trigger a `WOULD_FAIL` diff, run
      `testkit.py promote --case smoke-harvest`, confirm the diff renders
      correctly and prompts before writing.
    - Delete the smoke case + fixture.
- [ ] `--help` on each `testkit.py` sub-command renders a full workflow
      explanation matching the README.
- [ ] `flake8` clean across all new files.

## Out of scope (see [testing.md](testing.md))

- Selenium HTML report validation and its promotion CLI.
- The pre-push `make pretest` runner.
- Bug-retro feedback loop.
