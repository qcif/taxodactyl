from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from setup import open_tab, parse_csv, driver

# Test function
def test_overview_tab(driver):
    reports = parse_csv(Path("assertions.csv"))

    for report in reports:
        report_path = Path("reports") / report.filename
        assert report_path.exists(), f"Report file not found: {report.filename}"

        driver.get(report_path.resolve().as_uri())

        # Open the Overview tab using the helper
        overview_pane = open_tab(driver, tab_id="results-summary-tab", pane_id="results-summary")

        # Access component
        component = report.overview_tab
        if component is None:
            continue

        # Conclusion text
        component.conclusion_text.assert_contains(
            overview_pane.text,
            context=f"[{report.filename}] Conclusion:"
        )


        # Species list
        visible_rows = [
            row for row in overview_pane.find_elements(By.CSS_SELECTOR, "tbody tr")
            if row.is_displayed() and row.text.strip()
        ]
        row_texts = [row.text for row in visible_rows]

        component.species_found.assert_list_contains(
            row_texts,
            context=f"[{report.filename}] Species:"
        )


        # TOI row count
        tbodies = overview_pane.find_elements(By.TAG_NAME, "tbody")
        assert tbodies, "No tbody elements found in Overview tab"

        toi_rows = tbodies[-1].find_elements(By.TAG_NAME, "tr")

        component.toi_row_count.assert_equals(
            len(toi_rows),
            context=f"[{report.filename}] TOI row count:"
        )

        # Green tick in first row
        if toi_rows:
            detected_cell = toi_rows[0].find_elements(By.TAG_NAME, "td")[1]
            green_tick = detected_cell.find_elements(
                By.CSS_SELECTOR,
                ".text-success svg.bi-check-circle-fill"
            )
            tick_present = bool(green_tick)

            component.toi_green_tick_first_row.assert_bool(
                tick_present,
                context=f"[{report.filename}] Green tick first row:"
            )
        #  Flag text
        if toi_rows:
            component.flag_text.assert_contains(
                toi_rows[-1].text,
                context=f"[{report.filename}] Flag text:"
            )

        print(f"All assertions passed for {report.filename}")
