# Task 09 — Assess DB coverage for targets missing from the COL taxonomy

**Status:** active

**Priority:** High: since #313, every target whose name isn't in COL is
dropped from flag 5. This includes unclassified-virus placeholders and virus
common names.

**Issue:** [#353 — DB coverage fails for targets missing from COL (e.g. unclassified viruses) since #313](https://github.com/qcif/taxodactyl/issues/353)

**Implementation authorization:** user-authorized 2026-11-18 (`/speckit-implement 09`).

**Scope:** P5 target resolution (`scripts/src/gbif/relatives.py`,
`scripts/src/coverage/targets.py`, `assess.py`, `fetch.py`). A target with no
COL record:

- **Phase A (required):** keeps its NCBI-based 5.1 check and gets a clear
  explanation instead of being dropped.
- **Phase B (open decision, below):** also gets 5.2/5.3 by resolving its genus
  from the NCBI lineage and looking that genus up in COL.

**Source material:** issue #353 (including its "Interim" note); Selenium review
of nf-test run 2026-11-17 (fixtures
`test/selenium/expected/2_barcode_57_1916-01_Grapevine_virus_E_cluster_0_RC2300.yaml`
and `3_barcode_59_1906-01_AB_Apple_hammerhead_viroid_cluster_0_RC3653.yaml`);
`spec/python/p5-db-coverage.md` (P5-012, P5-014, P5-020/021, P5-030, P5-060,
P5-D-002); `spec/contracts/coverage-and-sources.md` (COV-002). No Spec Kit
feature directory is configured, so this brief uses `spec/`, source and tests
directly.

## Preconditions

- Implement after tasks 07 and 08 merge, branching from `main`. Task 07 stops
  kingdom/domain targets before any lookup, so they must never reach the
  fallback here.
- Baseline (commit `33a164d`): `api.name_suggest` always filters to
  `COL_CHECKLIST_KEY` (`scripts/src/gbif/api.py:21-37`). When suggest finds
  nothing, `RelatedTaxaGBIF` raises `GBIFRecordNotFound` with "Please check
  that this species name is correct" (`relatives.py:206-208`).
  `fetch_target_taxa` logs it and `continue`s (`targets.py:128-140`). The
  target then gets `{target, related, country} = null`, no flags data and no
  NCBI links.
- Observed examples (run 2026-11-17):
  - Candidate `Vitivirus GVL` (NCBI taxid 2956654). COL has only ICTV binomials
    in *Vitivirus* (genus key 338017750).
  - PMI/TOI `Apple hammerhead viroid`, the NCBI and common name. COL has
    `Pelamoviroid malleusmali`. Before #313 this PMI had 5.1A (230 records,
    whole genome) and 5.2A over 3 *Pelamoviroid* species.
- Useful existing code:
  - `scripts/src/taxonomy/extract.py`: `taxids(names, classification=...)`
    (taxonkit name2taxid, ranked by score), and `taxonomies(taxids)` (taxonkit
    lineage → per-rank dict including `genus`).
  - `scripts/src/coverage/fetch.py:get_target_coverage(taxid, gbif_target,
    locus, is_bold)` uses only `gbif_target.taxon`, `.canonical_name` and
    `.rank`.
  - `scripts/src/bold/stats.py:fetch_bold_records_count(taxon, rank)` rejects
    some ranks. Check its allowed list before passing a rank.
- Keep the fix for P5-D-002 out of scope, but never query Entrez with
  `taxid=None` on the new path.

## Objective

### Phase A — keep 5.1 and explain the gap (required)

1. Reword `GBIFRecordNotFound` (`relatives.py`), e.g.:

   > '<name>' is not in the Catalogue of Life (COL) taxonomy used by GBIF. This
   > is common for unclassified viruses and virus common names. GBIF-based
   > checks (related species, country occurrence, distribution map) could not
   > be run.

   Also update the companion message in `fetch_target_taxa` (currently "No GBIF
   record found for target taxon... could not be evaluated") so it no longer
   says the whole target couldn't be evaluated.
2. Don't drop the target. Resolve its taxid with
   `extract.taxids([target], classification=classification)`.
   - **Taxid found:** run `get_target_coverage` for 5.1 using an NCBI-only
     stand-in (below). Grade 5.1 with the normal A/B/C rules. Set
     `ncbi_urls` (BLAST and taxonomy links) from the taxid and target name.
   - **No taxid:** keep today's behaviour (`target=None`, 5.1 `ERR`). Also
     write the existing `DB_COVERAGE_TAXONKIT_ERROR`.
3. Without Phase B, `related` and `country` stay `null` and 5.2/5.3 are `ERR`.
   The modal shows the reworded `DB_COVERAGE_NO_GBIF_RECORD` error and does
   **not** show the misleading "No related species found... error in the GBIF
   API" error.

### Phase B — genus fallback for 5.2/5.3 (open decision)

4. For a COL-missing target with a taxid, get its NCBI lineage
   (`extract.taxonomies([taxid])`) and take the `genus` name.
5. Look the genus up in COL with the query's classification
   (`RelatedTaxaGBIF(genus, classification=...)`). Accept the result only if its
   rank is genus. Then compute 5.2 from that genus record's `relatives` and 5.3
   from its `for_country`, as for a lower target. Report the genus name in
   `db_coverage.json` `genus`.
6. Write an informational `DB_COVERAGE` error such as:

   > '<target>' is not in COL; related-species checks use its NCBI genus
   > '<genus>' (COL key <key>).

7. If there's no NCBI genus, or the COL genus lookup fails, keep Phase A
   behaviour, plus one informational error saying why.
8. Occurrence map: the target has no COL taxon ID, so draw a placeholder map
   with "Occurrence maps are unavailable for taxa not in the Catalogue of
   Life" (`draw_placeholder_map`).

## Implementation

- `scripts/src/coverage/targets.py`:
  - Add a small `NcbiOnlyTarget` dataclass with `taxon`, `canonical_name`
    (= original name), `rank` and `taxid`. `rank` comes from the taxonkit
    lineage's lowest rank, mapped via `RANK.from_string`, falling back to
    `RANK.NONE`. In Phase B, add a `genus_record: RelatedTaxaGBIF | None`
    field. Use it wherever `get_target_coverage` needs a `gbif_target`.
  - Add `col_missing_taxa: dict[str, NcbiOnlyTarget]` (keyed by original
    name) to `TargetGbifRecords`. Fill it in the `GBIFRecordNotFound` branch.
  - Root taxa (task 07) must be excluded before this branch.
- `scripts/src/coverage/assess.py`:
  - Remove COL-missing targets from `unknown_taxa`.
  - Phase A: add `(get_target_coverage, taxid, ncbi_target, locus, is_bold)`
    tasks for those with a taxid.
  - Phase B: add the related-coverage task using the genus record. Check how
    `scripts/src/coverage/threads.py` (`parallel_process_tasks`, the
    `isinstance(target, RelatedTaxaGBIF)` check at line ~56) keys and merges
    results. Adapt it so results are stored under the original target name,
    not the genus.
  - Write results with `target=<count>`, `related=null` (A) or `{...}` (B),
    and `country` following P5-050/052. Leave the related/country values `null`
    where they were not assessed. That gives `ERR` as set out in Objective
    step 3.
  - Fill `ncbi_urls` with `ncbi.build_blast_url` / `build_taxonomy_url`.
- `_set_flags`: no change is expected for Phase A. 5.1 grades from the count,
  and `null` gives `ERR` for 5.2/5.3. Check that the "No related species found"
  error is only written for an empty `{}`, never for `null`.
- `scripts/src/coverage/fetch.py`: check that `get_target_coverage` and
  `fetch_bold_records_count` work with `NcbiOnlyTarget`. In BOLD mode, if the
  rank isn't accepted by `fetch_bold_records_count`, use `ERR` with an
  informational error rather than querying.

## Documentation and configuration

- `spec/python/p5-db-coverage.md`:
  - Rewrite P5-012 for the new not-in-COL behaviour (Phase A and, if done,
    Phase B).
  - Add requirements for the NCBI-only 5.1 path and the genus fallback.
  - Add P5-062 wording for the not-in-COL placeholder map.
  - Update §6 (`genus` may come from the NCBI-lineage fallback) and §9 tests.
- `spec/contracts/coverage-and-sources.md` COV-002: a target with no COL
  record may now have an integer `target` (NCBI count), and in Phase B a
  `related`/`country` result from its NCBI genus.
- `spec/defects.md`: no row for #353, so no deletion is needed.
- Issue #353's "Interim" note (accept ERR flags in nf-test) no longer applies
  once this merges. Mention this in the PR.
- `tasks/changelog.md` (at completion): e.g. "Database coverage now evaluates
  targets that aren't in the Catalogue of Life (e.g. unclassified viruses or
  virus common names) using their NCBI taxid [and NCBI genus], with a clearer
  explanation, instead of dropping them (task 09_targets_missing_from_col,
  #353)".

## Open decision

**Phase B in scope?** The issue lists the taxid/genus fallback as optional.

- With Phase B: Apple hammerhead viroid and Vitivirus GVL get 5.2/5.3 again,
  close to pre-#313 behaviour.
- Without Phase B: they get 5.1 only, with 5.2/5.3 `ERR` and a clear
  explanation.

**Pending user decision.** If Phase B is deferred, record it in `tasks/todo.md`
as a follow-up when this task completes.

## Testing decision

**Pending user input.** Proposed: the agent writes and runs the unit tests
below. The user reviews nf-test and Selenium drift and owns baselines and
fixtures.

## Validation

Unit tests (run as in task 07), mocking GBIF and taxonkit and deriving
expectations from this brief:

- `scripts/tests/test_gbif.py`: the `GBIFRecordNotFound` message mentions COL
  and no longer says "check that this species name is correct".
- Coverage-target tests (extend `test_gbif.py`, or a new
  `scripts/tests/test_coverage_targets.py` if allowed):
  - When suggest returns `[]` and `extract.taxids` returns
    `{'Vitivirus GVL': '2956654'}`, the target is in `col_missing_taxa` with
    that taxid and is not in `unknown_taxa`.
  - When `extract.taxids` returns `None` for the target, the target stays
    unknown and no Entrez call is made with `taxid=None`.
- `assess_coverage`/`_set_flags` case with `get_target_coverage` patched to
  return 230: 5.1 = `A`, 5.2 = `ERR` and 5.3 = `ERR` (Phase A), and
  `ncbi_urls` has a taxonomy URL containing the taxid. No "No related species
  found" error is written.
- Phase B, if in scope:
  - `extract.taxonomies` is patched to give genus `Pelamoviroid`, and
    `RelatedTaxaGBIF("Pelamoviroid")` is mocked as a genus with 3 relatives:
    `related` has 3 species, `genus == "Pelamoviroid"`, and the
    informational error is written once.
  - A non-genus result from the COL lookup falls back to Phase A behaviour.

flake8 on all changed Python files.

## Test impact and manual review

| Suite | Path | Expected change | Owner |
|---|---|---|---|
| Python unit | `scripts/tests/test_gbif.py`, `test_coverage_failure.py`, `test_report_coverage.py` | New cases. Existing tests must pass. If any test asserts the old not-found wording, update it with a stated reason. | Per testing decision |
| Python integration | `scripts/tests/integration/test_integration_coverage.py` | Probably unaffected (SME25 Drosophila data). Check for any COL-missing targets. | Per testing decision |
| nf-test core flags | `test/core/flags/query_006_barcode_57_*_5.{1,2,3}.flag`, `query_007_barcode_59_*_5.{1,2,3}.flag` | The baselines predate #313: `Vitivirus GVL` 5.1A, and Apple hammerhead viroid PMI/TOI 5.1A, with 5.2/5.3 to be checked in the files. With Phase A, 5.1 should match again and 5.2/5.3 will be `ERR`. With Phase B they may match fully. **User reviews** `bin/test_flags.py` output and owns baseline updates. | User |
| nf-test snapshot | `test/core/taxodactyl.workflow.nf.test.snap` | Hashes change for barcode_57/59 (`db_coverage.json`, errors, report). **User reviews.** Do not update automatically. | User |
| Selenium | `test/selenium/expected/2_*.yaml`, `3_*.yaml` | Held back on 2026-11-18 because of this bug. 5.1 record counts (Vitivirus GVL, Apple hammerhead viroid) should come back. 5.2 fields depend on Phase B. The stale `flag_text2 "Warning no locus provided"` values in these two fixtures also need promoting. **User reviews** with the `selenium-report` skill and promotes. | User |

Handoff: run the core nf-test, then the `selenium-report` skill on the
reports. Check:

- the barcode_57 `Vitivirus GVL` and barcode_59 Apple hammerhead viroid modals
  (5.1 count and NCBI link present; 5.2/5.3 match the chosen phase);
- the reworded error text;
- that no target found in COL changed.

## Completion criteria

- No target is dropped just because it isn't in COL. Targets with an NCBI taxid
  get a 5.1 grade and NCBI links, and the report explains why GBIF-based checks
  are missing or come from the NCBI genus.
- No Entrez query is made with `taxid=None` on the new path.
- Phase B is either done to its criteria or recorded as a follow-up in
  `tasks/todo.md`.
- Spec and contract updated. Agreed unit tests pass and flake8 is clean.
- Manual nf-test and Selenium review recorded as pending or user-confirmed.

## Risks

- taxonkit name2taxid on a common name can match the wrong taxon. The
  classification filter limits this. Log the resolved taxid and name at INFO.
- Phase B mixes taxonomies (NCBI genus, COL species list). The genus name may
  not exist in COL, or may mean something else there. The rank-genus check and
  the informational error make this visible.
- `threads.py` result keying is the most likely source of mistakes in Phase B.
  Test that results land under the original target name.
