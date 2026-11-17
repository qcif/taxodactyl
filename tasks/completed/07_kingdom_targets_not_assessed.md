# Task 07 — Report kingdom/domain-level DB coverage targets as not assessed

**Status:** done

**Priority:** High: regression from #313 (COL refactor). Any sample whose PMI
or TOI names its own kingdom loses all of flag 5.

**Issue:** [#354 — DB coverage: kingdom-level PMI/TOI fails GBIF lookup since #313; should report 5.*NA](https://github.com/qcif/taxodactyl/issues/354)

**Implementation authorization:** granted by user via `/speckit-implement 07` on 2026-11-18.

**Scope:** P5 database coverage target handling (`scripts/src/coverage/`,
`scripts/src/gbif/relatives.py`) and the DB coverage modal template. A target
naming a kingdom, domain or COL root ("Fungi", "Plantae", "Bacteria",
"Viruses", ...) is not looked up or counted. It gets flags 5.1, 5.2 and 5.3
set to `NA`, with a message saying why.

**Source material:** issue #354; `spec/python/p5-db-coverage.md` (P5-010,
P5-012, P5-014, §5, §6); `spec/contracts/coverage-and-sources.md` (COV-002,
COV-004); Selenium review of nf-test run 2026-11-17 (fixture
`test/selenium/expected/10_FungusB_Btub.yaml`). No Spec Kit feature directory
is configured, so this brief uses the existing `spec/` documents, source and
tests directly. `.specify/memory/constitution.md` is an unfilled template.

## Preconditions

- Tasks 08 (#351) and 09 (#353) also change
  `scripts/src/gbif/relatives.py` and `scripts/src/coverage/targets.py`.
  Implement these three tasks in order 07 → 08 → 09. Each task branches from
  `main` after the previous one merges. Task 09 relies on this task stopping
  kingdom-level targets before any GBIF lookup.
- Baseline behaviour (commit `33a164d`): `fetch_target_taxa`
  (`scripts/src/coverage/targets.py:113`) builds a `RelatedTaxaGBIF` for
  every target. `RelatedTaxaGBIF._get_taxon_record`
  (`scripts/src/gbif/relatives.py:150`) rewrites a `KINGDOM_TAXA` name to
  `q=<root>&rank=<Kingdom|Domain|Unranked>`. It then adds
  `higher_taxon_key=<classification usage key>`. When the classification is
  the same kingdom, `higherTaxonKey` matches only descendants, so suggest
  returns nothing. That raises `GBIFRecordNotFound` and the target is skipped
  (`targets.py:128-140`). It ends up with `{target, related, country} = null`
  and ERR flags.
- Reproduce:

  ```bash
  DS=7ddf754f-d193-4cc9-b351-99906754a03b
  U=https://api.gbif.org/v1/species/suggest
  curl -s "$U?q=fungi&rank=KINGDOM&datasetKey=$DS" | jq '.[] | {key, scientificName}'   # 299629601 Fungi
  curl -s "$U?q=fungi&rank=KINGDOM&datasetKey=$DS&higherTaxonKey=299629601" | jq length # 0
  ```

- The current higher-rank path (family and above, P5-014) still fetches a
  record count for 5.1 and sets every flag to `NA`, explained by the
  `flags.csv` text "Assessment of related species is only possible for taxa at
  rank genus/species". That explanation doesn't account for 5.1 being `NA`.
  This task leaves family to phylum targets unchanged.

## Objective

When a target is at kingdom, domain or COL-root level:

1. Make no GBIF, taxonkit, Entrez/BOLD or occurrence requests for it.
2. Write flags 5.1, 5.2 and 5.3 as `NA` for each `(target, target_type)`.
3. Write no error. This is expected behaviour, not a failure, so the modal
   must not show an "Issues encountered" block for it.
4. Show this message in the DB coverage modal, in place of the generic "No
   database coverage information is available... likely because... an error
   was encountered":

   > Database coverage is not assessed for taxa at kingdom or domain rank
   > (*<target>*), because they are too broad for this analysis to be
   > meaningful.

5. Leave genus/species (lower) and family-to-phylum (higher) targets as they
   are.

## Implementation

### 1. Identify root-level targets

- In `scripts/src/gbif/relatives.py`, add a module-level helper
  `is_root_taxon(name: str) -> bool` that returns
  `name.strip().lower() in KINGDOM_TAXA`. Keep `KINGDOM_TAXA` as the single
  source of names. Do not fix P5-D-009 (protozoa → protista) here.
- Also define `ROOT_RANKS = {RANK.KINGDOM, RANK.DOMAIN, RANK.UNRANKED}` next to
  `RANK`. This catches names that `KINGDOM_TAXA` misses but GBIF resolves to a
  root rank.

### 2. Stop them in `fetch_target_taxa`

In `scripts/src/coverage/targets.py`:

- Add `root_taxa: list[str]` to `TargetGbifRecords`, holding original target
  names in input order without duplicates. Document it in the dataclass
  docstring.
- In `fetch_target_taxa`, before building `RelatedTaxaGBIF`: if
  `is_root_taxon(target)`, append the target to `root_taxa`, log at INFO, and
  `continue`. No errors.write.
- After a successful lookup, if `gbif_target.rank in ROOT_RANKS`, treat it the
  same way and don't add it to `lower_taxa`/`higher_taxa`. Keep the existing
  "analysed based on the first GBIF-accepted name" informational error only
  for targets that are still assessed.
- Keep `all_taxa`, `original_taxa` and the name maps free of root taxa, so
  `get_taxids`, `_draw_occurrence_maps` and the coverage tasks never see them.

### 3. Results, flags and output in `scripts/src/coverage/assess.py`

- Exclude root taxa from `unknown_taxa`. Give each one this result entry
  instead:
  `{'target': None, 'related': None, 'country': None, 'not_assessed': <message>}`.
  Use the Objective message with the original target name, defined once as a
  module constant template, e.g. `ROOT_TAXON_NOT_ASSESSED_MSG`.
- `assess_coverage` currently raises `ValueError("No tasks created...")` when
  `len(tasks) + len(unknown_taxa) == 0`. A query whose only target is a root
  taxon (e.g. the FungusB PMI with no candidates) must not hit this. Count root
  taxa in that guard.
- Add `ncbi_urls[<target>] = {'blast': None, 'taxonomy': None}` for root
  taxa.
- In `_set_flags`, add a `root_taxa` parameter (default empty) and write `NA`
  for 5.1, 5.2 and 5.3 for those targets, without the `count is None` ERR
  branch. Pass `[]` from `failed_coverage`.
- Make sure no occurrence-map file is expected for root taxa. Check the
  templates: if a missing map file breaks rendering, draw a placeholder map with
  the Objective message via `draw_placeholder_map`. Record which you chose in
  Outcomes.

### 4. Summary Flag 5

- Read `Flag.read` / the level rollup in `scripts/src/utils/flags.py` (around
  lines 100-160). Spec §5.4 says a level below 2 is replaced by `5B` when the
  query has no locus. Check that a target whose 5.1-5.3 are all `NA` still
  rolls up to `5NA` whether or not a locus was given. If it doesn't, special-case
  all-NA targets to `5NA` and record this in Outcomes and in spec §5.4.
  `scripts/tests/test_flags_coverage.py` covers the related ERR/no-locus
  cases. Follow its pattern.

### 5. Report template

- In `scripts/src/report/templates/macros/db-coverage-target-modal.html`,
  inside the `context.data.target is none and ... related is none and ...
  country is none` branch (line 73), render `context.data.not_assessed` when it
  is present. Use `<p class="alert alert-secondary">`, no `<strong>` label, and
  the target name in `<em>`. Keep the generic message and the candidate-count
  message for every other case.
- This macro is shared by the main report (`components/conclusions/pmi-table.html`,
  `components/results/toi-modals.html`,
  `components/results/1-candidate-species.html`) and the coverage-mode report
  (`templates/coverage/index.html`). Check that both render the new message
  and that summary-table badges show NA.

## Documentation and configuration

- `spec/python/p5-db-coverage.md`:
  - Add a requirement in §4.1 (e.g. P5-015) for root-level targets: no
    lookups, all flags `NA`, `not_assessed` message, no error.
  - Amend P5-010 to say kingdom names never reach suggest as targets.
  - Add the new case to the §5.1-5.3 tables.
  - Add `not_assessed` to the §6 JSON shape.
  - Add the new tests to §9.
- `spec/contracts/coverage-and-sources.md`: add a COV requirement. Root-level
  targets have `target/related/country = null` plus a `not_assessed` string.
  `null` there means "not assessed by design". Extend COV-004 to say so.
- `spec/defects.md`: no row exists for #354, so there's nothing to delete. Do
  not add one.
- `tasks/changelog.md` (at completion): one line, e.g. "Database coverage now
  reports flags 5.1-5.3 as NA, with an explanation, for kingdom- or
  domain-level targets such as 'Fungi', instead of failing with 'No GBIF record
  found' (task 07_kingdom_targets_not_assessed, #354)".

## Testing decision

**Decided 2026-11-18** (user accepted the proposal).

- The agent writes and runs the automated unit tests listed under
  Validation. The user reviews nf-test flag/snapshot drift and Selenium drift,
  and owns any baseline or fixture updates.

## Validation

Automated (scope set by the testing decision). Run from the repo root with the
command from `.vscode/launch.json` "Unit tests":

```bash
source scripts/venv/bin/activate
cd scripts && GENBANK_CONCURRENCY_TEST=0 PYTHONPATH=. python -m unittest discover -s tests -p "test*.py" -b
```

Proposed new or extended unit tests (derive expectations from the Objective,
not from the code's output):

- `scripts/tests/test_gbif.py`: `is_root_taxon` returns True for "Fungi",
  "fungi", " Viruses ", "metazoa" and False for "Drosophila", "Fungus gnat".
- Coverage-target tests in `scripts/tests/test_gbif.py`, or a new
  `scripts/tests/test_coverage_targets.py` if the testing decision allows a new
  file:
  - `fetch_target_taxa(["Fungi"], query_dir)` with classification `fungi`
    returns "Fungi" in `root_taxa` and nothing in `all_taxa`.
  - It makes no call to `src.gbif.api.name_suggest`. Patch it and assert
    `not_called`.
  - It writes no error file.
- An `_set_flags` test: a root taxon gets `NA` for 5.1, 5.2 and 5.3. A
  lower-target entry with `target=None` in the same call still gets `ERR`, so
  ERR behaviour is kept.
- `scripts/tests/test_report_coverage.py`: a coverage-mode report whose target
  has `not_assessed` shows the message and not the generic "error was
  encountered" text.
- If §4's rollup check needed a change: a `test_flags_coverage.py` case where
  an all-NA target with no locus rolls up to `5NA`.

Run `/home/cameron/.local/envs/claude/bin/flake8` on every changed Python file.

## Test impact and manual review

| Suite | Path | Expected change | Owner |
|---|---|---|---|
| Python unit | `scripts/tests/test_gbif.py`, `test_flags_coverage.py`, `test_report_coverage.py`, `test_coverage_failure.py` | New cases. Existing cases should pass unchanged. | Per testing decision |
| Python integration | `scripts/tests/integration/test_integration_coverage.py`, `kit/coverage_assert.py` | Probably unaffected: the test data (`scripts/tests/test-data/integration/blast/206/metadata.csv`) has no kingdom-level targets. Check, and report if it does. | Per testing decision |
| nf-test core flags | `test/core/flags/query_018_FungusB_Btub_5.1.flag`, `_5.2.flag`, `_5.3.flag` | The baseline already expects `pmi Fungi NA`. The 2026-11-17 run gives no flags or ERR, so the fix should bring it back in line. **User reviews** the `bin/test_flags.py` comparison. | User |
| nf-test snapshot | `test/core/taxodactyl.workflow.nf.test.snap` | `db_coverage.json` and report hashes for FungusB_Btub will change (new `not_assessed` key). **User reviews** the drift. Do not update the snapshot automatically. | User |
| Selenium | `test/selenium/expected/10_FungusB_Btub.yaml` | This fixture was held back on 2026-11-18 because of this bug. After the fix, `database_coverage.flag_text1/flag_text2 (Fungi)` should show `5.1NA`/`5.2NA` again. The new message is in a plain alert, so the collector reads empty flag text if it doesn't find the NA flags. **User reviews** the drift and runs `testkit promote 10`. | User |

Handoff for manual review: after merge, run the nf-test core scenario on the
runner (`.github/workflows/nf-test.yml`, or `bin/nf-test.sh`). Then use the
`selenium-report` skill with the new reports directory. Check that:

- the FungusB_Btub PMI modal shows the new message, has no "Issues
  encountered" block, and has NA flags;
- `test/core/flags/query_018_*` match;
- no other sample's flag 5 changed except through known drift.

## Completion criteria

- Kingdom/domain/root targets make no external lookups, get `NA` for 5.1-5.3,
  write no error, and show the message in both report types.
- Lower and higher (family-phylum) target behaviour is unchanged, shown by
  existing tests passing.
- Spec and contract updates are made as listed. Unit tests agreed in the
  testing decision pass and flake8 is clean.
- Manual nf-test/Selenium review is recorded as pending, or as passed only with
  the user's evidence.

## Risks

- Treating `RANK.UNRANKED` as root assumes COL's only unranked accepted taxa are
  roots such as Viruses. If an unranked non-root record turns up, it would
  silently become NA. Log the resolved key and name at INFO.
- `KINGDOM_TAXA` has a "chlorophyta" → plantae entry. Chlorophyta is a
  phylum, so a target "Chlorophyta" would now get NA rather than family+
  handling. That's acceptable (still far too broad), but note it in the spec.

## Outcomes

Completed 2026-11-18 on branch `task-07-kingdom-targets-not-assessed`.

### Implemented

- `scripts/src/gbif/relatives.py`: `is_root_taxon(name)` (stripped,
  lower-cased name in `KINGDOM_TAXA`) and `ROOT_RANKS = {KINGDOM, DOMAIN,
  UNRANKED}`.
- `scripts/src/coverage/targets.py`: `TargetGbifRecords.root_taxa` (original
  names, input order, no duplicates). `fetch_target_taxa` stops root names
  before building `RelatedTaxaGBIF`, and moves records that resolve to a
  `ROOT_RANKS` rank into `root_taxa` (key, name and rank logged at INFO). No
  errors are written for either, and root taxa are kept out of every other
  field. `get_taxids` now returns `{}` without running taxonkit when there
  are no targets left, so a root-only query makes no taxonkit call.
- `scripts/src/coverage/assess.py`: `ROOT_TAXON_NOT_ASSESSED_MSG`; root taxa
  are excluded from `unknown_taxa`, get
  `{target, related, country: null, not_assessed: <message>}` for each role
  they appear in, `ncbi_urls` of `null`, count in the "No tasks created"
  guard, and are passed to `_set_flags(..., root_taxa=...)`, which writes
  `NA` for 5.1-5.3. `failed_coverage` passes `root_taxa=[]`.
- Occurrence maps: **no placeholder map is drawn** for root taxa. The report
  already handles a missing map file (`_get_img_src` falls back to the
  placeholder image, and the map is only rendered in the modal's assessed
  branch, which root taxa never reach).
- `scripts/src/report/templates/macros/db-coverage-target-modal.html`: when
  `not_assessed` is set, the modal shows it in `alert alert-secondary` with
  the target name in `<em>`, in place of the generic message. The macro is
  shared by the main and coverage-mode reports, and the main report's PMI,
  TOI and candidate views use the same `db_coverage.json` shape that
  unresolved targets already render with; only the coverage-mode report is
  exercised by a unit test.

### Summary Flag 5 (§4 of this brief)

The check found a bug: an all-`NA` target with no locus rolled up to `5B`
("locus was not provided"). `Flag._post_process_flags`
(`scripts/src/utils/flags.py`) now skips the `5B` replacement when 5.1, 5.2
and 5.3 are all `NA`, so the summary stays `NA` (level 0) with or without a
locus. With a locus the representative flag is still the `5.1NA` flag, as
before, to avoid report drift. This also changes family-to-phylum targets
on queries **without a locus** from `5B` (warning) to `NA`; documented in
spec §5.4. Targets with only some 5.* flags `NA` (e.g. 5.3 when there is no
country) still get `5B`.

### Documentation

- `spec/python/p5-db-coverage.md`: new P5-015 (incl. the Chlorophyta and
  `UNRANKED` notes from Risks); P5-010, P5-014 and P5-060 amended; root rows
  in §5.1-5.3; §5.4 rollup rule; `not_assessed` in §6; tests in §9.
- `spec/contracts/coverage-and-sources.md`: `not_assessed` in the JSON shape,
  COV-004 amended, new COV-005.
- `spec/defects.md` and p5 §8: P5-D-009 narrowed to its below-genus rank
  half. Its "protozoa → protista" half is resolved by P5-015: a "protozoa"
  target is now reported not assessed before any lookup, so the wrong
  canonical name is never used. No row was added for #354.

### Validation

- Unit tests (agent-owned, per the testing decision): new
  `scripts/tests/test_coverage_targets.py` (6 tests: no lookups for root
  names, ordering and de-duplication, root-rank resolution for kingdom,
  domain and unranked, family still higher, end-to-end `assess_coverage` for
  a Fungi-only query with no GBIF/taxonkit/Entrez calls, NA flags, no errors
  or map, and `_set_flags` keeping `ERR` for a failed lower target);
  `TestIsRootTaxon` in `test_gbif.py`; three roll-up cases in
  `test_flags_coverage.py` (both all-NA cases failed before the fix);
  `ReportRootTaxonTestCase` in `test_report_coverage.py`. Full suite: 202
  tests OK (1 skipped), run from `scripts/` with `PYTHONPATH=.:..` (the
  repo root is needed for `test_phylogeny_sampling.py`, as in launch.json).
- flake8: clean on all changed Python files.
- Integration test data (`scripts/tests/test-data/integration/blast/206/metadata.csv`)
  has no kingdom-level targets, so the integration suite should be unaffected.

### Pending manual review (user-owned)

Not run by the agent: nf-test core (`test/core/flags/query_018_FungusB_Btub_5.*.flag`,
snapshot drift for FungusB_Btub `db_coverage.json` and report hashes) and the
Selenium review of `test/selenium/expected/10_FungusB_Btub.yaml`
(`testkit promote 10`), as described under "Test impact and manual review".
Also watch for flag 5 summary drift on family-to-phylum targets in samples
without a locus (now `NA` instead of `5B`).

### Spin-offs (added to `tasks/todo.md`)

- `RelatedTaxaGBIF._get_taxon_record`'s `KINGDOM_TAXA` rewrite is now
  unreachable (its only caller, `fetch_target_taxa`, stops those names
  first). Left in place to keep this task's code change minimal.
