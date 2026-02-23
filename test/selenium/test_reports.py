
from pathlib import Path

from setup import driver, parse_csv
from selenium.webdriver.remote.webdriver import WebDriver
from test_sample_metadata import check_sample_modal
from test_overview_tab import check_overview_tab

def test_reports(driver):
    reports = parse_csv(Path("assertions.csv"))

    for report in reports:
        report_path = Path("reports") / report.filename
        assert report_path.exists()

        driver.get(report_path.resolve().as_uri())

        check_sample_modal(driver, report)
        check_overview_tab(driver, report)

       