from types import SimpleNamespace
from pathlib import Path
from typing import Any, Iterator, Optional

from yaml import safe_load, safe_dump

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from lib.schema import (
    SIMPLE_COMPONENTS,
    GROUPED_COMPONENTS,
    COMPONENT_ORDER,
)


_SENTINEL = object()


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

    if expected_header:
        assert expected_header.lower() in pane.text.lower(), (
            f"Expected header '{expected_header}'"
        )

    return pane


class Assertion:
    """A single leaf in a Report: id, type, expected value, observed value.

    `expected` is populated by parse_yaml() (or left None when the Report is
    built from schema for ingest). `observed` is populated in-place by the
    collectors via `Report.set_observed`.
    """

    def __init__(
        self,
        assertion_data: Optional[dict],
        component_id: str,
        filename: str,
        assertion_id: Optional[str] = None,
        assertion_type: Optional[str] = None,
    ):
        self.report_filename = filename
        self.component = component_id
        self.observed = None

        if assertion_data is None:
            if assertion_id is None or assertion_type is None:
                raise ValueError(
                    "Assertion requires assertion_data or "
                    "(assertion_id, assertion_type)"
                )
            self.assertion_id = assertion_id
            self.assertion_type = assertion_type
            self.raw_value = None
        else:
            self.assertion_id = assertion_data['id']
            raw_type = str(assertion_data.get('type') or '').strip().lower()
            self.assertion_type = raw_type if raw_type else 'contains'
            self.raw_value = assertion_data.get('value')

        self.label = self.assertion_id.replace("_", " ").strip()
        self.expected = self._parse_value()

    def set_observed(self, value: Any) -> None:
        self.observed = value

    def _parse_value(self) -> Any:
        if self.raw_value is None:
            return None

        if self.assertion_type == 'list':
            if isinstance(self.raw_value, list):
                items = [
                    str(item).strip()
                    for item in self.raw_value
                    if str(item).strip()
                ]
                return items if items else None
            raw_str = str(self.raw_value).strip()
            if not raw_str:
                return None
            return [raw_str]

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

    def _resolve_actual(self, actual):
        if actual is _SENTINEL:
            return self.observed
        return actual

    def assert_equals(self, actual=_SENTINEL, context: str = ""):
        actual = self._resolve_actual(actual)
        if self.expected is None:
            return

        assert actual == self.expected, (
            f"{context} Expected '{self.expected}' but got '{actual}'"
        )

    def assert_min(self, actual=_SENTINEL, context: str = ""):
        actual = self._resolve_actual(actual)
        if self.expected is None:
            return

        assert actual >= self.expected, (
            f"{context} Expected value >= {self.expected} but got {actual}"
        )

    def assert_contains(self, actual=_SENTINEL, context: str = ""):
        actual = self._resolve_actual(actual)
        if self.expected is None:
            return

        actual = str(actual).strip().lower()
        expected = str(self.expected).strip().lower()

        assert expected in actual, (
            f"{context} Expected '{expected}' to be in '{actual}'"
        )

    def assert_list_contains(self, actual=_SENTINEL, context: str = ""):
        actual = self._resolve_actual(actual)
        if not self.expected:
            return

        for expected_item in self.expected:
            assert any(expected_item in item for item in actual), (
                f"{context} Expected '{expected_item}' not found"
            )

    def assert_bool(self, actual=_SENTINEL, context: str = ""):
        actual = self._resolve_actual(actual)
        if self.expected is None:
            return

        assert bool(actual) == bool(self.expected), (
            f"{context} Expected {self.expected} but got {actual}"
        )

    def assert_value(self, actual=_SENTINEL, **kwargs):
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
            raise ValueError(
                f"Unknown assertion type: {self.assertion_type}"
            )

    def is_drifted(self) -> bool:
        """True when the observed value violates the expected value under
        this assertion's type semantics. Returns False when either side is
        None (nothing to compare)."""
        if self.expected is None or self.observed is None:
            return False
        try:
            self.assert_value()
        except AssertionError:
            return True
        return False

    def observed_for_yaml(self) -> Any:
        """Return the observed value shaped for YAML serialisation."""
        val = self.observed
        if val is None:
            return None
        if self.assertion_type == "list":
            if isinstance(val, (list, tuple)):
                return [str(item) for item in val]
            return [str(val)]
        if self.assertion_type == "bool":
            return "TRUE" if bool(val) else "FALSE"
        if self.assertion_type in ("int", "float", "min"):
            return str(val)
        return str(val)


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
                f"{self.__class__.__name__!r} object has no attribute "
                f"{name!r}"
            )
        raise AttributeError(
            f"Component '{name}' is missing in report: {self.filename}"
        )

    # ------------------------------------------------------------------
    # Observed value plumbing (populated by collectors)
    # ------------------------------------------------------------------

    def iter_assertions(self) -> Iterator[Assertion]:
        """Flat iterator over every leaf assertion in the report,
        including grouped ones under database_coverage and publication_modal.
        """
        for component_id in COMPONENT_ORDER:
            comp = getattr(self, component_id, None)
            if comp is None:
                continue

            if component_id in GROUPED_COMPONENTS:
                for group_key in GROUPED_COMPONENTS[component_id]["groups"]:
                    items = getattr(comp, group_key, [])
                    for item_ns in items:
                        for a in vars(item_ns).values():
                            if isinstance(a, Assertion):
                                yield a
            else:
                for a in vars(comp).values():
                    if isinstance(a, Assertion):
                        yield a

    def set_observed(
        self,
        component_id: str,
        values: dict,
        index: Optional[int] = None,
        group: Optional[str] = None,
    ) -> None:
        """Set observed values on the assertions of `component_id`.

        For simple components pass `values` as a flat dict. For grouped
        components (database_coverage, publication_modal) pass `group` and
        `index` to select the row namespace.
        """
        comp = getattr(self, component_id, None)
        if comp is None:
            return

        if group is not None:
            items = getattr(comp, group, None)
            if items is None or index is None or index >= len(items):
                return
            ns = items[index]
        else:
            ns = comp

        for key, value in values.items():
            assertion = getattr(ns, key, None)
            if isinstance(assertion, Assertion):
                assertion.set_observed(value)

    def assert_all(self) -> None:
        for a in self.iter_assertions():
            if a.expected is None or a.observed is None:
                continue
            a.assert_value(context=f"[{a.component}.{a.assertion_id}]")

    def drifted(self) -> list:
        return [a for a in self.iter_assertions() if a.is_drifted()]

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_yaml(self, path: Path, source: str = "observed") -> None:
        """Write the report to a YAML fixture.

        source='observed' writes collected values (used by `testkit ingest`).
        source='expected' round-trips the parsed YAML (used for testing).
        """
        if source not in ("observed", "expected"):
            raise ValueError(f"Unknown source: {source}")

        components = []

        for component_id in COMPONENT_ORDER:
            comp = getattr(self, component_id, None)
            if comp is None:
                continue

            if component_id in GROUPED_COMPONENTS:
                spec = GROUPED_COMPONENTS[component_id]
                block = {"id": component_id}
                for group_key in spec["groups"]:
                    items = getattr(comp, group_key, [])
                    block[group_key] = []
                    for item_ns in items:
                        assertions_out = self._assertions_for_ns(
                            item_ns, spec["fields"], source
                        )
                        row = {"assertions": assertions_out}
                        # Preserve a `name` field if present on the ns
                        name = getattr(item_ns, "_name", None)
                        if name:
                            row = {"name": name, "assertions": assertions_out}
                        block[group_key].append(row)
                components.append(block)
            else:
                field_types = SIMPLE_COMPONENTS.get(component_id, {})
                assertions_out = self._assertions_for_ns(
                    comp, field_types, source
                )
                components.append({
                    "id": component_id,
                    "assertions": assertions_out,
                })

        data = {"filename": self.filename, "components": components}
        with open(path, "w") as f:
            safe_dump(data, f, sort_keys=False, default_flow_style=False)

    @staticmethod
    def _assertions_for_ns(ns, field_types: dict, source: str) -> list:
        out = []
        for field_id, field_type in field_types.items():
            a = getattr(ns, field_id, None)
            if not isinstance(a, Assertion):
                out.append({
                    "id": field_id,
                    "type": field_type,
                    "value": None,
                })
                continue

            if source == "observed":
                value = a.observed_for_yaml()
            else:
                value = a.raw_value

            out.append({
                "id": field_id,
                "type": field_type,
                "value": value,
            })
        return out

    # ------------------------------------------------------------------
    # Schema-only constructor (for testkit ingest of a brand-new HTML)
    # ------------------------------------------------------------------

    @classmethod
    def from_schema(cls, filename: str) -> "Report":
        """Build a skeleton Report with all schema-defined assertions in
        place but no expected/observed values.

        Grouped components (database_coverage, publication_modal) are
        created empty — the collector is responsible for extending them
        via `extend_group()` once it knows how many rows there are.
        """
        report = cls(filename, assertions=[])

        for component_id, field_types in SIMPLE_COMPONENTS.items():
            ns = SimpleNamespace()
            for field_id, field_type in field_types.items():
                setattr(ns, field_id, Assertion(
                    assertion_data=None,
                    component_id=component_id,
                    filename=filename,
                    assertion_id=field_id,
                    assertion_type=field_type,
                ))
            setattr(report, component_id, ns)

        for component_id, spec in GROUPED_COMPONENTS.items():
            group_ns = SimpleNamespace()
            for group_key in spec["groups"]:
                setattr(group_ns, group_key, [])
            setattr(report, component_id, group_ns)

        return report

    def get_or_extend_group_row(
        self,
        component_id: str,
        group: str,
        index: int,
        name: Optional[str] = None,
    ) -> SimpleNamespace:
        """Return the row namespace at `index` in `component_id.group`,
        extending the group with empty rows as needed."""
        rows = getattr(getattr(self, component_id), group)
        while len(rows) <= index:
            self.extend_group(component_id, group, name=name)
        return rows[index]

    def extend_group(
        self,
        component_id: str,
        group: str,
        name: Optional[str] = None,
    ) -> SimpleNamespace:
        """Append an empty row namespace to a grouped component and return
        it. Used by collectors when the number of rows depends on the HTML."""
        spec = GROUPED_COMPONENTS[component_id]
        ns = SimpleNamespace()
        if name:
            ns._name = name
        for field_id, field_type in spec["fields"].items():
            setattr(ns, field_id, Assertion(
                assertion_data=None,
                component_id=component_id,
                filename=self.filename,
                assertion_id=field_id,
                assertion_type=field_type,
            ))
        getattr(getattr(self, component_id), group).append(ns)
        return ns


def _build_ns_from_yaml_assertions(
    assertion_list: list,
    component_id: str,
    filename: str,
    name: Optional[str] = None,
) -> SimpleNamespace:
    ns = SimpleNamespace()
    if name:
        ns._name = name
    for a_data in assertion_list:
        a = Assertion(a_data, component_id, filename)
        setattr(ns, a.assertion_id, a)
    return ns


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
            assertions.append(
                Assertion(assertion_data, component_id, report_name)
            )

    report = Report(report_name, assertions)

    for component in special_components:
        component_id = component['id']

        if component_id == 'database_coverage':
            db_ns = SimpleNamespace()
            for group_key in ('pmi', 'toi', 'candidate'):
                items = component.get(group_key, [])
                setattr(db_ns, group_key, [
                    _build_ns_from_yaml_assertions(
                        item.get('assertions', []),
                        component_id,
                        report_name,
                        name=item.get('name'),
                    )
                    for item in items
                ])
            setattr(report, 'database_coverage', db_ns)

        elif 'candidates' in component:
            comp_ns = SimpleNamespace()
            comp_ns.candidates = [
                _build_ns_from_yaml_assertions(
                    item.get('assertions', []),
                    component_id,
                    report_name,
                    name=item.get('name'),
                )
                for item in component.get('candidates', [])
            ]
            setattr(report, component_id, comp_ns)

    return report
