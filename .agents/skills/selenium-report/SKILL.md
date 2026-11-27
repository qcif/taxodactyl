---
name: "selenium-report"
description: "Review a Selenium report-test run (test/selenium/test-report.json) against a directory of workflow HTML reports. For each failed or errored fixture, decide whether the diff is legitimate drift (live data, taxonomy backbone changes, known issues), a test-rig/fixture problem, or a genuine workflow bug, with evidence."
metadata:
  author: "neoformit"
---

## Inputs

Ask the user for anything missing:

- **Reports dir** (required): the directory of HTML reports the tests ran
  against, e.g. `~/Downloads/wf2-nftest-reports-YYYYMMDD`. `test-report.json`
  records it as `reports_dir`; confirm it if the user did not give one.
- **Scope**: all failures, or specific fixtures (by numeric prefix of
  `test/selenium/expected/N_*.yaml`). Ask which fixtures the user has
  already reviewed, and skip those.
- **The nf-test run** (optional): the `/var/runner/<run_id>-<attempt>/` run that
  produced the reports. Needed only when the HTML alone can't explain a diff
  (see [Runner](#runner-work-dirs)).

Read `test/selenium/README.md` first for the fixture schema, assertion
types and `flex`.

## Ground rules

- **Read-only on fixtures and code.** Do not run `testkit promote`, edit
  fixtures or fix collector code unless the user asks. Report verdicts and
  suggested fixes.
- **`test-report.json` is overwritten by every pytest run**, always at
  `test/selenium/test-report.json`. Copy the user's file to the scratchpad
  before you run anything, save each run you make there under a clear name,
  and restore the user's original when you finish.
- Run pytest from `test/selenium/` with its venv
  (`source venv/bin/activate`). A full run takes about 5 minutes; use `-k`
  to narrow it. The test IDs are `sample_id`s, not fixture numbers (list
  them with `pytest --collect-only -q --dir <dir>`).
- The scripts in `scripts/` use only the standard library. Run them with
  `python3 -I <skill-dir>/scripts/<script>.py`.

## Process

### 1. Get complete drift data

`test-report.json` may only hold the last (partial) run. If it doesn't
cover every failing fixture in scope, re-run them:

```bash
cd test/selenium && source venv/bin/activate
cp test-report.json $SCRATCH/test-report.orig.json
pytest test_reports.py -q --dir <reports-dir> [-k "<sample_id> or ..."]
cp test-report.json $SCRATCH/test-report.observed.json
```

### 2. Run the control (self-test)

Run the same fixtures against their own checked-in reference reports:

```bash
pytest test_reports.py -q --dir expected/reports [-k ...]
cp test-report.json $SCRATCH/test-report.control.json
```

If an assertion fails in the control, the workflow did not cause it. It
comes from the collector code (`test/selenium/lib/`) changing since the
fixture was promoted, or from a stale fixture. This one step separates rig
problems from workflow changes better than anything else.

### 3. Summarise and triage

```bash
python3 -I scripts/summarise_drift.py $SCRATCH/test-report.observed.json \
    --control $SCRATCH/test-report.control.json [--only 3 4 5]
```

Each drift line gets a tag:

| Tag | Meaning | Action |
|---|---|---|
| `[CONTROL]` | Same failure on the reference report | Rig/fixture. Find the cause in `git log -- test/selenium/lib` |
| `[MIXED]` | Fails on the reference too, but the new value differs | Stale fixture **and** a real change. Compare the HTML directly |
| `[NEW]` | Fails only on the new report | Workflow-side change. Investigate |

`subject` is the target taxon of the row (PMI/TOI/candidate). An `error`
outcome is a collector exception. Check whether the control errors too.

### 4. Investigate each `[NEW]` / `[MIXED]` diff in the HTML

Each result has `observed_html` and `reference_html`. Diff the relevant
sections as text:

```bash
python3 -I scripts/modal_dump.py <report.html> dbCov         # all coverage sections
python3 -I scripts/modal_dump.py <report.html> pmi-          # whole PMI/TOI modals
python3 -I scripts/modal_dump.py <report.html> candidate-    # candidate modals
```

Look for:

- **Issues encountered / Exception** blocks, e.g.
  `No GBIF record found for '<name>'`. These are in the modal-level dump,
  not inside `dbCov*` sections. A missing `dbCovTarget-*` section means the
  target was dropped entirely.
- **Genus in the 5.2/5.3 headings** (e.g. Tospovirus → Orthotospovirus).
  This shows what taxonomy the related-species search resolved to.
- **NCBI taxids.** Compare the links in both reports:
  `grep -o 'wwwtax.cgi?mode=Info&id=[0-9]*' <html> | sort | uniq -c`. Look
  up what they are:
  `curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=taxonomy&id=<id>&retmode=json"`.
  A big jump in 5.1 record counts often means the name resolved to a
  different taxid. Decide which taxid is correct before you call it drift
  or a bug.
- **GBIF/COL.** Query the API directly to confirm what the backbone holds
  (see the checklist key and query shapes in `scripts/src/gbif/api.py`).

Tie each change to a code change: `git log --since=<reference date>`,
especially under `scripts/src/gbif`, `scripts/src/coverage` and
`scripts/src/taxonomy`. The reference date is in the reference report
filename and in the fixture's `date:`.

### Runner work dirs

When the HTML doesn't explain a diff (unclear exception, a need to see the
API requests made, or which parameters a task ran with), invoke the
`investigate-runner` skill for the nf-test run that produced the reports.
The report timestamp, e.g. `2026-11-17_01_27_54`, is a few minutes after
that run started. `ls -lt /var/runner/` lists runs by when they finished,
so pick the run that started just before the timestamp, and confirm with its
`run_info.txt` (run URL).
Grep the run for the sample ID or the error message to find the task's
`.command.log` (it includes GBIF/Entrez request URLs) and `errors/*.json`.

## Classifying a diff

**Drift** (expected, promote):
- GenBank/core_nt counts that moved, beyond `flex`
  (`record_count`, `species_count`, bar counts).
- Taxonomy backbone changes (the GBIF Backbone → Catalogue of Life switch
  in #313): renamed or merged genera, different related-species sets, and
  ICTV binomials (`Vitivirus etavitis`, `Potyvirus batataplumei`) that now
  resolve where they used to fail.
- Things a merged fix changed on purpose. Name the commit or PR.

**Known issue** (cite the issue, don't re-raise it). Check what's still
open with `gh issue list --search "<keyword>"` and `gh issue view <n>`, and
the out-of-scope items in `tasks/todo.md`.

**Fixed issues that cause expected drift** when a fixture predates the fix
(classify as an improvement, citing the fix):
- #353 (task 09): targets missing from COL (unclassified-virus placeholders,
  virus common names such as "Apple hammerhead viroid") are now assessed
  through their NCBI taxid instead of being dropped.
- #351 (task 08): ties between duplicate COL records with the same name
  (e.g. *Drosophila*) are broken deterministically, so the intermittent 5.2
  ERR is gone.
- #354 (task 07): kingdom- or domain-level targets report 5.1–5.3 as NA
  (not assessed) instead of ERR.
- Task 11: near-miss COL names and duplicate genera (e.g. *Vitivirus*) now
  resolve to the right genus, changing related-species sets.

**Rig/fixture problem**: `[CONTROL]` drifts and collector exceptions. Give
the file and line in `test/selenium/lib/` and a suggested fix.

**Genuine bug**: a `[NEW]` change that no data or backbone change explains,
or that is wrong on inspection (wrong taxid, wrong genus, contradictory text
within a modal, a regression in rendering or flags). Gather evidence (HTML
excerpts, API responses, runner logs) and offer to draft an issue.

Also note any oddities you notice that are already present in the reference
report. They aren't regressions, but they may be bugs worth recording.

## Output

Report per fixture, as a table or short sections:

- fixture number, sample, and verdict (drift / improvement / known issue
  #n / rig / **bug**)
- one or two lines of evidence: what changed and why, with the commit,
  issue or taxid that explains it

Then list rig problems separately with suggested fixes, and say which
fixtures are safe to `testkit promote` once those are fixed. Finally,
restore `test-report.json` and give the scratchpad paths of the observed
and control JSON files.
