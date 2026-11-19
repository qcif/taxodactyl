# Task 10 — Accept input filenames containing spaces

**Status:** done

**Priority:** Medium. A submitter whose sample sheet is named e.g.
`My samples.csv` passes the validator web tool, then nf-schema rejects the
run before any process starts.

**Issue:** [#358 — Input validation tool doesn't check filename](https://github.com/qcif/taxodactyl/issues/358)

**Implementation authorization:** granted by the user via `/speckit-implement 10`, 2026-11-19.

**Scope:** Make the pipeline accept user input files whose path contains
spaces, for `--metadata`, `--sequences` and `--coverage_taxa`. Do this by
staging inputs under fixed names, then relaxing the nf-schema filename
patterns. This is the issue's "even better" option.

Out of scope (user decision, 2026-11-19):

- **No filename check in the validator web service.** It isn't needed once
  the pipeline accepts spaces. The service's download zip already uses
  space-free names (`validated_metadata_part<N>.csv`, `query_part<N>.fasta`,
  `services/input_validation/client/src/App.jsx:127-137`).
- `allowed_loci_file`: see `tasks/todo.md`.

**Source material:** issue #358; `nextflow_schema.json:40-73`;
`modules/prepare/inputs/main.nf`; `modules/validate/coverage/main.nf:12` (the
existing `stageAs` precedent); `spec/contracts/inputs.md` §1;
`spec/nextflow/params.md` (NF-PA-004); `spec/nextflow/processes.md` §1
(NF-PR-010/011); `spec/nextflow/workflow.md` (NF-WF-005, NF-WF-020);
`docs/params.md:13-18`. No Spec Kit feature directory is configured, so this
brief uses `spec/`, source and tests directly.

## Preconditions

- Branch from `main` (baseline `26b0e12`). Code doesn't overlap with
  other active tasks, but docs do:
  - Task 03 (`03_remove_obsolete_metadata_schema`) also edits
    `spec/contracts/inputs.md` §1 and `docs/params.md`.
  - Task 01 also edits `spec/nextflow/params.md` and `docs/params.md`.

  Rebase on whichever merges first, and resolve text conflicts by keeping
  both changes.
- Baseline behaviour:
  - nf-schema (`validateParameters()` in `PIPELINE_INITIALISATION`) rejects
    any `metadata`/`coverage_taxa` path not matching `^\S+\.csv$`, and any
    `sequences` path not matching `^\S+\.(fasta|fas|fna|fa)$`. This rejects
    a space anywhere in the path, directories included.
  - `PREPARE_INPUTS` (`modules/prepare/inputs/main.nf`) stages the user's
    file under its original name. The original name is then put into the
    bash script (`cp "${metadata_file}" metadata.csv`,
    `cp "${sequences_source}" sequences.fasta`, and the
    `[ "${metadata_file}" != "metadata.csv" ]` test). Double quotes cope
    with spaces but not with `"`, `$` or backticks in a name.
  - `VALIDATE_COVERAGE_TAXA` already stages its input as
    `input_coverage.csv` (`modules/validate/coverage/main.nf:12`). So
    coverage mode needs only the schema change.
  - nf-tests (`test/*/taxodactyl*.workflow.nf.test`) run the `TAXODACTYL` /
    coverage workflows directly. They never call `PIPELINE_INITIALISATION`,
    so the schema patterns are never exercised by tests.

## Objective

1. `nextflow run main.nf --metadata "/path/My samples.csv" --sequences
   "/path/my seqs.fasta" ...` passes parameter validation, and
   `PREPARE_INPUTS` emits `metadata.csv` and `sequences.fasta` with content
   byte-identical to the inputs.
2. `--coverage_taxa "/path/my taxa.csv"` passes parameter validation and
   `VALIDATE_COVERAGE_TAXA` runs.
3. Extension checks are kept. A `metadata` path that doesn't end in `.csv`,
   or a `sequences` path without a FASTA extension, still fails parameter
   validation with a clear message.
4. The original filename never appears in a process script.

## Implementation

### A. Stage inputs under fixed names (`modules/prepare/inputs/main.nf`)

1. Change the inputs to:
   ```groovy
   path sequences_file, stageAs: 'input_sequences.fasta'
   path metadata_file, stageAs: 'input_metadata.csv'
   ```
   The fixed names cannot clash with the outputs `sequences.fasta` /
   `metadata.csv`. This also removes the "already named metadata.csv"
   special case.
2. Rewrite the script so it uses only the staged names:
   - `if [ -e input_sequences.fasta ]; then cp input_sequences.fasta sequences.fasta; fi`
     (keep NF-PR-010: no `sequences.fasta` when no file was supplied).
   - `cp input_metadata.csv metadata.csv`. If `input_metadata.csv` is
     missing, keep the existing exit 1 with
     `ERROR: Metadata file not found` on stderr.
   - Keep the `wc -l` line-count echoes.
   - Remove the `def sequences_source = ...` Groovy line. With `stageAs`, a
     one-element list may be staged as a single `Path`, and indexing a
     `Path` with `[0]` returns a name component rather than a list element.
     Check this rather than assume it.
3. `tag`: keep `tag "$metadata_file"` only if it still shows something
   useful. Check what it renders to after staging (expected:
   `input_metadata.csv`). It becomes the `<tag>` in
   `<outdir>/errors/PREPARE_INPUTS/<tag>.*` (NF-WF-005). If it only ever
   shows the constant staged name, either keep it (harmless) or set it to
   `"${params.metadata ? file(params.metadata).name : ''}"`. Record which
   in the PR. Do not put the original name into the script body.
4. Check the empty-list case. `workflows/taxodactyl.nf:47` passes `[]` when
   `--sequences` is absent. Confirm that `stageAs` with a fixed name accepts
   an empty list (no staging, no error), and that `PREPARE_INPUTS.out.sequences`
   still emits nothing, so the `.ifEmpty([])` fallback (NF-WF-021) applies.
   If Nextflow rejects this, use `stageAs: 'input_sequences*.fasta'` (a
   glob is valid for 0..n files) and adjust the script's existence test.
   Record the outcome.
5. No change to `workflows/taxodactyl.nf` or `workflows/coverage.nf`.
   `file(params.metadata)` copes with spaces.
6. Lint: `nextflow lint modules/prepare/inputs/main.nf`.

### B. Relax the schema patterns (`nextflow_schema.json`)

1. `coverage_taxa` (line 42) and `metadata` (line 51): `"pattern": "^\\S+\\.csv$"`
   → `"pattern": "^.+\\.csv$"`.
2. `sequences` (line 67): `"^\\S+\\.(fasta|fas|fna|fa)$"` →
   `"^.+\\.(fasta|fas|fna|fa)$"`.
3. In the three `errorMessage` strings (lines 47, 56, 72), remove
   "file name cannot contain spaces". Keep the extension and
   required-column wording, e.g. "... be in CSV format with columns:
   'sample_id', 'locus', 'preliminary_id', and must have a .csv extension."
4. Keep the `format`, `exists` and `mimeType` keys unchanged. Extension
   matching stays case-sensitive, as now. Don't widen it in this task.
5. Check the JSON is still valid:
   `python -m json.tool nextflow_schema.json > /dev/null` (use the
   `scripts/venv` python).

## Documentation and configuration

- `docs/params.md`: on lines 13 (`coverage_taxa`), 16 (`metadata`) and 18
  (`sequences`), remove "no spaces" from the validation column. Leave line
  64 (`allowed_loci_file`) alone; it is out of scope.
- `spec/nextflow/params.md` NF-PA-004 (line 11): update the patterns to
  `^.+\.csv$` / `^.+\.(fasta|fas|fna|fa)$`. Add a short note that spaces
  in paths are accepted (#358, task 10).
- `spec/contracts/inputs.md` §1 (around line 24): replace "must match
  `^\S+\.csv$` (no spaces, `.csv` extension)" with the new pattern. Say that
  the original filename is not used after staging.
- `spec/nextflow/processes.md` §1 `PREPARE_INPUTS`: update **Input** (staged
  as `input_sequences.fasta` / `input_metadata.csv`) and **Behaviour** (always
  copies, with no "already named" special case). Add a requirement row:
  `NF-PR-012 | MUST stage user inputs under fixed names and MUST NOT
  interpolate the user-supplied filename into the task script (#358).`
- `tasks/changelog.md`: add one line on completion, e.g. "Input files
  (`--metadata`, `--sequences`, `--coverage_taxa`) may now have spaces in
  their file or folder names (task 10_input_filenames_with_spaces, #358)".
- No change to `services/input_validation/` or `spec/services/input-validation.md`.

## Testing decision

Recorded 2026-11-19 by the user for the task 10 scope (metadata, sequences
and coverage_taxa filename handling) — option "Mixed":

| Suite / check | Affected? | New assertions by | Run by | Drift review by | May update expected results |
|---|---|---|---|---|---|
| `nextflow lint` on changed `.nf` files | yes | — | agent | — | — |
| `nextflow_schema.json` JSON validity | yes | — | agent | — | — |
| Local smoke runs with spaced filenames + negative extension checks (see Validation) | new manual check, no test file added | — | agent (reports results) | agent reports; user accepts | — |
| nf-test scenarios `test/core`, `test/scenario_01`–`04`, `test/coverage` and their `.snap` files | not expected to change | none added | CI / self-hosted runner (`.github/workflows/nf-test.yml`) | **user** | **user only** |
| Flag baselines (`test_flags.py`) | not expected to change | none | CI | **user** | **user only** |
| Selenium report fixtures (`test/selenium/expected/`) | not expected to change | none | user | **user** | **user only** |
| Python unit/integration tests (`scripts/tests/`) | not affected (no Python change) | none | — | — | — |
| Validator service | not affected; no tests exist (TST-G-008) | none | — | — | — |

No new nf-test, module test or Python test is added. The agent must not
update snapshots, flag baselines or Selenium fixtures.

## Validation

Implementation evidence the agent records in the PR description. Record
every check actually run with its outcome, including failures and anything
skipped because a tool or data wasn't available.

1. `nextflow lint modules/prepare/inputs/main.nf`: no new errors.
2. `scripts/venv/bin/python -m json.tool nextflow_schema.json > /dev/null`
   succeeds.
3. **Positive smoke run (sequence mode).** In a scratch directory:
   ```bash
   cp test/metadata.csv "<scratch>/My samples.csv"
   cp test/query.fasta "<scratch>/my query.fasta"
   nextflow run main.nf -profile singularity,test \
       --metadata "<scratch>/My samples.csv" \
       --sequences "<scratch>/my query.fasta" \
       --taxdb ~/.taxonkit/ \
       --outdir "<scratch>/out_spaces"
   ```
   Pass: parameter validation succeeds, and `PREPARE_INPUTS` and
   `VALIDATE_INPUT` complete. `cmp` shows the `metadata.csv` and
   `sequences.fasta` in the `PREPARE_INPUTS` work dir are byte-identical
   to the originals. `.command.sh` for that task doesn't contain
   `My samples` or `my query`. The rest of the `test` profile runs BOLD
   live; let it finish if practical, and report how far it got.
4. **Positive smoke run (no `--sequences`).** Repeat with a copy of a
   metadata CSV that has a `sequence` column
   (`scripts/tests/test-data/validation/metadata_with_sequences.csv`). Name
   the copy with a space (e.g. `"<scratch>/with seqs.csv"`) and pass no
   `--sequences`. Pass:
   `PREPARE_INPUTS` emits no `sequences.fasta`, and `VALIDATE_INPUT` runs
   from the CSV `sequence` column.
5. **Positive smoke run (coverage mode).**
   `cp test/coverage_example.csv "<scratch>/my taxa.csv"`, then
   `nextflow run main.nf -profile singularity --coverage_taxa "<scratch>/my taxa.csv" --taxdb ~/.taxonkit/ --outdir "<scratch>/out_cov"`.
   Pass: parameter validation succeeds and `VALIDATE_COVERAGE_TAXA`
   completes.
6. **Negative checks.** Each must fail at parameter validation with the
   updated `errorMessage` (no mention of spaces):
   `--metadata "<scratch>/My samples.txt"` and
   `--sequences "<scratch>/my query.txt"`. Stop the run once the error is
   printed.
7. Existing paths without spaces still work: the `-profile test` defaults
   (`test/metadata.csv`, `test/query.fasta`) pass through `PREPARE_INPUTS`
   unchanged. Run 3 shows this if you also run once with the defaults, or
   rely on the CI nf-test run.

If singularity, `~/.taxonkit/` or network access isn't available locally,
record which checks couldn't run and hand them to the user rather than
marking them passed.

## Test impact and manual review

- **Expected changes:** none to any test, snapshot or expected output. Why:
  - nf-tests skip nf-schema.
  - `PREPARE_INPUTS` outputs keep the names `metadata.csv` /
    `sequences.fasta` with identical content, so every downstream task
    input is unchanged. Only the `PREPARE_INPUTS` task hash changes.
  - Snapshotted channels (`ch_hits_for_report`, `ch_candidates_for_report`,
    `ch_source_diversity_for_report`, `ch_homology_trees`) come from
    after `VALIDATE_INPUT`.
- **Possible change needing evidence:** `ch_params_json` (asserted only by
  count in `test/*/taxodactyl.workflow.nf.test`) holds `params.metadata`.
  Its value is unchanged in nf-tests. Also, the `PREPARE_INPUTS` tag can
  change the name of an error-log file under `<outdir>/errors/` if that
  task fails (NF-WF-005). It isn't asserted anywhere.
- **Preparation:** none needed. No new channels or fixtures.
- **Manual user review (handoff):** after the PR's CI nf-test run
  (`.github/workflows/nf-test.yml`, self-hosted runner, mock-test fixture
  `mock_test_20260804.tar.gz`), the user checks the zipped report for:
  - any snapshot mismatch, and
  - any change in `flags_results.txt` / `flags_errors.txt`.
  Any difference here is unexpected. Treat it as a suspected regression or
  reference-data drift, not an intended change. Only the user may accept
  snapshots or baselines.
- **Optional user check (Azure):** a `-profile azure` run with a
  space-containing blob path for `--metadata` / `--sequences`. This
  confirms Azure Batch staging handles the name (see Risks). It isn't run
  by the agent.

## Completion criteria

- [x] `modules/prepare/inputs/main.nf` stages inputs as
      `input_sequences.fasta` / `input_metadata.csv`, and its script contains
      no user filename.
- [x] `nextflow_schema.json` patterns and error messages for `metadata`,
      `sequences` and `coverage_taxa` updated as in §B.
- [x] `docs/params.md`, `spec/nextflow/params.md`,
      `spec/contracts/inputs.md` and `spec/nextflow/processes.md` updated;
      `tasks/changelog.md` line added.
- [x] Validation checks 1–7 recorded with their outcomes. Any not run are
      listed as pending for the user.
- [ ] **Manual (user):** CI nf-test run reviewed, with no unexpected
      snapshot or flag drift. Pending until the user confirms.
- [ ] Implementation status and manual-validation status reported
      separately in the PR.

## Risks

- **Azure Batch staging of paths with spaces** isn't covered by any local
  check. Nextflow escapes staged paths, and the user filename no longer
  reaches the script, so the risk is low but not verified. See the optional
  Azure check above.
- **`stageAs` with an empty list.** This is the no-`--sequences` case;
  step A4 and validation check 4 cover it. If Nextflow rejects a fixed
  `stageAs` name with zero files, use the glob fallback in A4.
- Relaxing `^\S+` to `^.+` also allows leading or trailing whitespace and
  other unusual characters. That's fine, because no script sees the
  original name, but say so in the PR.

## Outcomes

Implemented 2026-11-19 on branch `task-10-input-filenames-with-spaces`.

### Implementation status: complete

- **A. Staging.** `PREPARE_INPUTS` stages its inputs as
  `input_sequences.fasta` / `input_metadata.csv` and copies only those fixed
  names. The `sequences_source` Groovy line and the "already named
  `metadata.csv`" special case are gone. The script contains no user
  filename (NF-PR-012).
  - **A3 tag:** kept `tag "$metadata_file"`, which renders as
    `input_metadata.csv` (seen in the run log:
    `TAXODACTYL:PREPARE_INPUTS (input_metadata.csv)`). I didn't use the user
    filename: NF-WF-005 takes the `<tag>` from the first `(...)` in the task
    name, so a name like `My samples (v2).csv` would garble the
    `<outdir>/errors/PREPARE_INPUTS/<tag>.*` path. There's a comment in the
    module saying so.
  - **A4 empty list:** a fixed `stageAs` name with `[]` (no `--sequences`)
    works. Nothing is staged, there's no error, and no `sequences.fasta` is
    emitted, so the glob fallback wasn't needed.
- **B. Schema.** The `metadata` / `coverage_taxa` pattern is `^.+\.csv$` and
  the `sequences` pattern is `^.+\.(fasta|fas|fna|fa)$`. The three
  `errorMessage`s no longer mention spaces. `format`/`exists`/`mimeType`
  are unchanged.
- **Docs/spec:** `docs/params.md` (3 rows), `spec/nextflow/params.md`
  NF-PA-004 (now also covers `coverage_taxa`), `spec/contracts/inputs.md` §1,
  and `spec/nextflow/processes.md` §1 (Input, Behaviour, new NF-PR-012).
  `tasks/changelog.md` has the release note line.
- No test, snapshot, flag baseline or Selenium fixture was changed.
- Relaxing `^\S+` to `^.+` also accepts leading/trailing whitespace and other
  unusual characters in the path. That's acceptable because no task script
  sees the original name after staging.

### Validation (agent)

Local environment: Nextflow 26.04.6 is installed. It can't compile the
pipeline under its default strict parser (known, #304 / NF-CF-002), so runs
used `NXF_VER=25.04.6`, the version CI pins. Fixtures lived in
`<scratch>/smoke dir/`, so the directory has a space as well as the files.

| # | Check | Result |
|---|---|---|
| 1 | `nextflow lint modules/prepare/inputs/main.nf` | **Pass**: no errors |
| 2 | `python -m json.tool nextflow_schema.json` (scripts/venv) | **Pass** |
| 3 | Sequence mode, `--metadata "…/smoke dir/My samples.csv" --sequences "…/smoke dir/my query.fasta"` | **Pass**, see deviations: parameter validation OK, `PREPARE_INPUTS` and `VALIDATE_INPUT` exit 0. `cmp`: `metadata.csv` and `sequences.fasta` byte-identical to the originals. `.command.sh` has 0 matches for `My samples`/`my query`. Got as far as `MOCK_BLASTN`; `EXTRACT_HITS` then failed with `IndexError` because the reused `test/core/blast_result.xml` doesn't match these queries (same failure with the space-free paths in check 7, so unrelated). |
| 4 | No `--sequences`, `--metadata "…/smoke dir/with seqs.csv"` | **Pass**: `PREPARE_INPUTS` staged only `input_metadata.csv`, printed "Sequences file: not provided", emitted no `sequences.fasta`. `metadata.csv` byte-identical. `VALIDATE_INPUT` exit 0 with no `--query-fasta` (sequences taken from the CSV column). |
| 5 | Coverage mode, `--coverage_taxa "…/smoke dir/my taxa.csv"` | **Pass**: `VALIDATE_COVERAGE_TAXA`, 4× `EVALUATE_DATABASE_COVERAGE`, `REPORT_COVERAGE`, `PREPARE_LOG`; "Pipeline completed successfully". |
| 6 | Negative: `--metadata "…/My samples.txt"`, `--sequences "…/my query.txt"` | **Pass**: both stop at parameter validation with the new messages (no mention of spaces). |
| 7 | Space-free defaults `test/metadata.csv` + `test/query.fasta` | **Pass**: `PREPARE_INPUTS` outputs byte-identical, `VALIDATE_INPUT` exit 0. CI nf-test run still to be reviewed (below). |

**Deviations from the planned commands** (environment, not code):

- `-profile test` (`db_type=bold`) can't build the workflow on `main`:
  `EXTRACT_HITS.out` is referenced unconditionally
  (`workflows/taxodactyl.nf:316`, known defect NF-D-002, tasks 01/02). So
  checks 3, 4 and 7 used BLAST mode with mock BLAST
  (`--db_type blast_core_nt --mock_blast true --blast_xml
  test/core/blast_result.xml`, placeholder `--blastdb`) instead of the
  `test` profile with live BOLD.
- Pulling `docker://neoformit/taxodactyl:main` from Docker Hub failed locally
  with a registry auth error. The `daff_tax_assign` container was instead a
  SIF built from the locally cached `neoformit/taxodactyl:latest` Docker
  image, passed via `-c` override. That image may lag `main`, but this task
  changes no code inside the container.
- `--outdir` had to be outside the spaced directory. With a spaced
  `--outdir`, `VALIDATE_COVERAGE_TAXA` failed (`FATAL: could not open image
  …/dir/out_cov`) because `containerOptions` binds `--outdir` unquoted.
  That's out of scope and recorded in `tasks/todo.md`.

### Pending (user)

- **CI nf-test run** (`.github/workflows/nf-test.yml`, self-hosted runner)
  on the PR: check the zipped report for snapshot mismatches and any change
  in `flags_results.txt` / `flags_errors.txt`. None are expected. Only the
  `PREPARE_INPUTS` task hash changes.
- **Optional Azure check:** a `-profile azure` run with a space-containing
  blob path for `--metadata` / `--sequences` (not run).
- The PR description should report implementation status (complete) and
  manual-validation status (pending the above) separately.

### Spin-offs (`tasks/todo.md`)

- Widened the existing `allowed_loci_file` item: unquoted `containerOptions`
  binds also break on spaces in `--outdir` (9 modules) and `--taxdb`. Seen
  directly in the coverage smoke run.
- No new item for the BOLD-branch build failure (NF-D-002) or the Nextflow
  ≥25.10 strict-syntax failure (#304, NF-CF-002); both are already tracked.
