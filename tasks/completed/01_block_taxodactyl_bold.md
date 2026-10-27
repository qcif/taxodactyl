# Task 01 — Block taxodactyl execution against BOLD

**Status:** completed (awaiting merge)

**Priority:** P1

**Issue:** [#328 — Block execution of taxodactyl against BOLD for now](https://github.com/qcif/taxodactyl/issues/328)

**Scope:** Add an early pipeline-initialisation guard so `--db_type bold`
fails before any workflow process can execute. This is an operational block,
not a repair or retirement of the BOLD implementation.

**Source material:** Issue #328 and the existing repository specifications under `spec/`,
especially `spec/nextflow/workflow.md`, `spec/nextflow/error-handling.md`,
`spec/python/p1-bold-search.md`, and `spec/decisions.md` D-01.

## Preconditions

- The guard must run during `PIPELINE_INITIALISATION`.
- `main.nf` must continue to invoke `PIPELINE_INITIALISATION` before
  `TAXODACTYL`.
- The existing BLAST validation and startup checks must remain unchanged.
- This task does not repair BOLD API, orientation, output, or channel-wiring
  defects. Those remain governed by `spec/decisions.md` D-01.

## Objective

When a user selects `--db_type bold`, taxodactyl must fail immediately with a
clear, actionable message stating that BOLD execution is temporarily disabled
and that the supported execution mode is BLAST. No `PREPARE_INPUTS`,
`VALIDATE_INPUT`, `BOLD_SEARCH`, or downstream analysis process may be
scheduled.

## Implementation

1. Add an early `params.db_type == 'bold'` validation failure in
   `subworkflows/local/utils_nfcore_taxodactyl_pipeline/main.nf`, inside
   `validateInputParameters()`.
2. Place the guard before the existing database-coverage and BLAST-database
   checks.
3. Use an error message that names `--db_type bold`, explains the temporary
   block, and points users to the supported BLAST database mode.
4. Confirm the initialization order in `main.nf` prevents any process from
   starting before the guard fails.
5. Preserve the existing `blast_core_nt` validation, including the required
   `blastdb` and coverage-threshold checks.

## Specification changes

Update the source specifications to record the intended behavior:

- Add a Nextflow workflow requirement in
  `spec/nextflow/workflow.md` stating that `db_type == 'bold'` must fail during
  pipeline initialization before any process is scheduled.
- Update the BOLD parameter behavior in `spec/nextflow/params.md` to state
  that the parameter remains recognized but execution is temporarily blocked.
- Record the temporary block and its user-visible purpose in
  `spec/decisions.md` D-01 without closing the repair-or-retire decision.

This is a specification of the current operational policy, not a claim that
BOLD is repaired or permanently removed.

## User documentation

Update the following files so the block is discoverable and does not appear
to be an accidental BOLD regression:

- `README.md`
- `docs/params.md`
- `docs/README.md`

Leave `conf/test.config` unchanged in this task. Its current BOLD setting is
useful for exercising the intentional unsupported-mode guard. Task
02_test_profile_small_core separately moves the profile to dedicated
`test/smoke/` inputs and captured BLAST XML replay, retaining the small Core Nt
database from `test/core` for `blastdbcmd` taxonomy lookup. It does not run the
full Core test scenario.

## Validation

Validate through the pipeline entry point, `main.nf`, so each invocation runs
`PIPELINE_INITIALISATION` before `TAXODACTYL`. Use explicit command-line
invocations (or an entry-point nf-test) with fresh output/work directories and
a separate trace file for each case. For the existing test profile, invoke
`nextflow run main.nf -profile test --db_type bold` with those isolated paths.
The existing `test/core/taxodactyl.workflow.nf.test` invokes `TAXODACTYL`
directly and therefore cannot validate this initialization guard; it may be
used separately for BLAST workflow regression coverage.

Verify:

- `--db_type bold` exits non-zero with the documented error.
- No process is scheduled, including `PREPARE_INPUTS`, `VALIDATE_INPUT`,
  `BOLD_SEARCH`, and downstream analysis processes.
- The existing BOLD-based test profile returns the same documented unsupported
  mode error.
- A supported BLAST invocation is not rejected by the new guard.
- Existing BLAST startup validation still rejects missing `blastdb`.

Capture the error message and final exit status, and inspect the invocation's
trace, log, and fresh work directory to confirm zero scheduled tasks. An empty
work directory alone is not sufficient: the failure must be the documented
BOLD guard rather than a configuration, plugin, or missing-input error.

## Completion criteria

- The BOLD guard is implemented in the pipeline initialization path.
- The user-facing documentation identifies BOLD as intentionally blocked.
- The existing test profile remains unchanged and exercises the BOLD guard.
- Validation confirms no BOLD or downstream process starts for a blocked run.
- The task can then be moved to `tasks/completed/` once the implementation and
  validation are complete.

## Open decision

Removing this guard requires an explicit decision on whether BOLD will be
repaired or retired, as recorded in `spec/decisions.md` D-01.

## Outcomes

- Implemented the BOLD rejection at the start of `validateInputParameters()`.
  It identifies the temporary block and directs users to `--db_type
  blast_core_nt` with `--blastdb`. Existing BLAST checks and initialization
  order are unchanged, as is `conf/test.config`.
- Updated README, parameter documentation, documentation index, workflow and
  parameter specifications, and D-01. Also reconciled the test-profile
  specification and documented the startup regression suite in `spec/tests.md`.
  D-01 remains open; no BOLD repair or retirement was attempted.
- Added `test/startup/test_initialisation.sh`. All eight entry-point cases
  passed using Nextflow 25.04.6: explicit BOLD, BOLD test profile, BOLD before
  coverage validation, BOLD with schema validation disabled, BLAST missing
  database, BLAST coverage threshold, BLAST related-coverage threshold, and
  successful BLAST startup in preview mode. Each case verified zero process
  submissions, trace task rows, and process command scripts.
- Validation command: `bash test/startup/test_initialisation.sh`.
  Logs, exit statuses, and trace evidence are retained at
  `/tmp/taxodactyl-startup.FuIMwt` in the implementation environment.
  BLAST preview confirms startup/workflow construction only; full BLAST
  analysis and the Core nf-test scenario were not run. Reference databases
  and analysis containers were not needed for these startup tests.
- `nextflow lint subworkflows/local/utils_nfcore_taxodactyl_pipeline/main.nf`
  passed with four existing unused-variable warnings across included files.
  Shell syntax and `git diff --check` passed.
- Added `.worktrees/` to `.gitignore` for the isolated implementation
  worktree. Existing Docker ignore coverage was inspected; no change needed.
- No extension hooks or applicable feature checklists were present.
- Branch: `task-01-block-taxodactyl-bold`.
  Worktree: `.worktrees/task-01-block-taxodactyl-bold`.
  The source-worktree active entry remains until the user merges the branch.
- Follow-up: task 02_test_profile_small_core provides the supported smoke
  profile using manually provisioned references; its brief is unchanged.
