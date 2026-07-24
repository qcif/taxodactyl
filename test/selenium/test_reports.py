from pathlib import Path

import pytest

from lib.collect import collect_all
from lib.report import find_report_html, parse_yaml


REFERENCE_REPORTS_DIR = Path("expected/reports")


def _load_reports():
    out = []
    for yaml_path in sorted(Path("expected").glob("*.yaml")):
        report = parse_yaml(yaml_path)
        report.fixture_path = yaml_path.resolve()
        out.append(report)
    return out


reports = _load_reports()


@pytest.mark.parametrize("report", reports, ids=lambda r: r.sample_id)
def test_reports(driver, reports_dir, report):
    observed = find_report_html(report.sample_id, reports_dir)
    assert observed is not None, (
        f"No HTML report for sample_id '{report.sample_id}' found in "
        f"{reports_dir}"
    )
    observed = observed.resolve()

    reference = find_report_html(report.sample_id, REFERENCE_REPORTS_DIR)
    report.observed_html_path = observed
    report.reference_html_path = (
        reference.resolve() if reference is not None else None
    )

    driver.get(observed.as_uri())

    collect_all(driver, report)
    report.assert_all()
