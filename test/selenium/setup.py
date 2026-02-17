from types import SimpleNamespace
from pathlib import Path
from typing import List, Any
import pandas as pd
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Selenium fixture

@pytest.fixture
def driver():
    options = Options()
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    yield driver
    driver.quit()

# Domain model

class Assertion:
    def __init__(self, row, report_column: str):
        self.component = row['Component']
        self.assertion_id = row['Assertion ID']
        self.assertion_type = row['Type']
        self.raw_value = row[report_column]
        self.expected = self._parse_value()

    def _parse_value(self) -> Any:
        if pd.isna(self.raw_value):
            return None
        if self.assertion_type == "list":
            return str(self.raw_value).split("|")
        if self.assertion_type == "int":
            return int(self.raw_value)
        if self.assertion_type == "bool":
            return str(self.raw_value).strip().lower() == "true"
        return str(self.raw_value)

class Report:
    def __init__(self, filename: str, df: pd.DataFrame, report_column: str):
        self.filename = filename
        self._parse_assertions(df, report_column)

    def _parse_assertions(self, df: pd.DataFrame, report_column: str):
        for _, row in df.iterrows():
            assertion = Assertion(row, report_column)
            if not hasattr(self, assertion.component):
                setattr(self, assertion.component, SimpleNamespace())
            component_ns = getattr(self, assertion.component)
            setattr(component_ns, assertion.assertion_id, assertion)

# CSV parser

def parse_csv(filename: str) -> List[Report]:
    df = pd.read_csv(filename)
    reports: List[Report] = []

    # Find all report columns
    report_columns = [col for col in df.columns if col.endswith(".html")]

    for report_col in report_columns:
        report = Report(report_col, df, report_col)  # pass only this column
        reports.append(report)

    return reports
