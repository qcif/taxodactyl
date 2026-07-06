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
  - `scripts/tests/integration/toolkit.py` — sub-command CLI (`harvest`,
    `promote`, `seed`).
  - Kept out of `run_tests.sh`, which stays scoped to running tests
    ([run_tests.sh:16-39](scripts/tests/integration/run_tests.sh#L16-L39)).
    Test-execution flags and non-test tooling shouldn't share an
    entrypoint — different mental model, different arg surface, and it
    keeps `run_tests.sh --help` honest.
  - Sub-commands:
    - `toolkit.py harvest` — scaffold a new case dir from an NF workflow
      output, driven by a declarative manifest.
    - `toolkit.py promote` — copy a `--keep` output into `expected/`
      after a semantic-diff review.
    - `toolkit.py seed` — like `promote` but for a case that has no
      fixture yet (no diff step).

## Checklist

### Phase 1 — Assertion walker

- [ ] Create `scripts/tests/integration/coverage_assert.py` with two entry
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

### Phase 4 — `toolkit.py` skeleton + `promote` sub-command

- [ ] Create `scripts/tests/integration/toolkit.py` with an argparse
      sub-command dispatcher. Sub-commands: `harvest` (Phase 5), `promote`,
      `seed`. Shared flags: `--yes`, `--dry-run`, TTY-only colour.
- [ ] Do **not** wire toolkit into `run_tests.sh`. It's a separate
      entrypoint — invoked as
      `python -m scripts.tests.integration.toolkit <subcommand> …` or via
      the `venv` script alias.
- [ ] Implement `toolkit.py promote`:
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
- [ ] Implement `toolkit.py seed`:
    - Args: `--case <name>`; `--from <path>` (optional, same discovery
      rule as `promote`).
    - Refuses to run if `expected/db_coverage.json` already exists
      (use `promote` to update).
    - Skips the diff step; just writes the fixture and prints the git
      path.
- [ ] Extend
      [scripts/tests/integration/README.md](scripts/tests/integration/README.md)
      with a "Managing fixtures with toolkit.py" section.

### Phase 5 — `toolkit.py harvest` sub-command

- [ ] Create `scripts/tests/integration/harvest_manifest.yml` declaring
      required and optional input files per case (baseline from an
      existing case: `blast_result.xml`, `candidates.nwk`, `metadata.csv`,
      `query.fasta`, `taxids.csv`, `taxonomy.csv`).
- [ ] Implement `toolkit.py harvest`:
    - Args: `--from <nf-output-dir> --query <query-id> --name <case>`;
      `--from-report <report.html>`.
    - Interactive query picker when `--query` is omitted — list every
      `query_*` dir under the run with a one-line summary (species, flag
      count).
    - Copy each manifest-declared file into
      `scripts/tests/test-data/integration/blast/<name>/`; warn per
      missing required file, ignore missing optional files.
    - Rewrite absolute paths in copied files (start with `metadata.csv`)
      to relative / placeholder form so the case is portable across
      machines.
    - `--from-report`: parse the workflow timestamp and query id embedded
      in a completed report HTML and derive the source dir automatically.
    - Print a summary: files harvested, files skipped, git paths to
      `git add`.
- [ ] Extend the integration README with an "Adding a new case" section
      that walks: `toolkit.py harvest` → `run_tests.sh --test_case` →
      `toolkit.py seed`.
- [ ] Add a lint helper (invoked by the test suite in `setUpClass`) that
      flags any case dir missing a manifest-required file — catches
      hand-created cases that were half-set-up.

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
    - `toolkit.py harvest --from <past-run-dir> --query <query-id>
      --name smoke-harvest` — verify manifest coverage, portability
      rewrites, summary output.
    - `run_tests.sh --test_case smoke-harvest` — case runs end-to-end.
    - `run_tests.sh --keep --test_case smoke-harvest` then
      `toolkit.py seed --case smoke-harvest` — fixture written.
    - Re-run without `--keep` — passes cleanly.
    - Change a value in the fixture to trigger a `WOULD_FAIL` diff, run
      `toolkit.py promote --case smoke-harvest`, confirm the diff renders
      correctly and prompts before writing.
    - Delete the smoke case + fixture.
- [ ] `--help` on each `toolkit.py` sub-command renders a full workflow
      explanation matching the README.
- [ ] `flake8` clean across all new files.

## Out of scope (see [testing.md](testing.md))

- Selenium HTML report validation and its promotion CLI.
- The pre-push `make pretest` runner.
- Bug-retro feedback loop.
