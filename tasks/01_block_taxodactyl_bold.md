# Task 01 — Block taxodactyl execution against BOLD

**Status:** active

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
useful for exercising the intentional unsupported-mode guard. Moving the test
profile to the small Core database used by CI is tracked separately in
`tasks/02_test_profile_small_core.md`.

## Validation

Run the repository’s Nextflow/nf-test validation using
`test/core/taxodactyl.workflow.nf.test` and verify:

- `--db_type bold` exits non-zero with the documented error.
- No `BOLD_SEARCH` task is created.
- No downstream process is scheduled.
- The existing BOLD-based test profile returns the same documented unsupported
  mode error.
- A supported BLAST invocation is not rejected by the new guard.
- Existing BLAST startup validation still rejects missing `blastdb`.

Inspect the generated task/work directories and final exit status as evidence
that the block happens during initialization rather than after partial work.

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
