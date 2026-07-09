from pathlib import Path

import pytest

from lib.report import parse_yaml
from lib.sample_metadata import run_sample_modal
from lib.overview import run_overview_tab
from lib.candidate import run_candidate_tab
from lib.database_coverage import run_database_coverage
from lib.toi import run_toi_tab


reports = [parse_yaml(f) for f in sorted(Path("expected").glob("*.yaml"))]


@pytest.mark.parametrize("report", reports, ids=lambda r: r.filename)
def test_reports(driver, report):
    report_path = Path("./reports") / report.filename
    assert report_path.exists()

    driver.get(report_path.resolve().as_uri())

    run_sample_modal(driver, report)
    run_overview_tab(driver, report)
    run_candidate_tab(driver, report)
    run_database_coverage(driver, report)
    run_toi_tab(driver, report)
