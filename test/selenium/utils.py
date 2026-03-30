from types import SimpleNamespace
from pathlib import Path
from typing import Any
import pandas as pd

from yaml import safe_load

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement


def open_tab(
    driver: WebDriver,
    tab_id: str,
    pane_id: str,
    expected_header: str = None,
    timeout: int = 10
) -> WebElement:
    wait = WebDriverWait(driver, timeout)

    tab_element = wait.until(EC.element_to_be_clickable((By.ID, tab_id)))
    driver.execute_script("arguments[0].scrollIntoView(true);", tab_element)
    driver.execute_script("arguments[0].click();", tab_element)

    pane = wait.until(EC.presence_of_element_located((By.ID, pane_id)))
    wait.until(lambda d: "show" in pane.get_attribute("class"))

    # Optional header assertion
    if expected_header:
        assert expected_header.lower() in pane.text.lower(), (
            f"Expected header '{expected_header}'"
        )

    return pane


class Assertion:
    def __init__(self, row, report_column: str, filename: str):
        self.report_filename = filename
        self.component = row['Component']
        self.assertion_id = row['Assertion ID']
        self.assertion_type = (
            str(row['Type']).strip().lower()
            if pd.notna(row['Type']) and str(row['Type']).strip() != ""
            else "contains"
        )

        self.label = self.assertion_id.replace("_", " ").strip()
        self.raw_value = row[report_column]
        self.expected = self._parse_value()

    def _parse_value(self) -> Any:
        if pd.isna(self.raw_value):
            return None

        raw_str = str(self.raw_value).strip()

        if self.assertion_type == "list":
            return [
                item.strip()
                for item in raw_str.split("|")
                if item.strip()
            ]

        if raw_str == "":
            return None
        if self.assertion_type == "int":
            return int(raw_str)
        if self.assertion_type == "min":
            return float(raw_str) if "." in raw_str else int(raw_str)
        if self.assertion_type == "bool":
            return raw_str.lower() == "true"
        if self.assertion_type == "float":
            return float(raw_str)
        return raw_str

    def assert_equals(self, actual, context: str = ""):
        if self.expected is None:
            return

        assert actual == self.expected, (
            f"{context} Expected '{self.expected}' but got '{actual}'"
        )

    def assert_min(self, actual, context: str = ""):
        if self.expected is None:
            return

        assert actual >= self.expected, (
            f"{context} Expected value >= {self.expected} but got {actual}"
        )

    def assert_contains(self, actual: str, context: str = ""):
        if self.expected is None:
            return

        actual = actual.strip().lower()
        expected = str(self.expected).strip().lower()

        assert expected in actual, (
            f"{context} Expected '{expected}' to be in '{actual}'"
        )

    def assert_list_contains(self, observed_values, context: str = ""):
        if not self.expected:
            return

        for expected_item in self.expected:
            assert any(expected_item in item for item in observed_values), (
                f"{context} Expected '{expected_item}' not found"
            )

    def assert_bool(self, actual: bool, context: str = ""):
        if self.expected is None:
            return

        assert bool(actual) == bool(self.expected), (
            f"{context} Expected {self.expected} but got {actual}"
        )

    def assert_value(self, actual, **kwargs):
        if self.expected is None:
            return

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
        elif self.assertion_type == "float":
            self.assert_equals(actual, **kwargs)
        elif self.assertion_type == "min":
            self.assert_min(actual, **kwargs)
        else:
            raise ValueError(f"Unknown assertion type: {self.assertion_type}")


class Report:
    def __init__(self, filename: str, assertions: list):
        self.filename = filename
        self.assertions = assertions
        self.group_assertions()

    def group_assertions(self):
        for assertion in self.assertions:
            component = assertion.component

            if not hasattr(self, component):
                setattr(self, component, SimpleNamespace())

            component_ns = getattr(self, component)
            setattr(component_ns, assertion.assertion_id, assertion)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(
                f"{self.__class__.__name__!r} object has no attribute {name!r}"
            )
        raise AttributeError(
            f"Component '{name}' is missing in report: {self.filename}"
        )


class YamlAssertion(Assertion):
    """Assertion parsed from YAML format (id/type/value keys, native Python types)."""

    def __init__(self, assertion_data: dict, component_id: str, filename: str):
        self.report_filename = filename
        self.component = component_id
        self.assertion_id = assertion_data['id']
        raw_type = str(assertion_data.get('type') or '').strip().lower()
        self.assertion_type = raw_type if raw_type else 'contains'
        self.label = self.assertion_id.replace("_", " ").strip()
        self.raw_value = assertion_data.get('value')
        self.expected = self._parse_value()

    def _parse_value(self) -> Any:
        if self.raw_value is None:
            return None

        # 'list' type: always return a list of strings
        if self.assertion_type == 'list':
            if isinstance(self.raw_value, list):
                items = [str(item).strip() for item in self.raw_value if str(item).strip()]
                return items if items else None
            raw_str = str(self.raw_value).strip()
            if not raw_str:
                return None
            return [raw_str]

        # Non-list type but YAML gave us a list (e.g. type: bool, value: ['TRUE'])
        if isinstance(self.raw_value, list):
            return [self._parse_scalar(str(item)) for item in self.raw_value]

        return self._parse_scalar(str(self.raw_value).strip())

    def _parse_scalar(self, raw_str: str) -> Any:
        if raw_str == '':
            return None
        if self.assertion_type == 'int':
            return int(raw_str)
        if self.assertion_type == 'min':
            return float(raw_str) if '.' in raw_str else int(raw_str)
        if self.assertion_type == 'bool':
            return raw_str.upper() == 'TRUE'
        if self.assertion_type == 'float':
            return float(raw_str)
        return raw_str


def _build_ns_from_yaml_assertions(
    assertion_list: list, component_id: str, filename: str
) -> SimpleNamespace:
    ns = SimpleNamespace()
    for a_data in assertion_list:
        a = YamlAssertion(a_data, component_id, filename)
        setattr(ns, a.assertion_id, a)
    return ns


def parse_assertions(df, report_col, filename):
    assertions = []

    for _, row in df.iterrows():
        assertion = Assertion(row, report_col, filename)
        assertions.append(assertion)

    return assertions


def parse_csv(path: Path):
    df = pd.read_csv(path)

    report_columns = df.columns[3:]
    parsed_reports = []

    for report_col in report_columns:
        report_name = report_col
        assertions = parse_assertions(df, report_col, report_name)

        report = Report(report_name, assertions)
        parsed_reports.append(report)

    return parsed_reports


def parse_yaml(path: Path):
    with open(path, "r") as f:
        data = safe_load(f)

    report_name = data.get('filename', path.stem)
    assertions = []
    special_components = []

    for component in data.get("components", []):
        component_id = component['id']

        if component_id == 'database_coverage' or 'candidates' in component:
            special_components.append(component)
            continue

        for assertion_data in component.get("assertions", []):
            assertions.append(YamlAssertion(assertion_data, component_id, report_name))

    report = Report(report_name, assertions)

    for component in special_components:
        component_id = component['id']

        if component_id == 'database_coverage':
            db_ns = SimpleNamespace()
            for group_key in ('pmi', 'toi', 'candidate'):
                items = component.get(group_key, [])
                setattr(db_ns, group_key, [
                    _build_ns_from_yaml_assertions(
                        item.get('assertions', []), component_id, report_name
                    )
                    for item in items
                ])
            setattr(report, 'database_coverage', db_ns)

        elif 'candidates' in component:
            comp_ns = SimpleNamespace()
            comp_ns.candidates = [
                _build_ns_from_yaml_assertions(
                    item.get('assertions', []), component_id, report_name
                )
                for item in component.get('candidates', [])
            ]
            setattr(report, component_id, comp_ns)

    return report