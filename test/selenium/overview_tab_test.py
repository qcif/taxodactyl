from selenium.webdriver.common.by import By

from conftest import open_tab


def run_overview_tab(driver, report):
    # Open the Overview tab using the helper
    overview_pane = open_tab(
        driver,
        tab_id="results-summary-tab",
        pane_id="results-summary",
    )

    # Access component
    component = report.overview_tab

    component.conclusion_text.assert_value(overview_pane.text)

    # Test species list
    visible_rows = [
        row for row in overview_pane.find_elements(By.CSS_SELECTOR, "tbody tr")
        if row.is_displayed() and row.text.strip()
    ]
    row_texts = [row.text for row in visible_rows]
    component.species_found.assert_value(row_texts)

    # Count rows in TOI table
    tbodies = overview_pane.find_elements(By.TAG_NAME, "tbody")
    assert tbodies, "No tbody elements found in Overview tab"
    toi_rows = tbodies[-1].find_elements(By.TAG_NAME, "tr")
    component.toi_row_count.assert_value(len(toi_rows))

    # Check green tick in first TOI row
    if toi_rows:
        detected_cell = toi_rows[0].find_elements(By.TAG_NAME, "td")[1]
        green_tick = detected_cell.find_elements(
            By.CSS_SELECTOR,
            ".text-success svg.bi-check-circle-fill"
        )
        component.toi_green_tick_first_row.assert_value(green_tick)

    # Verify flag text in the last TOI row
    if toi_rows:
        component.flag_text.assert_value(
            toi_rows[-1].text)
