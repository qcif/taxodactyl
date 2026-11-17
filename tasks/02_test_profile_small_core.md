# Task 02 — Add a quick supported pipeline smoke check

**Status:** planned

**Priority:** P2

**Hold:** Paused at the user's request on 2026-10-28, pending the merge of
Task 01. Task 01 is implemented in a different worktree; its absence from
this checkout is not outstanding implementation work. Keep Task 02 planned
in `tasks/todo.md` until the user resumes it after that merge.

**Required review on resume:** Inspect Task 01's merged implementation and
validation coverage before deciding whether `test/smoke/test_bold_guard.sh`
is needed. Reuse existing coverage if sufficient; add or adapt a separate
guard test only if a concrete gap remains. Record the decision and revise
the implementation, documentation, validation, and completion criteria below
accordingly before implementation. All references below to adding or running
that script are provisional and subject to this review.

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

**Planning context:** Argument `02` selects this existing brief for refinement;
retain its number and planned status in `tasks/todo.md`. No new task number
is allocated (the next unused prefix is `04`).
`.specify/scripts/bash/setup-tasks.sh --json` reports no configured feature
directory, so this brief uses the repository's `spec/` documents and current
source directly. Do not generate a synthetic feature directory. Apply
`CONSTITUTION.md`, especially rules 10, 13, 15, 16, and the spec-before-code
rule; `.specify/memory/constitution.md` is an unfilled template.

## Preconditions

- Task 01_block_taxodactyl_bold is merged and available in the implementation
  checkout, and the user has resumed Task 02.
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
- Use `-profile test,singularity`: Singularity is the tested container engine
  in `spec/nextflow/config-profiles.md`. This task does not add CI coverage or
  claim support for other container engines. The existing manual CI pins
  Nextflow 25.04.6; record the actual engine/runtime versions used.
- Provide the runtime identity required by downstream NCBI requests through
  `--ncbi_user_email`. An NCBI API key is optional for the normal pipeline
  (`conf/env.config`); avoid placing credentials in fixture provenance.
  Replay retains live NCBI/GBIF dependencies and is not an offline test.

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
5. Subject to the required review on resume, add or adapt
   `test/smoke/test_bold_guard.sh` as a negative smoke test that invokes
   `main.nf` with the smoke metadata/FASTA and `--db_type bold`, expects a
   non-zero exit, checks for the documented unsupported-mode message, and
   confirms that no process was scheduled, including input preparation and
   validation. Use fresh output/work directories and a separate trace/log so
   results from earlier successful runs cannot contaminate this assertion.
6. Preserve the BOLD guard test as a separate invocation from the successful
   BLAST/XML-replay smoke check.

### Execution order and independent increments

1. **Setup/foundation:** confirm Task 01's guard is present in
   `subworkflows/local/utils_nfcore_taxodactyl_pipeline/main.nf`, provision
   references manually, and copy the one-sample smoke inputs. Keep
   `test/metadata.csv` and `test/query.fasta` unless a separate reference audit
   establishes they can be removed. Compare CSV and FASTA sample identifiers
   before capture; the current quick input is `VE24-1079_COI`.
2. **P2 — supported real capture:** update the affected specifications first,
   configure the smoke inputs/database in `conf/test.config`, and run real
   BLAST. A successful increment produces valid XML for exactly the smoke
   input and an HTML report for that sample. Use
   `modules/blast/blastn/main.nf`'s published `<outdir>/blast_result.xml`;
   copy it only after reviewing the successful run. If the subset contains
   insufficient hits for this input, record the blocker and resolve the
   fixture choice explicitly; do not substitute the full Core scenario or
   silently fabricate/reuse its XML.
3. **P2 — routine replay:** after capturing the XML, switch
   `conf/test.config` to the replay default and run with fresh output/work
   paths. Confirm the same sample reaches reporting through
   `modules/mock/blastn/main.nf`, `modules/blast/blastdbcmd/main.nf`, and
   `modules/extract/taxonomy/main.nf`. Preserve `workflows/taxodactyl.nf`'s
   existing routing and parameter interfaces. Set `taxdb` to the documented
   subset taxdump path in `conf/test.config`, with a CLI override, so default
   replay is executable after manual provisioning.
4. **P2 — early BOLD rejection:** implement
   `test/smoke/test_bold_guard.sh` against `main.nf`, then validate separately.
   Resolve the repository root from the script location, allocate a fresh
   directory with `mktemp -d`, and retain its evidence path on failure. Pass
   explicit smoke inputs, `--db_type bold`, and nonexistent `--blastdb` and
   `--taxdb` paths. Capture the Nextflow exit status without losing it through
   a pipe or `set -e`. Require the specific guard message established by
   Task 01, zero trace data rows (a missing/header-only trace is acceptable
   only with corroborating log evidence), no submitted/cached task events,
   and no task work directories. Missing plugins, configuration errors, or
   missing references must fail the test rather than count as a guard pass.
5. **Polish:** reconcile the README, profile usage comment, and specifications
   with the observed capture, replay, and negative-run evidence.

Dependency graph: `Task 01 → setup → real capture → XML fixture → replay →
final review`; `setup → BOLD guard check → final review`. After setup, the
BOLD guard script and its validation can proceed in parallel with real
capture. Drafting provenance documentation can proceed during capture, but
its commands, checksums, and results must be finalized afterward. There are
no separate product user stories in the fallback specifications; these
increments retain the existing P2 priority.

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

Run the following from the repository root after manual reference setup.
Set `NCBI_USER_EMAIL` to the operator's actual contact email in the launcher
environment. Each `mktemp` call creates a distinct run root; do not use
`-resume`. Document equivalent commands with reference-path overrides in
`test/smoke/README.md`.

```bash
smoke_capture_dir=$(mktemp -d /tmp/taxodactyl-smoke-capture.XXXXXX)
nextflow -log "$smoke_capture_dir/nextflow.log" run main.nf \
  -profile test,singularity \
  -work-dir "$smoke_capture_dir/work" \
  --outdir "$smoke_capture_dir/output" \
  --trace_file "$smoke_capture_dir/trace.tsv" \
  --blastdb "$PWD/test/core/refdata/blastdb/2026-07-29/subset_core_nt" \
  --taxdb "$PWD/test/core/refdata/taxonkit/2026-05-08" \
  --ncbi_user_email "${NCBI_USER_EMAIL:?Set NCBI_USER_EMAIL}" \
  --mock_blast false
```

After successful capture, inspect the XML's query identifiers and nonempty
hits, then copy `$smoke_capture_dir/output/blast_result.xml` to
`test/smoke/blast_result.xml`. Record SHA-256 checksums of the metadata,
FASTA, and XML in `test/smoke/README.md`, together with the reference versions,
capture command, actual BLAST/container version, and capture date. Commit
only the fixture and provenance, not downloaded reference databases or run
directories. Then enable replay defaults and run:

```bash
smoke_replay_dir=$(mktemp -d /tmp/taxodactyl-smoke-replay.XXXXXX)
nextflow -log "$smoke_replay_dir/nextflow.log" run main.nf \
  -profile test,singularity \
  -work-dir "$smoke_replay_dir/work" \
  --outdir "$smoke_replay_dir/output" \
  --trace_file "$smoke_replay_dir/trace.tsv" \
  --ncbi_user_email "${NCBI_USER_EMAIL:?Set NCBI_USER_EMAIL}"
bash -n test/smoke/test_bold_guard.sh
bash test/smoke/test_bold_guard.sh
```

Record each invocation's actual exit code and evidence locations. The guard
script must exit zero only when all negative-case assertions pass.

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
- Require zero exit status for capture and replay, successful trace statuses
  for the expected downstream tasks, and a nonempty HTML report beneath
  `<outdir>/query_001_VE24-1079_COI/`. Check the capture trace for
  `BLAST_BLASTN` and absence of `MOCK_BLASTN`; check the replay trace for the
  reverse. Inspect `BLAST_BLASTDBCMD`'s `.command.sh` using the trace's
  `workdir` column to verify its actual `-db` argument.
- Do not claim whole-report byte identity or use elapsed time as a pass/fail
  threshold: downstream APIs remain live. Verify fixture identity, intended
  process selection, successful downstream execution, and report presence.

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
- The brief stays in `tasks/todo.md` while planned. At implementation start,
  change its status to active and move its index entry to `tasks/active.md`;
  on completion, move it to `tasks/completed/02_test_profile_small_core.md`
  and remove its active entry according to the implementation workflow.

## Risks and decisions

- Task 01 is implemented in another worktree and awaiting merge. Resume
  this task after that merge and review the need for a dedicated BOLD guard
  test against the merged coverage; do not duplicate tests automatically.
- The minimal deliverable is the dedicated smoke inputs, real captured XML,
  replay-default profile, separate negative guard check, and matching
  provenance/specification updates. Automatic reference setup, a launcher,
  changes to CI workflows, and broad pipeline repairs are outside scope.
- A successful replay depends on manually installed references, containers,
  and live downstream services. Report external failures with their evidence;
  do not describe an unexecuted or partially failed run as validation success.
