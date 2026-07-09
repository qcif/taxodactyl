import re

from selenium.webdriver.common.by import By

from lib.report import open_tab


def get_badge_count(overview_pane, label):
    badges = overview_pane.find_elements(By.CSS_SELECTOR, "span.badge")
    for badge in badges:
        badge_text = badge.text.strip()
        if label.lower() in badge_text.lower():
            match = re.search(r"\d+", badge_text)
            if match:
                return int(match.group())
    return None


def collect_overview(driver, report):
    pane = open_tab(
        driver,
        tab_id="results-summary-tab",
        pane_id="results-summary",
    )

    visible_species_rows = [
        row
        for row in pane.find_elements(By.CSS_SELECTOR, "tbody tr")
        if row.is_displayed() and row.text.strip()
    ]
    species_texts = [row.text for row in visible_species_rows]

    tbodies = pane.find_elements(By.TAG_NAME, "tbody")
    assert tbodies, "No tbody elements found in Overview tab"
    toi_rows = tbodies[-1].find_elements(By.TAG_NAME, "tr")

    has_green_tick = False
    if toi_rows:
        detected_cell = toi_rows[0].find_elements(By.TAG_NAME, "td")[1]
        green_tick = detected_cell.find_elements(
            By.CSS_SELECTOR,
            ".text-success svg.bi-check-circle-fill"
        )
        has_green_tick = len(green_tick) > 0

    pane_text = pane.text

    report.set_observed("overview_tab", {
        "conclusion_text": pane_text,
        "species_found": species_texts,
        "toi_row_count": len(toi_rows),
        "toi_green_tick_first_row": has_green_tick,
        "overview_flag_text1": pane_text,
        "overview_flag_text2": pane_text,
        "overview_flag_text3": pane_text,
        "matching_species_strong": get_badge_count(pane, "Strong"),
        "matching_species_moderate": get_badge_count(pane, "Moderate"),
        "matching_species_weak": get_badge_count(pane, "Weak"),
    })
