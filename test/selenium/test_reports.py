from pathlib import Path

import pytest

from lib.report import parse_yaml
from lib.collect import collect_all


reports = [parse_yaml(f) for f in sorted(Path("expected").glob("*.yaml"))]


@pytest.mark.parametrize("report", reports, ids=lambda r: r.filename)
def test_reports(driver, report):
    report_path = Path("./reports") / report.filename
    assert report_path.exists()

    driver.get(report_path.resolve().as_uri())

    collect_all(driver, report)
    report.assert_all()
