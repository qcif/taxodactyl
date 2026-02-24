from types import SimpleNamespace
from pathlib import Path
from typing import List, Any
import pandas as pd
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

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

# Helper function for open tabs
def open_tab(
    driver: WebDriver,
    tab_id: str,
    pane_id: str,
    expected_header: str = None,
    timeout: int = 10
) -> WebElement:
    """
    Clicks a tab, waits for its pane to appear, and optionally checks a header.
    Returns the pane WebElement.
    """
    wait = WebDriverWait(driver, timeout)

    # Click tab
    tab_element = wait.until(EC.element_to_be_clickable((By.ID, tab_id)))
    tab_element.click()

    # Wait for pane
    pane = wait.until(EC.presence_of_element_located((By.ID, pane_id)))
    wait.until(lambda d: "show" in pane.get_attribute("class"))

    # Optional header assertion
    if expected_header:
        assert expected_header.lower() in pane.text.lower(), f"Expected header '{expected_header}'"

    return pane

class Assertion:
    def __init__(self, row, report_column: str, filename: str):
        self.filename = filename
        self.component = row['Component']
        self.assertion_id = row['Assertion ID']
        self.assertion_type = (
                    str(row['Type']).strip().lower()
                    if pd.notna(row['Type'])
                    else "contains"
                )        
        self.label = self.assertion_id.replace("Conclusion: ", "").strip()
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
            assert any(expected_item in item for item in actual_list), (
                f"{context} Expected '{expected_item}' not found"
            )
    
    def assert_bool(self, actual: bool, context: str = ""):
        if self.expected is None:
            return

        assert bool(actual) == bool(self.expected), (
            f"{context} Expected {self.expected} but got {actual}"
        )

    def assert_(self, actual, **kwargs):
        if self.assertion_type == "equals":
            self.assert_equals(actual, **kwargs)
        elif self.assertion_type == "contains":
            self.assert_contains(actual, **kwargs)
        elif self.assertion_type == "list":
            self.assert_list_contains(actual, **kwargs)
        elif self.assertion_type == "bool":
            self.assert_bool(actual, **kwargs)
        elif self.assertion_type == "int":
            self.assert_equals(actual, **kwargs)
        else:
            raise ValueError(f"Unknown assertion type: {self.assertion_type}")
            
class Report:
    def __init__(self, report_column: str, df: pd.DataFrame):
        self.filename = report_column
        self._parse_assertions(df, report_column)

    def _parse_assertions(self, df: pd.DataFrame, report_column: str):
        for _, row in df.iterrows():
            assertion = Assertion(row, report_column, self.filename)            
            if not hasattr(self, assertion.component):
                setattr(self, assertion.component, SimpleNamespace())

            component_ns = getattr(self, assertion.component)
            setattr(component_ns, assertion.assertion_id, assertion)

def parse_csv(filename: str) -> List[Report]:
    df = pd.read_csv(filename)
    reports: List[Report] = []

    # Find all report columns
    report_columns = [col for col in df.columns if col.endswith(".html")]

    for report_col in report_columns:
        report = Report(report_col, df)
        reports.append(report)

    return reports