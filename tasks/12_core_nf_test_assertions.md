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

**Revision 2026-11-23 (per-sample expectations and readable review):** store
core expectations as one YAML file per sample, like `test/selenium/expected/`,
so a sample is added by a metadata row plus `ingest`, without Groovy edits;
redesign the HTML review so problems are visible first; drop per-species
`related`/`country` coverage *counts* from core (keep species-name membership);
store hit sequences as accession plus short fingerprint. See Phase 5, which
supersedes the conflicting parts of Phases 2–3.

**Revision 2026-11-23 (report clarity and CI, Phase 6):** the review page omits
checks owned by Selenium; adds a plain-language "What this test checks" section;
explains every failure in plain words (expected, found, likely cause, next
step), with raw Groovy expressions only as collapsible technical detail. It
also updates `.github/workflows/nf-test.yml` so core can be run and reviewed
from GitHub Actions. The three failures in the baseline evaluation are explained
in Phase 6.1. Phase 6 supersedes conflicting parts of Phase 5.5.

**Revision 2026-11-23 (parallel old and new pipelines, Phase 7):** keep the
original snapshot test and CI workflow running unchanged, and run the new
assertion test under its own file and workflow, so both can be compared for a
while. Phase 7 supersedes the retirement in decision 6.6.2.

**Revision 2026-11-23 (page trim and Selenium overlap, Phase 8):** move "What
this test checks" to the end as a plain reference list without per-run counts.
State plainly which flags Selenium checks. Drop core rule checks that only
confirm a value Selenium already checks exists and is valid. Remove
known-defect labels from the page.

**Revision 2026-11-25 (Phase 10):** stop comparing related-species names in
`db_coverage.json` for every role (candidate, toi, pmi). Make it clear on the
review page and CI summary that "rule failed" vs "possible drift" is only a
suggestion based on the kind of check. Phase 10 supersedes the related-species
membership in 5.2 and the badge wording in 5.5.

**Revision 2026-11-26 (Phase 12):** delete from core every stored value the
HTML report shows; leave them to Selenium for every sample, but do not add
Selenium checks yet. Keep all rule checks. Core keeps only hit sequence
fingerprints and map filenames as stored values. Delete Selenium ownership
(`coverage-ownership.tsv`, ownership code). Phase 12 supersedes the ownership
rules of Phases 1, 5.2, 6.2 and 8 and the related completion criteria.

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

**Revision overview (2026-11-23).** The first implementation works, but the
review page is hard to use: it is 17 MB, shows all ~21,600 checks, hides the
three real failures inside collapsed sample sections, labels checks with
channel codes (`C.copy.all_hits.fasta`, `D.count/...`) and prints
"Expected: contract invariant / Observed: satisfied" for rule checks. All
expected values also live in one 106k-line `test/core/expectations.json`. The
fix: (1) one readable YAML file per sample, matched by `sample_id`, created by
`ingest` and updated by `promote`, exactly like Selenium fixtures; (2) a review
page that opens with "what needs attention", then a sample × channel matrix,
then per-sample cards with Selenium-style expected/observed tables; (3) fewer,
meaningful data checks — related/in-country species lists are compared by
name only, and hit sequences by fingerprint. Open: confirm fingerprint length
and Selenium-aligned file numbering (see Open decisions).

**Phase 6 overview (2026-11-23).** The user reviewed the new page. Three problems
remain. It still lists 208 values that Selenium owns, which belong in the Selenium
review instead. It never says, in plain words, what was checked. And its failure
messages are raw Groovy expressions such as
`Expression: ((table[0] == [rank, taxon]) && (table[1].size() == 1))`, which do
not say what is wrong or what to do. The fix: drop Selenium-owned values from the
page, add a "What this test checks" section written from `test/core/schema.yaml`,
and give every check a plain explanation. CI also gets the changes needed to run
core from GitHub and read the result there. The baseline evaluation's three
failures are real findings, not test faults (6.1). Open: how to handle the known
CSV bug (P3-D-008), and whether to retire the legacy flag gate and snapshot now.

**Implementation authorization: granted by explicit user request, 2026-11-23**
for the original scope. **Phase 6 implementation authorization: granted by explicit
user request ("Feel free to implement"), 2026-11-23.**
**Revision (Phase 5) implementation authorization:
granted by explicit user request ("implement all the changes you made to the task including phase 5"), 2026-11-23.**

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
Revision sources (2026-11-23): user review of the rendered page
`.nf-test/task12-review/nf-test-review.html` / `accepted-review.html` and
`accepted-assertions.json` in the task worktree; Selenium reference layout
`test/selenium/README.md`, `test/selenium/testkit.py`, `test/selenium/lib/schema.py`,
`test/selenium/lib/promote.py`, `test/selenium/lib/render.py`,
`test/selenium/lib/templates/review.html.j2`, `test/selenium/lib/static/review.css`,
`test/selenium/lib/database_coverage.py` and `test/selenium/expected/*.yaml`
(paths relative to the `nf-test-sh-runner` checkout).

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
Each sample's expectations live in their own file; adding a sample needs a
`test/core/metadata.csv` row, a run and a reviewed `ingest`, and no code edit.
A reviewer can see from the top of the HTML page which samples and checks need
attention and why, without expanding anything.

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
| `all_hits.fasta` — hit sequences (H and C) | Saved file fingerprints | Some alignment details in the BLAST popup | Read the sequence records. Check their names and sequence contents, whether an empty file is valid for this sample, and that the records correspond to the hit JSON. Check that copying the file into the candidate directory did not change it. **Revision:** per-sample expectations store the accession list and one short sequence fingerprint per accession, not full sequences (Phase 5). |
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
| `db_coverage.json` — reference database counts (D) | Only the number of files: 20 | Displayed counts/charts; some count fields allow ±10% | For each sample, taxon and role, identify which count values Selenium already checks and leave those checks there. Core checks only remaining target, related-species and in-country counts against reviewed values, plus distinct file/format requirements. Distinguish zero, unavailable and not-assessed results. Do not duplicate Selenium-owned counts or override their existing tolerance. **Revision (user decision 2026-11-23):** core does not store or compare per-species `related`/`country` counts — the original core nf-test only counted these files. Core checks that the related and in-country *species names* match the accepted lists, plus structure and assessed/null/`NA`/not-assessed state. |
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
| HTML failure review, ingest and promote | Snapshot error summary, separate flag differences, Selenium review page | Existing Selenium tools stay unchanged | Core review shows the file, sample, taxon, field, expected value and actual value, with problems listed first (Phase 5.5). `ingest` lets you review and save initial expectations; `promote` lets you review selected changes to existing expectations. Keep backups. Remove the separate core flag-checking step after confirming every required result is checked by unchanged Selenium or core, without duplicate checks. |

For precise implementation of D counts, the current JSON stores the target count
at `coverage.<role>.<taxon>.target`, with per-species counts under `related` and
`country` when assessed. Here `<role>` is `candidate`, `toi` or `pmi`, and `<taxon>`
is the taxon name. Check these values and their meaning, not just the presence of
these field names. There are two different “record counts” to check: how many
entries a flag file contains, and how many reference database records support a
taxon. Both must be checked across Selenium and core, with Selenium retaining any checks it already performs.
**Revision 2026-11-23:** no `db_coverage.json` count is a core expectation —
not `target`, nor the per-species values under `related` and `country`. Core
compares only which taxa and species are listed (membership) and the state of
each section; database record counts are owned by Selenium alone. Selenium keeps its summary
coverage checks (record count, species count/total, first/minimum bar, country
text) with its ±10% tolerance. Record this deliberate removal in
`test/core/README.md` and `test/core/coverage-ownership.tsv`.

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
**Superseded by Phase 5.1:** the store is `test/core/expected/<N>_<sample_id>.yaml`,
one file per sample; `test/core/expectations.json` is migrated and removed.

### Phase 3 — Core testkit: render, ingest and promote

Phase 5 supersedes the page layout in items 2–3, the CLI shapes in items 6 and
8, and the single-file digest/backup paths in items 4 and 7. All safety rules
in this phase still apply unchanged.

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
- Keep self-hosted retention under `/var/runner/<timestamp>/` (renamed to
  `/var/runner/assertions-<run_number>-<run_attempt>/` on 2026-11-25, Phase 11, then
  `/var/runner/assertions-<run_id>-<run_attempt>/` on 2026-11-27, Phase 13) and existing
  Selenium artifacts working. Provide a copyable targeted rerun command using
  supported nf-test selection and current config. Verify any cache/reexecution
  option against 0.9.5 before documenting it; do not promise assertion-only replay.

### Phase 5 — Revision 2026-11-23: per-sample expectations and readable review

Work in the existing task worktree
`/mnt/data/tests-wf-2/taxodactyl/nf-test-sh-runner/.worktrees/task-12-core-nf-test-assertions`
on branch `task-12-core-nf-test-assertions`. Reference implementation for the
interaction pattern: `test/selenium/` in the same checkout. Do not modify it.

#### 5.1 Per-sample expectation files

- Store core expectations in `test/core/expected/<N>_<sample_id>.yaml`, one file
  per sample in `test/core/metadata.csv`. The file's `sample_id:` key links it to
  the sample; the filename prefix and stem are for humans only (as in Selenium,
  where reports are matched by `sample_id`, not filename).
- Numbering: when a Selenium fixture `test/selenium/expected/<N>_<sample_id>.yaml`
  exists for the same `sample_id`, reuse its `<N>` so both suites share numbers;
  otherwise use the next unused prefix across both directories. (Confirmed by
  the user, 2026-11-23.)
- Layout mirrors Selenium fixtures (`components:` → `assertions:` with `id`,
  `type`, `value`; grouped components keyed by role, then `name`). Proposed:

  ```yaml
  sample_id: Scenario_01
  date: '2026-11-23T06:31:55Z'        # evaluated_at of the run last ingested/promoted
  provenance:
    source_run: /mnt/data/tests-wf-2/tests/2026-11-23_052042/tests/a6b58f1ab761dd04d3bfb3044ca4834
    reason: User-validated baseline, 2026-11-23
  components:
  - id: blast_hits                    # H: all_hits.json / all_hits.fasta
    assertions:
    - id: accessions
      type: membership
      value: [LC508677, LC510118, ...]
    - id: sequence_fingerprints
      type: fingerprints
      value: {LC508677: 3f2a9c1e0b7d4a51, ...}
  - id: candidates                    # C: flags 1/2/7 only where Selenium does not own them
    assertions: [...]
  - id: phylogeny                     # C/T: selected sequence names
  - id: source_diversity              # S
  - id: database_coverage             # D: state + species-name membership only
    candidate:
    - name: Spodoptera frugiperda
      assertions:
      - {id: target_state, type: state, value: assessed}
      - {id: related_species, type: membership, value: [Prodenia laysanensis, ...]}
      - {id: country_species, type: membership, value: [Spodoptera mauritia, ...]}
  - id: coverage_flags                # F: 5.1/5.2/5.3 values not owned by Selenium
  ```

- Declare components, their channel letter, plain-language title, rule text and
  assertion types once in `test/core/schema.yaml` (the equivalent of
  `test/selenium/lib/schema.py`). `CoreAssertions.groovy` uses it to map each
  data row to its YAML path; `testkit.py` uses it to write YAML and label the
  review page. Python must not re-evaluate outputs.
- `CoreAssertions.groovy` loads every `test/core/expected/*.yaml` with the YAML
  parsing it already uses for Selenium fixtures. Fail with an explicit `_run`
  error, naming the file, for: two files with the same `sample_id`, a file whose
  `sample_id` is not in `metadata.csv` (orphan), an unknown component/assertion
  ID, or a malformed value. A sample with no file is reported as
  **needs baseline** (`unbaselined`), not passed, and its invariant checks still run.
- No sample ID may appear in Groovy code. Any sample-specific expectation
  (e.g. an expected-empty phylogeny or skipped source-diversity assessment) is
  data in that sample's YAML. Move any that is currently derived elsewhere.
- Delegated (Selenium-owned) fields are never written to core YAML. Ownership
  continues to be derived from `test/selenium/expected/*.yaml` as today.

#### 5.2 Data checks changed by user decision (2026-11-23)

- **Coverage counts:** remove `D.count/<role>/<taxon>/related/<species>` and
  `D.count/<role>/<taxon>/country/<species>` (12,427 rows in the accepted run,
  4,958 distinct values). Keep `D.membership/<role>/<taxon>/related|country`
  (the species names must match; **superseded 2026-11-25, Phase 10:** related
  names are no longer compared for any role, only `country`), `D.membership/<role>`, `D.state/...`, the
  (the species names must match), `D.membership/<role>`, `D.state/...`, the
  integer/null/`NA` structure invariants. Also remove core
  `D.count/<role>/<taxon>/target` (user decision 2026-11-23): the taxon's own
  record count is never a core expectation, even where Selenium leaves
  `database_coverage.record_count` empty or the sample has no Selenium fixture;
  the review page lists such uncovered target counts under "Owned by Selenium /
  not checked" and `test/core/README.md` states the gap. Reason: the original core nf-test counted coverage files but
  did not test these counts, and they are live GenBank/BOLD record counts.
- **Hit sequences:** replace the 8,190 `H.sequence/<accession>` full-sequence
  expectations with one `sequence_fingerprints` map per sample: the first 16 hex
  characters (length confirmed by the user, 2026-11-23) of SHA-256 of the exact FASTA sequence string (uppercase as
  emitted, gaps kept, no header or line breaks). Keep `H.membership` (accession
  list) exact and keep the invariants (FASTA accessions = JSON accessions;
  sequence = last subject HSP; C copy byte-identical). The sidecar still
  carries the full observed sequence so the page can show what changed.
- Update `test/core/coverage-ownership.tsv` and `test/core/README.md` to record
  both decisions as deliberate, user-approved removals of granularity.

#### 5.3 Adding a sample (documented in `test/core/README.md`)

1. Add a row to `test/core/metadata.csv`. No Groovy or other sample file changes.
2. Run core nf-test with the core config. Invariants run for the new sample; its
   data checks are `unbaselined`, so the test fails as "needs baseline".
3. `python test/core/testkit.py render ...`: the sample appears under
   **Needs baseline** with one copyable command.
4. `python test/core/testkit.py ingest --sample <sample_id> --assertions <run>/nf-test-assertions.json`
   previews all values, asks for acceptance and a reason, and writes
   `test/core/expected/<N>_<sample_id>.yaml`.
5. Rerun core nf-test. Removing a sample: delete its metadata row and YAML file;
   a leftover YAML fails as an orphan with the file name in the message.

#### 5.4 `ingest` / `promote` CLI (mirror `test/selenium/testkit.py`)

- `ingest --assertions <json> (--sample <id> | --all) [--assertion <id>] [--dry-run] [--reason <text>]`:
  creates missing per-sample files, or adds missing keys to an existing file;
  never overwrites an existing key (directs to `promote`).
- `promote (<N> | <stem> | <sample_id> | --all) --assertions <json> [--component <id>] [--assertion <id>] [--dry-run] [--reason <text>]`:
  resolves the target like Selenium (`promote 1`, `promote 1_512503_1_Andrew`).
  For each changed value prints component/assertion, old → new (lists as
  `+added / −removed`; fingerprints with accession) and prompts
  `[y]es / [n]o / [a]ll in this sample / [q]uit`. No `--yes` flag (no
  unattended acceptance).
- Writes update only the selected file, bump `date:` and `provenance`, write
  atomically, and back up the previous version to
  `test/core/expected/.backups/<stem>.<timestamp>.yaml`, keeping the last 3 per
  file (gitignored, replacing `test/core/.backups/`).
- Freshness is per sample: the sidecar records the SHA-256 of each sample file
  used (or `null`); a write is refused only when *that* file changed since the
  evaluation. Contract/ownership digest checks and every other Phase 3 rule
  (no invariant failures, no incomplete or errored evidence) remain.
  **Narrowed 2026-11-27, Phase 14:** an invariant failure blocks only values in
  its own component of that sample; a run-level (`_run`) failure blocks all.

#### 5.5 Review page (`render`) redesign

Rewrite `render()` in `test/core/testkit.py` (standard library only; copy the
inexpensive look of `test/selenium/lib/static/review.css` inline). Page order:

1. **Verdict header:** one of `PASSED`, `FAILED`, `DRIFT`, `NEEDS BASELINE`,
   `INCOMPLETE`, `INVALID EVIDENCE` (worst wins), with run id, evaluated time,
   references and source test.
2. **Run health strip:** workflow success, evaluation complete, JUnit present
   and consistent, sidecar valid, expectation files loaded, with a one-line
   explanation each. Replaces the unordered problem paragraphs.
3. **Needs attention table**, ordered error → rule failure → value drift →
   needs baseline. Columns: sample, check (plain title from `schema.yaml`;
   ID as secondary text), what went wrong (first diagnostic line or a
   short expected → observed summary). Drift is collapsed per sample and component
   (e.g. "blast_hits: 37 sequence fingerprints changed"); needs-baseline is
   collapsed per sample.
3a. **Failure analysis table** (added 2026-11-24, user request): the same
   problems grouped across samples by kind (error, rule failure, drift, needs
   baseline) and component, e.g. "drift — Database coverage", "drift — Coverage
   flags". Ordered by kind, then by number of samples affected. Columns: problem
   (badge, component, result and sample counts), samples (linked to cards, first
   20), checks involved (title without per-taxon/file suffix, with counts),
   one example (`<rule> — expected …, actual …`). The CI summary carries the same
   grouping without the example column.
4. **Sample × component matrix** in `metadata.csv` order with cells such as
   `✔ 42`, `✖ 2`, `? 15` (needs baseline), `→ 6` (owned by Selenium); each
   cell links to the sample card.
5. **Sample cards** for samples with problems only, open by default: a
   Selenium-style `component.assertion | type | expected | observed` table.
   Rule checks show the rule text and diagnostic, never "contract invariant /
   satisfied". Lists show added/removed items (counts plus first 20).
   Fingerprint drift shows accession, old/new fingerprint and a position diff of
   the full sequences from the sidecar (capped). Artifact links appear once per
   card and only for files the check read. Narrow `artifacts` in Groovy to those
   files. A copyable `promote`/`ingest` command per sample and a targeted rerun
   command.
6. **Collapsed appendix:** passed-check counts per sample/component (no
   individual passing rows), Selenium-owned checks (count, fixture path,
   observed value), channel legend H/C/S/T/D/F/M, and run-wide commands.

Every check family in the sidecar must have a title and rule text in
`schema.yaml` (enforced by a test). For the accepted 20-sample run the page
must be under 1 MB. Retain all Phase 3 item 5 guarantees: missing/invalid
evidence never renders as a pass, all content escaped, portable links, exit
code 2 for invalid input.

#### 5.6 Migrate the accepted baseline

One-off conversion of `test/core/expectations.json` (accepted 2026-11-23) into
per-sample YAML. Copy values verbatim, except: drop the 5.2 coverage counts;
compute fingerprints from the accepted sequence values; omit delegated
fields. Keep provenance (source run, approval text, digests). Then delete
`test/core/expectations.json` and update `.github/workflows/nf-test.yml`,
`.gitignore`, `.prettierignore` and docs references. Verify by re-evaluating
the retained run (`.nf-test/task12-review/retained-view`): the same checks pass
apart from removed rows, and the same three integrity failures remain (two PMI
CSV, one missing map). Record the conversion command in Outcomes; do not keep a
migration subcommand in `testkit.py`.

### Phase 6 — Revision 2026-11-23: report clarity, failure explanations and CI

Same worktree and branch as Phase 5. Selenium code and fixtures stay unchanged.

#### 6.1 Why the baseline run fails three checks (findings, no change)

The old core test passed because its snapshot compared file *fingerprints*. A
file that was always wrong in the same way kept passing. The new checks read the
contents.

1. **`preliminary_id_match.csv`: Scenario_04 and
   barcode_83_P59_Potyviridae_cluster_0_RC205.** The file should have a
   header line and one data line:

   ```
   rank,taxon
   genus,Bruchophagus
   ```

   The file actually contains one line, `rank,taxongenus,Bruchophagus`.
   `_write_pmi_match` in `scripts/p3_assign_taxonomy.py` writes the header and
   the row without a line break. This is the known production defect
   **P3-D-008** in the specification checkout (`spec/defects.md`), already
   listed in `tasks/todo.md`. Nothing reads this file (not even the P6 report),
   so the defect was never visible. It occurs only for flag 7A samples, where
   the preliminary ID matched. It is a real workflow bug, not drift, and cannot
   be promoted. Handling needs a user decision (6.6).
2. **Coverage map: 512503_1_Andrew.** The input's preliminary ID is
   `Bulimulus Sporadicus` (capital S) and its TOI is `Bulimulus sporadicus`.
   The workflow wrote two maps that differ only in case:
   `map_Bulimulus_sporadicus.png` (05:08:05) and `map_Bulimulus_Sporadicus.png`
   (05:08:59). `.command.log` records both writes and the emitted channel lists
   both. The retained copy at `/mnt/data/tests-wf-2/tests/2026-11-23_052042/`
   was made about 50 minutes later (all files are timestamped 05:56–05:57). It
   has only the capitalised file and none of the 60 candidate symlinks. **The
   copy lost the file; the workflow did not.** Any copy route that drops
   symlinks or folds case (zip archives or artifact downloads unpacked on a
   case-insensitive filesystem) produces exactly this. Expect this check to pass
   in CI on the runner's own files (6.5 keeps a lossless copy). A separate
   fragility remains: two targets whose names differ only in case produce maps
   that collide on case-insensitive filesystems. Recorded as a spin-off; not
   fixed here.

#### 6.2 Omit Selenium-owned values from the core page

- `testkit.py render` does not display rows with status `delegated` or
  `not_checked`: no appendix table, no `→` matrix counts, no legend entry, no
  totals. They do not affect the verdict.
- The evidence file still records them, for `coverage-ownership.tsv` and audit.
  Ownership stays documented in `test/core/README.md` and
  `test/core/coverage-ownership.tsv`. The Selenium review page shows those results.

#### 6.3 "What this test checks" section

- Add a section near the top of the page, open by default. Per area (component)
  it states in plain words which files are read (filename and the workflow step
  that writes them), what the rule checks verify, and which stored values are
  compared. Show how many checks ran, passed and failed in this run. Items with
  no checks in this run (e.g. source diversity skipped for every sample) say so.
- Source every word from `test/core/schema.yaml`. Each component gets
  `description`, `files` and `producer` (Nextflow process plus script). Each check
  gets `explain` (one or two plain sentences) and keeps `title` and `rule`. Each
  stored value gets `explain`. The channel legend stays, collapsed, below it.
- Example (candidates): "Reads the candidate folder written by EXTRACT_CANDIDATES
  (`scripts/p3_assign_taxonomy.py`). Checks that the candidate list, table,
  sequences and count agree with each other and with the BLAST hits; that
  optional files appear only when they should; and that each flag file has one
  valid value. Compares stored flag values that Selenium does not check."
- A test requires every component, check and stored value in `schema.yaml` to
  have these fields.

#### 6.4 Plain-language failure explanations

- Every `assert` in `test/core/CoreAssertions.groovy` gets a plain message: what
  was expected, what was found, with the concrete values or a short file
  excerpt. Example for `C.pmi`: "preliminary_id_match.csv should be a header line
  `rank,taxon` and one data line; found 1 line: `rank,taxongenus,Bruchophagus`
  (header and data joined — missing line break)." Prefer separate assertions
  over compound expressions so each message names one problem.
- For each check, `schema.yaml` adds `on_fail`: the likely cause and next step in
  plain words. Rule failures say they are workflow or file bugs, name the
  producing step and say they cannot be promoted. Value changes say "compare with
  the reference, then promote if the change is expected".
- Optional `known_defect` per check (ID and one-line summary, e.g. P3-D-008).
  When present, the card shows "Known defect P3-D-008: …" next to the failure.
  The check still fails unless decision 6.6 says otherwise.
- Each card row shows **What should be true** (`explain`/`rule`), **What was found**
  (the plain message), **Likely cause / next step** (`on_fail`, known defect).
  The Groovy power-assert text (`Expression: …`, `Values: …`) appears only under a
  collapsed "Technical detail". The needs-attention table uses the plain
  message's first sentence.
- Value changes get a sentence, e.g. "BLAST hits: 3 accessions appeared (A, B, C)
  and 1 disappeared (D) compared with the stored list. This usually means the
  reference database changed; if expected, promote." Fingerprint changes name the
  accessions and the observed sequence length.
- Tests check that no `assert` in `CoreAssertions.groovy` lacks a message (static
  check), and that the page never shows `Expression:` outside a technical-detail
  block. Re-render the retained run and check that the three cards read as in 6.1.

#### 6.5 `.github/workflows/nf-test.yml`

- **Run core explicitly:** export `CORE_REPO_ROOT="$GITHUB_WORKSPACE"` in the
  "Run core nf-test" step, so evidence and expectations do not depend on the
  JVM's working directory. Keep `--ci --junitxml` and `CORE_ASSERTIONS_OUTPUT`.
  Record the nf-test exit code for later steps without hiding failure.
- **Result on the Actions page:** `testkit.py render` gains `--summary <file>`.
  It writes a short Markdown summary (verdict, run health, needs-attention table,
  how to download the full page). CI appends it to `$GITHUB_STEP_SUMMARY`.
- **Self-contained review bundle:** `testkit.py render` gains `--bundle-dir <dir>`.
  It copies the HTML, JSON, XML, logs and the files read by failing checks into one
  directory, with links rewritten to the copies. CI uploads that directory as the
  `nf-test-review-<runner>` artifact, so links work after download. Upload
  ordinary files only; no symlinks or case-colliding names, since artifacts
  lose them (6.1 item 2).
- **Standalone page (added 2026-11-24):** also upload the bundle's
  `nf-test-review.html` on its own with `archive: false` (artifact named after the
  file). Firefox blocked the zipped bundle as "contains a virus or malware"
  (download reputation check on a new, rarely downloaded zip); a plain `.html` is
  not checked, as with Selenium's `review.html`. Its evidence links only work
  inside the bundle.
- **Lossless retention:** keep `cp -a` to `/var/runner/<timestamp>/` and also
  write `/var/runner/<timestamp>/nf-test-run.tar.gz` (directory renamed in Phase 11) with `tar`, which keeps
- **Lossless retention:** keep `cp -a` to `/var/runner/<timestamp>/` and also
  write `/var/runner/<timestamp>/nf-test-run.tar.gz` with `tar`, which keeps
  symlinks and case. Document using that tarball when copying a run elsewhere.
- **Retire legacy gates (approved 2026-11-23):** remove the "Test flags"
  step and `--flags_results` from "Copy error workdirs", and delete
  `test/core/taxodactyl.workflow.nf.test.snap`. Keep `bin/collect_flags.sh`,
  `bin/test_flags.py` and `test/core/flags/` for other scenarios and history.
- **Running on this branch:** the existing `workflow_dispatch` trigger runs the
  workflow on the chosen branch once the branch is pushed. Document this in
  `docs/nf-tests.md`; add no push trigger.
- Selenium steps are unchanged. Validate with YAML parsing and `actionlint` if
  available; record when unavailable. A real CI run is the user's step.

#### 6.6 Decisions (answered by the user, 2026-11-23)

**Superseded in part by Phase 7 (2026-11-23):** the old workflow, snapshot test
and `.snap` are restored to run alongside the new pipeline. Answer (2) now
applies only to the new workflow.

**Recorded answers:** (1) option (b): keep the PMI CSV check failing, labelled
"Known defect P3-D-008", until a separate task fixes the producer; no production
change in task 12. (2) Retire the legacy CI flag gate and delete
`test/core/taxodactyl.workflow.nf.test.snap` now. (3) Same testing split as
before. The options considered are kept below for the record.

1. **P3-D-008 (malformed `preliminary_id_match.csv`).**
   (a) Fix it in production: one line break in `_write_pmi_match` in
   `scripts/p3_assign_taxonomy.py`, plus a Python unit test. This is a
   production change outside the original scope, so it needs explicit approval.
   The core check then passes on the next run.
   (b) Keep the check failing, labelled "Known defect P3-D-008", until a separate task fixes it.
   (c) Accept the current format as an explicitly approved legacy form (weakens the check).
2. **Retire the legacy CI flag gate and the core snapshot file now?** Coverage
   ownership is mapped (Phase 5). The gate re-checks Selenium-owned 5.x values
   against historical files, which the ownership rule forbids.
3. **Testing allocation for Phase 6:** proposed as before. The agent writes and
   runs the renderer, message and schema tests and the Groovy scenarios; the user
   runs CI and reviews the page.

### Phase 7 — Revision 2026-11-23: run old and new core tests side by side

User request: "bring back the old nf-test.yml and save the new nf-test.yml with a
new name and new test in a different file … I want to have both copies for some
time." Implementation authorized in the same request. Same testing split.

- **Old pipeline, restored byte-for-byte from `0f715e7`:**
  `.github/workflows/nf-test.yml` (snapshot test, snapshot-error CSV, "Test
  flags" gate, `--nft_errors`/`--flags_results` collection, Selenium),
  `test/core/taxodactyl.workflow.nf.test` (snapshot plus aggregate counts) and
  `test/core/taxodactyl.workflow.nf.test.snap`. This undoes the retirement in
  decision 6.6.2 for now. The flag gate and snapshot keep running in the old
  workflow only.
- **New pipeline:**
  - `.github/workflows/nf-test-core-assertions.yml` (workflow name
    `nf-test-core-assertions`, job `core_assertions_test`) holds the Phase 6
    workflow, running `test/core/taxodactyl.assertions.nf.test`.
  - That file is the assertion test formerly at `taxodactyl.workflow.nf.test`,
    with nf-test name "Test Workflow TAXODACTYL core assertions" and evidence
    `source_test` set to the new path.
  - It has no flag gate, snapshot or `--flags_results`, and keeps its own
    artifact names.
- **Triggers:**
  - Old workflow: unchanged (pull requests to main, Sunday 00:00 UTC, manual).
  - New workflow: manual (`workflow_dispatch`) and a weekly schedule on Sunday at
    12:00 UTC, so the two full runs do not compete for the single self-hosted
    runner.
  - Pull-request runs for the new workflow can be added with one trigger line.
- **Shared code is compatible with both:**
  - `bin/collect_artifacts.py` keeps both the legacy (`--nft_errors`,
    `--flags_results`) and the new (`--assertions`) inputs.
  - `test/core/testkit.py`, `schema.yaml` and `expected/` are used only by the
    new pipeline.
  - Running `nf-test test test/core/` would run both test files, so each
    workflow names its file explicitly.
- **Docs:** `test/core/README.md`, `docs/nf-tests.md` and `spec/tests.md`
  describe both pipelines and which file each one runs.
- **Validation:**
  - `git diff 0f715e7 --` on the three restored files is empty.
  - Both workflow files parse as YAML, and `bash -n` passes for their step
    scripts.
  - Python tests and Groovy scenarios pass after the rename.
  - nf-test discovers both test files (`nf-test list`) when that works offline.
- **Completion:** retiring the old pipeline is a later user decision, after the
  two have been compared. Until then, task 12 cannot be marked done for snapshot
  retirement.

### Phase 8 — Revision 2026-11-23: page trim and Selenium overlap

User review of the Phase 6/7 page. **Implementation authorization: granted by
explicit user request ("yes" to implementing Phase 8 including point 5),
2026-11-23.** Testing split unchanged.

**Facts behind point 2** (baseline run). Selenium owns a value for a sample only
when that sample's fixture `test/selenium/expected/<N>_<sample>.yaml` has a
non-empty expected value for it; empty values (`''`) do not count.

| Flag | Selenium checks | Core compares | Why core has some |
|---|---|---|---|
| 1, 7 | all 20 samples | none | — |
| 2 | 19 samples | 1 (FungusB_Btub) | its fixture `toi_flag` is `''` |
| 5.1 | 43 of 61 taxa | 18 | fixture `flag_text1` is `''` for those taxa (e.g. 4 of 5 in Scenario_04) |
| 5.2 | 45 of 61 taxa | 16 | fixture `flag_text2` is `''` for those taxa |
| 5.3 | none | 61 | Selenium checks only the explanatory country text |
| 4 | none | 20 | not in Selenium |

1. **"What this test checks" goes last.** Move it to the collapsed Reference
   section after "Commands", next to "Channel legend", closed by default. It
   becomes a static list per area: description, files and producer, then each
   rule check and stored value with its one-line explanation. Remove every
   per-run count ("38 passed", "40 checks this run: …", "not applicable in this
   run").
2. **Clear ownership wording.** Rewrite the `explain` text of flag values in
   `test/core/schema.yaml` to state the rule, not "compared only where Selenium
   does not check it". Example: "Flag 2: compared here only for samples whose
   Selenium fixture has no `toi_flag` value; otherwise Selenium checks it."
   Flag 5.3 and flag 4: "Not checked by Selenium; compared here for every taxon
   or candidate." The list also gets one sentence of explanation: a value
   belongs to Selenium when that sample's Selenium fixture has a non-empty
   expected value for it.
3. **No duplicate existence and validity checks.**
   - `C.flag.1`, `C.flag.2`, `C.flag.7` ("exactly one valid record, no target")
     run only for samples whose flag value Selenium does not own. With the
     baseline that means `C.flag.2` for FungusB_Btub only. Owned samples get no
     row.
   - In `F.5.1.records`, `F.5.2.records` and `F.5.3.records`, the per-record
     value check (valid value, target and type present) applies only to records
     Selenium does not own.
   - Proposed to keep: the cross-file check that each 5.x file has exactly one
     record per taxon in `db_coverage.json`, with none missing, extra or
     duplicated. Selenium reads only the taxa it displays and would not notice
     an extra or duplicate record. **Kept (user decision 2026-11-23).**
   - Rules that use a flag to decide whether another file should exist stay,
     because they check the other file, not the flag. These are
     `assigned_taxonomy.csv` only for flag 1A, and `preliminary_id_match.csv`
     only for flag 7A.
   - The `flag()` helper keeps reading flag files for those rules. Its
     value-domain check moves into the per-check code, so a Selenium-owned flag
     value is not validated twice.
4. **No known-defect label.** Remove the `known_defect` field from
   `test/core/schema.yaml`, the badge from the needs-attention table and
   summary, and the note from the sample cards. The `C.pmi` failure shows only
   its plain message and the generic next step. P3-D-008 stays tracked in this
   brief and in `tasks/todo.md`.

5. **Uniform "expected vs actual" messages instead of hand-written diagnoses.**
   The user found the Phase 6 message too detailed. Bespoke diagnoses (such as
   "header and data joined: missing line break") do not scale across all
   ~120 assertions in `CoreAssertions.groovy`, and only one had one. Replace them with one format:
   - Groovy helpers produce every message as `<file>: <short rule>` plus
     `Expected: <value>` and `Actual: <value>`. Values print verbatim:
     strings quoted, lists and maps as JSON, truncated at 200 characters. Line
     breaks are shown as `⏎`, so a joined line is visible without being
     diagnosed. Helper calls look like `same(file, rule, expected, actual)`,
     `oneOf(file, rule, allowed, actual)` and `present(file, rule, shouldExist,
     exists)`. For list comparisons, Actual adds "missing …, unexpected …".
   - No interpretations such as "missing line break" or "outputs may belong to
     another sample". The plain rule plus the two values is the message.
   - Example (`C.pmi`): `preliminary_id_match.csv: header line and one data row`
     with `Expected: "rank,taxon⏎<rank>,Bruchophagus"` and
     `Actual: "rank,taxongenus,Bruchophagus"`.
   - The page card columns become **Check | Expected | Actual | Next step**.
     Expected and Actual are parsed from the message; the Groovy power-assert
     text stays under "Technical detail". The needs-attention table shows
     `<rule> — expected …, actual …` in one line.
   - Tests: a static check that every assert uses a helper (or `assert false`
     with an Expected/Actual message); renderer tests for the Expected and
     Actual columns; Groovy scenarios updated to the new wording.

Tests:
- The page has no per-run counts in the reference list.
- The reference list sits after "Commands".
- No `known defect` text appears on the page or in the summary.
- Groovy: an owned flag gets no `C.flag.N` row, an unowned one does; a 5.x
  record with an invalid value fails only when it is not owned; the missing,
  extra and duplicate record checks still fail (if kept).
- Re-render the retained run: the same three failures, now without labels.

Dependencies: Phase 1 -> Phase 2; reporting format probe -> Phase 3;
Phases 2 and 3 -> Phase 4. After agreeing the diagnostic format, assertion
migration and renderer work can proceed independently. No delegation is required.
MVP: core-only contract migration, native XML plus structured assertion evidence,
HTML review, manual selective ingest and promotion with backups, and CI artifact integration.
Other-scenario migrations are not required.
Revision: Phase 5.1–5.2 (schema, per-sample loading, changed data checks) ->
5.6 (migration) and 5.4 (ingest/promote); 5.5 (render) can proceed in parallel
with 5.1 once the sidecar fields (`component`, narrowed `artifacts`, full
sequence detail, per-sample file digests) are agreed. 5.3 documentation last.

## Documentation and configuration

Update `docs/nf-tests.md`, `test/core/README.md`, and relevant sections of
`spec/tests.md` before/with implementation to describe the agreed contract,
coverage ownership, core configuration, rendering, retained evidence, and the
initial run -> ingest -> rerun and later drift -> promote -> rerun workflows.
Preserve instructions needed for other scenarios. `nf-test.config`
currently selects scenario_04 with a placeholder workDir; commands must explicitly
use a core-configured invocation, following the CI setup, rather than assuming
that passing the core test filename changes its configFile automatically.

Revision: document in `test/core/README.md` the per-sample file layout,
`test/core/schema.yaml`, the "Adding a sample" steps (Phase 5.3), the
`ingest`/`promote` commands with examples, how to read the review page, and the
two 2026-11-23 granularity decisions (coverage counts removed, hit sequences
fingerprinted). Mirror the short version in `docs/nf-tests.md`. Update path
references to `test/core/expectations.json` in `.github/workflows/nf-test.yml`,
`.gitignore` (`test/core/expected/.backups/`), `.prettierignore`,
`spec/tests.md` and `bin/collect_artifacts.py` if it reads the old path.

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

**Revision testing decision 2026-11-23, scope: Phase 5.** Same mixed approach.
Agent writes and runs the updated renderer/ingest/promote/migration tests and the
synthetic Groovy contract scenarios. The user stated the values in the
2026-11-23 run were validated and may be used as the baseline: the agent may
carry them into per-sample YAML (Phase 5.6) without further approval, applying
only the user-decided changes (drop per-species related/country counts;
convert sequences to fingerprints; omit Selenium-owned fields). After that,
any drift is reviewed and promoted manually by the user with `testkit.py promote`.
The agent must not run real `ingest`/`promote` against `test/core/expected/`.
Granularity decisions by the user, 2026-11-23: coverage counts not included,
species names must match; hit sequences stored as accession plus fingerprint.

**Phase 6 testing decision, agreed 2026-11-23** (same split as before): the agent writes and runs the renderer, message and schema tests,
the Groovy scenarios and CI syntax checks; the user runs GitHub Actions and
reviews the page and any drift. No expectation changes are planned. No
P3-D-008 production fix is made in this task (decision 6.6.1).

## Validation

Phase 6 validation:
- **Python (`scripts/tests/test_nf_test_review.py`):** Selenium-owned and
  not-checked rows never appear on the page. The "What this test checks" section
  lists every component with counts. Each card shows plain expected/found/
  next-step text. `Expression:` appears only inside technical detail.
  `--summary` writes the verdict and attention table. `--bundle-dir` copies the
  referenced files and rewrites links, holds no symlinks, and still works after
  copying the directory elsewhere.
- **Schema test:** every component has `description`, `files` and `producer`.
  Every check has `title`, `rule`, `explain` and `on_fail`. Every stored value
  has `explain`.
- **Static test:** every `assert` in `CoreAssertions.groovy` has a message.
- **Groovy scenarios (`test/core/contracts.test.groovy`):** extend with
  assertions on the plain messages for the PMI CSV, missing file and
  membership cases.
- **Retained-run re-render:** the three cards match 6.1, and no Selenium values
  are listed.
- **CI:** YAML parses; `actionlint` runs if available. A real Actions run is
  user-owned. Record its result separately.

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
  and a reference count in D without changing its flag (revision: the D count
  change must *not* fail core; verify instead that Selenium's existing
  `record_count`/bar checks catch it where populated). Choose core-owned fields
  for core negative cases and require failure with clear evidence in core HTML.
  For Selenium-owned results, verify the existing assertion covers the intended
  failure using its existing comparison/tolerance; do not add a duplicate core
  check merely because it would fail on a smaller change.
  Confirm a reviewed list-only drift (e.g. species names) can be selectively promoted without
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

Revision (Phase 5) validation:

- Update `scripts/tests/test_nf_test_review.py` for the new page: verdict
  precedence; needs-attention ordering and collapsing; matrix counts; passing
  rows not individually rendered; rule checks show rule text/diagnostic;
  list added/removed and fingerprint diff rendering; artifact links once per
  card; every sidecar check family has a `schema.yaml` title (test fails on a
  missing label); escaping; missing/invalid evidence never passes.
- Update `scripts/tests/test_nf_test_ingest.py` and `test_nf_test_promote.py`
  for per-sample files: new sample creates `<N>_<sample_id>.yaml` with
  Selenium-aligned or next prefix; adding missing keys to an existing file;
  refusing overwrite; target resolution by number/stem/sample_id; `[a]ll in this sample`;
  per-sample freshness (editing another sample's file does not block); per-file
  backups capped at 3; unrelated sample files byte-identical after a write.
- Extend `test/core/contracts.test.groovy` synthetic scenarios: orphan YAML,
  duplicate `sample_id`, unknown assertion ID, new metadata row without file
  (unbaselined, invariants still run, test fails), species-name change in
  `related`/`country` fails while a count-only change passes, fingerprint
  mismatch fails, no sample ID literal in `CoreAssertions.groovy`
  (`grep` check recorded).
- Demonstrate on disposable copies: add a synthetic sample row → run evaluation
  → render shows Needs baseline → `ingest --expectations`-style disposable path
  → rerun passes; then mutate one hit sequence → render shows fingerprint
  drift with position diff → `promote --dry-run` previews it.
- Re-evaluate the retained run after migration (Phase 5.6) and record:
  per-status counts before/after, the removed-row count by family, the
  same three integrity failures, and the rendered page size (< 1 MB).
- Run `PYTHONPATH=scripts python -m unittest discover -s scripts/tests -p 'test_nf_test_*.py'`
  after `source scripts/venv/bin/activate`.

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
- `test/core/expectations.json`: **removed by Phase 5.6**, replaced by
  `test/core/expected/<N>_<sample_id>.yaml` (one per sample) and
  `test/core/schema.yaml`. Values carried over from the user-validated
  2026-11-23 baseline; expected differences: no per-species related/country
  counts, fingerprints instead of sequences, no Selenium-owned fields. Updated
  afterwards only by explicit manual ingest or selective promotion.
  `test/core/expected/.backups/` holds local prior versions and must be excluded from commits.
- `test/core/coverage-ownership.tsv`: record the two deliberate granularity
  removals; delegated rows unchanged.
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

- (Phase 6) The legacy flag gate is gone from `.github/workflows/nf-test.yml` and
  the core `.snap` file is deleted. The P3-D-008 card is labelled as a known defect.
- (Phase 6) The core page lists no Selenium-owned or unchecked values. It explains
  what was checked, in plain words, from `schema.yaml`. Every failure states what
  should be true, what was found, and the likely cause or next step; raw
  expressions appear only as technical detail. CI shows a summary on the Actions
  page, uploads a self-contained review bundle, and keeps a lossless tarball of
  the run. The P3-D-008 decision and the legacy gate decision are recorded and
  applied.

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
  are ingested/promoted by core testkit. (Superseded by Phase 12: 5.x records and
  validity in core, values left to Selenium.)
- Automated validation results and user manual acceptance are recorded separately;
  all required user review is complete before marking the task complete.
- Documentation describes exact commands, paths, provenance and approved updates.
- Core expectations are one YAML file per sample under `test/core/expected/`;
  adding a sample needs only a `metadata.csv` row, a run and a reviewed
  `ingest`; orphan/duplicate files fail clearly; no sample ID in Groovy.
- (Phase 12) Core stores and compares only hit sequence fingerprints and map
  filenames; no value the HTML report shows is a core expectation. Every rule
  check stays, and flag values are checked for validity in every sample. No
  Selenium ownership index or ownership logic remains.
- The review page and CI summary label problems "rule failed" / "possible drift"
  and say the label is a suggestion, not a diagnosis.
- The review page opens with a verdict and a needs-attention table, shows a
  sample × component matrix, and lists no individual passing checks; the page
  for the accepted run is under 1 MB and the user agrees it is usable.

### Phase 10 — Revision 2026-11-25: drop related-species names; drift is a suggestion

User requests (2026-11-25):

1. **Drop the "Related species listed" check for all roles.** Started as
   candidate only, then corrected by the user to every role. `CoreAssertions.groovy`
   no longer records `database_coverage/<role>/<taxon>/related_species`; the
   assertion is removed from `schema.yaml`, so a leftover stored entry fails as
   an unknown assertion. The related list is still checked for structure (map of
   whole-number counts or null) and `related_state` (null/NA) is still compared.
   Remove the existing `related_species` entries from `test/core/expected/*.yaml`.
2. **Explain drift vs failure and mark it as a suggestion.** The rule is
   mechanical: a failed *rule check* (`checks:` in `schema.yaml`, rows without a
   value type) is a failure; a *stored value* (`assertions:`, rows with a type)
   that differs from `expected/` is drift. The tool never looks at why a value
   changed, so a regression in a stored value is labelled drift, and a rule
   failure caused by an external service is labelled a failure. The page and
   summary must say so:
   - badges "rule failed" and "possible drift" (verdict code `DRIFT` unchanged);
   - verdict text for `DRIFT` and `FAILED` says it is a suggestion;
   - a "How labels are chosen" note under "Needs attention" and in the CI summary
     when there are problems;
   - drift next step: "promote only if expected, otherwise treat it as a
     regression"; the shared `rule_fail` text in `schema.yaml` says "likely cause".

### Phase 11 — Revision 2026-11-25: name retained runs by run number

User request (2026-11-25): in `.github/workflows/nf-test-core-assertions.yml`,
step "Save run files on self-hosted runner", name the retained directory
`dir_name="${GITHUB_RUN_NUMBER}-${GITHUB_RUN_ATTEMPT}"` instead of
`timestamp=$(date "+%F_%H%M%S")`, following `.github/workflows/nf-test.yml` on
`main` (commit `f7fbfd8`). `cp -a`, `reports.zip`, `nf-test-run.tar.gz` and the
printed `scp` hint all use the new directory. Update `test/core/README.md` and
`spec/tests.md` (TST-029).

`GITHUB_RUN_NUMBER` is counted per workflow, so run *N* of `nf-test.yml` and
run *N* of `nf-test-core-assertions.yml` would share `/var/runner/N-1/` and
`cp -a` would mix them. **Decision (user, 2026-11-26):** prefix the directory:
`dir_name="assertions-${GITHUB_RUN_NUMBER}-${GITHUB_RUN_ATTEMPT}"`.

### Phase 12 — Revision 2026-11-26: delete report-visible values from core

User decision (2026-11-26), after a review proposing to move every stored value
the HTML report shows to Selenium: **delete those assertions from core now; do
not add Selenium tests yet.**

Reasons (from the review): core's checks depended on Selenium fixture contents
(`coverage-ownership.tsv`, per-sample `owned()`), so blanking a fixture value
silently moved or dropped a check; a drifted flag was promoted in Selenium for
some samples and in core for others. Splitting by kind needs no ownership index.

**Delete (stored values the report shows):**

| Core value | Shown in report as |
|---|---|
| `blast_hits/accessions` | Hits modal (fingerprints, keyed by accession, still catch a changed list) |
| `candidates/flag_1`, `flag_2`, `flag_7` | Flag badges |
| `phylogeny/selected_sequences` | Tree leaf labels |
| `source_diversity/source_accessions`, `flag_4` | Publication modal, button colour |
| `database_coverage/candidate_taxa`, `toi_taxa`, `pmi_taxa`, `target_state`, `related_state`, `country_species`, `country_state`, `target_record_count` (placeholder) | Coverage tables, messages and charts |
| `coverage_flags/flag_5_1`, `flag_5_2`, `flag_5_3` | Coverage tables and modals |

**Keep:** `blast_hits/sequence_fingerprints` and `maps/filenames` (not shown in
the report); every rule check. `C.flag.1/2/7` and `F.5.x.records` check value
validity for every sample, with no Selenium exception. `C.pmi` unchanged.

**Remove ownership:** `test/core/coverage-ownership.tsv`; `owned()`, fixture
loading, `ownershipDigest`, `owner`/`delegated`/`not_checked`/`stored: false`
in `CoreAssertions.groovy`; `ownership_digest`, the ownership freshness check
and hidden statuses in `testkit.py`; `flag`, `state` and `count` value types.
Strip the deleted entries from `test/core/expected/*.yaml`.

**Coverage gap (accepted for now):** until Selenium compares these values for
every sample, some are compared by neither suite (spec TST-G-011). Follow-up
work for Selenium, not started: fill fixtures for all 20 samples (flags 1/2/7,
5.1/5.2); exact-list comparisons for coverage taxa and hit accessions; extractors
for flag 5.3 (`flag_text3`), flag 4 and source accessions in the publication
modal, every in-country bar, coverage-state messages and tree `leafNames`;
confirm that a Selenium pytest failure fails the CI job (`set +e` step).

### Phase 13 — Revision 2026-11-27: name retained runs by run ID

User request (2026-11-27): in `.github/workflows/nf-test-core-assertions.yml`,
step "Save run files on self-hosted runner", use `GITHUB_RUN_ID` instead of
`GITHUB_RUN_NUMBER`:
`dir_name="assertions-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"`. Review spec,
docs and skills.

`GITHUB_RUN_ID` is unique across all workflows in the repository, so the
directory can no longer collide with `nf-test.yml`'s
`<run_number>-<run_attempt>` directories even without the prefix. The
`assertions-` prefix is kept so the directory shows which workflow wrote it.
Update `test/core/README.md` and `spec/tests.md` (TST-029, provenance).

### Phase 14 — Revision 2026-11-27: rule failures block only their component

User request (2026-11-27): `promote barcode_83_P59_Potyviridae_cluster_0_RC205
--assertion maps/filenames` was refused with "Invariant failures ... (C.pmi)".
"C.pmi is not promotable but maps should be." Review spec and docs.

- `test/core/testkit.py update`: a failed rule check in a sample blocks only
  promotable values in the same component (`candidates` for `C.pmi`); a `_run`
  failure still blocks every value. Blocked values are skipped and named
  (`<value ids> (<check id>)`); an explicit target errors only when nothing
  promotable is left, and `--all` skips fully blocked samples as before.
  Blockers are still checked before per-sample freshness. Invariant failures
  themselves stay non-promotable and visible.
- Docs: `spec/tests.md` TST-027, `docs/nf-tests.md`, `test/core/README.md`.
- C.pmi on that sample is P3-D-008 (`_write_pmi_match` in
  `scripts/p3_assign_taxonomy.py` writes header and row without a newline);
  still a separate fix (`tasks/todo.md`).

### Phase 15 — Revision 2026-11-27: simplify, comment, plain-language README

User request (2026-11-27): in `test/core`, simplify `CoreAssertions.groovy` and
`testkit.py` where possible, add comments explaining which part is for what,
rewrite `test/core/README.md` so a lay person can read it, review docs and spec.

- No behaviour change: every check, message, status and refusal stays the same;
  the 23 Groovy scenarios and the Python tests must pass unchanged.
- Any edit to `CoreAssertions.groovy` (comments included) changes
  `contract_sha256`, so evidence written before it is refused by
  `ingest`/`promote` as "Stale assertion code" until a new core run.
- README: lead with what the test is for, the two kinds of check, everyday tasks
  (run, read the page, promote, ingest, what each refusal means), then what is
  checked, known problems, CI, developer notes, and history/provenance last.
- No `db_coverage.json` record count (target, related or country) is a core
  expectation; species-name membership and section state are. Hit sequences are checked by accession list and fingerprint.
- The review page opens with a verdict and a needs-attention table, shows a
  sample × component matrix, and lists no individual passing checks; the page
  for the accepted run is under 1 MB and the user agrees it is usable.

## Open decisions and risks

- Phase 6 decisions recorded and implementation authorized 2026-11-23 (6.6).
- P3-D-008 stays a visible core failure for Scenario_04 and the Potyviridae
  sample until a separate task fixes `_write_pmi_match`, so CI core stays red
  for that reason alone. The page labels it as a known defect.

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
- Confirmed 2026-11-23: 16-hex-character fingerprints; core files reuse the
  Selenium fixture number for the same `sample_id`. Decided 2026-11-23: core never checks a taxon's own record count
  (`coverage.<role>.<taxon>.target`); Selenium owns it (all 61 in the accepted
  run), and samples without a Selenium fixture have no check on it.
- Related/country species-name lists come from live GBIF/COL lookups and may
  still drift; such drift appears as list changes and is promoted manually.
- Fingerprints make drift detection exact but unreadable on their own; the page
  depends on the sidecar's full sequences to show what changed.


## Outcomes

Implementation checkpoint, 2026-11-23. **Task remains active; manual acceptance
and full core rerun are outstanding.**

- Implemented on `task-12-core-nf-test-assertions`, based on the requested
  `nf-test-sh-runner` commit `0f715e7`, in
  `/mnt/data/tests-wf-2/taxodactyl/nf-test-sh-runner/.worktrees/task-12-core-nf-test-assertions`.
  Main task activation is recorded in `/mnt/data/sdd` commit `aff5d03`.
  The selected source branch had no task/spec scaffold, so only this task's
  tracking and branch-specific testing spec were introduced; unrelated main
  tasks were not imported. No plan or feature checklist/hooks existed there.
- Replaced the core snapshot invocation and aggregate counters with one Groovy
  contract evaluation: routing, identities, file schemas, copy preservation,
  sequence membership/content, candidate/source/tree relationships, conditional
  outputs, raw P5 integrity and uncovered values. Ordinary power assertions feed
  native `assertAll` via a closure array (spread calls exceed Groovy's argument
  limit). Independent failures and observed data are flushed to JSON first.
- Audited populated Selenium fixtures and collectors, including actual list
  comparison and count tolerance. `test/core/coverage-ownership.tsv` records 245
  concrete delegated fields for the supplied run. Core does not create accepted
  expectations for these fields. BLAST calculations/records and phylogeny
  sampling remain owned by their existing focused Python tests.
- Added offline HTML rendering and manual selective ingest/promote. Commands
  reject incomplete/malformed/duplicate or stale evidence, unknown data keys,
  Selenium-owned data and failed invariants. Explicit acceptance/reason, atomic
  writes, unrelated-entry preservation and three backups are implemented.
  Tests and disposable CLI demonstrations never accepted real data.
- CI requests native JUnit, renders under `always()`, uploads XML/JSON/HTML/logs,
  and collects core assertion failures by producer. Earlier nf-test failure
  remains a failed step; render errors also fail their step. Legacy collector
  arguments and other-scenario handling remain intact. Frozen mock artifacts
  explicitly report absent modern evidence. Selenium steps/code/fixtures are
  unchanged.
- Pinned nf-test 0.9.5 / Nextflow 25.04.6 probe: native JUnit retains only the
  aggregate assertAll count, establishing the need for the JSON sidecar. A second
  native wrapper probe exercised 374 checks, flushed evidence and returned
  failure for missing synthetic channels. Actual core test discovery succeeded
  with explicit core configuration; this dry-run is not execution evidence.
- Focused automated validation: **21 Python tests passed** (render, ingest,
  promotion and artifact collection); **15 synthetic Groovy scenarios passed**,
  including empty/skipped results, routing and duplicate errors, P5 value/count
  and record mutations, independent failures and populated-versus-empty Selenium
  ownership. Existing Selenium comparator separately verified: expected 100
  accepts 110, rejects 112; a B-to-C flag change fails. YAML parsing and
  `git diff --check` passed. No production `.nf` file was modified. The requested
  `nexflow lint` executable is unavailable for the disposable probe; that probe
  was executed successfully by pinned Nextflow before its intentional assertions failed.
- Legacy flag comparison on the same retained run: **60 identical files**, zero
  differences, missing files or invalid JSON; exit 0.
- Unchanged Selenium against the same run: **19 passed, 1 failed**, exit 1.
  `SME25-218` / PMI Drosophila / `database_coverage.record_count` expects 5266,
  observes 12255, outside its existing ±10% tolerance. This difference remains
  for user investigation/acceptance; no fixture/tolerance was changed. Browser
  prerequisites were supplied under `/tmp`; this host requires a temporary
  Chrome launcher with `--no-sandbox` because user namespaces are disabled.
- The retained workflow itself records success/exit 0 and a native original
  snapshot pass. Direct evaluation of retained channels yields 21019
  unbaselined data rows, 245 delegated rows, 290 passing invariants, 62 failed
  invariants and one evaluation error. This is diagnostic evaluation of old
  outputs, not a new workflow run or approved baseline. Exact historical checkout
  revision is unavailable; provenance hashes, reference labels, tool versions
  and per-sample candidate-file inventories are recorded without raw parameters.
- Of the 62 invariant failures, 60 are absent C-channel symlinks (H originals
  exist and pass their content checks). The retained `.command.run` establishes
  the original symlink targets; no emitted paths were silently substituted.
  Two are existing P3-D-008 malformed PMI CSVs. The map evaluation error is an
  absent lowercase `map_Bulimulus_sporadicus.png`; the retained directory has
  only `map_Bulimulus_Sporadicus.png`. These findings were not hidden by changing
  production behavior or expectations.
- Review bundle: `.nf-test/task12-review/` (ignored, retained locally), including
  `nf-test-review.html`, sidecar, diagnostics, native probe XML/logs, synthetic
  CLI demonstration, legacy flag results and Selenium JSON/HTML/logs. The HTML
  explicitly reports missing historical JUnit; no replacement passing XML was
  fabricated. Offline rerender succeeds in writing this diagnostic page and
  returns 2 for the missing XML, as intended.

### Outstanding review and completion work

1. Decide whether to retain the strict PMI CSV invariant until P3-D-008 is fixed
   separately, or explicitly approve a narrow check of the legacy format. A
   user clarification is pending. The production fix is recorded as a separate
   follow-up in `tasks/todo.md`; none of the source task's unrelated spin-offs
   were absorbed.
2. Review the coverage map, ancillary-format dispositions and actual data. No
   real `expectations.json` has been created and no real ingest/promote has run.
3. Obtain complete retained outputs or perform a newly configured core run;
   resolve/explicitly disposition the observed integrity problems, then manually
   ingest approved values and rerun. Full live core execution is not claimed by
   the synthetic probes or retained-file evaluation.
4. Review the independent Selenium count difference. Preserve the historical
   failure evidence if a fixture change is later approved through its own flow.
5. Only after the required review, retire the historical core snapshot file and
   remove the separate legacy flag gate. They remain for migration review now.
   Finish lifecycle (done/move/changelog/remove active entry) only after required
   validation and user acceptance; this checkpoint is deliberately not marked done.

No before/after extension hooks are configured. No production scientific code,
Selenium fixtures or scenario_01–04 snapshots were modified.


### Baseline acceptance update — 2026-11-23

The user explicitly instructed: “I want you to use these values as baseline.
These have been validated.” This supersedes the outstanding data-acceptance
requirement above. The supplied run is now the accepted baseline for all 21,019
core-owned observed data values across 20 samples. The 245 delegated Selenium
fields are excluded, and Selenium fixtures are unchanged.

`test/core/expectations.json` records each value and references shared provenance
containing the user approval, source run and evidence/code/ownership hashes.
This explicit initial baseline authoring preserves the original unbaselined and
failed evidence. It does not alter or bypass the conservative ingest/promote
implementation, accept an invariant failure, or claim a new full workflow run.

For retained-data comparison, a disposable view reconstructs all 60 candidate
staging symlinks using exact targets recorded in each `.command.run` and the
move recorded in `.command.sh`. The original run directory is untouched. The
mapping manifest is `.nf-test/task12-review/retained-view-manifest.json`.
The one missing lowercase map path is not substituted with a differently named
file. The two known malformed PMI CSV checks remain enforced.

Focused toolkit tests: 21 passed. All 21,019 accepted data values pass on
re-evaluation; zero rows are unbaselined. The 21,373-check evaluation has exactly
three remaining integrity failures (two PMI CSV checks and one missing map).
Data-baseline comparison results and remaining integrity failures are recorded in `.nf-test/task12-review/accepted-assertions.json`
and `accepted-evaluation.log`. Task status remains active for the remaining
integrity disposition, full workflow validation and final migration review;
initial expected-value acceptance is no longer pending.

### Revision planned — 2026-11-23

After reviewing the rendered page, the user requested per-sample expectation
files (Selenium-style), an easier way to add samples, and a redesigned review
page. Added Phase 5 and matching documentation, testing, validation and
completion items. User decisions: per-species related/country coverage counts
are not core expectations (species names must match); hit sequences are
stored as accession plus fingerprint; the 2026-11-23 validated values carry over
as the baseline, and later drift is promoted manually. Phase 5 implementation
is pending explicit authorization. No code changed by this revision.

### Phase 5 implementation — 2026-11-23

Implemented in the task worktree under explicit authorization. **Not committed.**
Task remains active.

- **Per-sample expectations:** `test/core/expected/<N>_<sample_id>.yaml` (20
  files, 0.8 MB total), numbered like the Selenium fixtures. Check catalogue:
  `test/core/schema.yaml`. `test/core/expectations.json` was removed.
  `CoreAssertions.groovy` loads and validates the files (`expected.files`),
  emits rows labelled by component/assertion, reports stale entries, narrows
  artifact paths to the files each check reads, and contains no sample IDs.
  Evidence schema is now version 2 with per-sample file digests.
- **Data decisions applied:** no `db_coverage.json` record count is a core
  expectation; target counts are shown as Selenium-owned or "not checked".
  Related/in-country species names and section states are compared. Hit
  sequences are compared by 16-hex SHA-256 fingerprints, with full sequences
  kept in the evidence only for failing rows. Rows per run: 21,617 → 1,021.
  Selenium-owned rows: 245 → 208, because the 37 first-bar related counts are
  no longer emitted at all. `coverage-ownership.tsv` was regenerated with new IDs.
- **Migration:** one-off script
  `/tmp/claude-1000/-mnt-data-sdd/c09a2742-6d25-4021-b9c8-2be098174d79/scratchpad/migrate_expectations.py`.
  It copied the accepted values verbatim, dropped the 12,390 `D.count` entries
  and converted 8,190 sequences into 20 fingerprint maps. Re-evaluating the
  retained view gives 810 passed, 208 Selenium-owned, 0 needing a baseline,
  0 stale, and the same three rule failures. Evidence:
  `.nf-test/task12-review/phase5-assertions.json`.
- **Review page:** `testkit.py render` rewritten as a verdict, run health,
  needs-attention table, sample × component matrix, problem-only sample cards
  and a collapsed reference section. `phase5-review.html` is 63 KB (was 17 MB).
- **Toolkit:** `ingest --sample|--all` and `promote <N|stem|sample_id>|--all`,
  with `--component`, `--assertion`, `--dry-run` and `--expected-dir`. Prompts
  are `[y]es/[n]o/[a]ll in this sample/[q]uit`. Backups are kept per file (3)
  in `test/core/expected/.backups/`. PyYAML is now required; CI installs it
  before rendering.
- **Validation run:**
  - 37 focused Python tests passed.
  - 22 synthetic Groovy scenarios passed.
  - A disposable end-to-end demo on the retained run: removing Scenario_01's
    file gave "needs baseline"; `ingest` recreated a file with values identical
    to the migrated baseline; a re-evaluation passed; an injected fingerprint
    change showed as drift with the observed sequence; `promote 13 --dry-run`
    previewed it; `promote 16` was refused because of Scenario_04's PMI rule
    failure.
  - `git diff --check` passed, and the YAML parses.
  - **Not run:** a new full core workflow execution, and Selenium (no Selenium
    files changed).
- **Deviations from the brief, for review:**
  1. The fingerprint diff cannot show the *old* sequence, because only its
     fingerprint is stored. The page shows old/new fingerprints plus the
     observed sequence and its length.
  2. The missing map `map_Bulimulus_sporadicus.png` is now a rule *failure*
     (missing emitted file) rather than an evaluation error, consistent with
     other missing files. Without this, the evaluation counted as incomplete and
     blocked all ingest/promote.
  3. Rule failures block ingest/promote only for their own sample (and for
     everything if a `_run` rule fails); with `--all`, those samples are skipped
     and named.
  4. A core-stored value that Selenium later owns is reported as stale and can
     be removed with `promote`.
  5. Older (version 1) evidence files render as INVALID EVIDENCE; re-evaluate
     them instead.
- Outstanding items from the earlier checkpoint are unchanged: PMI CSV
  disposition (P3-D-008), the missing map, a full core rerun, snapshot and
  flag-gate retirement after review, and the Selenium SME25-218 count difference.

### Phase 6 implementation — 2026-11-23

Implemented in the task worktree under explicit authorization. **Not committed.**
Task remains active (live CI run pending).

- **Page:**
  - Selenium-owned (`delegated`) and `not_checked` rows are no longer shown and
    do not affect the verdict. They remain in the evidence JSON.
  - New "What this test checks" section, written from `test/core/schema.yaml`
    (`description`, `files`, `producer`, `explain`, `on_fail`, `known_defect`),
    with per-check counts for the run.
  - Cards show *what should be true / what was found / likely cause and next
    step*, with the raw Groovy expression only under "Technical detail".
  - `C.pmi` is labelled "known defect P3-D-008" (decision 6.6.1; the check
    still fails).
- **Messages:** every `assert` in `CoreAssertions.groovy` has a plain message
  with concrete values (a static test enforces this). The PMI check now reads
  "found 1 line(s): 'rank,taxongenus,Bruchophagus' (header and data joined:
  missing line break)". The map check now reads "listed in the workflow output
  but the file does not exist (if the run was copied, the copy may have lost it)".
- **Schema fix:** inline `{…}` YAML entries silently cut values at the first
  comma, which had truncated some rule texts since Phase 5. Checks and values are
  now written in block style, and a test rejects unknown keys.
- **`render`:** gains `--summary` (Markdown for `$GITHUB_STEP_SUMMARY`),
  `--bundle-dir` (self-contained folder with copies of the files behind each
  failure: ordinary files with index prefixes, so no symlinks or case
  collisions) and `--include` (logs).
- **`.github/workflows/nf-test.yml`:**
  - `CORE_REPO_ROOT` is exported and the nf-test exit code is recorded.
  - Render writes the summary to the run page and uploads the bundle as
    `nf-test-review-<runner>`.
  - The "Test flags" step and `--flags_results` are removed (decision 6.6.2).
  - Retention also writes `nf-test-run.tar.gz`.
  - A `workflow_dispatch` note explains running on a branch.
  - `test/core/taxodactyl.workflow.nf.test.snap` is deleted.
- **Docs:** `test/core/README.md` (known defect, page guide, CI), `docs/nf-tests.md`,
  `spec/tests.md`. A spin-off for case-colliding map names is in `tasks/todo.md`.
- **Validation:**
  - 43 Python tests passed.
  - 25 Groovy scenarios passed (new: PMI plain message, well-formed PMI passes,
    routing message, missing-file message).
  - The workflow YAML parses, and `bash -n` passes for the step scripts.
    `actionlint` is unavailable.
  - Retained-run re-evaluation: 810 passed, 3 failed (two P3-D-008, one map
    lost by the copy), 208 Selenium-owned (hidden).
  - `phase6-review.html` is 32 KB. Evidence:
    `.nf-test/task12-review/phase6-{assertions.json,review.html,summary.md,bundle/}`.
  - **Not run:** GitHub Actions (user-owned) and a new full core workflow run.

### Phase 7 implementation — 2026-11-23

Implemented in the task worktree. **Not committed.**

- **Old pipeline:** `.github/workflows/nf-test.yml`,
  `test/core/taxodactyl.workflow.nf.test` and its `.snap` are restored
  (`git diff 0f715e7` on the three files is empty, including the original file's
  trailing whitespace).
- **New pipeline:**
  - `.github/workflows/nf-test-core-assertions.yml` (name
    `nf-test-core-assertions`, job `core_assertions_test`) triggers on Sunday at
    12:00 UTC and manually; a commented `pull_request` block shows how to add PRs.
  - It runs `test/core/taxodactyl.assertions.nf.test` (nf-test name "Test Workflow
    TAXODACTYL core assertions"; evidence `source_test` updated). Concurrency
    groups differ by workflow name.
- **References updated:** `testkit.py` (rerun command), `nf_test_support.py`,
  `test/core/README.md` (side-by-side table), `docs/nf-tests.md`, `spec/tests.md`.
- **Validation:**
  - Both workflows parse as YAML with the expected names, jobs and triggers, and
    `bash -n` passes for their step scripts.
  - 43 Python tests passed; 25 Groovy scenarios passed.
  - **Not run:** nf-test discovery (`nf-test list`). The local nf-test is 0.9.3
    rather than the pinned 0.9.5, and the attempt failed on configuration.
    Neither workflow has been run on GitHub Actions.

### Phase 8 implementation — 2026-11-23

Implemented in the task worktree under explicit authorization. **Not committed.**

1. **Reference list:** "What this test checks" is now a collapsed, static list
   in the Reference section, after "Commands" and before "Channel legend". It
   has no per-run counts.
2. **Ownership wording:** flag explanations in `test/core/schema.yaml` state who
   checks each value. Flags 1, 2 and 7 are Selenium's when the fixture has
   `conclusion_flag`/`toi_flag`/`preliminary_flag` respectively. Flags 5.1 and
   5.2 are Selenium's per taxon when the fixture has `flag_text1`/`flag_text2`.
   Flags 5.3 and 4 are never Selenium's. The reference list explains the
   ownership rule.
3. **No duplicate validity checks:**
   - `C.flag.1/2/7` run only for flags Selenium does not own. On the baseline
     that leaves only `C.flag.2` for FungusB_Btub; the 59 other runs are gone.
   - In the 5.x checks, record values are validated only where Selenium does not
     own them. The record structure (one record per taxon, none missing, extra
     or repeated) is always checked (user decision).
   - `flag()` no longer validates values; `flagValue()` does that where needed.
4. **No known-defect labels:** `known_defect` is removed from the schema, the
   page and the summary.
5. **Uniform messages:**
   - Every assertion goes through helpers (`holds`, `same`, `sameSet`, `unique`,
     `present`, `count`) producing `<file>: <rule>` / `Expected:` / `Actual:`
     (plus `Difference:` for lists). Values print as they are, with `⏎` for line
     breaks and no diagnosis.
   - Page cards: Check | Expected | Actual | Next step. Needs-attention rows and
     the CI summary use `<rule> — expected …, actual …`.
   - The boilerplate `Expression: ok …` technical detail is hidden.
   - A `Desc` helper class sits last in `CoreAssertions.groovy`, because callers
     use `parseClass()`, which returns the first class in the file.
- **Validation:**
  - 42 Python tests passed.
  - 27 Groovy scenarios passed (new: owned flags get no validity check, unowned
    do; an invalid Selenium-owned 5.x value is left to Selenium while the
    structure check still fails; messages updated to Expected/Actual).
  - Retained-run re-evaluation: 751 passed, 3 failed (same three), 208
    Selenium-owned (hidden). Page 29 KB.
  - Evidence: `.nf-test/task12-review/phase8-{assertions.json,review.html,summary.md,bundle/}`.
  - **Not run:** GitHub Actions and a new full core run.

**Temporary CI trigger (2026-11-24):** commit `4238a8d` on the task branch adds a
`push` trigger for `task-12-core-nf-test-assertions` to
`.github/workflows/nf-test-core-assertions.yml`. Manual dispatch needs the file
on the default branch. **Remove this trigger before merging.**

### Phase 9 implementation — 2026-11-24

Implemented in the task worktree. **Not committed.**

- **Failure analysis table (5.5 item 3a):** `testkit.py` `_failure_groups()`
  groups error/failed/drift/needs-baseline results by kind and component across
  samples; `render` shows it between "Needs attention" and "Samples × checks",
  and `--summary` adds a compact Markdown version.
- **Standalone review page (6.5):** `nf-test-core-assertions.yml` gains "Upload
  nf-test-review.html" (`archive: false`, `if: always()`) after the bundle
  upload. The summary's download hint names both artifacts.
- **Docs:** `test/core/README.md` (page guide, CI list, side-by-side table),
  `docs/nf-tests.md`, `spec/tests.md` (TST-028, TST-029).
- **Validation:**
  - 43 Python tests passed (new: grouping order, sample links, per-check
    grouping without taxon suffix, summary table).
  - Re-render of `phase8-assertions.json`: 2 groups (failed — Candidates,
    Preliminary-ID match table ×2 in 2 samples; failed — Coverage maps, Map
    images ×1). Page 30 KB.
  - **Not run:** GitHub Actions; the Groovy scenarios (Groovy files unchanged).

### Phase 10 implementation — 2026-11-25

Implemented in the task worktree. **Not committed.**

- `test/core/CoreAssertions.groovy`: skips the `related_species` value for every
  role. `test/core/schema.yaml`: `related_species` assertion removed; component
  description and `rule_fail` text reworded.
- `test/core/expected/*.yaml`: 28 `related_species` entries removed (candidate
  12, toi/pmi 16) with `testkit.dump`, so formatting is unchanged elsewhere.
- `test/core/testkit.py`: `LABEL_NOTE` and `BADGE` ("rule failed", "possible
  drift", "needs baseline") used on the page, failure-analysis table and CI
  summary; `DRIFT`/`FAILED` verdict text and drift next step reworded.
- Tests: `contracts.test.groovy` scenario "related species names are not
  compared for any role" (replaces "related species names must match");
  `test_nf_test_review.py` checks the new badges and note.
- Docs: `test/core/README.md` (D row, "Drift vs failure is a suggestion",
  scenario count 27), `docs/nf-tests.md`, `spec/tests.md` (TST-026, TST-028,
  provenance).
- **Validation:** 27 Groovy contract scenarios passed; 43 Python tests passed;
  all expected YAML files still load. **Not run:** the full core nf-test or
  GitHub Actions.

### Phase 11 implementation — 2026-11-25

Implemented in the task worktree. **Not committed.**

- `.github/workflows/nf-test-core-assertions.yml`: retained directory is
  `/var/runner/assertions-${GITHUB_RUN_NUMBER}-${GITHUB_RUN_ATTEMPT}/`, like
  `nf-test.yml` on `main` but prefixed so the two workflows never collide. The branch's own `nf-test.yml` still uses a
  timestamp until it is merged with `main`.
- Docs: `test/core/README.md` (CI list, bundle note), `spec/tests.md` (TST-029,
  provenance).
- **Not run:** GitHub Actions. `.agents/skills/investigate-runner` and
  `selenium-report` still describe `/var/runner/<timestamp>/`.

### Phase 12 implementation — 2026-11-26

Implemented in the task worktree. **Not committed.**

- `test/core/CoreAssertions.groovy`: deleted the report-visible `data()` values
  and all ownership code (`owned()`, fixture loading, `ownershipDigest`, `owner`,
  `delegated`/`not_checked`/`stored`). `C.flag.1/2/7` always run; 5.x values are
  always validated. `flag`/`state` value types removed.
- `test/core/schema.yaml`: only `blast_hits.sequence_fingerprints` and
  `maps.filenames` remain as assertions; groups removed; descriptions and rule
  explanations say values are left to Selenium.
- `test/core/expected/*.yaml`: 419 stored entries → 40 (fingerprints and map
  filenames per sample); provenance unchanged.
- `test/core/coverage-ownership.tsv` deleted.
- `test/core/testkit.py`: removed `ownership_digest`, the ownership staleness
  check, `owner` requirement, hidden statuses and `flag`/`state` types; "What
  this test checks" intro reworded.
- Tests: contract scenarios rewritten for ownership removal (27 → 23: changed
  flag/coverage values not compared; invalid flags fail in every sample whatever
  the Selenium fixture; a stored value core no longer compares fails as unknown).
  Python fixtures switched from `flag_5_1` to `sequence_fingerprints`; the
  Selenium-owned rendering test removed (43 → 42).
- Docs: `test/core/README.md` ("What core compares" replaces "Coverage
  ownership"), `docs/nf-tests.md`, `spec/tests.md` (TST-026, TST-028, TST-G-011,
  provenance); workflow comment in `nf-test-core-assertions.yml`.
- Group support (`groups` in schema, grouped YAML entries) is kept in the code
  but unused.
- **Validation:** 23 Groovy contract scenarios passed; 42 Python tests passed.
  **Not run:** the full core nf-test or GitHub Actions; the real expected files
  have not been re-evaluated against a run.

### Phase 13 implementation — 2026-11-27

Implemented in the task worktree. **Not committed.**

- `.github/workflows/nf-test-core-assertions.yml`: retained directory is
  `/var/runner/assertions-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}/`; comment
  explains the run ID is unique across workflows and the prefix names the
  workflow. `cp -a`, `reports.zip`, `nf-test-run.tar.gz` and the `scp` hint use
  `$dir_name` and needed no change.
- Docs: `test/core/README.md` (CI list with example
  `assertions-12345678901-1`, bundle note), `spec/tests.md` (TST-029,
  provenance). `docs/` has no reference to the directory name.
- Skills: `.agents/skills/investigate-runner` and `selenium-report` (and their
  `.claude/skills` copies) still describe `/var/runner/<timestamp>/`; not
  changed by this phase (already stale since Phase 11).
- **Not run:** GitHub Actions.

### Phase 14 implementation — 2026-11-27

Implemented in the task worktree. **Not committed.**

- `test/core/testkit.py`: new `_blockers_for(blockers, row)`; `update` builds
  the selected values first, drops those blocked by their own component or a
  `_run` failure, prints `Skipping: Invariant failures for <sid> cannot supply
  an accepted baseline for <ids> (<check>)`, and raises only if an explicit
  target has nothing left.
- Tests (`scripts/tests/test_nf_test_ingest.py`):
  `test_rule_failure_blocks_only_its_sample_and_component` (C.pmi does not block
  maps; M.files does; `_run` blocks all) and
  `test_rule_failure_skips_only_its_component_within_a_sample` (M.files skips
  maps, blast fingerprints still written).
- Docs: `spec/tests.md` TST-027, `docs/nf-tests.md`, `test/core/README.md`
  (blocking rule, test count 43).
- **Validation:** 43 Python tests passed (`test_nf_test_*.py`). Dry run of the
  user's command offered only `maps/filenames` (+`map_Potyvirus_batataplumei.png`).
  **Not run:** Groovy contract scenarios (no Groovy change), full core nf-test,
  GitHub Actions.

### Phase 15 implementation — 2026-11-27

Implemented in the task worktree. **Not committed.**

- `CoreAssertions.groovy`: class overview (call sequence, rule checks vs stored
  values, sections), comments on every field and helper, a comment per
  per-sample check, section headers (expectation files, run checks, per-sample
  checks). Simplified: one `NUCLEOTIDES` pattern (was repeated 3×); removed the
  unused `brief()`; `shortName in ['H','C','S','D','F','M']` → `shortName != 'T'`.
- `testkit.py`: module docstring explains nf-test → Groovy → evidence JSON →
  render/ingest/promote; section comments; docstrings on helpers. `update()`
  split into `_check_trustworthy`, `_select`, `_review` and `_write`; the two
  blocker helpers merged into `_blocking_checks(rows, sample, row)`; duplicate
  `check_title()` removed (uses `check_info()`); `_preview()` replaces repeated
  list truncation in `describe_change()`. CLI exit codes documented.
- `test/core/README.md` rewritten for lay readers (order as in the revision),
  with a table of refusal messages and what to do. Facts kept, including
  history and provenance (moved to the end).
- `docs/nf-tests.md`: README anchor updated
  (`#run-the-test-and-open-the-review-page`); pointer mentions refusals and that
  editing the Groovy or schema needs a new run. `spec/tests.md` TST-027: the
  evidence records digests of the Groovy, schema and sample files; any change,
  comments included, needs a new evaluation.
- **Validation:** 23 Groovy contract scenarios passed (nf-test 0.9.5 jar);
  43 Python tests passed (`test_nf_test_*.py`).
  **Not run:** the full core nf-test or GitHub Actions. Evidence written before
  this change (e.g. the 2026-11-27 run's `nf-test-assertions.json`) is now
  stale for ingest/promote; render still works.
