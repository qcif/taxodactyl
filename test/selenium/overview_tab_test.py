from selenium.webdriver.common.by import By
import re

from conftest import open_tab


def run_overview_tab(driver, report):
    overview_pane = open_tab(
        driver,
        tab_id="results-summary-tab",
        pane_id="results-summary",
    )

    component = report.overview_tab

    component.conclusion_text.assert_value(overview_pane.text)

    # Test species list
    visible_species_rows = [
        row for row in overview_pane.find_elements(By.CSS_SELECTOR, "tbody tr")
        if row.is_displayed() and row.text.strip()
    ]
    row_texts = [row.text for row in visible_species_rows]
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
        has_green_tick = len(green_tick) > 0
        component.toi_green_tick_first_row.assert_value(has_green_tick)

    # Verify flag text in the last TOI row
    flag_text = overview_pane.text

    component.overview_flag_text1.assert_value(flag_text)
    component.overview_flag_text2.assert_value(flag_text)
    component.overview_flag_text3.assert_value(flag_text)

    def get_badge_count(label):
        badge = overview_pane.find_element(
            By.XPATH,
            f".//span[contains(@class,'badge') and contains(text(),'{label}')]"
        )
        return int(re.search(r"\d+", badge.text).group())

    component.matching_species_strong.assert_value(
        get_badge_count("Strong")
    )
    component.matching_species_moderate.assert_value(
        get_badge_count("Moderate")
    )
    component.matching_species_weak.assert_value(
        get_badge_count("Weak")
    )