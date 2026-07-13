# Selenium Tests

End-to-end tests that load generated HTML workflow reports in a browser and assert that the UI renders the expected content. Fixtures live in [expected/](expected/) as one YAML per report; the collector code that extracts values from each rendered report lives in [lib/](lib/).

## Setup

From this directory (`test/selenium/`), create and activate a virtual environment, then install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

All the commands below assume this venv is active and the working directory is `test/selenium/`.


## Quick start

Brief summary of round-trip:

1. Run full Taxodactyl (Nextflow) on ./inputs/ input data with default params (and ideally with frozen test DBs)
1. Copy all outputs reports to /path/to/my/html_reports/
1. ```bash
   pytest test_reports.py -v --dir /path/to/my/html_reports/
   ```
1. `./testkit.py render`
1. Open the `review.html` produced - this is a nice overview of diffs for failed tests
1. Compare/view HTML docs to identify diffs that indicate bug(s)
1. Fix the bugs and repeat, until tests pass, or all diffs look like drift (e.g. sequence records published since last run)
1. If there is drift (no bugs), promote the fixtures:
   `./testkit.py promote <N> -d /path/to/my/html_reports/`

## Running the tests

First, generate a fresh set of workflow reports (input data lives in [inputs/](inputs/)). Then point the pytest runner at the directory containing the generated HTMLs:

```bash
pytest test_reports.py -v --dir /path/to/my/html_reports/
```

`--dir` (long form: `--reports-dir`) is **required** — the framework won't run without an explicit reports directory. This forces you to state whether you're validating fresh workflow output or self-testing the framework itself.

To self-test the framework against the checked-in reference reports:

```bash
pytest test_reports.py -v --dir expected/reports/
```

Each `.yaml` file in [expected/](expected/) is picked up automatically and run as a separate parametrised test case. Reports are matched to fixtures by `sample_id`, so timestamps and prefixes in the report filenames don't need to line up with the fixtures.

Every pytest run writes a structured `./test-report.json` alongside the usual pytest output. Feed it to `testkit render` to get a review page (see [Reviewing failures](#reviewing-failures)).

### CLI options

Custom pytest options live under the **Selenium report-validation tests** group in `pytest --help`:

```bash
pytest --help
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--dir <path>` / `--reports-dir <path>` | *required* | Directory to search for the HTML files to test. Reports are matched by `sample_id`. |

## Report ↔ fixture matching

Each fixture YAML declares a `sample_id:` at the top. Report filenames typically look like `report_{SAMPLE_ID}_{TIMESTAMP}.html` (or `{N}_report_{SAMPLE_ID}_{TIMESTAMP}.html` for the checked-in reference set). The runner extracts the `sample_id` from every `*.html` in `--dir` and links it to the fixture with the same id — timestamps and numeric prefixes are ignored.

The checked-in reference reports live in [expected/reports/](expected/reports/). When the review page shows "Open reference report", it links to the HTML in that directory whose `sample_id` matches the fixture.

## Reviewing failures

When drift is detected, the fastest review path is:

1. Run pytest as usual — this always writes `./test-report.json` containing every drifted assertion (all of them, not just the first per test) plus absolute paths to the observed and reference HTML reports.
2. Render the review page:
   ```bash
   python testkit.py render --open
   ```
   Defaults to reading `./test-report.json` and writing `./review.html`. `--open` launches the page in your default browser.

The page has a summary banner (total / passed / failed / errored), a results table, and an expanded card for each failing test showing the `component.field | type | expected | observed` matrix plus one-click "Open observed" / "Open reference" links to the two HTML reports.

For iterating on the review page itself, a sample JSON with drift is checked in at `.testkit-fixtures/test-report.sample.json`. Render straight from it to skip a pytest run:

```bash
python testkit.py render .testkit-fixtures/test-report.sample.json --out /tmp/review.html --open
```

Once you've inspected the reports and confirmed the drift is legitimate (e.g. new sequence records were deposited in the reference database), use `testkit promote` (below) to write the observed values back into the fixture.

## Ingesting and promoting fixtures — `testkit.py`

Two subcommands automate the two lifecycle operations that would otherwise be hand-editing:

```bash
python testkit.py --help
python testkit.py ingest  --help
python testkit.py promote --help
```

### `testkit ingest`

Extract values from a manually-verified HTML report and write a new `expected/*.yaml`:

```bash
python testkit.py ingest /path/to/report_VE24-1351_COI_2026-07-09_10_46_05.html
```

Copies the HTML into `expected/reports/`, extracts its `sample_id`, and writes the fixture with the next unused numeric prefix. Refuses to overwrite an existing fixture unless `--force` is passed. Spot-check the output before committing.

### `testkit promote`

When legitimate drift is observed (e.g. new sequence records were deposited in the reference database), re-open the HTML and prompt through each drifted assertion:

```bash
python testkit.py promote 1                        # numeric prefix — resolves to expected/1_*.yaml
python testkit.py promote 1_SME25-218.yaml         # full filename or bare stem
python testkit.py promote --all
python testkit.py promote --all -d /path/to/nf-test-output/
```

For each drifted field the CLI prints old vs. new and prompts `[y]es / [n]o / [a]ll / [q]uit`. Accepted drifts are written back to the same YAML preserving the schema layout. `--yes` skips prompts (accepts all). `-d` / `--reports` picks the directory to look up HTML reports by `sample_id` (default: `expected/reports/`).

Every successful promote:
- Bumps the fixture's `date:` to match the HTML report it was promoted against.
- Snapshots the previous YAML into `expected/.backups/{stem}.{timestamp}.yaml` and rotates so at most the **3 most recent backups** per fixture are kept. Backups are gitignored.

## Fixture YAML structure

```yaml
sample_id: SME25-218   # links this fixture to the HTML report with the same sample_id
date: '2025-12-11T07:30:03'   # timestamp of the HTML the fixture was last promoted against

components:
  - id: input_sequence_modal
    assertions:
      - id: sample_id
        type: contains
        value: SME25-218

  - id: database_coverage        # grouped component
    pmi:
      - name: Species Name
        assertions: [...]
    toi:
      - name: Species Name
        assertions: [...]
    candidate:
      - name: Species Name
        assertions: [...]

  - id: publication_modal        # grouped by candidate species
    candidates:
      - name: Species Name
        assertions: [...]
```

The set of components, the fields inside each, and each field's type are all declared centrally in [lib/schema.py](lib/schema.py). `testkit ingest` and `testkit promote` regenerate the YAML from that schema, so unused metadata fields (e.g. the old `rows:` counter on `candidate_tab_table`) get dropped on any round-trip.

### Assertion types

| Type | Behaviour |
|------|-----------|
| `contains` (or `''`) | Case-insensitive substring match with whitespace collapsed |
| `equals` | Exact equality (whitespace collapsed on both sides for strings) |
| `list` | Each expected item must appear as a substring in some observed item |
| `int` | Exact integer equality |
| `float` | Exact float equality |
| `bool` | Boolean equality (`TRUE` / `FALSE`) |
| `min` | Observed value must be `>=` expected value |

Whitespace (including newlines and leading indentation from HTML) is collapsed to single spaces before every string comparison and on YAML write, so cosmetic wrapping doesn't cause spurious drift.

Leave `value` empty (or omit it) to keep an assertion in the file without checking it.
