# Task 02 — Add a quick supported pipeline smoke check

**Status:** planned

**Priority:** P2

**Scope:** Follow-up task to establish a small, repeatable BLAST smoke
scenario. Develop it first as a real BLAST run to capture a representative XML,
then switch the quick check to replay that XML with `mock_blast`. This task is
intentionally separate from the immediate BOLD execution block. Reuse the
small Core Nt database documented in `test/core/README.md` for initial BLASTN
capture and subsequent `blastdbcmd` taxonomy lookup, while keeping the smoke
inputs and execution separate from the full `test/core` scenario. Reference
data is downloaded and extracted manually before running the smoke check.
Automatic reference-setup workflows and launchers are out of scope.

**Source material:** Task 01_block_taxodactyl_bold, `test/core/README.md`,
`spec/nextflow/workflow.md`, `spec/nextflow/config-profiles.md`, and
`spec/tests.md`.

## Preconditions

- Task 01_block_taxodactyl_bold is complete.
- Manually download and extract the subset Core Nt database using the
  instructions in `test/core/README.md`. Its database prefix is
  `test/core/refdata/blastdb/2026-07-29/subset_core_nt`. It is required for
  both initial capture and replay. Reuse an existing valid installation.
- Manually provision the taxonomy dump required by P0 and
  `EXTRACT_TAXONOMY`; the Core instructions use
  `test/core/refdata/taxonkit/2026-05-08/`. Record its version and `--taxdb`
  path in `test/smoke/README.md`.
- Nextflow and the selected container runtime must be available.
- The test profile must remain reproducible on supported local/CI profiles.

## Objective

Create `test/smoke/` as the home for the quick scenario. Use
`test/smoke/metadata.csv` and `test/smoke/query.fasta` for the inputs, first
run the real BLAST path to produce `test/smoke/blast_result.xml`, then use the
captured XML for fast repeatable checks. Replay skips BLASTN only;
`BLAST_BLASTDBCMD` still reads the subset database, and taxonomy extraction
still requires the taxonomy dump. Invoke `main.nf` directly with the test and
container profiles after manually preparing the references. Keep the existing
analysis workflow and its reference-path interfaces unchanged.

## Implementation

1. Create `test/smoke/metadata.csv`, `test/smoke/query.fasta`, and
   `test/smoke/README.md` by moving or copying the current quick-check inputs
   from `test/metadata.csv` and `test/query.fasta`. Do not substitute the full
   Core metadata, FASTA, or XML fixtures.
2. Configure `conf/test.config` for `db_type = 'blast_core_nt'` and the
   `test/smoke/` inputs. Set `blastdb` to
   `${baseDir}/test/core/refdata/blastdb/2026-07-29/subset_core_nt` for both
   capture and replay, and document how to override the reference paths.
3. Run the smoke scenario with `--mock_blast false` against that subset database and
   capture the resulting XML as `test/smoke/blast_result.xml`; record the
   database/taxdump provenance and complete command in `test/smoke/README.md`.
4. Add the replay configuration using `mock_blast = true` and
   `blast_xml = "${baseDir}/test/smoke/blast_result.xml"`. Retain the
   `blastdb` configuration and startup validation: the normal quick check
   bypasses BLASTN but still runs `BLAST_BLASTDBCMD` against the subset database.
5. Add `test/smoke/test_bold_guard.sh` as a negative smoke test that invokes
   `main.nf` with the smoke metadata/FASTA and `--db_type bold`, expects a
   non-zero exit, checks for the documented unsupported-mode message, and
   confirms that no process was scheduled, including input preparation and
   validation. Use fresh output/work directories and a separate trace/log so
   results from earlier successful runs cannot contaminate this assertion.
6. Preserve the BOLD guard test as a separate invocation from the successful
   BLAST/XML-replay smoke check.

## Specification and documentation changes

- Update `spec/nextflow/config-profiles.md` to describe the `test` profile's
  smoke input paths, BLAST mode, default XML replay, and retained subset
  database requirement; remove the obsolete claim that this profile selects
  BOLD and cannot succeed. State that references must be prepared manually.
- Update `spec/tests.md` to document the smoke scenario, entry-point BOLD
  guard check, real-capture/replay commands, and required reference data.
  State that replay replaces only BLASTN and retains downstream execution
  and its external dependencies. Distinguish manual smoke commands from
  existing CI coverage.
- Update `spec/nextflow/workflow.md` where it describes `conf/test.config`
  as BOLD-based. Preserve the operational BOLD guard established by Task 01.
- In `test/smoke/README.md` and the usage comment in `conf/test.config`,
  document manual reference download/extraction using `test/core/README.md`,
  reference-path overrides, the supported container profile, capture
  with `--mock_blast false`, default replay, and the separate BOLD guard check.

## Validation

- Follow the documented manual reference-setup instructions and confirm the
  extracted database prefix and taxonomy directory work with the documented
  `--blastdb` and `--taxdb` parameters.
- Confirm the real-BLAST smoke run completes and produces
  `test/smoke/blast_result.xml`.
- Confirm the replay profile completes using the captured XML: its trace must
  show `MOCK_BLASTN` and `BLAST_BLASTDBCMD`, but no `BLAST_BLASTN`. Confirm
  `BLAST_BLASTDBCMD` uses the provisioned subset Core Nt database.
- Run `test/smoke/test_bold_guard.sh` and confirm BOLD fails early with the
  unsupported-mode message and no analysis task starts. Verify this with
  absent references and confirm no reference downloads are attempted.
- Confirm the smoke run uses its own inputs/XML and only the shared reference
  data from `test/core`; no full Core scenario or full Core Nt database is
  required.
- Confirm the updated specifications and documented commands agree with
  `conf/test.config` and the observed capture/replay behavior.

## Completion criteria

- `test/smoke/` contains the metadata, FASTA, captured XML, and provenance
  README for the scenario.
- The documented invocation supports both initial real-BLAST capture and fast
  XML replay.
- Manual download/extraction instructions and reference-path overrides are
  documented; no automatic setup workflow or launcher is introduced.
- `conf/test.config` defaults to the fast replay once the XML is captured.
- The subset Core Nt database remains configured and available for
  `blastdbcmd` in replay mode; taxonomy-dump requirements are documented.
- Profile/workflow specifications and the test inventory describe the smoke
  scenario and its retained dependencies accurately.
- BOLD guard validation remains a separate, explicit check.
