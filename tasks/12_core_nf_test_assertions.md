# Task 12 — Core nf-test assertions and HTML failure review

**Status:** active

**Scope:** Replace the core workflow channel snapshot with maintainable assertions
that complement existing Selenium; replace the separate core 5.x flags check with
checks of reference-record counts and flag values only where Selenium does not
already test them; add a small nf-test testkit HTML review command and
integrate its artifacts into existing CI. Include manual `ingest` for initial
core expectations and `promote` for reviewing and accepting selected changes,
like Selenium's testkit. Other nf-test scenarios, production
scientific behavior, all Selenium changes, and automatic baseline promotion are
outside this task. Existing Selenium runs remain part of validation unchanged.

## Overview

Core currently compares four whole output channels to a snapshot, including
hashes of files influenced by live services. A failure says that content changed,
but does not clearly explain which workflow contract broke. Keep one core workflow
execution and replace the snapshot with named assertions about sample routing,
output structure, and relationships between outputs. Selenium continues to check
the scientific values displayed in reports. Produce an HTML page showing failed
checks and evidence so investigation does not start with file hashes.

Use nf-test's existing Groovy assertions, assertAll, and JUnit XML reporting.
Add only the reporting glue necessary for useful differences. The user's recent
successful run is still to be supplied; do not invent sample-specific expectations.

**Implementation authorization: pending explicit user instruction**

**Source material:** User request and testing allocation, 2026-11-23;
`test/core/taxodactyl.workflow.nf.test`, its `.snap` file,
`test/core/metadata.csv`, `test/core/README.md`, `workflows/taxodactyl.nf`,
`test/selenium/test_reports.py`, `test/selenium/lib/report.py`,
`test/selenium/lib/render.py`, `test/selenium/testkit.py`,
`scripts/tests/integration/testkit.py`, `.github/workflows/nf-test.yml`,
`.github/workflows/mock-nf-test.yml`, `.vscode/launch.json`,
`spec/tests.md`, `spec/contracts/outputs.md`, `spec/contracts/query-folder.md`,
`spec/contracts/hits.md`, `spec/contracts/candidates.md`, and `CONSTITUTION.md`.
Read `tasks/todo.md`; none of its spin-offs are absorbed by this task.

**Planning context:** Inspected branch `main`. Next unused prefix is 12 across
active, planned, completed and shelved tasks. No configured feature directory:
`.specify/scripts/bash/setup-tasks.sh --json` failed with “Feature directory not
found”; use existing `spec/` documents and source directly. The Spec Kit
constitution is an unfilled template; `CONSTITUTION.md` supplies project rules.
No `.specify/extensions.yml` exists, so there are no before/after task hooks.

## Preconditions

- Receive explicit implementation authorization.
- Obtain the user's successful run location, repository revision, input hashes,
  reference versions, image/tool versions, run timestamp, trace, nf-test logs and
  retained channel output/work files. HTML reports alone cannot establish all
  workflow output contracts. Record evidence provenance in `test/core/README.md`.
- Review the successful results with the user before accepting changed expected
  values. Success alone does not establish correctness.
- Verify features and emitted JUnit detail against CI's nf-test 0.9.5 and Nextflow
  25.04.6. Do not upgrade solely to obtain a reporting convenience.
- Use actual CI as execution evidence: `.github/workflows/nf-test.yml` currently
  selects `runner: [self-hosted]`, supports scheduled, called and manual runs,
  and explicitly executes core. Older `spec/tests.md` descriptions of a solely
  manual GitHub-hosted run are stale; flag this discrepancy when reconciling docs.

## Objective

One core run yields meaningful failures naming the sample, channel and failed
contract, with expected and observed evidence available in a portable HTML report.
Changing a check requires a small reviewed code/data edit, not whole-channel
snapshot regeneration. Report rendering can be repeated without a workflow run.

## Coverage by artifact and workflow function — plain-language explanation

This table lists the files we will check, what checks exist today, and what the
new core tests should prove. It includes all 18 different filenames found in the
current snapshots, plus the other files exposed to core nf-test. **Selenium stays
unchanged.** Exact expected results still need your review of a successful run.
For every proposed core check below, first check the existing Selenium assertions.
If Selenium already checks that same result, keep its check and omit/remove the
core or flags equivalent. Listing an artifact here does not require duplicating
every check of its contents in core.

Terms used below:

- **Artifact** means a file produced by the workflow.
- **Channel** is how Nextflow passes files and their sample identifiers between
  steps. A channel can carry several files for each sample.
- **Record** means one entry in a file, such as one hit, candidate or flag.
- **Target** means the taxon being assessed. Its **role** says whether it is a
  candidate, a taxon of interest (TOI), or the preliminary identification (PMI).
  The same taxon can occur in more than one role and must be checked separately.
- **Snapshot/hash** means the existing test compares a file fingerprint with a
  saved fingerprint. It detects a change but does not explain which result is wrong.
- **Expected value** is a result you have reviewed and saved for future comparisons.
  **Actual value** is what the current run produced.
- **Structure/schema** means required fields and their kinds of values: for
  example, a flag needs its ID, value, target and target type. A structure check
  alone does not prove the result is correct.
- **Membership** means which entries should be present, not just how many.
  Expecting A and B must fail if the output contains A twice instead.
- **Cross-file consistency** means files describing the same sample agree with
  each other. Agreement alone is not proof of correctness, so we also keep checks
  against reviewed expected results where needed.

For tracing the code: H = `ch_hits_for_report`; C = `ch_candidates_for_report`;
S = `ch_source_diversity_for_report`; T = `ch_homology_trees`;
D = `ch_db_coverage_json`; F = `ch_db_coverage_flags`; M = `ch_db_coverage_maps`.

C contains the entire candidate output directory, including copied hit files.
During implementation, list its actual files for every sample. Any additional
files must be considered explicitly, rather than silently left out of the tests.

| File / workflow function | How it is checked today | What Selenium already checks — unchanged | What the new core check means in practice |
|---|---|---|---|
| `all_hits.fasta` — hit sequences (H and C) | Saved file fingerprints | Some alignment details in the BLAST popup | Read the sequence records. Check their names and sequence contents, whether an empty file is valid for this sample, and that the records correspond to the hit JSON. Check that copying the file into the candidate directory did not change it. |
| `all_hits.json` — hit information (H and C) | Saved file fingerprints | Selected hit statistics and taxonomy | Check that each hit has the required information in the right format. Check the expected hits/counts and that references to sequence records make sense. Check that the candidate-directory copy is unchanged. Do not repeat statistics Selenium already checks. |
| `query_title.txt` — sample identity (H and C) | Saved file fingerprints | Sample ID in the input popup | Check that the title belongs to the correct input sample and is preserved in the copied file. This catches files accidentally assigned to another sample. |
| `1.flag` — candidate outcome (C) | Saved file fingerprint | Candidate/conclusion flag shown in the report | Check that the flag file has the expected number of entries, required fields and correct connection to candidate results. If an important flag result is not actually tested by Selenium, add a core check for its expected value. |
| `2.flag` — TOI outcome (C) | Saved file fingerprint | TOI flag and matching results shown in the report | Check that each flag has the required fields, refers to the correct TOI for this sample, and agrees with the TOI result files. Inspect the existing Selenium expectations: any important raw result they do not check must still be tested by core. This does not authorize adding Selenium tests. |
| `7.flag` — preliminary-ID outcome (C) | Saved file fingerprint | Preliminary-ID flag shown in the report | Check the required flag fields and that the result belongs to the sample's preliminary ID. Test important expected flag results in core if Selenium does not already check them. |
| `assigned_taxonomy.csv` — assigned taxon names (C) | Saved fingerprint when the file exists | Candidate names and taxonomy in the report | Check column names, which records are present, and that they refer to the right candidates. Specify which samples need this file and which may legitimately have no file or no rows. |
| `candidates.csv` — candidate table data (C) | Saved file fingerprint | Candidate table values | Check the required columns, unintended duplicate records, and agreement with candidate JSON and sequence files. Respect the actual format: several sequences may belong to one candidate species. |
| `candidates.json` — candidate data (C) | Saved file fingerprint | Candidate table and selected popup values | Check the required fields, which candidates are present, and agreement with the CSV, FASTA and count file. An explicit result saying “no candidates” must be distinguished from a missing or unreadable file. |
| `candidates.fasta` — candidate sequences (C) | Saved file fingerprint | No complete check of these sequences | Check sequence names and contents, that required sequences are not empty, and that they belong to the reported candidates/hits. Keep checks of reviewed exact sequence content where the inputs should always give the same result. |
| `candidates_count.txt` — decides whether to assess source diversity (C) | Saved file fingerprint | No direct check of this file or decision | Check that it contains a whole number and agrees with the candidate results. Samples with 1 through `max_candidates_for_analysis` candidates should have source-diversity results; samples outside that range should be deliberately skipped. |
| `candidates_phylogeny.fasta` — sequences selected for the tree (C) | Saved file fingerprint, including empty files | A minimum number of tree nodes for some fixtures | Check the selected sequence names/contents and which samples may have an empty file. Check that the tree labels match the selected sequences after the workflow's renaming. Do not require every candidate to appear if the workflow deliberately selects a subset. |
| `candidates_identity_boxplot.png` — plot for many candidates (C) | Saved fingerprint when present | No dedicated comparison of the image pixels | Check that the image exists when the candidate-count rule requires it, is a valid readable PNG, and has nonzero dimensions. Do not fail merely because rendering changes individual pixels. |
| `preliminary_id_match.csv` — preliminary-ID matches (C) | Saved fingerprint when present | Preliminary flag and coverage display | Check the columns and that results refer to this sample's preliminary ID and candidate/taxonomy records. Define separately when no file, no matches, or an invalid file should occur. |
| `taxa_of_concern_detected.csv` — TOI matches (C) | Saved fingerprint when present | TOI match table | Check the columns and that matched TOIs/accessions belong to the relevant sample inputs and results. Add checks for important results Selenium does not cover, without repeating its existing expected-value checks. |
| `4.flag` — independent-source outcome (S) | Saved file fingerprint for assessed samples | Publication display covers only part of this information | Check that assessed samples have the required flag entries and correct candidate associations. Check important flag values not already tested by Selenium. Intentionally skipped samples should have no S files; an assessed sample missing its output is a failure. |
| `aggregated_sources.json` — combined source information (S) | Saved file fingerprint for assessed samples | Publication names, sources and counts where expectations exist | Check required fields, which candidates and sources are represented, and agreement with `4.flag`. Distinguish “assessment ran and found no sources” from “assessment was skipped” and “output is missing”. |
| `candidates_phylogeny.nwk` — resulting tree (T) | Saved file fingerprint, including empty files | Tree title and minimum nodes | Check that a nonempty file can be read as a tree and that its leaf labels correspond to the selected sequences. Check allowed empty cases explicitly. Do not freeze every branch length or branching arrangement unless there is a reviewed reason those must remain exact. |
| `db_coverage.json` — reference database counts (D) | Only the number of files: 20 | Displayed counts/charts; some count fields allow ±10% | For each sample, taxon and role, identify which count values Selenium already checks and leave those checks there. Core checks only remaining target, related-species and in-country counts against reviewed values, plus distinct file/format requirements. Distinguish zero, unavailable and not-assessed results. Do not duplicate Selenium-owned counts or override their existing tolerance. |
| `5.1.flag` — target coverage result (F) | Core counts files; a separate script compares all saved flag entries | Displayed coverage flag and record count | List the required flag entries, target identities, flag values and corresponding D reference counts. Keep any existing checks of those results in Selenium. Core checks only what is missing, including file/record integrity requirements not already covered. Remove the overlapping separate flag-baseline comparisons. |
| `5.2.flag` — related-species coverage result (F) | Core counts files; separate saved-entry comparison | Related-species coverage display | Keep Selenium checks of related-species flags/counts. Add core checks only for remaining sample/role/taxon values, counts and record/file requirements. Every required result needs an owner, but must not receive a duplicate core expectation. |
| `5.3.flag` — in-country coverage result (F) | Core counts files; separate saved-entry comparison | Country coverage display where expectations exist | Keep existing Selenium country-coverage checks. Core checks only uncovered flag entries/values and country-specific counts or states. Distinguish not assessed from assessed with zero results. Remove duplicate flag/core expectations. |
| `map*.png` — geographical coverage images (M) | 18 sample groups containing 34 files | Country message, not every raw map | List the expected maps for each sample/target and check that the required ones exist and are readable PNGs. Checking only the total could miss one sample's missing map if another has an extra map. |
| HTML reports — one per sample | Core checks a total of 20 | Browser content and interactions covered by existing tests | Keep Selenium’s existing per-sample missing-report checks. Core checks only additional workflow requirements, such as duplicate or wrongly associated channel outputs, that Selenium does not already check. Do not add a second expected report-presence result for the same sample. |
| `software_versions.yml` — tool versions | One channel entry | No dedicated check of the complete file | Check there is exactly one readable versions file and it lists the required tools that ran. Do not require every future run to have identical file contents. |
| Parameters JSON — settings used by the run | One channel entry | No dedicated check of the complete file | Check there is exactly one readable settings file with the required run information. Do not expect temporary directory paths to remain constant or copy secrets into the review report. |
| Workflow timestamp — run date/time | One channel entry | No dedicated check of the raw timestamp | Check there is exactly one valid timestamp in the form the workflow actually emits. Do not compare it with the date of the old run. |
| Workflow completion and sample routing | Snapshot sample/file pairs and total counts; no explicit success assertion | Missing report detected for each expected sample | Check that the workflow succeeded, each file belongs to the right sample, and samples were not lost or duplicated when outputs were combined. Check which samples should receive source-diversity assessment and which should be skipped. |
| Intermediate files not exposed to core | No direct snapshot check for BLAST XML, accession/taxonomy files, alignment/PHYLIP files, label mappings, FastME statistics/matrices, logs or optional error files | Some of their later results appear in reports | Clearly record that these files are not directly checked by the current channels. Use logs and trace information to investigate failures. This task does not automatically add new workflow channels to check every intermediate file. |
| HTML failure review, ingest and promote | Snapshot error summary, separate flag differences, Selenium review page | Existing Selenium tools stay unchanged | Core review shows the file, sample, taxon, field, expected value and actual value. `ingest` lets you review and save initial expectations; `promote` lets you review selected changes to existing expectations. Keep backups. Remove the separate core flag-checking step after confirming every required result is checked by unchanged Selenium or core, without duplicate checks. |

For precise implementation of D counts, the current JSON stores the target count
at `coverage.<role>.<taxon>.target`, with per-species counts under `related` and
`country` when assessed. Here `<role>` is `candidate`, `toi` or `pmi`, and `<taxon>`
is the taxon name. Check these values and their meaning, not just the presence of
these field names. There are two different “record counts” to check: how many
entries a flag file contains, and how many reference database records support a
taxon. Both must be checked across Selenium and core, with Selenium retaining any checks it already performs.

The inventory was checked against `workflows/taxodactyl.nf`, the producing modules,
`conf/filenames.config` and the core snapshot on 2026-11-23. Intermediate filenames
outside the channels include `blast_result.xml`, `accessions.txt`, `taxids.csv`,
`taxonomy.csv` and `candidates_phylogeny.msa`. They are listed to make the limit of
this task clear, not to claim they already have direct tests.

**If Selenium already checks a result, keep that check in Selenium and remove
the overlapping check from flags/core nf-test.** This applies to every artifact,
including 5.1/5.2/5.3 flag values and reference counts. Core checks only remaining
results and distinct file/workflow requirements. Selenium stays unchanged.
Map ownership per sample, taxon, role and field to an actual populated Selenium
assertion; a field merely appearing in the report is not proof it is tested.
Respect Selenium's existing comparison method and tolerance for fields it owns;
do not introduce a stricter duplicate in core. Both count values and flag values
must be tested across the combined suites, without testing the same result twice.
Historical flag files and scripts may remain for other scenarios and reference.
The copied hit files in C need checks that the copy is unchanged, not a second
independent set of expected hit results.

Before removing snapshots, give each table row concrete checks and record any
sample-specific exceptions in `test/core/README.md`. If a file is deliberately
left without a check, explain why and obtain user review. A saved fingerprint
currently catches any content change; replacing it only with “file exists” or
“contains numbers” would lose important protection.

## Implementation

### Phase 1 — Establish coverage ownership and evidence

1. In `test/core/README.md`, map each current snapshot channel and count check to
   the contract it protects and its owner (nf-test, Python, or Selenium). Audit
   `test/selenium/lib/` and `test/selenium/expected/*.yaml` field coverage before
   deleting any snapshot protection. Map P3/P4 flag hashes explicitly: they must
   not disappear without an identified semantic check or a recorded gap resolved
   within the migration.
2. Preserve the existing core scenario and its input/reference setup. Prefer
   existing emitted channels from `workflows/taxodactyl.nf`; do not add production
   outputs just for a convenient test. Emitting a channel, publishing a file, and
   feeding a scientific process are different actions.
3. Establish a stable sample-key mapping from `test/core/metadata.csv` through
   query identifiers and channel tuple keys. Validate multiplicity as well as
   sets, so duplicate rows cannot conceal missing samples. Never rely on channel
   arrival order or zip separately sorted channels without checking their keys.

### Phase 2 — Replace the core snapshot with contracts

Modify `test/core/taxodactyl.workflow.nf.test` using ordinary Groovy power assertions
inside `assertAll`, with independent closures for independent checks. Retain one
workflow execution; do not create twenty full workflow test cases for reporting.

- Assert workflow success, complete sample membership, uniqueness, and compatible
  sample keys across hits, candidates, source-diversity, trees, coverage and HTML
  outputs according to their documented conditional behavior.
- Validate tuple shape, required files and readable structured content where it
  establishes a producer/consumer contract. Check schema essentials and references
  between files, rather than whole-file hashes. Match emitted paths directly;
  do not search arbitrary old work directories for a plausible file.
- Retain singleton version/parameter/timestamp checks without pinning timestamps,
  absolute paths or full parameter contents. Leave per-sample report presence
  to existing Selenium checks; core checks additional routing/duplicate-output
  behavior only where it is not already covered. Do not parse HTML scientific values.
- Review current hard-coded counts (20 reports/coverage groups, 18 map groups,
  34 maps, 60 flag files) against contracts and supplied evidence. Preserve
  meaningful coverage; replace brittle aggregate counts with per-sample required
  membership where appropriate. Do not merely remove a failing count.
- Explicitly distinguish valid empty phylogeny/candidate or skipped-source cases
  from missing outputs and evaluation errors. Derive exceptions from reviewed
  behavior and inputs, not “whatever the latest run contained”.
- Keep existing Selenium assertions, fixtures, tolerances and toolkit behavior
  unchanged. For every overlapping check, retain Selenium's assertion and remove
  the flags/core equivalent. This includes P5 counts and flag values. Record the
  owning Selenium fixture/field or core assertion in the coverage map.
  Precise Python algorithm counts/IDs/sequences remain in scoped Python tests.
  Raw-file structure, routing and consistency are nf-test responsibilities.
- Give each assertion a stable ID and include sample key, channel/field, expected
  rule, actual value and relevant file path in failures. Independent failures must
  remain visible together; missing prerequisites must produce explicit errors,
  not a cascade of misleading null failures or a silently skipped check.
- Delete `test/core/taxodactyl.workflow.nf.test.snap` only after its coverage map
  and replacement assertions have been reviewed. Leave scenario_01–04 snapshots
  unchanged. Replace the separate `test/core/flags/` comparison gate only after
  every required P5 check has an owner in unchanged Selenium or core, with no
  overlapping flags/core check left running.
- For every sample and target role (`candidate`, `toi`, `pmi`), read all three
  flag files and `db_coverage.json` from F/D channel paths. Determine which record
  counts, target keys, flag values and target/related/country reference counts
  Selenium already asserts. Add core assertions only for remaining checks and
  distinct file requirements. Numeric results assigned to core need reviewed
  value expectations, not just file counts or value types. Cover zero, missing, null, `NA`, legitimate
  not-assessed results and error results distinctly. Do not use the production
  flag calculation as the expected-value oracle.
- Move only reviewed P5 expected data owned by core into `test/core/expectations.json` with stable
  sample/role/taxon/flag/field keys. Inspect historical `test/core/flags/*.flag`
  as evidence, not automatically accepted truth; derive reference-count values
  from the user's reviewed run. Manual core promotion supports selected numeric
  counts and flag values, with membership changes shown explicitly for review.
  Ingest/promote must exclude Selenium-owned expectations; do not create a second
  baseline for them. Core review can identify their owning Selenium checks without
  reevaluating their expected values.

Store reviewed, promotable sample-specific expected values in
`test/core/expectations.json`, keyed by stable sample ID and assertion ID, with
provenance and reasons. Keep invariant rules (success, uniqueness, required files,
schema and relationships) in assertion code. Promotion changes selected data
values only; it must not rewrite assertion logic or create a whole-output baseline.

### Phase 3 — Core testkit: render, ingest and promote

1. Enable native `--junitxml` output. First inspect an intentionally failing check
   under version 0.9.5: determine whether each assertAll closure's diagnostics reach
   XML or only the console. JUnit is test-case-level, not necessarily one row per
   assertion, and does not promise structured expected/actual fields.
2. Add `test/core/testkit.py` with a proposed CLI:
   `render --junit <run>/nf-test.xml --output <run>/nf-test-review.html`.
   It must work on retained results without Nextflow, browsers or live APIs. Use
   Python standard-library XML parsing and escaped HTML for the MVP. Reuse the
   visual conventions of `test/selenium/lib/templates/review.html.j2` and
   `test/selenium/lib/static/review.css` where inexpensive; do not refactor the
   Selenium collector/promoter into a universal framework.
3. Show run identity, status, assertion diagnostics, expected/observed evidence,
   missing/extra sample keys, source test path, and available artifact/log links.
   Native power-assert text is acceptable evidence for the MVP if it retains every
   failure. Do not scrape console text to reconstruct a general diff language.
4. Emit a small JSON sidecar alongside the checks in the existing core test to
   support reliable manual ingest and promotion; do not recover values by parsing assertion
   text. Keep JUnit for native test status and diagnostics.
   Use rows containing assertion ID, sample ID, channel/field, expected rule/value,
   observed value, status, promotable marker and artifact paths; generate rows from the same check,
   not a second evaluator in Python. Flush evidence even when assertions fail.
   Include run provenance and the expectation-file digest used for evaluation
   (explicitly absent when no expectations exist). Collect actual values even
   when expectations are missing: mark those checks unbaselined, not passed,
   and retain a failing ordinary test status. Missing expectations must not
   prevent evidence collection needed for first-time ingest. Invariants still run.
   Extend render with `--assertions <run>/nf-test-assertions.json` and retain the
   sidecar in CI artifacts on failure as well as success.
5. Handle success, assertion failure, execution error, missing XML and partial
   runs distinctly. Missing/invalid evidence must never render as a pass. Escape
   all diagnostic content, use portable relative artifact links, and distinguish
   unavailable links. Do not embed raw params/environment or credentials.
6. Implement manual promotion in `test/core/testkit.py`, following the interaction
   pattern in `test/selenium/lib/promote.py`. Proposed CLI:
   `promote <sample-id> --assertions <run>/nf-test-assertions.json`, with optional
   `--assertion <assertion-id>` to narrow the selection and `--dry-run` to preview.
   Show each changed promotable value (old/new), sample, assertion, source run and
   provenance; let the operator accept or reject individual differences before
   writing. Show a copyable scoped command in `nf-test-review.html`.
7. Update only accepted entries in `test/core/expectations.json`, preserving all
   unrelated entries. Back up the previous file in `test/core/.backups/`, retaining
   the last three backups, and write atomically. Record source-run provenance and
   a supplied reason for accepted changes. Reject stale evidence if the expectation
   digest no longer matches, and reject missing, malformed or incomplete observed
   values. A completed run with assertion drift can be promoted; an execution
   failure or incomplete evaluation cannot supply accepted expectations.
8. Implement manual initial ingestion in `test/core/testkit.py`. Proposed CLI:
   `ingest --assertions <run>/nf-test-assertions.json`, optionally scoped with
   `--sample <sample-id>` and `--assertion <assertion-id>`, plus `--dry-run`.
   Preview candidate expectations, artifact/field keys, observed values and run
   provenance, then let the operator select and accept entries before writing.
   Create `test/core/expectations.json` if absent or add selected missing entries;
   refuse to overwrite existing keys and direct the operator to `promote`.
   Reject ambiguous sample/target IDs, duplicate keys, malformed/incomplete
   observations and execution failures. A complete run lacking expectations is
   eligible for ingestion even though its unbaselined checks did not pass.
9. Share evidence validation, selection, atomic writes, provenance/reason capture
   and backup handling between ingest and promote. Ingest backs up an existing
   expectation file before adding entries; first creation needs no backup. Only
   defined data expectations can be ingested, never arbitrary output contents,
   assertion code or failed invariants. Document how the supplied successful run
   obtains structured evidence; older runs without the sidecar need a new core
   evaluation producing it, not fabricated evidence or a second Python evaluator.
   Add copyable scoped ingest commands to HTML for unbaselined entries.
10. Keep `render`, ordinary test execution and CI read-only with respect to
   expectations. Only explicitly invoked manual `ingest` or `promote` writes accepted
   changes. Invariant failures remain visible and cannot be promoted away. Do not
   modify Groovy assertions, historical `test/core/flags/*.flag` files or Selenium fixtures through this
   commands. Initial creation is explicitly reviewed through ingest, not inferred
   automatically from a successful run. After ingest or promotion, rerun the affected checks;
   preserve the original run's failure record rather than relabeling it as passed.

### Phase 4 — Integrate CI and investigation

- In `.github/workflows/nf-test.yml`, write XML under `$RUNNER_TEMP/nf-test/`,
  render `nf-test-review.html` under `if: always()`, and upload/retain it beside
  existing logs and Selenium `review.html`. Preserve the nf-test failure status
  even if rendering succeeds. Rendering failure must also be visible.
- Replace core's snapshot-error CSV path through
  `bin/diff_json_snapshot_to_csv.py` with assertion evidence. Inspect and adapt
  `bin/collect_artifacts.py` where it consumes that CSV; route core P5 failures
  from structured assertion evidence into artifact collection alongside other
  failures. After verifying the combined coverage map, remove the separate core invocation of
  `bin/collect_flags.sh` / `bin/test_flags.py` as a CI gate. Preserve helpers and
  legacy input handling used by other scenarios; do not refactor Selenium steps.
- Review `.github/workflows/mock-nf-test.yml`: its frozen artifact predates the
  new XML and may only support legacy post-processing. Explicitly report missing
  new evidence; do not claim it validates assertions or manufacture passing XML.
- Keep self-hosted retention under `/var/runner/<timestamp>/` and existing
  Selenium artifacts working. Provide a copyable targeted rerun command using
  supported nf-test selection and current config. Verify any cache/reexecution
  option against 0.9.5 before documenting it; do not promise assertion-only replay.

Dependencies: Phase 1 -> Phase 2; reporting format probe -> Phase 3;
Phases 2 and 3 -> Phase 4. After agreeing the diagnostic format, assertion
migration and renderer work can proceed independently. No delegation is required.
MVP: core-only contract migration, native XML plus structured assertion evidence,
HTML review, manual selective ingest and promotion with backups, and CI artifact integration.
Other-scenario migrations are not required.

## Documentation and configuration

Update `docs/nf-tests.md`, `test/core/README.md`, and relevant sections of
`spec/tests.md` before/with implementation to describe the agreed contract,
coverage ownership, core configuration, rendering, retained evidence, and the
initial run -> ingest -> rerun and later drift -> promote -> rerun workflows.
Preserve instructions needed for other scenarios. `nf-test.config`
currently selects scenario_04 with a placeholder workDir; commands must explicitly
use a core-configured invocation, following the CI setup, rather than assuming
that passing the core test filename changes its configFile automatically.

## Testing decision

**Agreed 2026-11-23, scope: task 12.** The user selected the mixed approach:
agent writes the agreed assertions and report-tool tests and runs checks after
implementation authorization; the user reviews drift and approves expectation
changes. Agent may apply only those expectation changes the user approves.
No blanket authorization to replace snapshots, flag baselines or Selenium YAML.

Affected suites: core nf-test (including migrated P5 checks), focused tests of its
render/ingest/promotion toolkit, legacy flag comparison as migration evidence, and
unchanged Selenium as a regression/review surface. Python scientific
integration assertions are not rewritten. User manual review remains required
for replacement core coverage, snapshot retirement, and any observed flag or
Selenium differences. Implementation authorization remains separately pending.

**Clarification 2026-11-23:** The user explicitly requires manual core promotion.
The agent implements and tests this tooling under the existing mixed allocation
once implementation is authorized; the user runs promotion to review and accept
expectation changes. This request authorizes the planning revision, not execution
of promotion or implementation. No automatic acceptance is authorized.

**Toolkit clarification 2026-11-23:** Both manual `ingest` and `promote` are
required. Ingest creates missing reviewed expectations; promote updates existing
ones. The existing toolkit testing allocation applies: agent writes/runs focused
tooling tests after authorization, user reviews and accepts real expectations.
The expanded P5 testing allocation is confirmed below.

**Scope correction 2026-11-23:** The user requires artifact/function-level
coverage of every channel file, raw 5.x record counts and flag values inside core
or existing Selenium, and no Selenium changes. Core owns only migrated checks
not already covered by Selenium.
**Testing ownership confirmed 2026-11-23:** The user explicitly selected the same
mixed approach for the expanded P5 migration (flag records/values and coverage
counts): agent writes the assertions and runs checks after implementation is
authorized; user reviews drift and manually promotes expectations. This extends
the existing testing allocation to the expanded scope. No automatic expectation
acceptance is authorized, and Selenium remains unchanged.
Exact numeric expectations await supplied evidence; tolerances are not authorized
by this correction. Implementation authorization remains pending.

**Ownership correction 2026-11-23:** For any overlap, keep the existing Selenium
check and remove the flags/core equivalent. This supersedes the earlier proposal
to retain P5 overlap. The agreed mixed testing allocation remains unchanged;
Selenium code, fixtures and tolerances remain unchanged. This narrows duplicated
checks, not the requirement to test counts and flag values across the suites.

## Validation

After authorization, configure core references according to `test/core/README.md`
(current documented subset BLAST 2026-07-29 and taxdump 2026-05-08; record actual
versions supplied by the user). Activate `source scripts/venv/bin/activate` before
any Python execution. Use `.vscode/launch.json` for unit/integration environment
settings; no integration run is implied by planning.

- Run `nf-test test test/core/taxodactyl.workflow.nf.test --ci --junitxml <run>/nf-test.xml`
  with the core config and retained work directory. Record exit code, revision,
  input checksums, references, container versions and evidence paths.
- Run `python test/core/testkit.py render --junit <run>/nf-test.xml --output <run>/nf-test-review.html`.
  This is the proposed command to implement, not an available command today.
- Add focused renderer tests at `scripts/tests/test_nf_test_review.py` for multi-
  failure diagnostics, success, execution errors, missing/malformed XML, escaping
  and portable links. Use small synthetic diagnostic inputs, not a live workflow.
  Run with `PYTHONPATH=scripts python -m unittest discover -s scripts/tests -p test_nf_test_review.py`.
- Add focused promotion tests at `scripts/tests/test_nf_test_promote.py` using
  temporary expectation files and synthetic run evidence. Verify selective
  acceptance/rejection, dry-run/no-change behavior, stale-evidence rejection,
  malformed/incomplete evidence, invariant failures being non-promotable,
  preservation of unrelated entries, atomic updates and three-backup retention.
  Run with `PYTHONPATH=scripts python -m unittest discover -s scripts/tests -p test_nf_test_promote.py`.
  Manually demonstrate review -> scoped promote -> rerun on disposable evidence;
  the user separately approves changes to real expectations.
- Add focused ingest tests at `scripts/tests/test_nf_test_ingest.py` for first
  creation, selected missing-entry additions, refusing existing-key overwrites,
  dry-run/rejection without writes, unbaselined-but-complete evidence, invalid or
  incomplete observations, duplicate IDs, provenance and existing-file backups.
  Run with `PYTHONPATH=scripts python -m unittest discover -s scripts/tests -p test_nf_test_ingest.py`.
  Demonstrate a disposable initial run without expectations -> review -> ingest
  -> rerun, followed by changed observations -> promote -> rerun. Neither command
  may turn failed invariant checks into passing expectations.
- Demonstrate negative cases using disposable test copies/evidence: a missing
  sample, a duplicate that preserves total count, wrong sample association,
  malformed output, and multiple independent failures. Verify the intended check
  fails and HTML contains actionable evidence. Do not mutate approved baselines.
- Verify a legitimate empty/skipped case passes and a missing output fails.
  Compare the agreed coverage matrix against every retired snapshot field.
- Include targeted negative cases changing a 5.x value without changing its
  record count, a duplicate replacing a target, a missing/extra flag record,
  and a reference count in D without changing its flag. Choose core-owned fields
  for core negative cases and require failure with clear evidence in core HTML.
  For Selenium-owned results, verify the existing assertion covers the intended
  failure using its existing comparison/tolerance; do not add a duplicate core
  check merely because it would fail on a smaller change.
  Confirm a reviewed count-only drift can be selectively promoted without
  changing flag values or accepting an unrelated failure.
- During migration, use the legacy flag comparison on the same retained run as
  evidence for the coverage map before removing its core CI gate. Assign required
  record keys, flag values, counts, missing-file and invalid-JSON checks to core
  or existing Selenium. Record deliberate removal of stricter duplicate baseline
  checks where Selenium owns the result, including its existing tolerance.
- Run unchanged Selenium using the commands in
  `.github/workflows/nf-test.yml` against the same run. Record their exit statuses
  and review artifacts separately from nf-test results; report live-data drift.
- Test reporting after failure and offline rerender from retained artifacts.
  Confirm failure exit status survives report generation and links work after
  copying the artifact bundle. No passing page for an unexecuted suite.
- Run required checks relevant to changed files. If any `.nf` file unexpectedly
  needs modification, apply the repository's `nexflow lint <file>` instruction
  and report tool availability. Do not change production code merely to pass.

Expected values must come from agreed contracts and independently understood
inputs, never production logic or blind copies of actual output. Preserve
meaningful content, membership, boundaries, ordering where meaningful, and error
coverage. Do not skip failures or broaden tolerances to pass. Classify failures as
implementation, test, or environment/data issues; record failures and unavailable
checks honestly. Automated passes do not complete manual acceptance.

## Test impact and manual review

- `test/core/taxodactyl.workflow.nf.test` and
  `test/core/taxodactyl.workflow.nf.test.snap`: intentional assertion migration
  and reviewed snapshot retirement; new exact values await supplied evidence.
- `test/core/expectations.json`: small reviewed contract data, updated only by
  explicit manual ingest or selective promotion; not a captured whole-output snapshot.
  `test/core/.backups/` holds local prior versions and must be excluded from commits.
- `test/core/flags/*.flag`: historical expected-value evidence, not automatically
  promoted or rewritten. Selenium retains existing checks; core expectations cover the remaining P5 results;
  retire the separate core execution gate after combined coverage is verified.
  Differences and new coverage-count expectations require manual user review.
- `test/selenium/expected/*.yaml`, `test/selenium/expected/reports/`, and
  `test/selenium/expected/test/`: no planned updates. Existing Selenium owns its
  presentation/scientific-value checks. Possible live-data drift is reviewed by
  the user with `test/selenium/test-report.json` and `review.html`.
- `test/scenario_01/taxodactyl.workflow.nf.test.snap` through scenario_04: unchanged.
- Handoff: supply `<run>/nf-test.xml`, `<run>/nf-test-review.html`, assertion sidecar,
  logs/trace, provenance, coverage map, and Selenium/flag differences. User checks
  intentional coverage changes separately from reference drift and regressions.
  Manual validation status is pending until the user provides acceptance evidence.

## Completion criteria

- No whole-channel snapshot remains in core; every retired protection has a
  documented owner and meaningful replacement or explicitly agreed disposition.
- Every inventoried artifact and required P5 flag/count result has a documented
  test owner. Existing Selenium checks take precedence; no overlapping flags/core
  expectation remains. Core covers missing checks and distinct workflow/file
  requirements, with no changes to Selenium assertions or expectations.
- One core execution exposes all independent failures with stable sample/check IDs.
- Testkit renders useful differences from retained evidence without rerunning the
  workflow, and partial/missing runs cannot look successful.
- Manual `ingest` creates selected missing expectations from reviewed complete
  observations and never overwrites existing keys. Unbaselined evaluation emits
  usable evidence without falsely passing or bypassing invariant checks.
- Manual `promote` previews and selectively accepts expectation changes with
  provenance and backups. It cannot weaken invariant assertions, accept incomplete
  evidence, update unrelated suites or silently change expectations during CI.
- CI retains XML/HTML and investigation evidence on both success and failure,
  preserves failure status, incorporates P5 differences into core review, and
  leaves existing Selenium execution and review functioning unchanged.
- No separate core flag-comparison gate remains after the combined coverage map
  is verified. Required 5.1/5.2/5.3 records, values and associated D counts are
  checked by unchanged Selenium or core, not both. Only core-owned expectations
  are ingested/promoted by core testkit.
- Automated validation results and user manual acceptance are recorded separately;
  all required user review is complete before marking the task complete.
- Documentation describes exact commands, paths, provenance and approved updates.

## Open decisions and risks

- Successful run location and evidence are pending from the user. Sample-specific
  assertions cannot be finalized until inspected and reviewed.
- JUnit fidelity under pinned nf-test 0.9.5 determines how much native diagnostic
  detail the renderer can reuse. Structured sidecar values are required for
  promotion; keep their format small rather than building a general framework.
- Some scientific behavior is currently covered only by snapshot hashes. The
  coverage audit must resolve these before removal; avoiding duplicate Selenium
  assertions must not silently reduce bug detection.
- This brief proposes a dedicated `test/core/testkit.py` because the existing
  Selenium toolkit is browser/fixture specific and the integration toolkit manages
  Python fixtures. Reuse small presentation pieces only where it reduces work.
