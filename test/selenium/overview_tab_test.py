from selenium.webdriver.common.by import By
import re

from utils import open_tab


def get_badge_count(overview_pane, label):
    badges = overview_pane.find_elements(By.CSS_SELECTOR, "span.badge")
    for badge in badges:
        badge_text = badge.text.strip()
        if label.lower() in badge_text.lower():
            match = re.search(r"\d+", badge_text)
            if match:
                return int(match.group())
    raise AssertionError(f"Badge with label '{label}' not found")


def run_overview_tab(driver, report):
    overview_pane = open_tab(
        driver,
        tab_id="results-summary-tab",
        pane_id="results-summary",
    )

    component = report.overview_tab

    component.conclusion_text.assert_value(overview_pane.text)

    visible_species_rows = [
        row
        for row in overview_pane.find_elements(By.CSS_SELECTOR, "tbody tr")
        if row.is_displayed() and row.text.strip()
    ]
    row_texts = [row.text for row in visible_species_rows]
    component.species_found.assert_value(row_texts)

    tbodies = overview_pane.find_elements(By.TAG_NAME, "tbody")
    assert tbodies, "No tbody elements found in Overview tab"

    toi_rows = tbodies[-1].find_elements(By.TAG_NAME, "tr")
    component.toi_row_count.assert_value(len(toi_rows))

    if toi_rows:
        detected_cell = toi_rows[0].find_elements(By.TAG_NAME, "td")[1]
        green_tick = detected_cell.find_elements(
            By.CSS_SELECTOR,
            ".text-success svg.bi-check-circle-fill"
        )
        has_green_tick = len(green_tick) > 0
        component.toi_green_tick_first_row.assert_value(has_green_tick)

    flag_text = overview_pane.text
    component.overview_flag_text1.assert_value(flag_text)
    component.overview_flag_text2.assert_value(flag_text)
    component.overview_flag_text3.assert_value(flag_text)

    component.matching_species_strong.assert_value(
        get_badge_count(overview_pane, "Strong")
    )
    component.matching_species_moderate.assert_value(
        get_badge_count(overview_pane, "Moderate")
    )
    component.matching_species_weak.assert_value(
        get_badge_count(overview_pane, "Weak")
    )