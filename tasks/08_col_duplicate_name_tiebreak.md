# Task 08 — Break ties between duplicate COL records with the same name

**Status:** active

**Priority:** High: intermittent 5.2 `ERR` for genus-level targets such as
*Drosophila* (SME25-218), which makes nf-test and Selenium results flaky.

**Issue:** [#351 — Selection of GBIF name_suggests result creates error for Drosophila](https://github.com/qcif/taxodactyl/issues/351)

**Implementation authorization:** granted by user via `/speckit-implement 08` (2026-11-18).

**Scope:** `RelatedTaxaGBIF._get_taxon_record` in
`scripts/src/gbif/relatives.py`, and recording of tie-break events in
`scripts/src/coverage/targets.py`. When several accepted suggest results share
the chosen record's name and rank, pick the populated, well-formed record,
whatever order GBIF returns them in.

**Source material:** issue #351; `spec/python/p5-db-coverage.md` (P5-011,
P5-D-010); nf-test run `2026-11-17_021237`. No Spec Kit feature directory is
configured, so this brief uses `spec/`, source and tests directly.

## Preconditions

- Implement after task 07 (`07_kingdom_targets_not_assessed`) merges, and
  before task 09. All three edit `scripts/src/gbif/relatives.py` and
  `scripts/src/coverage/targets.py`. Branch from `main` after 07 merges.
- Baseline (commit `33a164d`): `_get_taxon_record`
  (`scripts/src/gbif/relatives.py:150-208`) returns the **first** suggest
  result that passes `_is_accepted` (after synonym replacement).
- Data problem (persistent as of 2026-11-17). The COL checklist
  `7ddf754f-d193-4cc9-b351-99906754a03b` has two accepted genus records named
  *Drosophila*:

  | Key | `scientificName` | Parent | `publishedIn` | Species under it |
  |---|---|---|---|---|
  | 298353264 | *Drosophila* Fallén, 1823 | Drosophilina | Fallén (1823) | 3417 |
  | 314480147 | *Drosophila* Fallen-Nominotypical | Drosophilini | none | **0** |

  Both score the same for `q=Drosophila`, so their order depends on GBIF's tie
  handling. When 314480147 comes first, `relatives` is empty and 5.2 gets
  `ERR` ("No related species found in genus 'Drosophila'").
- Reproduce:

  ```bash
  DS=7ddf754f-d193-4cc9-b351-99906754a03b
  curl -s "https://api.gbif.org/v1/species/suggest?q=Drosophila&limit=20&datasetKey=$DS&higherTaxonKey=296374190" | jq '.[:3][] | {key, scientificName, rank, status}'
  curl -s "https://api.gbif.org/v1/species/search?rank=species&higherTaxonKey=314480147&datasetKey=$DS&limit=1" | jq .count   # 0
  curl -s "https://api.gbif.org/v1/species/search?rank=species&higherTaxonKey=298353264&datasetKey=$DS&limit=1" | jq .count   # 3417
  ```

- Before coding, check which fields `/v1/species/suggest` actually returns,
  using the first curl above. Use `scientificName`, `authorship` and
  `publishedIn` only if they are present. If a field is missing, either fetch
  it with one cached `name_usage` call per tied record, or drop that signal.
  Record which in Outcomes.

## Objective

1. Go through suggest results as now (same accepted-status, extinct and rank
   rules, same synonym replacement), and take the first accepted record `R`.
2. Gather every other accepted record in the same response with the same
   lower-cased `canonical_name` and the same `rank` as `R`. If there are none,
   return `R` (unchanged behaviour, no extra requests).
3. If there are ties, choose deterministically, in this order:
   1. Prefer records whose `scientificName` (and `authorship`, if present) does
      **not** contain "nominotypical" (case-insensitive).
   2. Prefer records with a well-formed authorship ending in a 4-digit year,
      e.g. `Fallén, 1823` or `(Linnaeus, 1758)`.
   3. Prefer records with a non-empty `publishedIn`.
   4. Otherwise keep suggest order.
4. When a tie-break happens, record it so it shows in the report. Write an
   informational `DB_COVERAGE` error with `context={'target': <original
   target>}` listing the chosen key/name and the rejected key(s)/name(s), e.g.:

   > GBIF returned 2 accepted records named 'Drosophila' (genus). Using key
   > 298353264 'Drosophila Fallén, 1823'; ignoring 314480147 'Drosophila
   > Fallen-Nominotypical'.

## Implementation

- In `scripts/src/gbif/relatives.py`:
  - Refactor the loop in `_get_taxon_record` into two steps. First, build the
    list of accepted `GBIFRecord`s in suggest order, keeping the synonym
    handling and `from_synonym` assignment. Second, select from them.
    `from_synonym` must reflect the record finally chosen.
  - Add `_break_tie(records: list[GBIFRecord]) -> GBIFRecord` as a pure
    function implementing Objective step 3, plus regex constants for the
    authorship check (`AUTHORSHIP_YEAR_RE`) and the nominotypical marker,
    defined under the imports.
  - Fill in the COL `taxon_id` (`api.get_col_taxon_id`) only for the chosen
    record. Don't make lookups for rejected ones.
  - Store tie details on the instance, e.g.
    `self.tie_break = {'chosen': (key, name), 'rejected': [(key, name), ...]}`,
    or `None` when there was no tie. `RelatedTaxaGBIF` has no `query_dir`, so
    it can't write errors itself.
- In `scripts/src/coverage/targets.py` `fetch_target_taxa`: after a successful
  lookup, if `gbif_target.tie_break`, log a warning and call `errors.write`
  with `errors.LOCATIONS.DB_COVERAGE`, the Objective message and
  `context={'target': target}`. Follow the existing `from_synonym` pattern
  (`targets.py:156-169`).
- Out of scope: this task does not pick between records with *different*
  names (P5-D-010, fuzzy suggest).

## Documentation and configuration

- `spec/python/p5-db-coverage.md`:
  - Amend P5-011: "first" now means the first accepted suggestion, then the
    same-name/same-rank tie-break, with its order and the informational error.
  - Add a note to P5-013's list of informational errors.
  - Add the new tests to §9.
- `spec/defects.md`: no row for #351, so no deletion is needed.
- `tasks/changelog.md` (at completion): e.g. "Database coverage now picks the
  correct GBIF record when the Catalogue of Life has duplicate accepted records
  with the same name (e.g. *Drosophila*), avoiding intermittent 5.2 ERR flags,
  and notes the choice in the report (task 08_col_duplicate_name_tiebreak,
  #351)".

## Testing decision

Agreed 2026-11-18: the agent writes and runs the unit tests
below. The user reviews nf-test and Selenium drift and owns baselines and
fixtures.

## Validation

Unit tests (run as in task 07), in `scripts/tests/test_gbif.py` following the
existing `@patch('src.gbif.api.name_suggest')` pattern
(`test_classification_filter`, line ~80):

- Use a mocked suggest response that lists the empty duplicate **first**:
  `{key: 314480147, scientificName: "Drosophila Fallen-Nominotypical",
  canonicalName: "Drosophila", rank: "GENUS", status: "ACCEPTED"}` then
  `{key: 298353264, scientificName: "Drosophila Fallén, 1823", ...}`.
  `RelatedTaxaGBIF("Drosophila").key == 298353264` and `tie_break` names
  314480147 as rejected.
- The same records in the opposite order still give 298353264.
- A single accepted record gives `tie_break is None` and no extra
  `name_usage`/`get_col_taxon_id` calls beyond today's.
- Two records with the same name but different ranks (genus vs subgenus, or
  genus vs species): no tie-break, the first is kept.
- `_break_tie` unit cases cover each signal on its own (nominotypical marker;
  authorship with vs without a year; publishedIn present vs empty) and the
  fallback to suggest order.
- A `fetch_target_taxa` case (with `RelatedTaxaGBIF` patched to have a
  `tie_break`) writes exactly one `DB_COVERAGE` error with the target context.

flake8 on all changed Python files.

## Test impact and manual review

| Suite | Path | Expected change | Owner |
|---|---|---|---|
| Python unit | `scripts/tests/test_gbif.py` | New cases. Existing synonym/extinct/classification cases must pass unchanged. | Per testing decision |
| Python integration | `scripts/tests/integration/test_integration_coverage.py`, test data `scripts/tests/test-data/integration/blast/206/` (SME25-218..220, PMI *Drosophila*) | Should become stable for PMI *Drosophila*. With live GBIF a tie-break error is now also written, so check whether `kit/coverage_assert.py` or error-count assertions are affected. | Per testing decision |
| nf-test core flags | `test/core/flags/query_013_SME25-218_5.2.flag` | The baseline expects `pmi Drosophila B`. Runs should match it every time instead of sometimes giving `ERR`. **User reviews.** | User |
| nf-test snapshot | `test/core/taxodactyl.workflow.nf.test.snap` | Error JSON / report hashes change for SME25-218 (new tie-break error) and any other duplicated name. **User reviews.** Do not update automatically. | User |
| Selenium | `test/selenium/expected/18_SME25-218.yaml` | Held back on 2026-11-18 because of this bug. After the fix, `database_coverage.flag_text2 (Drosophila)` should no longer be `5.2ERR`. **User reviews** and promotes fixture 18. | User |

Handoff: run the core nf-test at least twice, since the bug was intermittent.
Confirm SME25-218 PMI 5.2 is `B` both times and the modal shows the
tie-break note. Run the `selenium-report` skill on the reports.

## Completion criteria

- A *Drosophila* PMI resolves to 298353264 whatever the suggest order, and the
  tie-break is reported as an informational error.
- Responses without ties behave and make requests exactly as before.
- Spec updated as listed. Agreed unit tests pass and flake8 is clean.
- Manual nf-test and Selenium review recorded as pending or user-confirmed.

## Risks

- Other COL duplicates may not have a "nominotypical" marker. The authorship
  and publishedIn signals reduce that risk but don't remove it. The new
  informational error makes any such cases visible in reports for follow-up.
