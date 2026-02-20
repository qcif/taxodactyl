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
        
        val = str(self.raw_value).strip()
        
        if self.assertion_type == "list":
            return [item.strip() for item in val.split("|") if item.strip()]

        if val == "":
            return None
        
        if self.assertion_type == "int":
            return int(val)
        
        if self.assertion_type == "float":
            return float(val)
        
        if self.assertion_type == "bool":
            return val.lower() == "true"
        
        return val
    
    def assert_equals(self, actual, context: str = ""):
        if self.expected is None:
            return

        assert actual == self.expected, (
            f"{context} Expected '{self.expected}' but got '{actual}'"
        )

    def assert_contains(self, actual: str, context: str = ""):
        if self.expected is None:
            return

        actual = actual.strip().lower()
        expected = str(self.expected).strip().lower()

        assert expected in actual, (
            f"{context} Expected '{expected}' to be in '{actual}'"
        )
    
    def assert_list_contains(self, actual_list, context: str = ""):
        if not self.expected:
            return

        for expected_item in self.expected:
            expected_item = str(expected_item).strip().lower()

            assert any(expected_item in str(item).lower() for item in actual_list), (
                f"{context} Expected '{expected_item}' not found"
            )
    
    def assert_bool(self, actual: bool, context: str = ""):
        if self.expected is None:
            return

        assert bool(actual) == bool(self.expected), (
            f"{context} Expected {self.expected} but got {actual}"
        )

    def assert_float(self, actual: float, context: str = "", tolerance: float = 0.01):
        if self.expected is None:
            return

        assert abs(float(actual) - float(self.expected)) <= tolerance, (
            f"{context} Expected {self.expected} but got {actual}"
        )

    def assert_value(self, actual, msg=None):
        """
        Generic dispatcher based on assertion_type
        """
        if self.assertion_type == "equals":
            self.assert_equals(actual, msg)
        elif self.assertion_type == "float":
            self.assert_float(float(actual), msg)
        elif self.assertion_type == "contains":
            self.assert_contains(actual, msg)
        elif self.assertion_type == "min":
            self.assert_min(actual, msg)
        else:
            raise ValueError(f"Unknown assertion type: {self.assertion_type}")

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
