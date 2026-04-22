from dataclasses import dataclass, field
from typing import List
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from utils import open_tab
from candidate_tab_test import (
    open_modal_from_button,
    close_modal,
    merge_modal_data,
)


@dataclass
class CoverageModalRow:
    title: str
    flag1: str
    record_count: int
    record_text: str
    flag2: str
    species_count: str
    species_total: str
    min_bar_count: int
    first_bar_species: str
    first_bar_count: int
    final_text: str


@dataclass
class CoverageModalData:
    title: List[str] = field(default_factory=list)
    flag1: List[str] = field(default_factory=list)
    record_count: List[str] = field(default_factory=list)
    record_text: List[str] = field(default_factory=list)
    flag2: List[str] = field(default_factory=list)
    species_count: List[str] = field(default_factory=list)
    species_total: List[str] = field(default_factory=list)
    min_bar_count: List[str] = field(default_factory=list)
    first_bar_species: List[str] = field(default_factory=list)
    first_bar_count: List[str] = field(default_factory=list)
    final_text: List[str] = field(default_factory=list)


def find_text(modal, css_selector, default=""):
    elements = modal.find_elements(By.CSS_SELECTOR, css_selector)
    return elements[0].text.strip() if elements else default


def extract_flag_text(modal, *css_selectors):
    for selector in css_selectors:
        elements = modal.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            flag_text = elements[0].find_element(
                By.TAG_NAME, "strong").text.strip()
            return flag_text.replace("Flag ", "").replace(":", "")
    return ""


def extract_big_number(modal):
    for selector in ("div.big-number.alert-success",
                     "div.big-number.alert-secondary"):
        elements = modal.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            raw = elements[0].text.strip().split()[0]
            return int(raw.replace(",", ""))
    return 0


def extract_plotly_chart_data(modal, driver):
    plot_divs = modal.find_elements(By.CSS_SELECTOR, "div.js-plotly-plot")
    if not plot_divs:
        return None
    return driver.execute_script("""
        const plot = arguments[0];
        return {
            x: plot.data[0].x,
            y: plot.data[0].y
        };
    """, plot_divs[0])


def collect_coverage_modal_data(
    cells: List[WebElement],
    driver: WebDriver,
    button_cell_index: int,
    button_attr: str,
) -> CoverageModalRow:
    modal = open_modal_from_button(
        driver,
        cells[button_cell_index].find_element(By.TAG_NAME, "button"),
        attr=button_attr,
    )

    chart_data = extract_plotly_chart_data(modal, driver)
    if chart_data is not None:
        x_values = [int(v) for v in chart_data["x"]]
        y_values = [str(v).strip() for v in chart_data["y"]]
        min_bar_count = len(x_values)
        first_bar_species = y_values[-1]
        first_bar_count = max(x_values)
    else:
        min_bar_count = 0
        first_bar_species = ""
        first_bar_count = 0

    target_section = modal.find_elements(
        By.CSS_SELECTOR, "div[id^='dbCovTarget']")
    related_section = modal.find_elements(
        By.CSS_SELECTOR, "div[id^='dbCovRelated']")
    flag1_scope = target_section[0] if target_section else modal
    flag2_scope = related_section[0] if related_section else modal

    row = CoverageModalRow(
        title=find_text(modal, "h5.modal-title"),
        flag1=extract_flag_text(
            flag1_scope, "p.alert.alert-success", "p.alert.alert-secondary"),
        record_count=extract_big_number(modal),
        record_text=find_text(modal, "p.my-3"),
        flag2=extract_flag_text(
            flag2_scope, "p.alert.alert-warning", "p.alert.alert-secondary"),
        species_count=find_text(
            modal,
            "span.small-number span[class^='relatedHasReference']",
        ),
        species_total=find_text(
            modal,
            "span.small-number span[class^='relatedCount']",
        ),
        min_bar_count=min_bar_count,
        first_bar_species=first_bar_species,
        first_bar_count=first_bar_count,
        final_text=find_text(modal,
                             "div[id^='dbCovCountry'] p.alert.alert-info"),
    )

    close_modal(modal, driver)
    return row


def collect_group_coverage_data(
    rows: List[WebElement],
    driver: WebDriver,
    button_cell_index: int,
    button_attr: str,
    min_cells: int,
) -> CoverageModalData:
    coverage_modal_data = CoverageModalData()
    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < min_cells:
            continue
        merge_modal_data(
            coverage_modal_data,
            collect_coverage_modal_data(cells,
                                        driver,
                                        button_cell_index,
                                        button_attr),
            stringify_keys={"record_count",
                            "min_bar_count",
                            "first_bar_count"},
        )
    return coverage_modal_data


def assert_group_coverage(group_assertions, modal_data: CoverageModalData):
    for i, entry in enumerate(group_assertions):
        entry.title.assert_value([modal_data.title[i]])
        entry.flag_text1.assert_value([modal_data.flag1[i]])
        entry.record_count.assert_value([modal_data.record_count[i]])
        entry.record_text.assert_value([modal_data.record_text[i]])
        entry.flag_text2.assert_value([modal_data.flag2[i]])
        entry.species_count.assert_value([modal_data.species_count[i]])
        entry.species_total.assert_value([modal_data.species_total[i]])
        for count in modal_data.min_bar_count:
            entry.min_bar_count.assert_value(int(count))
        entry.first_bar_species.assert_value([modal_data.first_bar_species[i]])
        entry.first_bar_count.assert_value([modal_data.first_bar_count[i]])
        entry.final_text.assert_value([modal_data.final_text[i]])


def run_database_coverage(driver, report):
    db_coverage = report.database_coverage

    summary_pane = open_tab(
        driver,
        tab_id="results-summary-tab",
        pane_id="results-summary",
    )
    tables = summary_pane.find_elements(
        By.CSS_SELECTOR,
        "table.table.tight.border.align-middle.centered-columns",
    )

    if db_coverage.pmi:
        pmi_rows = tables[0].find_elements(By.CSS_SELECTOR, "tbody tr")
        pmi_data = collect_group_coverage_data(
            pmi_rows, driver,
            button_cell_index=4,
            button_attr="data-bs-target",
            min_cells=6,
        )
        assert_group_coverage(db_coverage.pmi, pmi_data)

    if db_coverage.toi:
        toi_rows = tables[1].find_elements(By.CSS_SELECTOR, "tbody tr")
        toi_data = collect_group_coverage_data(
            toi_rows, driver,
            button_cell_index=4,
            button_attr="data-bs-target",
            min_cells=6,
        )
        assert_group_coverage(db_coverage.toi, toi_data)

    if db_coverage.candidate:
        candidate_pane = open_tab(
            driver,
            tab_id="candidate-species-tab",
            pane_id="results-candidate-species",
        )
        species_table = candidate_pane.find_element(
            By.CSS_SELECTOR,
            "table.table.table-striped.freeze-header.sortable",
        )
        candidate_rows = species_table.find_elements(
            By.CSS_SELECTOR, "tbody tr")
        candidate_data = collect_group_coverage_data(
            candidate_rows, driver,
            button_cell_index=6,
            button_attr="onclick",
            min_cells=8,
        )
        assert_group_coverage(db_coverage.candidate, candidate_data)
