# Task 04 — Preserve all BLAST hits and select context in 500-hit blocks

**Status:** active

**Priority:** Unassigned; DAFF enhancement.

**Issue:** [#160 — Consider blast hits down to 93.5% identity for better context](https://github.com/qcif/taxodactyl/issues/160)

**Scope:** Rename the retrieval cap to `blast_max_target_seqs` (default 2000),
extract every XML hit into `all_xml_hits.json`, then derive
separate `all_hits.json` / `all_hits.fasta` using 500-hit blocks.
Publish `all_hits.*`; keep `all_xml_hits.json` as an internal workflow artifact.
All downstream analysis and reporting use selected hits only. Complete hits
remain available internally for extraction/selection inspection.

**Source material:** Existing issue discussion through 29 October 2025;
user correction on 3 November 2026 requiring complete extraction followed by
separate selection, and explicit confirmation to keep the 500-hit block rule;
`spec/python/p1-parse-blast.md`, `spec/contracts/hits.md`,
`spec/python/p3-assign-taxonomy.md`, `spec/python/p6-report.md`,
`spec/nextflow/processes.md`, and `spec/nextflow/params.md`.

## Preconditions

- Update this existing task, preserving number 04 and its entry in
  `tasks/active.md`. Its implementation worktree is
  `.worktrees/task-04-expand-blast-hit-context`; reconcile any implementation
  there against this corrected contract before continuing it.
- No active Spec Kit feature design directory is configured. Use the existing
  `spec/` documents, source and tests rather than synthesizing feature files.
  `.specify/memory/constitution.md` is an unfilled template.
- Baseline `modules/blast/blastn/main.nf` uses `-max_target_seqs 500`,
  `-task megablast`, XML output (`-outfmt 5`), `-evalue 0.05`, `-reward 1`
  and `-penalty -3`. `conf/process.config` pins BLAST 2.16.0.
- Baseline P1 extracts all XML hits without coverage or identity filtering.
  `scripts/src/blast/parse_xml.py` computes aggregate identity and stably sorts
  JSON hits by it; FASTA records retain BLAST order.
- `blast_max_target_seqs_for_report` currently defaults to 2000 and is passed
  to P1, but does not control BLAST or parsing. P1's configuration changes do
  not propagate to the separately launched P6 process.

## Objective

The complete extraction is an inspectable record, independent of subsequent
selection. Never overwrite `all_xml_hits.json` with a selected subset. This
internal JSON contains every hit present in the supplied XML, not every
database match. The established downstream filename `all_hits.*` now means
all block-selected hits available for downstream evaluation, not all XML hits.

1. Run BLAST once with `-max_target_seqs` from `blast_max_target_seqs`
   (default 2000, integer >= 1). Leave `-perc_identity` unset.
2. Extract every retrieved hit and its HSP evidence. Calculate identity using
   the existing length-weighted aggregate, rounded to three decimals, and
   sort JSON hits descending with stable BLAST-order ties.
3. Write the complete `all_xml_hits.json` before deriving a
   separate selected set. Coverage/length and identity eligibility filters
   must not remove records from the complete extraction.
4. Select an initial block of up to 500 hits in aggregate-identity order.
   If its last hit is above the effective stopping threshold (default 0.935),
   append another block, until the last retained identity is at or below the
   threshold or available hits/the configured cap are exhausted.
5. Keep the whole stopping block, including below-threshold hits. This is a
   block stopping condition, not a per-hit minimum-identity exclusion filter.
6. Use the selected set for every downstream consumer, including taxonomy,
   candidate evaluation and reporting. Keep the complete set and calculated
   identities internal to extraction/selection for inspection in work files.

For each query, after complete extraction and stable identity sorting:

```python
all_xml_hits = parsed_query["hits"]  # complete; never truncate or mutate membership
available = min(len(all_xml_hits), max_target_seqs)
end = min(500, available)
while end < available and all_xml_hits[end - 1]["identity"] > stopping_identity:
    end = min(end + 500, available)
all_hits = all_xml_hits[:end]  # downstream selected set
```

Replay XML may contain more hits than the cap. Preserve every one in
`all_xml_hits.json`; apply the cap only to selection. This replay cap does not
reproduce which records a capped live BLAST search would retrieve.

## Output and consumer contracts

| Artifact | Membership and purpose |
|---|---|
| `blast_result.xml` | Complete raw retrieval evidence. |
| `query_*/all_xml_hits.json` | Every XML hit, original top-level query schema and full HSP evidence, sorted by calculated identity. Internal only; not published. |
| `query_*/all_hits.json` | Same query/hit schema, containing only block-selected hits, sorted by identity. Published. |
| `query_*/all_hits.fasta` | Corresponding selected records in relative BLAST order. Published. |
| `accessions.txt` | Unique union of selected-hit accessions across queries; the only accession list, used for downstream taxonomy lookup. |

Do not produce a separate selection-decision file or a complete-set accession
list. `accessions.txt` is generated after block selection and contains only
selected accessions. Selection runs in P1 in this implementation.

Selection must preserve an exact prefix of the stably identity-sorted complete
list. Validate this internally, using original hit positions to preserve
JSON/FASTA associations even when accessions repeat. Preserve the existing
complete JSON schema. Log complete/selected counts, effective cap/threshold
and termination reason in the selection process; do not add an audit artifact.

Every downstream BLAST consumer uses `all_hits.*` or outputs derived
from it. P3 reads selected JSON/FASTA; P6 reads selected JSON for its BLAST
table. Taxonomy lookup uses the selected-only `accessions.txt`. Candidate
outputs remain based on P3's existing coverage/length, identity and
species-selection rules. A block-selected hit is not necessarily a candidate.

`all_xml_hits.json` is internal to extraction and selection, not an input to P2/P3,
P4/P5, phylogeny or P6. Do not stage it to those processes or publish it.
Internal work files allow comparison of complete and selected hits; the
report does not show hits excluded by block selection. Selection runs in P1
before emitting the selected-only downstream bundle.

## Implementation

**Provisional architecture and working filenames:** Use `all_hits.json` /
`all_hits.fasta` for selected downstream hits and `all_xml_hits.json` for complete
internal extraction for now. Final hit filenames remain open to discussion.
Selection remains within P1 as recorded below; preserve the existing
downstream interfaces. Complete extraction
into `all_xml_hits.json` and taxonomy lookup on selected accessions are fixed
requirements of this implementation. The accession-list filename is fixed
as `accessions.txt`, containing only selected accessions.

### 1. Preserve complete extraction and derive selection

- In `scripts/src/blast/parse_xml.py`, retain the existing complete parser
  output. Implement selection as a separate helper/operation after parsing,
  without truncating the parser's complete lists. Reuse stored identity:
  `round(sum(hsp.identities) / sum(hsp.align_length), 3)`, capped at 1 for
  positive-length alignments. Do not replace it with best-HSP identity.
- In `scripts/p1_parse_blast.py`, write the complete internal JSON, then derive and
  write selected assets and the single selected-only `accessions.txt`. Preserve all HSPs, stable ties and
  original FASTA content/order. Do not extend blocks to include tied records.
  Write empty selected JSON and an empty selected FASTA
  when selection is empty. Preserve existing complete-set zero-hit behavior;
  `modules/extract/hits/main.nf` still ensures the downstream `all_hits.fasta`
  exists. Complete extraction with no hits still produces internal JSON
  containing an empty hit list. Do not create a complete-extraction FASTA.
- Keep the existing `hits_json` / `hits_fasta` defaults and readers pointing
  to `all_hits.json` / `all_hits.fasta`. P1 writes the selected set to those
  established paths; downstream readers need no filename migration. Add
  internal complete-file name `all_xml_hits.json` in
  P1 or, if configurable, `scripts/config/default.yml` and
  `scripts/src/utils/config/schema.py`. Update
  `scripts/src/utils/config/config.py` / `scripts/src/utils/config/mappings.py`
  only if needed to support those internal settings, not to introduce new
  selected-file readers.
- Log complete and selected counts, minimum selected identity when present,
  effective configuration and termination reason. Changing selection settings
  on the same XML must not change complete-set content.

### 2. Wire retrieval and downstream consumers

- Rename `blast_max_target_seqs_for_report` to `blast_max_target_seqs` in
  `conf/params.config` and `nextflow_schema.json`; default 2000. Use it in
  `modules/blast/blastn/main.nf`. Preserve other BLAST settings and version
  recording. Blocks do not trigger repeated BLAST searches.
- In `modules/extract/hits/main.nf`, pass the cap and effective threshold to P1.
  Emit selected JSON/FASTA for downstream staging. Keep complete JSON local
  to extraction; it is not a Nextflow downstream output.
  Publish only the selected JSON/FASTA, plus the single selected-only
  `accessions.txt`; do not publish `all_xml_hits.json`.
  Update `conf/process.config` file-name bindings where needed. Audit all
  downstream staging and publish rules so complete files cannot enter
  analysis/report bundles or published output through wildcard patterns. Selected files must remain
  published even if later analysis fails. Complete files remain in work
  directories for internal inspection only.
- Update `workflows/taxodactyl.nf` to carry the selected-only per-query bundle by
  query identity and route `accessions.txt` to
  `modules/blast/blastdbcmd/main.nf`. Verify
  `modules/extract/taxonomy/main.nf` receives the resulting taxid list.
- Preserve the existing hit filenames and readers in
  `modules/extract/candidates/main.nf` and `scripts/p3_assign_taxonomy.py`:
  `all_hits.*` already contains only the selected set when staged downstream.
  Validate routing rather than adding filename remapping or new readers.
  Preserve BOLD behavior and P3's existing eligibility/sampling algorithms.
- Validate `modules/mafft/align/main.nf`, `modules/fastme/main.nf`,
  `scripts/p4_source_diversity.py` and `scripts/p5_db_coverage.py` with their
  existing downstream inputs. Retaining more context can change candidates,
  summaries, flags and tree membership; it does not mean aligning every hit.

### 3. Report only selected hits

- In `scripts/src/report/report.py` and
  `scripts/src/report/templates/components/results/1a-blast-hits-modal.html`,
  keep the existing `all_hits.json` reader and render only block-selected hits with their calculated
  aggregate identity. Display the selected count, effective threshold, cap
  and block rule. Define table rank as aggregate-identity rank among selected
  hits, not BLAST score rank. Do not add All / Selected / Excluded views or
  read complete extraction to derive excluded rows or counts.
- Distinguish block selection from P3 candidate eligibility. Below-threshold
  hits in the final selected block remain in the BLAST table; selection does
  not itself mean they meet candidate criteria.
- Update `scripts/src/report/templates/macros/db-coverage-target-modal.html`
  to distinguish the retrieval cap, selected context and candidate eligibility.
  Explain that retrieval may exhaust without reaching the stopping threshold;
  do not present the selected count as the total XML hit count.
- In `modules/report/main.nf` and `scripts/p6_report.py`, pass the same effective
  cap and threshold used by selection. Stage only selected hit files through
  `workflows/taxodactyl.nf` to P6. Keep complete hits/counts and termination
  details in extraction/selection work files and logs for internal inspection.
- Publish selected JSON/FASTA. Complete internal JSON must not be published or
  read by the report, even as a fallback for missing selected files.

## Documentation and configuration

- Update `docs/detailed_tech.md`, `docs/params.md`, `scripts/README.md`,
  `spec/python/p1-parse-blast.md`, `spec/contracts/hits.md`,
  `spec/python/p3-assign-taxonomy.md`, `spec/python/p6-report.md`,
  `spec/python/shared/config.md`, `spec/nextflow/processes.md` and
  `spec/nextflow/params.md` to describe complete extraction, separate block
  selection, artifacts, selected-only consumer routing and report content.
  Explicitly document that `all_hits.*` now contains the selected set, while
  complete extraction is preserved internally as `all_xml_hits.json`.
- Document parameter migration and that the cap now controls retrieval and
  selection, while replay extraction always preserves every XML hit. Resolve
  NF-D-005 in `spec/defects.md` only when live retrieval and report agree.
- Validate the cap as an integer >= 1 across CLI/config/Nextflow paths; reject
  zero, negative and fractional values. Preserve three-decimal identity and
  block size 500. Validate thresholds as finite numbers in [0, 1], including
  zero, using the configuration decision below.

## Open decision — hit artifact filenames

**Status: open to discussion.** This brief uses `all_xml_hits.json` as the
working name for the complete internal extraction (JSON only),
and `all_hits.json` / `all_hits.fasta` as working names for the selected,
published downstream set. Use these names for now; final naming remains
open and does not block implementation with the working names.

Preserve the distinction between complete internal extraction and selected
downstream inputs regardless of the final names. If names change, update
producer/consumer configuration, staging, publishing, documentation and
validation consistently. Document the membership of each file explicitly.
The accession-list name remains `accessions.txt`, containing only selected
accessions. No second accession list is required.

## Implementation decisions carried forward

Selection remains a separate Python operation within P1/`EXTRACT_HITS`,
following the existing task-04 implementation and the user's request to keep
changes concentrated in P1. P1 writes complete internal JSON before selection,
then writes the selected files under the existing downstream names. No new
Nextflow process is introduced. Sequence associations remain in memory; no
complete-extraction FASTA or selection-decision file is written.

The existing independent `blast_context_min_identity` setting (default 0.935)
is retained. The prior implementation outcomes record that the user selected
this option pending client review. This revision does not reopen or change
that configuration choice. P1 and P6 receive the same effective value;
P3's candidate `min_identity` remains independent.

## Validation

New automated test files are optional. Record reproducible validation commands
and evidence using edited source and the project environment.

1. Run existing parser/phylogeny checks:
   `PYTHONPATH=.:scripts python -m unittest scripts.tests.test_blast_parser scripts.tests.test_phylogeny_sampling`.
2. Exercise the following with default cap 2000 and threshold 0.935. Confirm
   internal complete-set counts, selected-set counts and selected-only report rows.

   | XML hits / identity condition | `all_xml_hits.json` count | `all_hits.*` count |
   |---|---:|---:|
   | No hits | 0 | 0 |
   | 37 hits, any identities | 37 | 37 |
   | 2000 all below threshold | 2000 | 500 |
   | Hit 500 exactly at threshold | 2000 | 500 |
   | Hit 500 above, hit 1000 at/below | 2000 | 1000 |
   | 600 above followed by 600 below | 1200 | 1000 |
   | Only 80 above threshold | 2000 | 500 |
   | First stopping boundary at 1500 | 2000 | 1500 |
   | 2000 all above threshold | 2000 | 2000 |
   | 750, first 500 above threshold | 750 | 750 |
   | Replay 2500, all above threshold | 2500 | 2000 |

3. Check caps 1, 300, 750 and 2500, threshold 0/1 and a non-default 0.95;
   reject invalid/non-finite settings. Include boundary rounding, ties,
   shuffled XML order, a multi-HSP hit and different per-query counts.
   Changing cap/threshold on identical XML must leave `all_xml_hits.json` unchanged,
   while selected outputs and `accessions.txt` follow the new selection.
4. Verify exact JSON/FASTA membership by original hit index, including duplicate
   accessions. The single `accessions.txt` must equal the unique union of
   selected accessions across queries. Confirm no complete-set accession list
   or selection-decision file is emitted, and no complete-extraction FASTA is
   created. Verify selected FASTA content still matches the corresponding
   XML last-HSP subject strings. Compare complete/selected sets
   internally, including block and cap exclusions in oversized replay.
5. Confirm every downstream consumer uses selected hits or their derived
   outputs. Check the P6 hit count/rows against selected JSON, including a
   below-threshold final-block hit and zero-hit behavior. Verify report
   rendering does not require `all_xml_hits.json`: inspect staging and render with
   that file absent. Ensure selected JSON/FASTA is published and remains
   available after downstream failure. Confirm complete files remain only in
   extraction/selection work directories, never in analysis/report staging
   or published output (including wildcard rules). Record existing empty/
   no-candidate report defects if encountered rather than claiming success.
6. Follow `docs/nf-tests.md` and `test/core/README.md` for
   `test/core/taxodactyl.workflow.nf.test` using local values in
   `test/core/nextflow.config`. Use a development bind or rebuilt image so
   checks use edited scripts. Verify file staging, per-query joins, taxonomy
   inputs, generated BLAST command and rendered report for default and
   non-default settings. Compare candidate summaries, flags and phylogeny
   membership; explain differences rather than blindly updating snapshots.
7. Benchmark 500 versus 2000 live retrieval using the same queries, database
   and BLAST versions. Include dense/sparse queries and a boundary-reaching
   example. Record elapsed time, peak memory where available, XML size,
   complete/selected counts, taxonomy work and changed scientific outputs.
   Replay cannot prove live search membership or performance; record unavailable
   live checks explicitly and do not claim full validation without them.

## Dependencies and parallel opportunities

Complete extraction and association tracking precede selected outputs;
those contracts precede P3/P6 wiring, which precedes end-to-end validation.
Use the working artifact names and the recorded P1 selection boundary and
independent threshold configuration. Retrieval
parameter changes and complete extraction work can proceed independently;
report presentation can proceed against the selected JSON contract once
fixed. Minimum deliverable includes complete internal JSON, separate selection,
selected-only downstream routing and reporting together.

## Completion criteria

- Every XML hit and calculated identity remains in `all_xml_hits.json`,
  regardless of selection settings. No complete-extraction FASTA is created;
  only selected hits are written to `all_hits.fasta`.
- Separate selected assets follow the confirmed 500-hit block rule, including
  the entire stopping block; no individual minimum-identity filter replaces it.
- Complete and selected sets can be compared internally. The report shows
  only selected hits and its counts agree with published selected JSON.
- `all_hits.json` and `all_hits.fasta` are published; `all_xml_hits.json`
  remains internal and is not copied into the published output.
- Only one `accessions.txt` is produced, containing selected accessions, and
  no selection-decision artifact is produced.
- All downstream consumers use selected hits or their derived outputs: P3
  evaluates selected assets, P6 shows selected hits, and taxonomy uses
  `accessions.txt`. Complete files are not staged to analysis/report processes.
- Retrieval, selection and report use consistent validated configuration;
  threshold configuration and the selection process boundary are resolved and
  documented. Use `all_hits.*` unless a later rename is explicitly agreed.
- Specs and documentation match the new contract, and validation evidence
  explains any remaining limitations and changes in scientific outputs.
- Move this brief to `tasks/completed/` only after successful full validation.
  Keep the main active-index entry until the branch is merged.

## Risks and limits

- BLAST retrieval rank is based on significance/scoring, not Taxodactyl
  aggregate identity. Sorting only orders retrieved hits; increasing the cap
  does not guarantee a simple appended set or globally highest-identity hits.
- Keeping complete extraction internally adds work-directory storage, while
  taxonomy and screening use only selected context. Excluded hits can lack resolved taxonomy.
- Keep the existing last-HSP FASTA behavior (P1-D-001) and identity precision;
  neither is fixed by this task. The zero-total-HSP-length calculation divides
  before checking zero; record malformed-fixture failures separately.
- Candidate eligibility and phylogeny sampling remain separate from block
  selection. More context may change results without making every hit eligible.

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


### Recent output-contract revision (3 November 2026)

Implemented the revised contract in the existing task worktree, preserving
prior implementation outcomes above. Naming remains open to discussion;
current names are the working names requested by the user.

- `parse_blast_xml` now returns the complete, stably identity-sorted extraction.
  P1 writes it to internal `all_xml_hits.json` before calling a separate
  `select_blast_hits` operation within the same process. Selection leaves
  complete records unchanged; FASTA associations use internal identity ranks
  on in-memory sequence records, including duplicate accessions.
- Only selected hits are written to `all_hits.json` / `all_hits.fasta`, and
  the single `accessions.txt` contains their unique union. Empty queries
  produce empty JSON hit lists and empty selected FASTA. No complete FASTA,
  decision file or second accession list is created.
- Existing downstream readers and scientific algorithms are unchanged.
  `EXTRACT_HITS` publishes selected JSON/FASTA and `accessions.txt`; its emitted
  hit tuple excludes the complete JSON, which stays in the P1 work directory.
- Added internal filename configuration `all_xml_hits_json` and updated P1,
  hit/output/process contracts and user documentation. The existing independent
  threshold configuration is preserved rather than reimplemented.

Validation of this revision:

- Focused parser/context/phylogeny suite: **17 tests passed**, including a new
  P1 output regression with repeated accessions, an empty query, changing
  caps/thresholds, complete JSON written before selection, and exact selected
  sequence/accession membership. Complete-hit invariance is also checked
  across existing block-boundary, rounding and oversized-replay cases.
- Full Python discovery: **156 tests run, 154 passed, 2 skipped**, using the
  same Python 3.12 Singularity image and temporary `fakeredis` dependency as
  prior validation. No application dependencies were changed.
- Actual P1 CLI on captured 2000-hit-per-query XML at cap/threshold pairs
  2000/0.935, 750/0.95 and 300/0: complete counts remain [2000, 2000, 2000];
  selected counts are [1000, 500, 500], [750, 500, 500], and [300, 300, 300].
  Complete JSON is byte-identical across these settings. Selected JSON/FASTA
  is byte-identical to the previous task-04 implementation's saved output.
  The accession list equals the selected union, with no extra artifacts.
- Actual Nextflow `EXTRACT_HITS` module executions passed at 2000/0.935 and
  750/0.95 using the edited scripts. Verified published selected JSON/FASTA
  and accessions, internal complete JSON only in work directories, and an
  emitted tuple containing only selected JSON/FASTA and query titles.
- The existing report BLAST modal rendered successfully from selected JSON
  with the internal file absent at all three settings. This confirms the
  changed output contract, not full-report/P4/P5 integration.
- Validation commands, outputs and module harness are in
  `/tmp/task04-revision/`; the durable count/compatibility summary is
  `tasks/validation/04_output_contract_revision.json`.

The recent output-contract revision is implemented and validated. The task
remains **active** because the previously documented complete workflow,
P4/P5/report integration and snapshot reconciliation are still outstanding.
No new full-workflow or live-search benchmark success is claimed. The brief
is not moved to completed, and the main active-index entry remains unchanged.
No extension hooks are configured in this worktree.
