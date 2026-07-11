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

## Running the tests

First you have to generate a new set of reports from the selenium test case samples. You can use the input files in ./reports/.

Then copy the generated reports to a single directory and run:

```bash
pytest test_reports.py -v --reports-dir /my/workflow/reports/
```

Each `.yaml` file in [expected/](expected/) is picked up automatically and run as a separate parametrised test case. Pytest opens a Chrome browser window per report, walks each tab, and asserts every value declared in the fixture. Reports in `--reports-dir` are resolved to fixtures by sample_id, so timestamps and prefixes in the report filenames don't need to line up with the fixtures.

Without `--reports-dir`, the runner falls back to the checked-in [reports/](reports/) directory — that's a self-test of the framework against known-good reports, not a validation of new workflow output.

### CLI options

Custom pytest options live under the **Selenium report-validation tests** group in `pytest --help`:

```bash
pytest --help
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--reports-dir <path>` | `reports/` | Directory to search for the HTML files to test. File names are resolved by sample_id. |

## Report ↔ fixture matching

Fixture filenames follow `{N}_report_{SAMPLE_ID}_{TIMESTAMP}.yaml`; freshly generated reports are typically `report_{SAMPLE_ID}_{TIMESTAMP}.html` (no numeric prefix, different timestamp). Both the test runner and `testkit promote` match reports to fixtures by **sample_id**, so timestamps and prefixes don't need to line up.

Resolution order for each fixture:

1. Exact filename match in the reports directory.
2. First `*.html` in the reports directory whose extracted sample_id equals the fixture's sample_id.

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
python testkit.py ingest reports/3_report_VE24-1351_COI_2026-07-09_10_46_05.html
```

Auto-picks the next unused numeric prefix. Refuses to overwrite an existing fixture unless `--force` is passed. Spot-check the output before committing.

### `testkit promote`

When legitimate drift is observed (e.g. new sequence records were deposited in the reference database), re-open the HTML and prompt through each drifted assertion:

```bash
python testkit.py promote 1_report_SME25-218_2025-12-11_07_30_03.yaml
python testkit.py promote --all
python testkit.py promote --all --reports /path/to/nf-test-output/
```

For each drifted field the CLI prints old vs. new and prompts `[y]es / [n]o / [a]ll / [q]uit`. Accepted drifts are written back to the same YAML preserving the schema layout. `--yes` skips prompts (accepts all). `--reports <dir>` mirrors the pytest option and resolves reports by sample_id.

## Fixture YAML structure

```yaml
filename: my_report.html   # must match a file in reports/ (or a sample_id there)

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
