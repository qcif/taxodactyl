# Task 04 — Expand BLAST context in 500-hit blocks

**Status:** active

**Priority:** Unassigned; DAFF enhancement.

**Issue:** [#160 — Consider blast hits down to 93.5% identity for better context](https://github.com/qcif/taxodactyl/issues/160)

**Scope:** Rename the Nextflow maximum-hit parameter to
`blast_max_target_seqs` (default 2000) and use it to limit
BLAST retrieval per query, then retain blocks
of 500 sorted by Taxodactyl aggregate identity until the last retained hit is
at or below the effective stopping threshold (default 93.5%), or the available
hits are exhausted. Use the retained set
for downstream screening and the report.

**Source material:** Issue #160 and its supplied discussion through 29 October
2025; the user's clarification that blocks remain required and the stopping
comparison uses aggregate identity after BLAST; `spec/python/p1-parse-blast.md`,
`spec/contracts/hits.md`, `spec/python/p3-assign-taxonomy.md`,
`spec/nextflow/processes.md`, and `spec/nextflow/params.md`.

## Preconditions

- No active Spec Kit feature directory is configured. The setup script
  `.specify/scripts/bash/setup-tasks.sh --json` reported “Feature directory not
  found”. This brief uses the existing `spec/` documents, source and tests.
  `.specify/memory/constitution.md` is an unfilled template.
- `modules/blast/blastn/main.nf` currently uses `-max_target_seqs 500` with
  `-task megablast`, XML output (`-outfmt 5`), `-evalue 0.05`, `-reward 1`
  and `-penalty -3`. `conf/process.config` pins BLAST 2.16.0.
- `scripts/src/blast/parse_xml.py` already computes aggregate identity and
  stably sorts JSON hits by it. Its FASTA list remains in original BLAST order.
  `scripts/p1_parse_blast.py` currently writes all parsed hits and accessions.
- The current Nextflow parameter `blast_max_target_seqs_for_report` defaults
  to 2000 in `conf/params.config`
  and is passed to P1 by `modules/extract/hits/main.nf`. It does not control
  BLAST. P1 changing its in-process configuration does not propagate that
  value to the separately launched P6 report process. Audit the actual report
  path through `modules/report/main.nf`, `scripts/p6_report.py` and
  `scripts/src/report/report.py` when correcting the reported cap.

## Objective

Give analysts additional context when the first 500 hits are all very similar,
while bounding retrieval and downstream work. The agreed behavior is:

1. Run BLAST once with `-max_target_seqs` set from the renamed Nextflow
   parameter `blast_max_target_seqs` (default 2000, integer >= 1),
   leaving `-perc_identity` unset. This parameter
   will control retrieval, parser selection limit and reported search cap.
2. Compute each retrieved hit's aggregate identity using Taxodactyl's existing
   calculation, then sort by that identity descending.
3. Retain the first 500 hits, or all available hits if fewer exist.
4. If the last retained hit has aggregate identity **greater than the effective stopping threshold**,
   append another block of up to 500. Repeat until that last identity is
   **at or below that threshold**, or the available hits/cap are exhausted.
5. Keep the entire stopping block, including hits below the threshold.

**The stopping threshold defaults to 0.935 (93.5%).** It is a block stopping
condition, not an individual-hit exclusion filter. Its configuration source
is the independent `blast_context_min_identity` parameter (see decision below). Candidate
eligibility remains a separate operation even if it shares `min_identity`.

For each query, the implementation must be equivalent to:

```python
# stopping_identity is supplied by the chosen configuration option below
# hits have already been stably sorted by aggregate identity, descending
available = min(len(hits), max_target_seqs)  # configured cap, default 2000
end = min(500, available)
while end < available and hits[end - 1]["identity"] > stopping_identity:
    end = min(end + 500, available)
retained = hits[:end]
```

This also defines replay behavior for XML containing more hits than the
configured cap: selection is limited to that cap in aggregate-identity order.
That parser limit does not reproduce how BLAST would have limited the original
search. A cap below 500 limits the first block; a cap not divisible by 500
allows a partial final block. The cap does not change block size or threshold.

## Retrieval and downstream consequences

### What does BLAST's “top” mean?

BLAST selects/ranks matches using alignment significance and scoring, rather
than Taxodactyl aggregate percent identity. Lower E-values indicate stronger
statistical significance; a longer lower-identity alignment can outrank a
short high-identity alignment. The [NCBI manual](https://www.ncbi.nlm.nih.gov/sites/books/NBK279684/)
defines `max_target_seqs` as a retained sequence limit and describes database
sequence order as the tie breaker. BLAST uses heuristic search and retention;
2000 returned hits are not a guarantee of the globally highest-identity 2000
sequences in the database. Python sorting only orders hits actually retrieved.

Record the pinned runtime's version and relevant `blastn -help` descriptions
with validation evidence. Do not equate its XML rank with the sum of HSP bit
scores or aggregate identity calculated by this parser. The formatting option
`-sorthits` is ignored for XML formats above 4 in the
[NCBI implementation](https://www.ncbi.nlm.nih.gov/IEB/ToolBox/CPP_DOC/doxyhtml/blast__args_8cpp_source.html),
so sorting and block selection belong in Python. No BLAST identity cutoff or
new HSP/coverage filter is needed for this task.

### Which hits proceed, and can query counts differ?

Yes, with the default cap, counts vary independently by query: 500, 1000,
1500 or 2000,
with partial final blocks when results run out and zero when no hits exist.
The first block is retained even if all its hits are below the effective stopping threshold.

| Stage | Input and consequence |
|---|---|
| P1 parsing | Inspect all retrieved hits to calculate identity and choose the retained blocks. Keep raw XML as retrieval evidence. |
| Taxonomy lookup | `accessions.txt` contains the unique union of retained hit accessions across queries. Discarded hits do not add lookup work. |
| P3 screening | All retained hits are available to `scripts/p3_assign_taxonomy.py`; its alignment-length/coverage, identity and species-selection logic still determines downstream eligibility. |
| Candidate summaries | Selected-species summaries can include lower-identity hits for those species. Additional context can change hit counts, minimum/median identity and flags. |
| Phylogeny | `_get_accessions_for_phylogeny` samples from coverage/length-filtered hits, including context outside selected candidate species. Existing per-species and overall selection rules apply; the current overall maximum is soft because it is checked before adding a species. |
| P4/P5 and report | `scripts/p4_source_diversity.py` and `scripts/p5_db_coverage.py` consume their existing downstream inputs. `scripts/src/report/report.py` reads the retained `all_hits.json` for the BLAST table. Candidate or tree changes may affect later conclusions. |

Retaining more hits therefore does not mean aligning every retained sequence
or making every hit a candidate. It does mean more taxonomy/screening work and
potentially different scientific outputs. Validate those effects without
changing downstream eligibility or sampling rules as part of this task.

## File-by-file impact map

“Required edit” means this task changes that file's behavior or descriptions.
“Reuse / validate” means an existing interface already fits; edit only if the
integration checks expose a concrete gap. Downstream consumers receive different
records, but do not need new selection algorithms.

### Nextflow modules and workflow

| File | Change category | Impact |
|---|---|---|
| `modules/blast/blastn/main.nf` | Required edit | Replace hard-coded `-max_target_seqs 500` with `params.blast_max_target_seqs`; leave `-perc_identity` unset. |
| `modules/extract/hits/main.nf` | Required edit | Read the renamed cap and pass it to P1 as `--blast-max-target-seqs`; also pass the chosen threshold setting. Verify non-default values and invalid-value handling; the returned JSON/FASTA/accessions now contain selected blocks. |
| `modules/report/main.nf` | Required edit | Pass the same parameter explicitly to P6 as `--blast-max-target-seqs`; P6 runs separately from P1. |
| `workflows/taxodactyl.nf` | Reuse / validate | Existing channels carry retained hit files and accession lists. Verify per-query routing with different retained counts; no new channel or workflow branch is planned. |
| `modules/blast/blastdbcmd/main.nf` | Downstream validation | Looks up taxonomy IDs for the unique retained accession union; potentially more lookups. Existing command/interface suffices. |
| `modules/extract/taxonomy/main.nf` | Downstream validation | Receives the resulting taxid list and runs P2; potentially more taxonomy rows. |
| `modules/extract/candidates/main.nf` | Downstream validation | Runs P3 on retained hit bundles; candidate and phylogeny outputs may change. |
| `modules/mafft/align/main.nf`, `modules/fastme/main.nf` | Downstream validation | Operate on P3's sampled phylogeny sequences, not all retrieved hits. Sequence membership and resulting trees may change. |
| `modules/evaluate/sourcediversity/main.nf`, `modules/evaluate/databasecoverage/main.nf` | Downstream validation | Existing P4/P5 processes consume candidate-derived outputs; results and cost may change as candidates change. |

### Python entry points and supporting modules

| File | Change category | Impact |
|---|---|---|
| `scripts/p1_parse_blast.py` | Required edit | Reuse its existing cap argument, pass the effective cap into the parser, and write JSON/FASTA/accessions from the selected records. Update CLI help to describe its selection role. |
| `scripts/src/blast/parse_xml.py` | Required edit | Accept the cap and effective stopping threshold, perform per-query aggregate-identity sorting and 500-hit block selection, preserve hit-to-FASTA associations, and log retrieved/retained counts. |
| `scripts/p6_report.py` | Required edit | Accept `--blast-max-target-seqs` using the existing mapping and apply it to P6 configuration before rendering. |
| `scripts/src/utils/config/schema.py` | Required edit | Constrain the existing `blast_max_target_seqs` field to a positive integer for standalone Python as well as Nextflow use. Ensure fractional values cannot be silently coerced/truncated along the CLI/config path. |
| `scripts/src/utils/config/mappings.py` | Reuse / validate | The `blast-max-target-seqs` mapping already exists. Reuse it in P1/P6; inspect conversion/validation behavior before introducing any additional mapping. |
| `scripts/src/report/report.py` | Reuse / validate | Already reads `all_hits.json` and exposes `hits` and `config` to templates. Verify the count comes from retained hits and the cap comes from P6's effective configuration; edit only if necessary. |
| `scripts/p2_extract_taxonomy.py` | Downstream validation | Resolves taxonomy for retained accessions through its existing taxid input. |
| `scripts/p3_assign_taxonomy.py` | Downstream validation | Screens the retained set, computes candidate counts/minimum/median identity, and samples phylogeny sequences. Preserve its existing eligibility and sampling rules. |
| `scripts/p4_source_diversity.py`, `scripts/p5_db_coverage.py` | Downstream validation | Process existing candidate-derived inputs; inspect changed conclusions and runtime without adding the block algorithm here. |

### Templates and configuration

| File | Change category | Impact |
|---|---|---|
| `scripts/src/report/templates/components/results/1a-blast-hits-modal.html` | Required edit | Explain selected blocks, show retained count, and correct rank wording to aggregate-identity order. |
| `scripts/src/report/templates/macros/db-coverage-target-modal.html` | Required edit | Distinguish the effective retrieval cap, retained context and candidate eligibility. |
| `conf/params.config`, `nextflow_schema.json` | Required edit | Rename the parameter to `blast_max_target_seqs`, preserving default 2000 and the positive-integer constraint; update its documented role from reporting-only to retrieval/selection/reporting. |
| `scripts/config/default.yml` | Reuse / validate | Already defaults `blast_max_target_seqs` to 2000; keep it aligned with the Nextflow default. |

The specification/documentation edits and validation files are listed in their
sections below. This map describes planned implementation; no runtime modules
have been edited while preparing this brief.

## Implementation

### 1. Rename the cap and increase retrieval

Rename `blast_max_target_seqs_for_report` to `blast_max_target_seqs` in
`conf/params.config` and `nextflow_schema.json`, including schema error messages.
Update `modules/extract/hits/main.nf` to read the renamed parameter. Python's
`blast_max_target_seqs` field and `--blast-max-target-seqs` CLI already match;
reuse them. Use the new name throughout active configuration, code and docs.
Document the migration for existing command lines and parameter files. A
compatibility alias is not part of this brief; do not add a second effective
cap. Historical report artifacts may retain the original name; refresh expected
reports when regenerated as validation evidence.

In `modules/blast/blastn/main.nf`, replace the hard-coded limit with
`-max_target_seqs ${params.blast_max_target_seqs}`. Keep the existing
2000 default and integer >= 1 validation in `conf/params.config` and
`nextflow_schema.json`. Preserve the other search settings, XML output,
compressed-input handling and version recording. Leave `-perc_identity` unset. Blocks operate on this one
retrieval result; they do not trigger repeated BLAST searches.

### 2. Select blocks and preserve output associations

1. Implement the objective's per-query selection in
   `scripts/src/blast/parse_xml.py`, after aggregate identity calculation and
   stable sorting. Use existing stored identity values:
   `round(sum(hsp.identities) / sum(hsp.align_length), 3)`, capped at 1 for
   valid positive-length alignments. This is a length-weighted aggregate over
   all HSPs, not an average of HSP percentages or a best-HSP identity.
   Compare those rounded values at block boundaries; equality stops expansion.
   Pass the configured cap and effective stopping threshold from
   `scripts/p1_parse_blast.py` into the parser;
   reuse its existing `--blast-max-target-seqs` argument and the wiring in
   `modules/extract/hits/main.nf`. Validate positive integer caps for standalone
   Python use as well as Nextflow runs; reject zero, negative and fractional
   values rather than silently falling back to a default.
2. Preserve each hit's association with its original FASTA record while sorting
   and selecting. Filter FASTA records by selected original hit positions or
   another unambiguous association, rather than slicing the unsorted FASTA
   list or relying solely on accession membership. Preserve retained FASTA
   records' relative BLAST order and existing sequence content (P1-012).
   Keep all HSP details for each selected hit and stable BLAST order for tied
   identities. Do not extend block boundaries to include additional ties.
3. In `scripts/p1_parse_blast.py`, ensure `all_hits.json`, `all_hits.fasta` and
   `accessions.txt` derive from the same selected records. JSON keeps aggregate
   identity order; FASTA keeps the relative order described above; accessions
   remain unique across queries. Preserve existing filenames, query folders,
   top-level JSON schema and zero-hit output behavior. The published
   `blast_result.xml` remains the complete raw retrieval output.
4. Log per-query retrieved and retained counts, minimum retained aggregate
   identity when present, and whether the threshold or retrieval/selection
   limit ended expansion. Confirm the retained bundles flow through
   `workflows/taxodactyl.nf`, `modules/blast/blastdbcmd/main.nf`,
   `modules/extract/taxonomy/main.nf` and `modules/extract/candidates/main.nf`.
   Keep selection confined to the BLAST path.

### 3. Make reports describe the actual selection

1. Update `scripts/src/report/templates/components/results/1a-blast-hits-modal.html`
   to describe retained context, show its actual count, and explain the
   500-hit blocks and effective aggregate stopping threshold (93.5% by
   default), rendered from configuration. Correct the rank
   tooltip: the table position is aggregate-identity rank among retained hits.
2. Update `scripts/src/report/templates/macros/db-coverage-target-modal.html`
   so it distinguishes the configured retrieval limit from retained context and
   candidate eligibility. A capped search may miss other useful hits;
   reaching the configured threshold is not guaranteed. Avoid claiming every retained hit meets
   candidate criteria or that BLAST retrieved the globally top identity hits.
3. Pass the same `params.blast_max_target_seqs` value directly to
   P6 from `modules/report/main.nf`. Add support for the existing Python
   `--blast-max-target-seqs` CLI mapping to `scripts/p6_report.py`, using
   `scripts/src/utils/config/mappings.py` and the `blast_max_target_seqs` field
   in `scripts/src/utils/config/schema.py`. Ensure
   `scripts/src/report/report.py` renders that effective value. P1's
   in-process configuration does not propagate to P6. Keep the Python default
   in `scripts/config/default.yml` aligned at 2000 and validate non-default
   values end to end. Pass the effective stopping-threshold setting to P6
   as well, using the option selected below, so report wording agrees with P1.

## Documentation and configuration

- Update `docs/detailed_tech.md`, `docs/params.md` and the P1 description in
  `scripts/README.md` to explain retrieval versus block selection, per-query
  counts and downstream use. Update relevant parameter descriptions in
  `conf/params.config` and `nextflow_schema.json` consistently. Remove the
  obsolete reporting-only description of the maximum-hit parameter:
  it now changes search results and downstream analysis. Document that
  existing non-default values now affect retrieval, with 2000 remaining the
  default. Document migration from `blast_max_target_seqs_for_report` to
  `blast_max_target_seqs` in `docs/params.md`.
- Update `spec/nextflow/processes.md` (including NF-PR-030),
  `spec/nextflow/params.md`, `spec/python/p1-parse-blast.md` and
  `spec/contracts/hits.md` with the changed scientific/output behavior.
  Resolve NF-D-005 in `spec/defects.md` and its specification references only
  once the effective retrieval cap and actual rendered report agree.
- Keep the renamed cap at default 2000 and block size at 500. Implement and
  document the chosen stopping-threshold option below, default 0.935. Preserve
  candidate eligibility and phylogeny selection algorithms.

## Decision — stopping threshold

Use independent `blast_context_min_identity`, default 0.935 and range 0–1.
The user selected this option on 31 October 2026 pending client verification;
`min_identity` continues to control candidate eligibility independently.
Wire `--blast-context-min-identity` / `BLAST_CONTEXT_MIN_IDENTITY` through
configuration, P1 selection and P6 reporting. Validate finite values, including
zero, and render the effective threshold in reports. Client feedback may lead
to a later change; it does not block this implementation.

## Validation

Use the project Python environment and edited source. For workflow checks,
ensure the container uses the edited scripts (a development bind or rebuilt
image); the stock image in `conf/process.config` does not include local edits.
New automated test files are optional; record reproducible validation evidence.

1. Run the existing parser and phylogeny checks from the repository root with
   the project interpreter and dependencies:
   `PYTHONPATH=.:scripts python -m unittest scripts.tests.test_blast_parser scripts.tests.test_phylogeny_sampling`.
2. Exercise block selection with controlled hit lists or XML. In these cases,
   identities refer to the stored rounded aggregate values and the cap is
   the default 2000 and stopping threshold 0.935 unless specified otherwise:

   | Retrieved hits / boundary condition | Retained count |
   |---|---:|
   | No hits | 0 |
   | 37 hits, any identities | 37 |
   | 2000 hits all below 0.935 | 500 |
   | 500th hit exactly 0.935 | 500 |
   | 500th hit above 0.935; 1000th at or below | 1000 |
   | 600 above 0.935, followed by 600 below | 1000 |
   | 80 above 0.935 among 2000 | 500 |
   | First boundary at or below 0.935 is hit 1500 | 1500 |
   | 2000 hits all above 0.935 | 2000 |
   | 750 hits, first 500 above 0.935 | 750 |

   Include near-threshold rounding, ties across block boundaries, a partial
   final block, shuffled XML order, more than 2000 replay hits, and multiple
   queries selecting different counts. Include a multi-HSP boundary hit whose
   aggregate identity differs from its first/best HSP. Confirm the complete
   stopping block and its HSP evidence survive selection. Also check caps of
   1, 300, 750 and 2500: with enough hits all above the threshold, retain
   exactly the cap, including a partial last block. With cap 2500 and hit 500
   at or below threshold, retain 500. Reject zero, negative and fractional caps.
   Also validate a non-default stopping threshold (for example 0.95), equality,
   endpoints 0 and 1, and rejection of out-of-range/non-finite values. Changing
   `min_identity` alone must not change P1 block selection; changing
   `blast_context_min_identity` alone must not change the candidate eligibility
   threshold. Verify P6 displays the actual stopping threshold in each case.
3. Compare selected record membership across JSON and FASTA, including repeated
   accessions if present, and verify `accessions.txt` equals the unique retained
   union across queries. Verify accession lookup and P3 receive that selection.
   Check candidate summaries, flags and phylogeny membership before/after;
   explain changes caused by added context rather than updating snapshots blindly.
4. Follow `docs/nf-tests.md` and `test/core/README.md` for
   `test/core/taxodactyl.workflow.nf.test`, supplying local values for the
   placeholders in `test/core/nextflow.config`. Inspect the generated BLAST
   command and rendered report, including count/rank descriptions. For both
   the default and a non-default cap, verify that the BLAST command, P1
   argument/selection limit and P6 reported cap all agree under the new name.
   Verify schema/help and captured parameters use `blast_max_target_seqs`,
   and validate migration of a legacy parameter file. Captured XML can validate parsing
   and reporting, but live BLAST is required to validate retrieval changes.
5. Benchmark 500 versus 2000 retrieval on the same queries, database version,
   BLAST version, threads and search settings. Include a query with more than
   500 hits, a sparse query and a query whose retained boundary reaches 93.5%.
   Record search and downstream elapsed time, peak memory where available,
   XML size, retrieved/retained counts and changes to scientific outputs.
   Compare shared hit membership rather than assuming the new search merely
   appends hits. Record commands, data versions and results in this brief.
   If runtime/data is unavailable, identify outstanding live checks explicitly;
   do not claim replay proves search performance or mark the work fully validated.

## Dependencies and parallel opportunities

The independent threshold decision is recorded above. Retrieval and parser edits can
proceed independently against the agreed
algorithm; report corrections depend on the retained-output contract. Finish
with combined workflow validation and benchmarking. Coordinate overlapping
files with active task branches before implementation. No other numbered task
is a stated functional prerequisite.

## Completion criteria

- The live command, parser and report use the same validated maximum-hit
  `blast_max_target_seqs` parameter (default 2000), without a BLAST identity cutoff.
- The threshold decision is recorded and implemented consistently in P1/P6
  configuration and documentation, with non-default behavior validated.
- Each query follows the specified 500-hit block algorithm using aggregate
  identity, retaining the whole stopping block and handling empty/partial input.
- Selected record membership agrees across JSON, FASTA and accession lookup;
  downstream analysis and the report use the retained set.
- Reports show accurate retained counts, ranking and retrieval limits, including
  when the configured cap is reached before the identity threshold.
- Specifications and documentation match implementation; parser/phylogeny checks,
  workflow evidence and benchmark results are recorded with differences explained.
- On completion, move the brief to `tasks/completed/` and remove its entry from
  the lifecycle index used when implementation finishes.

## Risks and limits

- Neither the configured cap nor block selection guarantees finding every useful hit
  or a hit at the configured stopping threshold. Added context can change scientific results and costs.
- The stopping comparison uses the existing three-decimal aggregate identity.
  Preserve that convention and document its rounding boundary; changing the
  identity definition or precision is outside this task.
- The existing zero-total-HSP-length calculation divides before checking for
  zero. Do not describe that guard as working or confuse malformed alignments
  with a query containing no hits. Record any such fixture failure separately;
  this task does not require a general parser repair. The last-HSP FASTA defect
  P1-D-001 and existing empty/no-candidate workflow defects are also separate.

## Outcomes

Implementation committed on branch `task-04-expand-blast-hit-context` in
`.worktrees/task-04-expand-blast-hit-context`. Status remains **active**, pending
successful end-to-end validation; do not move this brief to completed yet.

### Implemented

- Renamed the Nextflow cap to `blast_max_target_seqs`, default 2000, and wired
  it to live BLAST, P1 selection and P6 reporting. Legacy overrides require the
  documented rename; no compatibility alias was added.
- Added independent `blast_context_min_identity`, default 0.935, with YAML,
  environment and CLI mappings. The user selected this pending client review.
- Added per-query stable aggregate-identity block selection, preserving whole
  final blocks, all retained HSPs and original hit/FASTA associations (including
  duplicate accessions). Logs include counts, minimum identity and stop reason.
- Validated caps without fractional truncation and finite thresholds in [0, 1]
  at schema, CLI/environment mapping and direct-parser boundaries. Zero
  thresholds pass through Nextflow explicitly.
- Updated report count/rank/context wording, specifications and migration docs.
  Existing candidate eligibility and phylogeny sampling algorithms are unchanged.

### Validation completed (31 October 2026)

- Full Python unit discovery: **155 tests run: 153 passed, 2 skipped**. Command from the
  worktree: `python -m unittest discover -s scripts/tests -p 'test_*.py'` with
  `PYTHONPATH=.:scripts`, using Python 3.12 in
  `/mnt/data/images/neoformit-taxodactyl-v1.5.0.img`, mounting edited scripts at
  `/app/scripts` and the worktree at `/workspace`. The image lacked `fakeredis`;
  installed it only under `/tmp/task04-validation/test-deps` for the full run.
  Earlier focused parser/context/phylogeny/config run: 35 tests passed.
- `scripts/tests/test_blast_context.py` covers block boundaries, caps below 500,
  partial blocks, excess XML hits, tied identities, repeated accessions,
  multi-HSP aggregate identity, rounding, empty queries, non-default thresholds
  and invalid settings. Syntax/name checks (`flake8 --select E9,F63,F7,F82`) and
  `git diff --check` passed.
- Actual P1 CLI output checks verified JSON/FASTA membership and accession union.
  Actual P6 argument parsing/config updates plus rendering the modified BLAST
  modal passed at cap/threshold pairs 2000/0.935, 750/0.95 and 300/0. The selected
  counts were [1000, 500, 500], [750, 500, 500] and [300, 300, 300] respectively.
- Live BLAST **2.16.0+**, four threads, same local reference subset and search
  settings, compared 500 and 2000 retrieval. The pinned help confirms `-sorthits`
  is not applicable to XML (`outfmt > 4`). No `-perc_identity` was supplied.
  Commands, data identity, per-query candidates/flags/phylogeny membership and
  measurements are in `tasks/validation/04_blast_hit_context.json`.

| Query | Retrieved at cap 500 / 2000 | Retained at cap 500 / 2000 |
|---|---:|---:|
| Scenario_01 | 500 / 2000 | 500 / 1000 |
| Scenario_02 | 500 / 2000 | 500 / 500 |
| Scenario_03 | 500 / 2000 | 500 / 500 |
| Grapevine virus E (barcode 57) | 170 / 170 | 170 / 170 |

Candidate summaries and P3 flags were unchanged in these four cases.
Scenario_01 phylogeny input expanded from 9 to 21 sequences; the other three
were unchanged (24, 29 and 6). Shared hit membership was checked for the first
three queries: each larger retrieval included all original 500 accessions.
XML grew from 4,669,752 to 18,393,324 bytes. P1/P3 wall time was 12.07 versus
16.70 seconds, including interpreter startup. Search time was 11.82 versus
4.84 seconds, peak RSS 3,966,868 versus 4,001,164 KiB. These single trials had
different filesystem cache states and concurrent host work; they demonstrate
output/cost scope, **not** a search speedup or production performance guarantee.

### Integration limits and follow-up

- Ran `nf-test test -c /tmp/task04-validation/nf-test.config --ci
  test/core/taxodactyl.workflow.nf.test` with local containers and edited scripts
  bound into `/app/scripts`. The first attempt failed because the local override
  had not propagated `TAXONKIT_DATA`; the corrected retry passed live BLAST,
  P1, taxonomy lookup and all 20 P3 tasks. Retained counts ranged from 2 to 1000.
  Actual generated BLAST/P1 commands used the same cap 2000 and threshold 0.935.
- **Correction (3 November 2026):** the earlier missing-helper diagnosis was
  incorrect. `modules/fastme/main.nf:28` renames tree tips inline using `awk`
  and `sed` with the supplied ID mapping file. This is also the implementation
  in commit `55be0e3`; it does not call or require `rename_tip_labels.py`.
  The standalone attempt to execute that nonexistent helper was an erroneous
  validation step, not evidence of a workflow defect. No helper needs to be
  restored or provisioned.
- The retry was deliberately interrupted during live coverage lookups because
  of that incorrect diagnosis, before the workflow could finish. It is
  therefore **not a passing nf-test run**, but it does not demonstrate a
  FastME helper failure either. No snapshots were refreshed. Rerun the workflow
  with the intended reference-data versions to finish integration validation.
- Standalone full-report validation with a real FastME tree and manually mapped
  validation-only tip labels also cannot establish the full workflow: missing
  P5 output makes the existing `index.html` access to `db_coverage.full` fail
  with an Undefined serialization error. No synthetic coverage data was supplied.
  The changed modal and P6 effective settings did pass independently above.
- Complete P4/P5/report integration, non-default Nextflow report verification,
  downstream runtime measurement and expected-snapshot reconciliation remain
  outstanding. The local BLAST subset is April 2026, while the core snapshot
  documents July 2026 reference data; explain reference drift separately from
  the intentional selection change.
- Detailed logs and standalone validation scripts remain in
  `/tmp/task04-validation/` on this host. No extension hooks were registered
  (`.specify/extensions.yml` absent). The active branch/worktree record remains
  on main and must remain until the implementation has been validated and merged.
