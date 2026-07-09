from typing import List

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from lib.report import open_tab
from lib.candidate import open_modal_from_button, close_modal


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


def _collect_coverage_row(
    cells: List[WebElement],
    driver: WebDriver,
    button_cell_index: int,
    button_attr: str,
) -> dict:
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

    row = {
        "title": [find_text(modal, "h5.modal-title")],
        "flag_text1": [extract_flag_text(
            flag1_scope, "p.alert.alert-success", "p.alert.alert-secondary")],
        "record_count": [str(extract_big_number(modal))],
        "record_text": [find_text(modal, "p.my-3")],
        "flag_text2": [extract_flag_text(
            flag2_scope, "p.alert.alert-warning", "p.alert.alert-secondary")],
        "species_count": [find_text(
            modal, "span.small-number span[class^='relatedHasReference']")],
        "species_total": [find_text(
            modal, "span.small-number span[class^='relatedCount']")],
        "min_bar_count": min_bar_count,
        "first_bar_species": [first_bar_species],
        "first_bar_count": [str(first_bar_count)],
        "final_text": [find_text(
            modal, "div[id^='dbCovCountry'] p.alert.alert-info")],
    }
    close_modal(modal, driver)
    return row


def _collect_group(
    report,
    group: str,
    table_rows: List[WebElement],
    driver: WebDriver,
    button_cell_index: int,
    button_attr: str,
    min_cells: int,
):
    idx = 0
    for row_element in table_rows:
        cells = row_element.find_elements(By.TAG_NAME, "td")
        if len(cells) < min_cells:
            continue
        row_data = _collect_coverage_row(
            cells, driver, button_cell_index, button_attr,
        )
        report.get_or_extend_group_row("database_coverage", group, idx)
        report.set_observed(
            "database_coverage", row_data, index=idx, group=group,
        )
        idx += 1


def collect_database_coverage(driver, report):
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

    if len(tables) >= 1 and db_coverage.pmi is not None:
        _collect_group(
            report, "pmi",
            tables[0].find_elements(By.CSS_SELECTOR, "tbody tr"),
            driver,
            button_cell_index=4, button_attr="data-bs-target", min_cells=6,
        )

    if len(tables) >= 2 and db_coverage.toi is not None:
        _collect_group(
            report, "toi",
            tables[1].find_elements(By.CSS_SELECTOR, "tbody tr"),
            driver,
            button_cell_index=4, button_attr="data-bs-target", min_cells=6,
        )

    candidate_pane = open_tab(
        driver,
        tab_id="candidate-species-tab",
        pane_id="results-candidate-species",
    )
    species_tables = candidate_pane.find_elements(
        By.CSS_SELECTOR,
        "table.table.table-striped.freeze-header.sortable",
    )
    if species_tables:
        candidate_rows = species_tables[0].find_elements(
            By.CSS_SELECTOR, "tbody tr")
        _collect_group(
            report, "candidate",
            candidate_rows, driver,
            button_cell_index=6, button_attr="onclick", min_cells=8,
        )
