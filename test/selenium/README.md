# Selenium Tests

End-to-end tests that load generated HTML reports in a browser and assert that the UI renders the expected content.

## Setup

From this directory, create and activate a virtual environment, then install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running the tests

The tests must be run from the `test/selenium/` directory so that the YAML fixtures and the `reports/` folder are resolved correctly:

```bash
cd test/selenium
pytest test_reports.py -v
```

Each `.yaml` file in this directory is picked up automatically and run as a separate test case. Pytest will open a Chrome browser window for each report, navigate through each tab, and assert the values defined in the YAML.

## How reports are tested

`test_reports.py` parametrises over every `*.yaml` file it finds in `expected/`. For each one it:

1. Opens the corresponding HTML file from `reports/`.
2. Calls into each tab-specific module (`overview_tab_test.py`, `candidate_tab_test.py`, `database_coverage_test.py`, `toi_tab_test.py`) and the sample modal (`sample_metadata_test.py`).
3. Asserts the values extracted from the browser against the expectations in the YAML.

## Adding a new report

1. Place the generated `.html` report in `test/selenium/reports/`.
2. Copy an existing YAML file from `expected/` (e.g. `1_report_SME25-218_2025-12-11_07_30_03.yaml`) as a starting point and place the new file in `expected/`. Name it with the next sequential prefix so it sorts predictably (e.g. `3_report_<ticket>_<timestamp>.yaml`).
3. Set `filename` at the top of the YAML to the exact HTML filename (including extension).
4. Update each component's assertion values to match what the new report is expected to display. Run the tests once without assertions (or with known-good values) to confirm the report loads correctly, then fill in the expected values.
5. Run `pytest test_reports.py -v` and verify the new test passes.

## YAML structure

```yaml
filename: my_report.html   # must match the file in reports/

components:
  - id: input_sequence_modal    # component id used by the test modules
    assertions:
      - id: sample_id           # assertion id, maps to a field extracted from the UI
        type: ''                # assertion type: '', equals, contains, list, int, float, bool, min
        value: SME25-218        # expected value

  - id: database_coverage       # special component with grouped sub-assertions
    pmi:
      - name: Species Name
        assertions: [...]
    toi:
      - name: Species Name
        assertions: [...]
    candidate:
      - name: Species Name
        assertions: [...]
```

### Assertion types

| Type | Behaviour |
|------|-----------|
| `''` or `contains` | Case-insensitive substring match |
| `equals` | Exact string equality |
| `list` | Each expected item must appear somewhere in the observed list |
| `int` | Exact integer equality |
| `float` | Exact float equality |
| `bool` | Boolean equality (`TRUE`/`FALSE`) |
| `min` | Observed value must be >= expected value |

Leave `value` empty (or omit it) to skip an assertion without removing it from the file.
