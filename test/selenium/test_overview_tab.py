from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from setup import driver, parse_csv
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

# Helper function for tabs
def open_tab(
    driver: WebDriver,
    tab_id: str,
    pane_id: str,
    expected_header: str = None,
    timeout: int = 10
) -> WebElement:
    """
    Clicks a tab, waits for its pane to appear, and optionally checks a header.
    Returns the pane WebElement.
    """
    wait = WebDriverWait(driver, timeout)

    # Click tab
    tab_element = wait.until(EC.element_to_be_clickable((By.ID, tab_id)))
    tab_element.click()

    # Wait for pane
    pane = wait.until(EC.presence_of_element_located((By.ID, pane_id)))
    wait.until(lambda d: "show" in pane.get_attribute("class"))

    # Optional header assertion
    if expected_header:
        assert expected_header.lower() in pane.text.lower(), f"Expected header '{expected_header}'"

    return pane

# Test function
def test_overview_tab(driver):
    reports = parse_csv(Path("assertions.csv"))

    for report in reports:
        report_path = Path("reports") / report.filename
        assert report_path.exists(), f"Report file not found: {report.filename}"

        driver.get(report_path.resolve().as_uri())
        wait = WebDriverWait(driver,10)


        # Open the Overview tab using the helper
        overview_pane = open_tab(driver, tab_id="results-summary-tab", pane_id="results-summary")

        # Access component
        component = report.overview_tab
        if component is None:
            continue

        # Conclusion text
        component.o1_conclusion_text.assert_contains(
            overview_pane.text,
            context=f"[{report.filename}] Conclusion:"
        )

        # Species list
        visible_rows = [
            row for row in overview_pane.find_elements(By.CSS_SELECTOR, "tbody tr")
            if row.is_displayed() and row.text.strip()
        ]
        row_texts = [row.text for row in visible_rows]

        component.o2_species_found.assert_list_contains(
            row_texts,
            context=f"[{report.filename}] Species:"
        )


        # TOI row count
        tbodies = overview_pane.find_elements(By.TAG_NAME, "tbody")
        assert tbodies, "No tbody elements found in Overview tab"

        toi_rows = tbodies[-1].find_elements(By.TAG_NAME, "tr")

        component.o3_toi_row_count.assert_equals(
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
            component.o4_toi_green_tick_first_row.assert_bool(
                tick_present,
                context=f"[{report.filename}] Green tick first row:"
            )

        #  Flag text 1 
        wait = WebDriverWait(driver, 10)
        flag_element = wait.until(
            EC.presence_of_element_located((
                By.XPATH,
                f".//span[contains(@class,'badge') and normalize-space(.)='{component.o5_overview_flag_text.expected}']"
            ))
        )
        component.o5_overview_flag_text.assert_contains(
            flag_element.text,
            context=f"[{report.filename}] Flag 1:"
        )
       # Flag 2
        component.o6_overview_flag_text.assert_contains(
            overview_pane.text,
            context=f"[{report.filename}] Flag 2:"
        )

        # Flag 3 (table)
        tbodies = overview_pane.find_elements(By.TAG_NAME, "tbody")
        all_rows = [
            row
            for tbody in tbodies
            for row in tbody.find_elements(By.TAG_NAME, "tr")
        ]

        row_texts = [row.text for row in all_rows]

        component.o7_overview_flag_text.assert_list_contains(
            row_texts,
            context=f"[{report.filename}] Flag 3:"
        )

       # Matching species counts
        badges_div = WebDriverWait(overview_pane, 10).until(
            EC.presence_of_element_located((
                By.XPATH,
                ".//div[strong[contains(.,'Matching species')]]"
            ))
        )

        strong_badge = badges_div.find_element(By.XPATH, ".//span[contains(@class,'bg-success')]")
        moderate_badge = badges_div.find_element(By.XPATH, ".//span[contains(@class,'bg-warning')]")
        weak_badge = badges_div.find_element(By.XPATH, ".//span[contains(@class,'bg-danger')]")

        strong_count = int(strong_badge.text.strip().split()[-1])
        moderate_count = int(moderate_badge.text.strip().split()[-1])
        weak_count = int(weak_badge.text.strip().split()[-1])

        component.o8_matching_species_strong.assert_equals(
            strong_count,
            context=f"[{report.filename}] Strong matches:"
        )

        component.o9_matching_species_moderate.assert_equals(
            moderate_count,
            context=f"[{report.filename}] Moderate matches:"
        )

        component.o10_matching_species_weak.assert_equals(
            weak_count,
            context=f"[{report.filename}] Weak matches:"
        )

        print(f"All assertions passed for {report.filename}")