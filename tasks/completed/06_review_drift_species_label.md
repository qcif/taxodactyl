# Task 06 — Show target species in Selenium drift rows

**Status:** done

**Priority:** Unassigned; developer-experience improvement to test review.

**Scope:** In the Selenium review page (`test/selenium/review.html`), the
drift table's **Field** cell for `database_coverage` and `publication_modal`
assertions should name the target taxon, so reviewers can tell which modal
(PMI, TOI or candidate coverage, or a candidate's publications) drifted.
Example:

```
Field                                              Type  Expected  Observed
database_coverage.min_bar_count (Homo sapiens)      min   39        35
publication_modal.count (Spodoptera frugiperda)     list  ['47']    ['49']
```

The label is the taxon alone, without the role (PMI/TOI/candidate). The user
confirmed on 2026-11-17 that identical labels across groups are acceptable.

Use the same label in the other places that print drifted assertions:
`Report.assert_all()` (pytest failure message) and `testkit.py promote`
prompts. Only labels change. Assertion ids, comparison logic, YAML fixture
format, flex handling and pass/fail outcomes stay exactly as they are.

**Source material:** User request on 2026-11-17. Code inspected at `0b39089`:
`test/selenium/lib/report.py`, `test/selenium/lib/database_coverage.py`,
`test/selenium/lib/schema.py`, `test/selenium/conftest.py`,
`test/selenium/lib/render.py`, `test/selenium/lib/templates/review.html.j2`,
`test/selenium/lib/promote.py`, `test/selenium/README.md`, `spec/tests.md`
(TST-030 to TST-033). No active Spec Kit feature directory is configured, so
this brief works from the `spec/` documents and the code directly.

**Implementation authorization:** granted by the user on 2026-11-17
(`/speckit-implement task 06`).

## Preconditions

- Current data flow:
  - `CoverageRowCollector` (`test/selenium/lib/database_coverage.py`)
    collects one row per coverage modal into
    `report.database_coverage.<group>[idx]`, where group is `pmi`, `toi` or
    `candidate`. It does not set a row `name`. `get_or_extend_group_row` is
    called without `name=`.
  - Each row has a `title` assertion (type `list`). Its value in every
    fixture under `test/selenium/expected/*.yaml` has one of these forms:
    - `Database coverage of Preliminary Morphology ID <taxon>`
    - `Database coverage of Taxon of Interest <taxon>`
    - `Database coverage of Candidate <taxon>`

    `<taxon>` may be a higher rank (`Diptera`, `Planta`) or contain
    punctuation (`Phyllocnistinae sp. BOLD:ABZ3983`, `Bulimulus aff.
    sporadicus`).
  - `Report.drifted()` returns a flat list of `Assertion` objects. An
    `Assertion` knows `component` and `assertion_id`, but not which group
    row it belongs to.
  - `conftest._drift_records()` turns each drifted assertion into a dict
    (`component`, `assertion_id`, `type`, `flex`, `expected`, `observed`)
    and writes it to `test/selenium/test-report.json`.
    `testkit.py render` → `lib/render.py:render_html` →
    `lib/templates/review.html.j2` builds the Field cell as
    `{{ d.component }}.{{ d.assertion_id }}`.
  - `Report.assert_all()` (`lib/report.py`) and `promote_yaml` in
    `lib/promote.py` print `[{a.component}.{a.assertion_id}]`.
- `publication_modal` rows (group `candidates`, fields `title`, `source`,
  `count`) already carry the species as the row namespace attribute `_name`:
  - Collection: `lib/candidate.py` calls
    `get_or_extend_group_row("publication_modal", "candidates", pub_i,
    name=species_name)`, where `species_name` is the candidate table's first
    cell.
  - Fixtures: every `publication_modal.candidates[]` entry in
    `test/selenium/expected/*.yaml` has a `name:` key (20 of 20 at
    `0b39089`). `parse_yaml` passes it through as `_name`.
  - Note: `get_or_extend_group_row` only applies `name` to rows it creates,
    so a row parsed from YAML keeps its fixture name.

## Objective

Every drifted `database_coverage` and `publication_modal` assertion shows its
target taxon in parentheses after the field path, in review.html, in the
pytest assertion message and in promote prompts. Labels for other components
stay as they are. Older `test-report.json` files without the new key still
render.

## Implementation

All paths are relative to the repository root. Follow the user's Python style
(see `~/.claude/CLAUDE.md`): declare constants at module top, no trailing
whitespace, flake8-clean.

1. **`test/selenium/lib/report.py` — `Assertion` label support**
   - In `Assertion.__init__`, add `self.subject: Optional[str] = None`.
   - Add a property `label` that returns
     `f"{self.component}.{self.assertion_id} ({self.subject})"` when
     `subject` is set, and `f"{self.component}.{self.assertion_id}"`
     otherwise.

2. **`test/selenium/lib/report.py` — derive the taxon from the row title**
   - Add module-level constants:
     - `COVERAGE_TITLE_PREFIX = "Database coverage of "`
     - `COVERAGE_ROLE_PREFIXES = ("Preliminary Morphology ID ",
       "Taxon of Interest ", "Candidate ")`
   - Add a function `coverage_subject(title) -> Optional[str]`:
     - Accept a list (use its first element), a string or `None`. Apply
       `normalize_whitespace`. Return `None` for an empty result.
     - Remove `COVERAGE_TITLE_PREFIX` if present, then the first matching
       entry of `COVERAGE_ROLE_PREFIXES` if present. Return the stripped
       remainder. If no prefix matches, return the normalised title
       unchanged, so a template wording change degrades to a longer label
       and never to a wrong or missing one.
   - Add `Report.annotate_subjects()`. For each group in
     `GROUPED_COMPONENTS["database_coverage"]["groups"]` and each row `ns`
     in `getattr(self.database_coverage, group, [])` (skip if the component
     is missing):
     - Choose the subject from the row's `title` assertion: its
       **expected** value (`raw_value` / `expected`) first, so the label
       matches the fixture the reviewer will edit; otherwise its
       `observed` value; otherwise `f"{group} row {index + 1}"`.
     - Set `a.subject` on every `Assertion` in `vars(ns).values()`,
       including `title` itself.
   - In the same method, for each row `ns` (at index `index`) in
     `getattr(self.publication_modal, "candidates", [])` (skip if the
     component is missing), set `a.subject` on every `Assertion` in
     `vars(ns).values()`. Use `normalize_whitespace(getattr(ns, "_name",
     None))` if it is non-empty, otherwise `f"candidates row {index + 1}"`.
     Do not parse the publication title: `_name` is the candidate table's
     species cell and is present in every fixture row.
   - Do not hard-code the two component ids in more than one place. Declare
     them once, e.g. as a module-level constant
     `SUBJECT_LABELLED_COMPONENTS = ("database_coverage",
     "publication_modal")`, or call two small helpers from
     `annotate_subjects()`. Keep the per-component subject logic in
     separate, readable branches.
   - Call `self.annotate_subjects()` at the start of `Report.drifted()`. It
     is idempotent and cheap, and this covers pytest
     (`assert_all`/conftest) and `promote`, both of which go through
     `drifted()`.
   - In `Report.assert_all()`, print `a.label` in place of
     `{a.component}.{a.assertion_id}`.

3. **`test/selenium/conftest.py`**
   - In `_drift_records()`, add `"subject": a.subject` to each record. Keep
     the existing keys and their values unchanged.

4. **`test/selenium/lib/templates/review.html.j2`**
   - Change the Field cell to:
     `{{ d.component | e }}.{{ d.assertion_id | e }}{% if d.subject %}
     ({{ d.subject | e }}){% endif %}` inside the existing
     `<code style="white-space: nowrap;">`. The Jinja `if` makes older JSON
     files without `subject` render as they do now.

5. **`test/selenium/lib/promote.py`**
   - In `promote_yaml`'s drift loop, print `[{a.label}]` in place of
     `[{a.component}.{a.assertion_id}]`. Leave the flex-change listing as it
     is unless it prints the same pattern; if it does, use `a.label` there
     too (call `report.annotate_subjects()` first if that path does not go
     through `drifted()`).

Do not change `GROUPED_COMPONENTS`, the YAML writer (`to_yaml`), `parse_yaml`,
`Assertion.is_drifted`, collectors' extraction logic, or any file under
`test/selenium/expected/`.

## Documentation and configuration

- `test/selenium/README.md`, section "Reviewing failures": change the
  `component.field | type | expected | observed` sentence to say that
  `database_coverage` and `publication_modal` rows show the target taxon,
  e.g. `database_coverage.min_bar_count (Homo sapiens)`.
- `spec/tests.md` TST-031: add one clause saying that review rows for
  `database_coverage` and `publication_modal` name the target taxon: the
  first is taken from the coverage modal title, the second from the
  candidate row name.
- `test/selenium/.testkit-fixtures/test-report.sample.json`: leave as is. It
  stays the backward-compatibility input (no `subject` key).
- Add one line to `tasks/changelog.md` on completion.

## Testing decision

Recorded 2026-11-17, scope: this task (06) only. The user chose the **mixed**
approach. On the same date the scope grew to include `publication_modal`
labels. That uses the same suites and the same kind of label-only change,
so the testing decision covers it as well.

- **Affected suites:** Selenium report tests (`test/selenium/test_reports.py`
  via `conftest.py`), `testkit.py render` and `testkit.py promote`. No
  nf-test, flag baseline or Python integration suite is affected.
- **New assertions implemented by the agent:** none committed. The agent
  runs the one-off checks under Validation and does not add a test module.
- **Checks run by the agent:** flake8, `testkit.py render` on the sample
  JSON, and the ad-hoc label script below.
- **Checks run by the user:** full Selenium pytest against real reports
  (needs Chrome plus `expected/reports/` or CI output), then review of the
  rendered `review.html`.
- **Drift review:** the user.
- **Changing expected results:** nobody, as part of this task. No YAML
  fixture, reference report or sample JSON changes. If a run shows real
  drift, the user handles it separately with `testkit.py promote`.

## Validation

Run from `test/selenium/` with `source venv/bin/activate` (create it from
`requirements.txt` if missing).

1. Lint: `/home/cameron/.local/envs/claude/bin/flake8 lib/report.py
   lib/promote.py conftest.py`. It must report nothing new.
2. Backward-compatible render:
   `python testkit.py render .testkit-fixtures/test-report.sample.json
   --out <scratchpad>/review_legacy.html`. It must succeed, and Field cells
   must be identical to a render of the same file on `main`. Compare with
   `diff`. Rendering adds a timestamp, so ignore any `generated_at` lines.
3. Label derivation (one-off script, not committed). Load
   `expected/13_Scenario_01.yaml` with `lib.report.parse_yaml`. On
   `report.database_coverage.pmi[0]`, `.toi[0]` (if present) and
   `.candidate[0]`, set `min_bar_count.observed` to a value below the
   expected `min`. Leave every other observed value as is or equal it to
   expected. Call `report.drifted()` and check that:
   - the PMI label is `database_coverage.min_bar_count (Spodoptera
     frugiperda)`, matching the PMI title in that fixture;
   - each label's taxon matches what you get by hand from that row's
     fixture `title` (read the YAML, do not call `coverage_subject`);
   - after forcing a row's `title` to empty expected and observed, the
     label falls back to `<group> row <n>`.
   Also call `coverage_subject` directly on `"Database coverage of
   Candidate Phyllocnistinae sp. BOLD:ABZ3983"` (→ `Phyllocnistinae sp.
   BOLD:ABZ3983`) and on an unprefixed string (→ returned unchanged).
   In the same loaded report, set `report.publication_modal.candidates[0]
   .count.observed` to a value different from its expected value. Check
   that the label is `publication_modal.count (Spodoptera frugiperda)`,
   matching the fixture's `name:` for that row. Then delete that row's
   `_name` and check the fallback label `candidates row 1`.
4. Render with subjects: put the drift records from step 3 through
   `conftest._drift_records`, wrap them in a minimal results JSON shaped like
   the sample, and render it. Check that the Field cells read
   `database_coverage.min_bar_count (Spodoptera frugiperda)` and
   `publication_modal.count (Spodoptera frugiperda)`, and that a
   non-grouped component row has no parentheses.

Record every check actually run and its outcome in the PR description,
including any that failed or were skipped. Expected values in these checks
come from the YAML fixture text, not from the new code. If a check fails,
work out whether the cause is the implementation, the check, or the data
before changing anything.

## Test impact and manual review

- **Expected-result files:** none should change. `test/selenium/expected/*.yaml`,
  `test/selenium/expected/reports/*.html` and
  `test/selenium/.testkit-fixtures/test-report.sample.json` must not appear
  in the diff.
- **Behaviour that changes:** the text of drift labels in
  `test/selenium/test-report.json` (new `subject` key), `review.html`, pytest
  `AssertionError` messages and promote prompts. Pass/fail outcomes and drift
  counts must stay the same. Any change to them is a regression.
- **CI:** `.github/workflows/nf-test.yml` and `mock-nf-test.yml` run
  `pytest test_reports.py` and `testkit.py render`, and upload `review.html`.
  Neither needs a workflow change.
- **Manual handoff (user):**
  1. Run the Selenium suite against the checked-in reports, as in
     `test/selenium/README.md`: `cd test/selenium && source venv/bin/activate
     && pytest test_reports.py`, then `python testkit.py render --open`.
     Or trigger `mock-nf-test.yml` and download its `review.html`.
  2. Check that pass/fail counts match a run on `main` with the same inputs.
  3. In each failing card, check that every `database_coverage.*` row
     shows a taxon matching that coverage modal in the observed HTML report,
     that every `publication_modal.*` row shows the candidate species from
     that row, and that other components look as they did.
  4. Any drifted values are reference-data drift or regressions to be
     handled separately. They are not part of this task.
- **Manual validation status:** accepted by the user on 2026-11-17.

## Completion criteria

- Steps 1–5 of Implementation are done. Validation checks 1–4 pass and are
  reported with their outcomes.
- README and `spec/tests.md` TST-031 are updated, and a changelog line is
  added.
- No fixture, reference report or sample JSON is modified.
- The user has confirmed the manual handoff above (review.html labels
  correct, outcomes unchanged). Until then the task stays active, with
  implementation complete and manual validation pending.

## Resolved decisions

Both resolved by the user on 2026-11-17:

- **Duplicate labels:** the label is `(<taxon>)` with no role. Identical
  labels for the same taxon in different groups (e.g. `Spodoptera
  frugiperda` as both PMI and candidate in `13_Scenario_01.yaml`) are
  acceptable.
- **`publication_modal`:** in scope. Rows are labelled from the row `_name`
  (Implementation step 2).

## Outcomes

**Implementation status:** complete on branch
`task-06-review-drift-species-label` (worktree
`.worktrees/task-06-review-drift-species-label`), 2026-11-17.

**Manual validation status:** accepted by the user on 2026-11-17
("looks good") after reviewing the implementation. The user ran the manual
check; the agent has no run output of its own to record here.

### Completed work

- `test/selenium/lib/report.py`: added `subject` to `Assertion`, a
  `display_id` property (`component.assertion_id (taxon)`),
  `coverage_subject()`, and `Report.annotate_subjects()`. That method
  labels `database_coverage` rows from the title (expected first, then
  observed, then `<group> row N`) and `publication_modal` rows from `_name`
  (then `candidates row N`). `drifted()` calls `annotate_subjects()` first,
  and `assert_all()` prints `display_id`. Component ids, the group name and
  title prefixes are module constants.
- `test/selenium/conftest.py`: drift records include `subject`.
- `test/selenium/lib/templates/review.html.j2`: the Field cell appends
  ` (subject)` when present.
- `test/selenium/lib/promote.py`: drift prompts print `display_id`. The
  flex-change summary only prints a count, so it is unchanged.
- `test/selenium/README.md` and `spec/tests.md` TST-031 now describe the
  labels.

### Deviation

- The brief named the new property `label`, but `Assertion` already sets an
  instance attribute `self.label` (the id with spaces). A property of that
  name would clash with it. The new property is named `display_id`. The
  existing `label` attribute is unused in the repository and was left as is.

### Validation run (agent)

1. flake8 on `lib/report.py`, `lib/promote.py` and `conftest.py`: clean.
2. Rendering `.testkit-fixtures/test-report.sample.json` (no `subject`
   keys) on this branch and on `main` gives byte-identical output.
3. and 4. A one-off script (not committed) loaded
   `expected/13_Scenario_01.yaml`, injected drift and checked labels
   against taxa copied by hand from the YAML. 19 of 19 checks passed:
   PMI, TOI and candidate[0] gave `Spodoptera frugiperda`, candidate[1]
   gave `Spodoptera exigua`, and the two publication rows were labelled
   from `name:`. A non-grouped drift (`input_sequence_modal.sample_id`) is
   unlabelled in the render. Both fallbacks (`candidate row 2`,
   `candidates row 1`) work, as do the BOLD-style taxon, an unprefixed
   title and an empty title. In the first run, the check that a
   non-grouped row stays unlabelled failed. That was a fault in the script,
   not the code: unset observed values don't count as drift, so there was
   no non-grouped drift to check. The script was fixed to inject one
   explicitly.
- No files under `test/selenium/expected/` or `.testkit-fixtures/` were
  changed.
- Not run by the agent: the full Selenium pytest (left to the user per the
  testing decision).

### Completion

- Status set to done after user acceptance. The brief moved to
  `tasks/completed/`, the active entry was removed, and a changelog line
  was added.
