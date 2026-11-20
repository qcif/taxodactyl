# Task 11 — Resolve the right genus for near-miss and duplicate COL names

**Status:** done

**Priority:** High: some virus targets get the wrong genus, so their 5.2/5.3
show 1 related species instead of about 22 (nf-test sample barcode_57).

**Issue:** none yet.

**Implementation authorization:** user-approved plan, 2026-11-19.

**Scope:** P5 target and genus resolution (`scripts/src/gbif/relatives.py`,
`scripts/src/coverage/targets.py`), with spec and unit tests.

**Source material:** Selenium review on 2026-11-19 of nf-test reports from
2026-11-18. Fixture
`test/selenium/expected/2_barcode_57_1916-01_Grapevine_virus_E_cluster_0_RC2300.yaml`.
Live GBIF and NCBI lookups on 2026-11-19. `spec/python/p5-db-coverage.md`:
P5-011, P5-012, P5-013, P5-016, P5-017 and P5-D-010.

## Problem

In sample barcode_57, `Vitivirus GVL` and `Grapevine virus` get genus
*Vitivirus* with 1 species. `Vitivirus epsilonvitis` gets the real genus, with
22 species. There are two causes.

1. **Duplicate accepted COL genera named *Vitivirus*.**
   - 338017750 is the real genus: 22 ICTV binomials, `numDescendants` 22.
   - 338017727 is a stray: only "Grapevine virus A", `numDescendants` 1.

   Neither record has authorship or `publishedIn`, so the task 08 tie-break
   (`_break_tie`) falls back to suggest order and picks the stray. The task 09
   genus fallback for `Vitivirus GVL` looks up 'Vitivirus' by name, so it gets
   the stray.
2. **Near-miss COL match.** COL has no record named "Grapevine virus", which is
   this sample's PMI and TOI. Suggest prefix-matches it to the species "Grapevine
   virus A" (key 338017729), whose genusKey is the stray genus. P5-D-010 only
   warns about this, so the target never reaches the NCBI path. Its 5.1 count
   (754) is Grapevine virus A's count, not the target's. NCBI has the exact name
   "Grapevine virus" (taxid 2934366), a species under "unclassified viruses"
   with no genus.

## Decisions (user, 2026-11-19)

- If COL returns a different accepted name (not a synonym) and NCBI has the
  exact input name, use the NCBI taxid for 5.1. Treat the target as not in COL.
- If NCBI gives no genus, take the genus from GBIF's closest COL match.
- Among same-name COL genera, use the one with the most species. This applies
  to genus lookups by name only. COL species keep their own genusKey.
- Testing: as in task 09. The agent writes and runs unit tests. The user owns
  the nf-test and Selenium review and the baseline updates.

## Implementation

1. `relatives.py`:
   - `_enrich_record` also copies `numDescendants` from the cached
     `api.name_usage` lookup.
   - `_break_tie` scores `numDescendants` first (missing counts as 0), then the
     existing signals, then suggest order.
   - `tie_break_message` includes the descendant counts.
   - *Drosophila* Fallén has 2427 descendants and the nominotypical record has
     0, so task 08's choice is unchanged.
2. `targets.py` `fetch_target_taxa`:
   - For an inexact non-synonym match, call `extract.taxids([target],
     classification=…)`.
   - If NCBI has a taxid, the target goes to `col_missing` with the closest
     COL name and genus and the known taxid. The P5-013 warning is not written.
   - Otherwise, today's behaviour is kept.
3. `targets.py` `_apply_genus_fallback`: the genus name is the NCBI genus or,
   failing that, the closest COL match's genus. An informational message names
   the source. The acceptance check is unchanged.

## Validation

- Unit tests:
  - tie-break by descendants, *Drosophila* unchanged, enrichment, and the
    message;
  - inexact match with and without an NCBI taxid;
  - closest-match genus end to end.
- flake8 clean. Full unit suite passes.
- User: core nf-test, then the `selenium-report` skill on barcode_57 and
  barcode_90.

## Completion criteria

- Same-name COL genus ties choose the record with the most descendants.
- A near-miss COL match with an exact NCBI name uses that taxid for 5.1, and a
  genus from NCBI or the closest COL match for 5.2/5.3.
- Spec (P5-011, P5-012/016, P5-013, P5-017, P5-D-010, §9) and COV-002 are
  updated. Tests pass.

## Outcomes

Implemented 2026-11-19 on branch `task-11-inexact-col-match-genus`.

### Completed work

- `scripts/src/gbif/relatives.py`:
  - `_enrich_record` copies `numDescendants`.
  - `_break_tie` ranks most descendants first.
  - `tie_break` stores `descendants`, and `tie_break_message` shows them, e.g.
    "(22 descendants)".
- `scripts/src/coverage/targets.py`:
  - **Near-miss COL match.** A non-synonym match whose name differs from the
    input, at a non-root rank, triggers a `taxonkit name2taxid` lookup of the
    input name.
    - If NCBI has the name, the target joins `col_missing` with that taxid and
      the closest COL name and genus (P5-018). The P5-013 mismatch warning is
      skipped.
    - Otherwise the old behaviour is kept.
  - `col_missing` entries are now dicts (`_col_missing_entry`).
    `_resolve_col_missing_taxa` only looks up taxids that aren't already known.
  - `NcbiOnlyTarget.closest_col_name` / `closest_col_genus`.
  - **Genus source.** `_apply_genus_fallback` uses the NCBI genus, else the
    closest COL match's genus. Its messages name the source.
  - **Error order.** The tie-break error is now written after the root-rank
    check, so root targets write no error (as P5-015 requires).
- Spec:
  - `spec/python/p5-db-coverage.md`:
    - P5-011: descendants come first.
    - P5-013: narrowed, with the new example message.
    - P5-018: new.
    - P5-017: genus source.
    - P5-D-010 and §9 updated.
  - `spec/defects.md` and `spec/reference-data.md`: P5-D-010 text.
  - `spec/contracts/coverage-and-sources.md`: COV-002.

### Deviations

- **Bookkeeping.** The main checkout was on `ci/build-pr-image`, so the task
  start (brief and `active.md` entry) was committed as the first commit on the
  task branch, not on `main`.
- **Wording.** The "not found" genus-fallback message changed from "its NCBI
  genus 'X' is not in COL either" to "its NCBI genus 'X' is not in COL." because
  the genus may now come from another source. One task 09 assertion was
  updated to match.

### Validation

- Unit tests (as in `.vscode/launch.json`): 229 run, OK (1 skipped);
  baseline was 223.
- New tests:
  - `test_gbif.py`: most descendants wins (Vitivirus 1 vs 22); descendants
    outrank the other signals; singular message; the *Drosophila* tie-break
    test now also checks `descendants` and the message.
  - `test_coverage_targets.py::NearMissColMatchTestCase`: 3 cases.
- flake8 clean on all changed files. `scripts/src/utils/cache.py:242` has a
  pre-existing E501; that file is not changed here.

### Pending manual review (user)

- Core nf-test, then the `selenium-report` skill on barcode_57.
  - Expected: `Vitivirus GVL` and `Grapevine virus` get genus *Vitivirus*,
    with about 22 species.
  - `Grapevine virus` 5.1 counts taxid 2934366, not Grapevine virus A's 754.
  - Promote species totals 22 (baseline 17), and the `Vitivirus epsilonvitis`
    count drift.
- Check barcode_90 (`Grapevine vitivirus`) for changes.

### Follow-ups

- Added to `tasks/todo.md`: a COL species target whose own genusKey is a
  stray duplicate genus (e.g. "Grapevine virus A" in 338017727) still gets
  that genus's relatives. This was left out of scope by the user's decision.
