
from pathlib import Path
from utils import parse_csv
from sample_metadata_test import run_sample_modal
from overview_tab_test import run_overview_tab
from candidate_tab_test import run_candidate_tab
import pytest

reports = parse_csv(Path("assertions.csv"))


@pytest.mark.parametrize("report", reports, ids=lambda r: r.filename)
def test_reports(driver, report):
    report_path = Path("reports") / report.filename
    assert report_path.exists()

    driver.get(report_path.resolve().as_uri())

    run_sample_modal(driver, report)
    run_overview_tab(driver, report)
    run_candidate_tab(driver, report)
