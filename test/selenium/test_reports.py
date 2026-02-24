
from pathlib import Path

from setup import driver, parse_csv
from selenium.webdriver.remote.webdriver import WebDriver
from sample_metadata_test import run_sample_modal
from overview_tab_test import run_overview_tab
import pytest


def test_reports(driver):
    reports = parse_csv(Path("assertions.csv"))
    for report in reports:
        report_path = Path("reports") / report.filename
        assert report_path.exists()

        driver.get(report_path.resolve().as_uri())
        
        run_sample_modal(driver, report)
        run_overview_tab(driver, report)

       