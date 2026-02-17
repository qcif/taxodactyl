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

        # Open the Overview tab using the helper
        overview_pane = open_tab(driver, tab_id="results-summary-tab", pane_id="results-summary")

        # Access component
        component = getattr(report, "overview_tab", None)
        if component is None:
            continue

        # Conclusion text
        conclusion_assertion = getattr(component, "o1_conclusion_text", None)
        if conclusion_assertion and conclusion_assertion.expected:
            expected_text = conclusion_assertion.expected.lower()
            actual_text = overview_pane.text.lower()
            assert expected_text in actual_text, (
                f"Conclusion '{expected_text}' not found in {report.filename}"
            )

        # Species list
        species_assertion = getattr(component, "o2_species_found", None)
        if species_assertion and species_assertion.expected:
            visible_rows = [
                row for row in overview_pane.find_elements(By.CSS_SELECTOR, "tbody tr")
                if row.is_displayed() and row.text.strip()
            ]
            row_texts = [row.text for row in visible_rows]
            for species in species_assertion.expected:
                assert any(species in text for text in row_texts), (
                    f"Species '{species}' not found in {report.filename}"
                )

        # TOI row count
        count_assertion = getattr(component, "o3_toi_row_count", None)
        tbodies = overview_pane.find_elements(By.TAG_NAME, "tbody")
        assert tbodies, "No tbody elements found in Overview tab"
        toi_rows = tbodies[-1].find_elements(By.TAG_NAME, "tr")
        if count_assertion and count_assertion.expected is not None:
            assert len(toi_rows) == count_assertion.expected, (
                f"Expected {count_assertion.expected} TOI rows but found {len(toi_rows)} in {report.filename}"
            )

        # Green tick in first row
        green_tick_assertion = getattr(component, "o4_toi_green_tick_first_row", None)
        if green_tick_assertion and green_tick_assertion.expected is not None and toi_rows:
            detected_cell = toi_rows[0].find_elements(By.TAG_NAME, "td")[1]
            green_tick = detected_cell.find_elements(
                By.CSS_SELECTOR,
                ".text-success svg.bi-check-circle-fill"
            )
            tick_present = bool(green_tick)
            assert tick_present == green_tick_assertion.expected, (
                f"Expected green tick presence to be {green_tick_assertion.expected} "
                f"but found {tick_present} in {report.filename}"
            )

        #  Flag text
        flag_assertion = getattr(component, "o5_flag_text", None)
        if flag_assertion and flag_assertion.expected:
            assert flag_assertion.expected in toi_rows[-1].text, (
                f"Expected '{flag_assertion.expected}' in {report.filename}"
            )

        print(f"All assertions passed for {report.filename}")
