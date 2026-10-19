# Decisions required

Open questions collected from every spec file. Each needs an owner's
decision before the related requirement (or defect fix) can be written as
final. Once decided, record the outcome here and update the referenced
spec in the same change.

**Status legend:** `open` · `decided: <outcome> (<date>, <who>)`.

## A. Product scope

| # | Question | Affects | Status |
|---|---|---|---|
| D-01 | **BOLD: repair or retire?** Repair means BOLD v5 API, HMMER in the image (or drop orientation), regroup hits, write/remove `bold_taxonomy.json`. Retire means deleting the branch, `bold_*` params, BOLD tests and docs. | NF-D-002, NF-D-009, P1B-D-001..010, P3-D-005, testing | open |
| D-02 | Should a query whose analysis fails still get a report (with an explicit "analysis incomplete" state) so nothing disappears silently? | NF-D-003, NF-D-015, P3-D-001, P4-D-003, P5-D-004, THR-D-002 | open |
| D-03 | Should the run publish machine-readable per-query results (flags, `candidates.json`, `db_coverage.json`, a run summary)? | OUT-D-001, OUT-D-002 | open |
| D-04 | Is a cross-sample run report wanted? | overview §3 | open |
| D-05 | Should Flag 6 (phylogenetic assessment) be implemented or removed? | P3-D-003 | open |
| D-06 | **(vs Design Proposal)** Should `--bold` mode restrict `locus` to COI, as the Design Proposal specifies, or keep the current behaviour (locus check merely relaxed, no BOLD-specific restriction)? | P0-D-010 | open |

## B. Scientific rules

| # | Question | Affects | Status |
|---|---|---|---|
| D-10 | 5.1 grading: does "B" start at 1 record or 2? (fix comparison vs fix text/param) | P5-D-001, FLG-D-001 | open |
| D-11 | Taxid-less targets: grade `5.1C` explicitly instead of querying Entrez? | P5-D-002 | open |
| D-12 | Publication independence: single-linkage grouping? author overlap? automated records separate from publication-less? | P4-D-001, P4-D-002 | open |
| D-13 | Flag 7 also for genus-level agreement when Flag 1 is B/C/D? TOIs vs moderate candidates when strict ones exist? | P3 §13 | open |
| D-14 | Store the subject **sequence** (not the last HSP fragment) for phylogeny/candidates? | P1-D-001 | open |
| D-15 | Should hard-coded BLAST settings (megablast, 500 targets, e-value, scoring) be parameters or recorded in the report? | NF-PR-030, NF-D-005 | open |
| D-16 | Summary Flag 5 aggregation rule when any sub-flag is level 0. | FLG-D-002 | open |
| D-17 | `db_cov_country_missing_a`: implement or remove. `phylogeny_min_hit_identity`: pass through or remove. | P5-D-003, NF-D-004 | open |
| D-18 | **(vs Design Proposal)** Should the report's `confirmed` result require source-diversity verification (Flag 4a, ≥5 sources) in addition to Flag 1a, as the Design Proposal's Conclusion A specifies — rather than Flag 1a alone, with source verification only affecting colour as it does today? | P6-D-009 | open |

## C. Input handling

| # | Question | Affects | Status |
|---|---|---|---|
| D-20 | Loci: make matching case-insensitive on both sides (fix `atpB`, `trnL`, `AChE`)? | P0-D-001, LOC-002 | open |
| D-21 | Apply length/count limits to CSV sequences; reject empty sequences and duplicate sample ids? | P0-D-002..004 | open |
| D-22 | Allow `sp.`, digits, hyphens in `preliminary_id`/`taxa_of_interest`? | P0 §9 | open |
| D-23 | P0 writes a normalised `metadata.csv`? Checks taxdump age? | P0 §9 | open |
| D-24 | Should P0 special-case a bare `NA`/`N/A` in the `country` column as "no country" (matching the common missing-value convention) instead of resolving it to the real country Namibia via `pycountry`? | P0-D-011 | open |

## D. Security and provenance

| # | Question | Affects | Status |
|---|---|---|---|
| D-30 | Params shown in the report: allow-list; never keys/emails/passwords. Rotate exposed NCBI keys. | P6-D-001, OUT-004 | open (**urgent**) |
| D-31 | Enable Jinja autoescape and sanitise error HTML. | P6-D-002 | open |
| D-32 | Stop writing full config to `report_context.json`. | P6-D-003 | open |
| D-33 | Record reference-data versions (BLAST DB build date, taxdump date) in every report and `params_*.json`; separately, consider validating *identity*, not just presence, before a run starts — today `--blastdb` is only checked for being set and ending in `core_nt` (`NF-WF-013`, `DEP-030`), a purely superficial check a correctly-named but wrong/stale database trivially satisfies. BLAST+ itself catches a missing/corrupt database (its own index-loading error), but nothing catches a structurally valid, wrong one. | deployment §4, architecture §6, reference-data.md §1.1 | open |
| D-34 | Vault authentication model (identity vs email). | SEC-D-001 | open |

## E. Engineering

| # | Question | Affects | Status |
|---|---|---|---|
| D-40 | Make `default.yml` the single source and generate the schema (or vice versa); remove hard-coded names from Nextflow. | CFG-D-001, FN-002 | open |
| D-41 | Add `stub:` blocks and a stub-run CI job; add nf-test with a mocked API layer to CI. | NF-PR-008, TST-G-005, TST-003 | open |
| D-42 | Image: pin base/taxonkit, drop `latest`, add HMMER (or not), single release-consistency check for all five version locations. | IMG-D-001, DEP-D-001..003 | open |
| D-43 | Replace placeholder `1MB` memory defaults with real limits. | NF-D-011 | open |
| D-44 | Move Azure tenancy values out of the repo (overlay config). | DEP-D-006 | open |
| D-45 | Guard/replace the `429` string test in the retry policy. | THR-D-002 | open |
| D-46 | Rename `ch_candidates_for_report`'s stale first definition (line 217 of `workflows/taxodactyl.nf`) to something else — or delete it, if confirmed unused — so the name is bound exactly once. **Not** a proposal to collapse the two-phase naming itself: `ch_<step>_files` during computation, `ch_<step>_for_report` at hand-off, is nf-core's own documented `ch_<previousprocess>_for_<nextprocess>` convention ([nf-core contributing guide](https://nf-co.re/docs/contributing/contributing_to_pipelines)) and should be kept — the fix is narrowly about the double-binding, not the pattern. | NF-D-016 | open |
| D-19 | **(vs nf-core best practice)** Should error handling adopt the nf-core template's retry pattern (transient-failure exit codes retried with `task.attempt`-scaled resources, `ignore` only as a per-process opt-in label) instead of today's blanket `errorStrategy = 'ignore'`? Would reduce how often `NF-D-003` triggers, not just how it's reported. | NF-D-003, NF-D-011, NF-D-013 | open |
