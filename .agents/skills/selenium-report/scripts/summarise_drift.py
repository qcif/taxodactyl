"""Summarise drift in a Selenium test-report.json, optionally against a
control run of the same fixtures on their checked-in reference reports.

Usage:
    python3 -I summarise_drift.py OBSERVED.json [--control CONTROL.json]
        [--only N|SUBSTR ...]

OBSERVED.json is the report from running pytest on the new HTML reports.
CONTROL.json is the report from running pytest on expected/reports/
(the self-test). A drift that also appears in the control run cannot have
been caused by the workflow: it comes from the collector code or a stale
fixture. Tags:

    [CONTROL]  same failure (same observed value) in the control run:
               collector/fixture problem, not the workflow
    [MIXED]    the assertion also fails in the control run, but the
               observed value differs: stale fixture AND a real change -
               compare observed vs reference HTML directly
    [NEW]      fails only on the new report: a workflow-side change

--only takes fixture numbers (e.g. 3 7) or substrings of the fixture
filename. Duplicate drift entries are collapsed.
"""
import argparse
import json

CONTROL_TAG = '[CONTROL]'
MIXED_TAG = '[MIXED]'
NEW_TAG = '[NEW]'
ERROR_PREVIEW_CHARS = 160


def _drift_key(drift: dict) -> tuple:
    return (
        drift['component'],
        drift.get('subject'),
        drift['assertion_id'],
        json.dumps(drift['expected'], sort_keys=True),
    )


def _observed_value(drift: dict) -> str:
    return json.dumps(drift['observed'], sort_keys=True)


def _fixture_number(fixture: str) -> int:
    head = fixture.split('_')[0]
    return int(head) if head.isdigit() else 0


def _selected(fixture: str, only: list) -> bool:
    if not only:
        return True
    for item in only:
        if item.isdigit():
            if _fixture_number(fixture) == int(item):
                return True
        elif item in fixture:
            return True
    return False


def _load_results(path: str) -> dict:
    with open(path) as f:
        data = json.load(f)
    return {
        result['fixture'].split('/')[-1]: result
        for result in data['results']
    }


def _first_line(text: str) -> str:
    return (text or '').strip().splitlines()[0][:ERROR_PREVIEW_CHARS]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('observed')
    parser.add_argument('--control')
    parser.add_argument('--only', nargs='*', default=[])
    args = parser.parse_args()

    observed = _load_results(args.observed)
    control = _load_results(args.control) if args.control else {}

    for fixture, result in sorted(
        observed.items(), key=lambda kv: _fixture_number(kv[0]),
    ):
        if not _selected(fixture, args.only):
            continue
        print(f"===== {fixture}  [{result['outcome']}]")
        print(f"  observed:  {result.get('observed_html')}")
        print(f"  reference: {result.get('reference_html')}")
        if result.get('error_message'):
            print(f"  ERROR: {_first_line(result['error_message'])}")
        control_result = control.get(fixture)
        if control_result is not None:
            print(f"  control outcome: {control_result['outcome']}")
            if control_result.get('error_message'):
                print(
                    '  control ERROR: '
                    f"{_first_line(control_result['error_message'])}")
        control_observed = {
            _drift_key(d): _observed_value(d)
            for d in (control_result or {}).get('drifted', [])
        }
        seen = set()
        for drift in result.get('drifted', []):
            key = _drift_key(drift)
            if key in seen:
                continue
            seen.add(key)
            tag = ''
            if args.control:
                if key not in control_observed:
                    tag = NEW_TAG
                elif control_observed[key] == _observed_value(drift):
                    tag = CONTROL_TAG
                else:
                    tag = MIXED_TAG
            flex = f" flex={drift['flex']}" if drift.get('flex') else ''
            print(
                f"  {tag:9} {drift['component']}.{drift['assertion_id']}"
                f" ({drift.get('subject') or '-'}){flex}"
                f" | exp: {drift['expected']} | obs: {drift['observed']}")


if __name__ == '__main__':
    main()
