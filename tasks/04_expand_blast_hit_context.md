# Task 04 — Preserve all BLAST hits and select context in 500-hit blocks

**Status:** active

**Priority:** Unassigned; DAFF enhancement.

**Issue:** [#160 — Consider blast hits down to 93.5% identity for better context](https://github.com/qcif/taxodactyl/issues/160)

**Scope:** Rename the retrieval cap to `blast_max_target_seqs` (default 2000),
extract every XML hit into `all_xml_hits.json`, then derive
separate `all_hits.json` / `all_hits.fasta` using 500-hit blocks.
Publish `all_hits.*`; keep `all_xml_hits.json` as internal workflow artifacts.
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
selected accessions, regardless of whether selection runs in P1 or a new process.

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
report does not show hits excluded by block selection. If selection becomes
a separate process, that process alone may consume the complete extraction
before emitting the selected-only downstream bundle (see open decision).

## Implementation

**Provisional architecture and working filenames:** Use `all_hits.json` /
`all_hits.fasta` for selected downstream hits and `all_xml_hits.json` for complete
internal extraction for now. Final hit filenames remain open to discussion.
Instructions placing selection in P1 describe
the in-process option, not a settled architecture. Resolve the
process-boundary decision before implementing the affected wiring, then
update all paths and producer references consistently. Complete extraction
into `all_xml_hits.json` and taxonomy lookup on selected accessions are fixed
requirements under either architecture. The accession-list filename is fixed
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
  Emit selected JSON/FASTA for downstream staging. Keep complete JSON
  local to extraction, or emit it only to a separate selection process if
  that architecture is chosen.
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

## Open decision — selection in P1 or a separate process

**Status: unresolved.** Decide where block selection executes after complete
extraction; do not silently choose an architecture during implementation.

| Option | Behavior | Tradeoff |
|---|---|---|
| A — selection within P1 | `scripts/p1_parse_blast.py` writes the complete extraction, then invokes selection and writes the selected assets and `accessions.txt` in `EXTRACT_HITS`. | Fewer workflow stages; extraction and selection share one execution/cache boundary. |
| B — separate selection process | P1/`EXTRACT_HITS` produces complete extraction only; a new Python entry point and Nextflow process consume it and produce selected assets and the selected-only `accessions.txt`. | Explicit stage boundary and independent selection reruns/caching; additional files, channels and staging. |

For option B, record the exact new script/module paths and process name before
implementation. Wire the new process after `EXTRACT_HITS` and before
`BLAST_BLASTDBCMD`/`EXTRACT_TAXONOMY` and P3 in
`workflows/taxodactyl.nf`. Pass cap/threshold to the selection process rather
than P1; preserve stable original-hit associations across the serialized
boundary, including duplicate accessions. Because complete extraction has no
FASTA and the existing JSON lacks a raw subject-sequence field, also stage
the source BLAST XML into the selector to recover selected hits' last-HSP
subject sequences in original BLAST order. Do not reconstruct sequences from
printable alignment text or introduce a complete-extraction FASTA. For the
in-P1 option, retain the hit-to-sequence association in memory and write
FASTA only after selection. This separate selector is the only
permitted consumer of complete extraction outside P1; all subsequent analysis
and reporting receive selected hits only. Publish only selected hit files. Update the threshold
wiring instructions below to target the chosen selection producer.

For either option, **taxonomy lookup runs only on the selected hit accessions**:
`accessions.txt` (selected accessions only) → `BLAST_BLASTDBCMD` → `EXTRACT_TAXONOMY` → P3.
P3 evaluates the selected hit JSON/FASTA using the existing candidate rules.
The full extraction remains internal to extraction/selection work files;
reporting consumes and displays selected hits only.

## Open decision — stopping threshold

**Status: unresolved.** Decide before implementing threshold configuration.
The default is 0.935 in either option; do not silently hard-code that value or
select an option during implementation.

| Option | Behavior | Tradeoff |
|---|---|---|
| A — reuse `min_identity` | P1 uses the same effective value as P3's moderate candidate threshold (`criteria.alignment_min_identity`, default 0.935). | Fewer controls; changing candidate stringency also changes retained context and potentially downstream work. |
| B — separate `blast_context_min_identity` | Add an independent block-stopping parameter, default 0.935; `min_identity` still controls candidate eligibility. | Independent control of context depth and candidate stringency, with extra configuration and documentation. |

For option A, pass `params.min_identity` through
`modules/extract/hits/main.nf` and `modules/report/main.nf` to P1/P6 via
`--min-identity`. Add argument support in `scripts/p1_parse_blast.py` and
`scripts/p6_report.py`, reusing the mapping in
`scripts/src/utils/config/mappings.py` and existing criteria field. P1, P3
and P6 must receive the same effective value, including zero; update the
truthiness-based argument handling in `modules/extract/candidates/main.nf`
so valid zero values are not omitted.

For option B, add `blast_context_min_identity` to `conf/params.config`,
`nextflow_schema.json`, `scripts/config/default.yml` and
`scripts/src/utils/config/schema.py`, with default 0.935 and range 0–1.
Add its environment/CLI mapping (`BLAST_CONTEXT_MIN_IDENTITY` /
`--blast-context-min-identity`) in `scripts/src/utils/config/mappings.py`.
Wire it through the same P1/P6 entry points and Nextflow modules; P3 continues
to use `min_identity` unchanged.

For either option, validate a finite numeric threshold in [0, 1] without
omitting zero. Pass its effective value explicitly into
`scripts/src/blast/parse_xml.py` and render it in the report templates listed
above. Update `docs/params.md`, `spec/nextflow/params.md`,
`spec/python/shared/config.md`, `spec/python/p1-parse-blast.md` and
`spec/python/p6-report.md` to describe the selected behavior. Record the
decision here and remove the unselected implementation branch before marking
the task ready for implementation.

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
Use the confirmed current artifact names and resolve the selection process
boundary and threshold configuration before implementing that wiring. Retrieval
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
- On implementation completion, move this brief to `tasks/completed/` and
  remove its entry from `tasks/active.md`.

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
