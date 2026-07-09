from pathlib import Path

import pytest

from lib.collect import collect_all
from lib.report import extract_sample_id, find_report_html, parse_yaml


reports = [parse_yaml(f) for f in sorted(Path("expected").glob("*.yaml"))]


@pytest.mark.parametrize("report", reports, ids=lambda r: r.filename)
def test_reports(driver, reports_dir, report):
    exact = reports_dir / report.filename
    if exact.exists():
        report_path = exact
    else:
        sample_id = extract_sample_id(report.filename)
        assert sample_id, (
            f"Cannot extract sample_id from fixture filename "
            f"'{report.filename}'"
        )
        matched = find_report_html(sample_id, reports_dir)
        assert matched is not None, (
            f"No HTML report for sample_id '{sample_id}' found in "
            f"{reports_dir}"
        )
        report_path = matched

    driver.get(report_path.resolve().as_uri())

    collect_all(driver, report)
    report.assert_all()
