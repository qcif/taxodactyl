# Task 02 — Add a quick supported pipeline smoke check

**Status:** planned

**Priority:** P2

**Scope:** Follow-up task to establish a small, repeatable BLAST smoke
scenario. Develop it first as a real BLAST run to capture a representative XML,
then switch the quick check to replay that XML with `mock_blast`. This task is
intentionally separate from the immediate BOLD execution block and does not
use the `test/core` scenario.

## Preconditions

- Task 01, `tasks/01_block_taxodactyl_bold.md`, is complete.
- The appropriate lightweight BLAST reference database is available for the
  initial capture run; the full `test/core` scenario is out of scope.
- The test profile must remain reproducible on supported local/CI profiles.

## Objective

Create `test/smoke/` as the home for the quick scenario. Use
`test/smoke/metadata.csv` and `test/smoke/query.fasta` for the inputs, first
run the real BLAST path to produce `test/smoke/blast_result.xml`, then use the
captured XML for fast repeatable checks.

## Implementation

1. Create `test/smoke/metadata.csv`, `test/smoke/query.fasta`, and
   `test/smoke/README.md` by moving or copying the current quick-check inputs
   from `test/metadata.csv` and `test/query.fasta` without involving `test/core`.
2. Configure `conf/test.config` for `db_type = 'blast_core_nt'` and the
   `test/smoke/` inputs for the initial real-BLAST run.
3. Run the smoke scenario against the available lightweight BLAST database and
   capture the resulting XML as `test/smoke/blast_result.xml`; record the
   database provenance and command in `test/smoke/README.md`.
4. Add the replay configuration using `mock_blast = true` and
   `blast_xml = ${baseDir}/test/smoke/blast_result.xml`, so the normal quick
   check does not require BLAST database access after capture.
5. Add `test/smoke/test_bold_guard.sh` as a negative smoke test that invokes
   the pipeline with the smoke metadata/FASTA and `--db_type bold`, expects a
   non-zero exit, checks for the documented unsupported-mode message, and
   confirms that no `BOLD_SEARCH` or downstream task was scheduled.
6. Preserve the BOLD guard test as a separate invocation from the successful
   BLAST/XML-replay smoke check.

## Validation

- Confirm the real-BLAST smoke run completes and produces
  `test/smoke/blast_result.xml`.
- Confirm the replay profile completes using the captured XML without running
  BLAST again.
- Run `test/smoke/test_bold_guard.sh` and confirm BOLD fails early with the
  unsupported-mode message and no analysis task starts.
- Confirm no `test/core` scenario or full Core Nt fixture is required.

## Completion criteria

- `test/smoke/` contains the metadata, FASTA, captured XML, and provenance
  README for the scenario.
- The documented invocation supports both initial real-BLAST capture and fast
  XML replay.
- `conf/test.config` defaults to the fast replay once the XML is captured.
- BOLD guard validation remains a separate, explicit check.
