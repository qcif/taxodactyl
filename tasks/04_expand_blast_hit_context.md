# Task 04 — Preserve all BLAST hits and select context in 500-hit blocks

**Status:** active

**Priority:** Unassigned; DAFF enhancement.

**Issue:** [#160 — Consider blast hits down to 93.5% identity for better context](https://github.com/qcif/taxodactyl/issues/160)

**Scope:** Rename the retrieval cap to `blast_max_target_seqs` (default 2000),
extract every XML hit into `all_hits.json`, then derive
separate `filtered_hits.json` / `filtered_hits.fasta` using 500-hit blocks.
Publish `filtered_hits.json` / `filtered_hits.fasta`; keep `all_hits.json` as internal workflow artifacts.
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
selection. Never overwrite `all_hits.json` with a selected subset. This
internal JSON contains every hit present in the supplied XML, not every
database match. The downstream filenames `filtered_hits.json` / `filtered_hits.fasta` contain
all block-selected hits available for downstream evaluation, not all XML hits.

1. Run BLAST once with `-max_target_seqs` from `blast_max_target_seqs`
   (default 2000, integer >= 1). Leave `-perc_identity` unset.
2. Extract every retrieved hit and its HSP evidence. Calculate identity using
   the existing length-weighted aggregate, rounded to three decimals, and
   sort JSON hits descending with stable BLAST-order ties.
3. Write the complete `all_hits.json` before deriving a
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
`all_hits.json`; apply the cap only to selection. This replay cap does not
reproduce which records a capped live BLAST search would retrieve.

## Output and consumer contracts

| Artifact | Membership and purpose |
|---|---|
| `blast_result.xml` | Complete raw retrieval evidence. |
| `query_*/all_hits.json` | Every XML hit, original top-level query schema and full HSP evidence, sorted by calculated identity. Internal, required output on `EXTRACT_HITS.out.all_xml_hits`; not published. |
| `query_*/filtered_hits.json` | Same query/hit schema, containing only block-selected hits, sorted by identity. Published. |
| `query_*/filtered_hits.fasta` | Corresponding selected records in relative BLAST order. Published. |
| `accessions.txt` | Unique union of selected-hit accessions across queries; the only accession list, used for downstream taxonomy lookup. |

Do not produce a separate selection-decision file or a complete-set accession
list. `accessions.txt` is generated after block selection and contains only
selected accessions, regardless of whether selection runs in P1 or a new process.

Selection must preserve an exact prefix of the stably identity-sorted complete
list. Validate this internally, using original hit positions to preserve
JSON/FASTA associations even when accessions repeat. Preserve the existing
complete JSON schema. Log complete/selected counts, effective cap/threshold
and termination reason in the selection process; do not add an audit artifact.

Every downstream BLAST consumer uses `filtered_hits.json` / `filtered_hits.fasta` or outputs derived
from it. P3 reads selected JSON/FASTA; P6 reads selected JSON for its BLAST
table. Taxonomy lookup uses the selected-only `accessions.txt`. Candidate
outputs remain based on P3's existing coverage/length, identity and
species-selection rules. A block-selected hit is not necessarily a candidate.

`all_hits.json` is internal to extraction and selection, not an input to P2/P3,
P4/P5, phylogeny or P6. Do not stage it to those processes or publish it.
Internal work files allow comparison of complete and selected hits; the
report does not show hits excluded by block selection. If selection becomes
a separate process, that process alone may consume the complete extraction
before emitting the selected-only downstream bundle (see open decision).

## Implementation

**Confirmed filenames (10 November 2026):** Complete internal extraction uses
`all_hits_json` with default `all_hits.json`. Selected downstream files use
`hits_json: filtered_hits.json` and `hits_fasta: filtered_hits.fasta`.
Rename the former
`all_xml_hits_json` setting and references to `all_hits_json`. The process
output `all_xml_hits` and workflow channel `ch_all_xml_hits` retain their names;
they are distinct from the filename configuration key.

Selection in P1 remains a provisional architecture. Resolve the process-boundary
decision before implementing affected wiring. Complete extraction and
selected-only taxonomy lookup remain required under either architecture.
The single accession-list filename remains `accessions.txt`.

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
  `modules/extract/hits/main.nf` still ensures the downstream `filtered_hits.fasta`
  exists. Complete extraction with no hits still produces internal JSON
  containing an empty hit list. Do not create a complete-extraction FASTA.
- In `scripts/config/default.yml` and `scripts/src/utils/config/schema.py`,
  set `all_hits_json: all_hits.json`, `hits_json: filtered_hits.json` and
  `hits_fasta: filtered_hits.fasta`. Rename any existing `all_xml_hits_json`
  setting/references to `all_hits_json`. Align YAML and schema defaults.
  In `scripts/p1_parse_blast.py`, write complete extraction using `all_hits_json`
  and selected outputs using `hits_json` / `hits_fasta`. Audit
  `scripts/src/utils/config/config.py` and `scripts/src/utils/config/mappings.py`
  for corresponding filename settings/readers. Retain selected reader keys
  with their new defaults. Update `conf/filenames.config` and hard-coded
  producer/consumer, staging and publishing references consistently. Complete
  and selected JSON must resolve to distinct default paths.
- Log complete and selected counts, minimum selected identity when present,
  effective configuration and termination reason. Changing selection settings
  on the same XML must not change complete-set content.

### 2. Wire retrieval and downstream consumers

- Rename `blast_max_target_seqs_for_report` to `blast_max_target_seqs` in
  `conf/params.config` and `nextflow_schema.json`; default 2000. Use it in
  `modules/blast/blastn/main.nf`. Preserve other BLAST settings and version
  recording. Blocks do not trigger repeated BLAST searches.
- In `modules/extract/hits/main.nf`, pass the cap and effective threshold to P1.
  Emit selected JSON/FASTA for downstream analysis staging. Declare complete
  JSON as a separate required output channel for validation, as specified below.
  Publish only the selected JSON/FASTA, plus the single selected-only
  `accessions.txt`; do not publish `all_hits.json`.
  Update `conf/process.config` file-name bindings where needed. Audit all
  downstream staging and publish rules so complete files cannot enter
  analysis/report bundles or published output through wildcard patterns. Selected files must remain
  published even if later analysis fails. Complete files remain in work
  directories for internal inspection only.
- Update `workflows/taxodactyl.nf` to carry the selected-only per-query bundle by
  query identity and route `accessions.txt` to
  `modules/blast/blastdbcmd/main.nf`. Verify
  `modules/extract/taxonomy/main.nf` receives the resulting taxid list.
- Migrate selected filenames while retaining configured readers in
  `modules/extract/candidates/main.nf` and `scripts/p3_assign_taxonomy.py`:
  `filtered_hits.json` / `filtered_hits.fasta` already contains only the selected set when staged downstream.
  Validate routing and migrate any hard-coded old filename references.
  Preserve BOLD behavior and P3's existing eligibility/sampling algorithms.
- Validate `modules/mafft/align/main.nf`, `modules/fastme/main.nf`,
  `scripts/p4_source_diversity.py` and `scripts/p5_db_coverage.py` with their
  existing downstream inputs. Retaining more context can change candidates,
  summaries, flags and tree membership; it does not mean aligning every hit.

### 2a. Expose complete JSON for validation without publishing it

**Requested 4 November 2026; pending implementation.** Declare the internal
JSON in `modules/extract/hits/main.nf` as a required named process output:

```nextflow
path("query_*/${task.ext.all_hits_json}"), arity: '1..*', emit: all_xml_hits
```

Bind `ext.all_hits_json` in `conf/filenames.config` from
`pyDefaults.all_hits_json`, matching the Python filename setting. Do not
hard-code a different filename in the process. Do not mark this output
optional or create a placeholder: missing complete JSON must fail output
collection. The glob requires at least one file. Python CLI integration tests must check
that every XML iteration has its corresponding JSON, including empty hit
lists; a glob alone does not prove per-query completeness.

Keep `all_xml_hits` separate from `hits_files` and `hits_accessions`. Existing
`publishDir` patterns must continue to match only selected assets and the
selected accession list; declaring an output must not publish the complete
JSON or put it into P3/P6 input bundles.

In `workflows/taxodactyl.nf`, expose `ch_all_xml_hits` in the workflow `emit:`
block for workflow nf-tests. In BLAST mode derive it from
`EXTRACT_HITS.out.all_xml_hits`, flatten the file list, and map each path to
`tuple(file.parent.name, file)` so assertions can join by query folder rather
than channel arrival order. Initialize it as an empty channel for a branch
that does not run BLAST. Do not mix it into `ch_hits_files`,
`ch_hits_for_report`, taxonomy inputs or any scientific-analysis channel.

Update `spec/nextflow/processes.md`, `spec/contracts/hits.md`,
`spec/contracts/query-folder.md`, `spec/python/p1-parse-blast.md` and
`spec/contracts/outputs.md` to distinguish an emitted internal process output
from a published artifact and an analysis input. Keep complete JSON internal
and unpublished, while making its existence and contents accessible to tests.

### 3. Report only selected hits

- In `scripts/src/report/report.py` and
  `scripts/src/report/templates/components/results/1a-blast-hits-modal.html`,
  use the configured `hits_json` reader (default `filtered_hits.json`) and render only block-selected hits with their calculated
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
  Explicitly document that `filtered_hits.json` / `filtered_hits.fasta` now contains the selected set, while
  complete extraction is preserved internally as `all_hits.json`.
- Document parameter migration and that the cap now controls retrieval and
  selection, while replay extraction always preserves every XML hit. Resolve
  NF-D-005 in `spec/defects.md` only when live retrieval and report agree.
- Validate the cap as an integer >= 1 across CLI/config/Nextflow paths; reject
  zero, negative and fractional values. Preserve three-decimal identity and
  block size 500. Validate thresholds as finite numbers in [0, 1], including
  zero, using the configuration decision below.

## Confirmed decision — hit artifact filenames

**Confirmed 10 November 2026.** These Python defaults supersede the previous
provisional names:

```yaml
all_hits_json: all_hits.json
hits_fasta: filtered_hits.fasta
hits_json: filtered_hits.json
```

`all_hits_json` replaces `all_xml_hits_json`. Complete `all_hits.json` remains
internal and unpublished. Selected `filtered_hits.json` and
`filtered_hits.fasta` are published and consumed downstream. Update configuration, documentation,
staging, publishing and validation consistently. `accessions.txt` remains
selected-only; there is no complete-extraction FASTA.

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

## Testing decision

**Naming revision, 10 November 2026: confirmed by the user.** The implementer
updates Python assertions and runs Python checks. All other testing and review
is manual and user-owned: running nf-tests, flag comparisons and Selenium;
reviewing output drift; and deciding/editing snapshots, flag baselines and
Selenium fixtures or expected reports. Manual checks remain pending until the
user supplies evidence. No automatic baseline regeneration or promotion.

**Bug-detection requirement:** Derive Python expectations independently from
the specified contract and deterministic input fixtures, not from the output
under test. Preserve exact membership, count, identity, ordering, sequence,
accession and complete/selected separation assertions. Change filename/default
expectations only as required by the confirmed naming contract. Do not weaken,
remove or skip assertions, copy failing actual output into expected values, or
mock away the behavior being tested to make checks pass. Investigate failures;
fix implementation defects within authorized scope or report unresolved bugs.
Record commands and results, including failures and unavailable checks.

**Implementation authorization: granted 10 November 2026** for the recent
naming revision via explicit speckit-implement invocation. Python assertion
updates and checks are authorized; other validation remains manual/user-owned.

Agreed Python checks and manual handoff: verify YAML/schema defaults and
Nextflow bindings, then assert the three distinct output paths in the planned
`scripts/tests/test_p1_cli_integration.py`. Confirm downstream consumers read
selected files and complete `all_hits.json` stays unpublished. Use the existing
unit discovery command below for implementer-run Python checks; the user
runs the core workflow and other manual checks below. Filename
changes alone must preserve membership, sequences, report values and flags.

## Validation

Output-channel preparation and Python CLI integration tests are implementer
work. The user adds the observation channel to the existing core nf-test and
runs and reviews existing nf-test/flag/Selenium checks manually. Live retrieval
benchmarks and other non-Python validation are also user-owned. Do not add new cases for those
suites. Record automated evidence and pending manual checks separately.

1. Run existing parser/phylogeny checks:
   `PYTHONPATH=.:scripts python -m unittest scripts.tests.test_blast_parser scripts.tests.test_phylogeny_sampling`.
2. Exercise the following with default cap 2000 and threshold 0.935. Confirm
   internal complete-set counts, selected-set counts and selected-only report rows.

   | XML hits / identity condition | `all_hits.json` count | `filtered_hits.json` / `filtered_hits.fasta` count |
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
   Changing cap/threshold on identical XML must leave `all_hits.json` unchanged,
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
   rendering does not require `all_hits.json`: inspect staging and render with
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

### Python integration coverage and existing CI suite handoff

Do not create a new nf-test scenario, flag case or Selenium case for task 04.
The user will add `workflow.out.ch_all_xml_hits` to the existing core nf-test
in `test/core/taxodactyl.workflow.nf.test` and review its snapshot. The
implementer supplies the process/workflow channel; exact per-query counts,
identity order, hit IDs and FASTA/accession membership belong in Python
integration tests rather than new workflow assertions.

Add `scripts/tests/test_p1_cli_integration.py` using `unittest` and a real
subprocess invocation of `scripts/p1_parse_blast.py`. Generate deterministic
XML/FASTA/metadata in a temporary directory from the existing XML fixture;
do not mock the parser, configuration or writers. Include 1200 hits (600 at
0.99 followed in identity rank by 600 at 0.90), an empty query and 37 hits,
with reversed XML order, identity ties and repeated accessions carrying
different sequences. Exercise 2000/0.935, 750/0.935, 300/0 and 2000/0.99.
Check exact complete/selected hit IDs and counts, identity values, stable
order, original-order FASTA sequences, accession union/deduplication, empty
outputs, complete JSON invariance and absence of extra FASTA/decision files.

Run from the repository root:
`PYTHONPATH=.:scripts python -m unittest scripts.tests.test_p1_cli_integration`.
The existing `.github/workflows/unit-tests.yml` discovery command
`python -m unittest discover -s scripts/tests -p 'test*.py' -v` will include
this file without a new CI job. This offline P1 test needs project Python
dependencies but no BLAST/taxonomy database, network, Nextflow or browser.
It is separate from the existing network-dependent full Python integration
suite under `scripts/tests/integration/`; do not add live-service dependencies
to this focused test.

## Test impact and manual review

**Ownership:** The implementer adds the observation channels and offline Python
CLI integration tests. The user adds the complete-hit channel to the existing
core nf-test and reviews nf-test snapshots, flags and Selenium expectations.
No new workflow/browser/flag test case is needed, and no baselines are
regenerated or promoted automatically.

**Naming revision impact:** `scripts/tests/test_blast_parser.py` asserts parsed
content using `scripts/tests/test-data/one_hit.json` and
`scripts/tests/test-data/one_hit.fasta`; these fixtures need no rename for output
configuration changes. Update filename assertions in the planned
`scripts/tests/test_p1_cli_integration.py`. Review
`test/core/taxodactyl.workflow.nf.test.snap` for selected-output filename/path
drift. Flag baselines in `test/core/flags/*.flag` and Selenium expectations in
`test/selenium/expected/*.yaml` and `test/selenium/expected/reports/*.html` need
manual user review if changed; scientific values should not change from this
rename alone. Capture before/after output inventories with the handoff artifacts
to distinguish path changes from content drift. Ownership follows the confirmed
testing decision above: implementer-run Python checks, all other validation
and expected-result review/changes manually performed by the user.

**CI inspected:** `.github/workflows/nf-test.yml` runs only
`test/core/taxodactyl.workflow.nf.test`, compares `test/core/flags`, then runs
`test/selenium/test_reports.py` against the resulting reports. Its checked-in
runner label is `ubuntu-latest`, not `self-hosted`; this advice concerns that
version of the workflow, not an uninspected runner configuration. It uses
BLAST data dated 2026-07-29 and taxonomy data dated 2026-05-08.
`.github/workflows/mock-nf-test.yml` replays an archived 2026-08-04 run for
flags/Selenium and cannot validate fresh P1 code or its new channel.

| Existing CI coverage | Where task 04 can affect it | User action / implementer preparation |
|---|---|---|
| `test/core/taxodactyl.workflow.nf.test` and `.snap` | Currently snapshots `ch_hits_for_report`, `ch_candidates_for_report`, `ch_source_diversity_for_report`, `ch_homology_trees`. Increased BLAST context may change their file hashes/content. The new complete-hit channel is not yet in that snapshot. | Implementer exposes `EXTRACT_HITS.out.all_xml_hits` and query-keyed `ch_all_xml_hits`, without mixing it into the four existing channels. User adds the new channel to the existing nf-test snapshot and reviews changes. Exact hit counts/IDs are checked in Python. |
| Core nf-test size assertions | Existing expectations include 20 reports, one versions/params/timestamp item, 18 map groups / 34 maps, 20 coverage JSONs, 20 flag groups / 60 P5 flags. The new observation channel itself does not justify changing any of these. Scientific output changes may affect map counts; missing reports require investigation. | Preserve these assertions unless the user determines an actual intended behavior change. Do not replace them with new hard-coded values simply to pass. |
| `bin/collect_flags.sh`, `bin/test_flags.py`, `test/core/flags/*.flag` | The runner compares P5 flags **5.1–5.3**, not every flag. More context may affect candidate-derived coverage decisions; no change is guaranteed. Channel emission alone must not change flags. | Existing collector/comparator need no new case. User inspects `flags_results.txt` / `flags_errors.txt` and accepts any justified baseline changes. P3 flags 1/2/7 must be reviewed through existing report/snapshot coverage instead. |
| `test/selenium/test_reports.py`, `test/selenium/lib/candidate.py`, `test/selenium/lib/schema.py`, `test/selenium/expected/*.yaml` and `expected/reports/*.html` | Existing candidate collectors assert strong/moderate/weak hit counts, lowest hit, per-species `no_of_hits`, `top_identity`, `median_identity`, `min_identity`; BLAST modal checks the first row's rank/accession/identity and other fields. Tree checks include `min_node`; flag/TOI fields may also change. These are possible scientific changes, not guaranteed replacements. The current BLAST collector does not assert the new block-description prose or total XML count. | Reuse current report cases. User reviews fresh reports and existing field diffs; adjust collectors/assertions only if desired for changed wording, and promote expected YAML/reference reports only after review. Complete JSON must not appear in report data. |
| `.github/workflows/unit-tests.yml` | Discovers the new offline `scripts/tests/test_p1_cli_integration.py` through its existing `test*.py` pattern. | Implementer adds/runs exact count/identity/ID/sequence assertions without new nf-test/Selenium/flag cases. |

The current runner does not execute `test/scenario_01/` through
`test/scenario_04/` in this job. Do not claim CI covers them or require new
cases there; the user may review them separately if they run those suites.

Manual handoff: use the existing core command
`nf-test test test/core/taxodactyl.workflow.nf.test` with the runner's resolved
configuration. Review snapshot differences and flag result/error artifacts.
From `test/selenium/`, run
`pytest test_reports.py -v --dir <fresh-report-directory>`, then
`python testkit.py render`; inspect `test-report.json`, `review.html` and
reference/fresh HTML before promotion. Record data versions and effective
cap/threshold so selection effects can be distinguished from database drift.
Keep nf-test/flag/Selenium acceptance **pending user review** until results
are supplied; successful Python tests do not replace manual acceptance.

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

- Complete JSON is a required, separately named `EXTRACT_HITS.out.all_xml_hits`
  output, exposed as query-keyed `ch_all_xml_hits` for workflow nf-test access.
  It is neither published nor routed to analysis/report consumers.
- Implementation provides the channels and review handoff. User-owned nf-test,
  flag and Selenium review remains explicitly pending until results are
  supplied; snapshot/fixture/baseline acceptance is not automated. Required
  manual validation must be recorded before overall task completion.

- Every XML hit and calculated identity remains in `all_hits.json`,
  regardless of selection settings. No complete-extraction FASTA is created;
  only selected hits are written to `filtered_hits.fasta`.
- Separate selected assets follow the confirmed 500-hit block rule, including
  the entire stopping block; no individual minimum-identity filter replaces it.
- Complete and selected sets can be compared internally. The report shows
  only selected hits and its counts agree with published selected JSON.
- `filtered_hits.json` and `filtered_hits.fasta` are published; `all_hits.json`
  remains internal and is not copied into the published output.
- Only one `accessions.txt` is produced, containing selected accessions, and
  no selection-decision artifact is produced.
- All downstream consumers use selected hits or their derived outputs: P3
  evaluates selected assets, P6 shows selected hits, and taxonomy uses
  `accessions.txt`. Complete files are not staged to analysis/report processes.
- Retrieval, selection and report use consistent validated configuration;
  threshold configuration and the selection process boundary are resolved and
  documented. Use the confirmed filenames and `all_hits_json` configuration key consistently.
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


### Implemented follow-up (4 November 2026): observation channel and Python integration

- Added required `EXTRACT_HITS.out.all_xml_hits` (arity `1..*`), with its
  filename bound through `conf/filenames.config`. Added workflow output
  `ch_all_xml_hits` keyed by query folder; non-BLAST mode initializes it empty.
  Complete JSON remains unpublished and separate from analysis/report inputs.
- Added `scripts/tests/test_p1_cli_integration.py`: real subprocess P1 runs,
  with no mocked parser/config/writers. Four cap/threshold settings validate
  complete counts [1200, 0, 37], selected counts [1000, 0, 37], [750, 0, 37],
  [300, 0, 37] and [500, 0, 37], exact IDs/identity order, sequence associations,
  duplicate-accession handling, complete JSON invariance and output filenames.
- Confirmed the existing CI discovery includes this integration test without
  changing its workflow. Full discovery ran **157 tests: 155 passed, 2 skipped**.
  Syntax/name lint and whitespace checks passed.
- The real Nextflow extraction module executed successfully with the new
  required output. Its observation channel contained all three query JSONs;
  selected outputs were published and complete JSON was absent from publishing.
  This is a scoped module check, not a new nf-test case or a full-workflow run.
- Updated the task plan from inspecting `.github/workflows/nf-test.yml`,
  `.github/workflows/mock-nf-test.yml` and `.github/workflows/unit-tests.yml`.
  They currently specify `ubuntu-latest`; no self-hosted job was found in the
  inspected checkout. The actual core snapshot, P5 flag and Selenium field
  impacts are listed in Test impact and manual review.
- Removed the proposed new nf-test scenario. No nf-test, Selenium or flag case,
  assertion, snapshot or expected baseline was edited. The user will add
  `ch_all_xml_hits` to the existing core nf-test and review results/baselines.
  Full-workflow and manual validation remain pending; task 04 stays active.

Local evidence: `/tmp/task04-revision/cli-integration.log`,
`ci-discovery.log`, `channel-nextflow.log` and `published-channel/`.
No extension hooks were configured.


### Implemented naming revision (10 November 2026)

- Implementation explicitly authorized by the user's speckit-implement request
  for recent task 04 changes. Reused the existing isolated branch/worktree
  `task-04-expand-blast-hit-context` / `.worktrees/task-04-expand-blast-hit-context`.
- Renamed the complete-output setting to `all_hits_json`, default `all_hits.json`,
  in Python YAML/schema, P1 writer, Nextflow binding and required output glob.
  Selected settings remain `hits_json` / `hits_fasta`, now defaulting to
  `filtered_hits.json` / `filtered_hits.fasta` in both YAML and schema.
- Preserved process/workflow channel names `all_xml_hits` / `ch_all_xml_hits`.
  Configured downstream readers and selected-only publishing use the new names;
  complete extraction remains internal. Updated current docs/specs and migration
  guidance. Historical captured fixtures, reports and validation evidence retain
  their original names; they were not rewritten to make checks pass.
- Updated Python path assertions without changing expected scientific content.
  Added independent literal YAML/schema default checks and exact CLI output-file
  inventory assertions. Existing exact counts, IDs, identities, ordering,
  sequence/accession associations and complete-output invariance remain intact.
- Red/green evidence: revised tests against the old implementation failed
  (8 tests, 3 failures and 6 errors/subtest errors) on missing/old settings and
  filenames. After implementation, focused parser/context/phylogeny/CLI coverage
  passed all 19 tests. Full discovery ran 158 tests: 156 passed, 2 skipped
  (GenBank concurrency disabled; hmmsearch unavailable). No failing assertion
  was weakened or removed, and no expected scientific values were changed.

Python validation used the existing Python 3.12 image
`/mnt/data/images/neoformit-taxodactyl-v1.5.0.img` with this worktree mounted at
`/workspace`, its scripts at `/app/scripts`, and the previously installed test
extras `/tmp/task04-validation/test-deps` at `/test-deps`. From the worktree:

```sh
singularity exec --bind "$PWD:/workspace,$PWD/scripts:/app/scripts,/tmp/task04-validation/test-deps:/test-deps" --pwd /workspace /mnt/data/images/neoformit-taxodactyl-v1.5.0.img env PYTHONPATH=/workspace:/workspace/scripts:/test-deps GENBANK_CONCURRENCY_TEST=0 python -m unittest discover -s scripts/tests -p 'test*.py' -v
```

Focused command in the same environment:
`python -m unittest scripts.tests.test_blast_parser scripts.tests.test_blast_context scripts.tests.test_phylogeny_sampling scripts.tests.test_p1_cli_integration`.
Local logs: `/tmp/task04-naming-red.log`, `/tmp/task04-naming-focused.log`,
`/tmp/task04-naming-discovery.log`. `git diff --check` passed.

The naming revision is implemented with Python validation complete. Task 04
remains **active**: nf-test execution/snapshots, flags, Selenium, publishing and
other workflow/live validation remain manual and user-owned. No such suites or
benchmarks were run for this revision, and no snapshots/flags/Selenium fixtures
were changed. Review output paths and confirm internal `all_hits.json` is not
published using the handoff commands above. Existing broader architecture and
threshold decisions were not changed by this naming-only revision; the current
implementation still selects within P1 using the independent threshold.
The main active-index record remains in place. No extension hooks are configured.
