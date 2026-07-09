from typing import List

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from lib.report import open_tab
from lib.candidate import (
    CANDIDATE_TAB_ID,
    CANDIDATE_PANE_ID,
    close_modal,
    open_modal_from_button,
)
from lib.schema import GROUPED_COMPONENTS


SUMMARY_TAB_ID = "results-summary-tab"
SUMMARY_PANE_ID = "results-summary"


def _find_text(modal, css_selector, default=""):
    elements = modal.find_elements(By.CSS_SELECTOR, css_selector)
    return elements[0].text.strip() if elements else default


def _flag_text(modal, *css_selectors):
    for selector in css_selectors:
        elements = modal.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            flag_text = elements[0].find_element(
                By.TAG_NAME, "strong").text.strip()
            return flag_text.replace("Flag ", "").replace(":", "")
    return ""


def _big_number(modal):
    for selector in ("div.big-number.alert-success",
                     "div.big-number.alert-secondary"):
        elements = modal.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            raw = elements[0].text.strip().split()[0]
            return int(raw.replace(",", ""))
    return 0


def _plotly_chart_data(modal, driver):
    plot_divs = modal.find_elements(By.CSS_SELECTOR, "div.js-plotly-plot")
    if not plot_divs:
        return None
    return driver.execute_script("""
        const plot = arguments[0];
        return { x: plot.data[0].x, y: plot.data[0].y };
    """, plot_divs[0])


class CoverageRowCollector:
    """Extracts one database_coverage row from an opened modal.

    Fields correspond to GROUPED_COMPONENTS['database_coverage']['fields'].
    """
    component_id = "database_coverage"

    def __init__(self, driver):
        self._driver = driver
        self._chart_cache = None
        self._modal = None

    def _fields(self):
        return list(GROUPED_COMPONENTS[self.component_id]["fields"].keys())

    def collect_row(self, modal) -> dict:
        self._modal = modal
        self._chart_cache = _plotly_chart_data(modal, self._driver)
        return {
            field: getattr(self, f"_extract_{field}")(modal)
            for field in self._fields()
            if hasattr(self, f"_extract_{field}")
        }

    def _target_scope(self, modal):
        target = modal.find_elements(
            By.CSS_SELECTOR, "div[id^='dbCovTarget']")
        return target[0] if target else modal

    def _related_scope(self, modal):
        related = modal.find_elements(
            By.CSS_SELECTOR, "div[id^='dbCovRelated']")
        return related[0] if related else modal

    def _extract_title(self, modal):
        return [_find_text(modal, "h5.modal-title")]

    def _extract_flag_text1(self, modal):
        return [_flag_text(
            self._target_scope(modal),
            "p.alert.alert-success", "p.alert.alert-secondary")]

    def _extract_record_count(self, modal):
        return [str(_big_number(modal))]

    def _extract_flag_text2(self, modal):
        return [_flag_text(
            self._related_scope(modal),
            "p.alert.alert-warning", "p.alert.alert-secondary")]

    def _extract_species_count(self, modal):
        return [_find_text(
            modal,
            "span.small-number span[class^='relatedHasReference']")]

    def _extract_species_total(self, modal):
        return [_find_text(
            modal, "span.small-number span[class^='relatedCount']")]

    def _extract_min_bar_count(self, modal):
        if self._chart_cache is None:
            return 0
        return len([int(v) for v in self._chart_cache["x"]])

    def _extract_first_bar_species(self, modal):
        if self._chart_cache is None:
            return [""]
        y = [str(v).strip() for v in self._chart_cache["y"]]
        return [y[-1] if y else ""]

    def _extract_first_bar_count(self, modal):
        if self._chart_cache is None:
            return ["0"]
        x = [int(v) for v in self._chart_cache["x"]]
        return [str(max(x)) if x else "0"]

    def _extract_final_text(self, modal):
        return [_find_text(
            modal, "div[id^='dbCovCountry'] p.alert.alert-info")]


def _collect_rows_into_group(
    report,
    group: str,
    table_rows: List[WebElement],
    driver,
    button_cell_index: int,
    button_attr: str,
    min_cells: int,
):
    row_collector = CoverageRowCollector(driver)
    idx = 0
    for row_element in table_rows:
        cells = row_element.find_elements(By.TAG_NAME, "td")
        if len(cells) < min_cells:
            continue
        modal = open_modal_from_button(
            driver,
            cells[button_cell_index].find_element(By.TAG_NAME, "button"),
            attr=button_attr,
        )
        row_dict = row_collector.collect_row(modal)
        close_modal(modal, driver)

        report.get_or_extend_group_row(
            "database_coverage", group, idx)
        report.set_observed(
            "database_coverage", row_dict, index=idx, group=group)
        idx += 1


class DatabaseCoverageCollector:
    """Orchestrator: opens the summary tab (pmi + toi) and candidate tab,
    then delegates each row to CoverageRowCollector."""

    def collect(self, driver, report):
        db_coverage = report.database_coverage

        summary_pane = open_tab(driver, SUMMARY_TAB_ID, SUMMARY_PANE_ID)
        tables = summary_pane.find_elements(
            By.CSS_SELECTOR,
            "table.table.tight.border.align-middle.centered-columns",
        )

        if len(tables) >= 1 and db_coverage.pmi is not None:
            _collect_rows_into_group(
                report, "pmi",
                tables[0].find_elements(By.CSS_SELECTOR, "tbody tr"),
                driver,
                button_cell_index=4,
                button_attr="data-bs-target",
                min_cells=6,
            )

        if len(tables) >= 2 and db_coverage.toi is not None:
            _collect_rows_into_group(
                report, "toi",
                tables[1].find_elements(By.CSS_SELECTOR, "tbody tr"),
                driver,
                button_cell_index=4,
                button_attr="data-bs-target",
                min_cells=6,
            )

        candidate_pane = open_tab(
            driver, CANDIDATE_TAB_ID, CANDIDATE_PANE_ID)
        species_tables = candidate_pane.find_elements(
            By.CSS_SELECTOR,
            "table.table.table-striped.freeze-header.sortable",
        )
        if species_tables:
            _collect_rows_into_group(
                report, "candidate",
                species_tables[0].find_elements(
                    By.CSS_SELECTOR, "tbody tr"),
                driver,
                button_cell_index=6,
                button_attr="onclick",
                min_cells=8,
            )
