import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lib.driver import make_driver


JSON_REPORT_PATH = Path("test-report.json")


def pytest_addoption(parser):
    group = parser.getgroup(
        "selenium",
        "Selenium report-validation tests",
    )
    group.addoption(
        "--dir", "--reports-dir",
        action="store",
        dest="reports_dir",
        required=True,
        help=(
            "Directory containing HTML reports to test against. Reports "
            "are matched to expected/*.yaml fixtures by sample_id, so "
            "timestamps in the report filename may differ. Point this at "
            "expected/reports/ to self-test the framework against the "
            "checked-in reference reports."
        ),
    )


@pytest.fixture(scope="session")
def reports_dir(request):
    return Path(request.config.getoption("--reports-dir"))


@pytest.fixture
def driver():
    driver = make_driver()
    yield driver
    driver.quit()


# ---------------------------------------------------------------------------
# JSON test report emitter — writes ./test-report.json at session end.
# ---------------------------------------------------------------------------


def _serialise_value(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_serialise_value(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _drift_records(report) -> list:
    return [
        {
            "component": a.component,
            "assertion_id": a.assertion_id,
            "type": a.assertion_type,
            "expected": _serialise_value(a.expected),
            "observed": _serialise_value(a.observed),
        }
        for a in report.drifted()
    ]


def pytest_configure(config):
    config._selenium_json_results = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    result = outcome.get_result()

    if result.when != "call":
        return

    report = item.funcargs.get("report")
    if report is None:
        return

    fixture_path = getattr(report, "fixture_path", None)
    observed = getattr(report, "observed_html_path", None)
    reference = getattr(report, "reference_html_path", None)

    non_assert_error = (
        call.excinfo
        and not isinstance(call.excinfo.value, AssertionError)
    )
    outcome_str = "error" if non_assert_error else result.outcome

    entry = {
        "fixture": str(fixture_path) if fixture_path else None,
        "sample_id": report.sample_id,
        "outcome": outcome_str,
        "duration_s": round(result.duration, 3),
        "observed_html": str(observed) if observed else None,
        "reference_html": str(reference) if reference else None,
        "drifted": _drift_records(report) if result.failed else [],
        "error_message": (
            str(call.excinfo.value) if non_assert_error else None
        ),
    }
    item.config._selenium_json_results.append(entry)


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    results = getattr(config, "_selenium_json_results", None)
    if results is None:
        return

    reports_dir_opt = config.getoption("--reports-dir")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reports_dir": str(Path(reports_dir_opt).resolve()),
        "results": results,
    }
    JSON_REPORT_PATH.write_text(json.dumps(payload, indent=2))
