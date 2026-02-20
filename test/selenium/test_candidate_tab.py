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
def test_candidate_tab(driver):
    reports = parse_csv(Path("assertions.csv"))

    for report in reports:
        report_path = Path("reports") / report.filename
        assert report_path.exists(), f"Report file not found: {report.filename}"

        driver.get(report_path.resolve().as_uri())
        wait = WebDriverWait(driver,10)


        # Open the candidate tab using the helper
        candidate_pane = open_tab(
            driver, 
            tab_id="candidate-species-tab", 
            pane_id="results-candidate-species")

        # Access component
        component = report.candidate_tab
        if component is None:
            continue

        # Tab title
        component.c1_tab_title.assert_contains(
            candidate_pane.text,
            context=f"[{report.filename}] Candidate tab title:"
        )

        # Candidate flag
        flag_element = WebDriverWait(candidate_pane, 10).until(
            EC.presence_of_element_located((
                By.XPATH,
                ".//div[contains(@class,'alert')]//span[contains(@class,'badge')]"
            ))
        )

        component.c2_candidate_flag_text.assert_contains(
            flag_element.text,
            context=f"[{report.filename}] Candidate flag:"
        )

        # Alignment identity thresholds
        rows = candidate_pane.find_elements(By.XPATH, ".//table[contains(@class,'tight')]//tbody/tr")

        strong_row = rows[0]
        moderate_row = rows[1]
        weak_row = rows[2]

        # Identity thresholds ****
        strong_identity = strong_row.find_elements(By.TAG_NAME, "td")[1].text
        moderate_identity = moderate_row.find_elements(By.TAG_NAME, "td")[1].text
        weak_identity = weak_row.find_elements(By.TAG_NAME, "td")[1].text

        component.c3_strong_alginment_identity.assert_contains(
            strong_identity,
            context=f"[{report.filename}] Strong identity:"
        )

        component.c4_moderate_alginment_identity.assert_contains(
            moderate_identity,
            context=f"[{report.filename}] Moderate identity:"
        )

        component.c5_weak_alginment_identity.assert_contains(
            weak_identity,
            context=f"[{report.filename}] Weak identity:"
        )

        # Lowest hit (float)
        lowest_hit_span = driver.find_element(
            By.XPATH,
            "//p[contains(text(),'Lowest identity of all')]/span[contains(@class,'badge')]"
        )
        lowest_hit_value = lowest_hit_span.text.strip().replace("%", "")

        # Assert using your float assertion
        component.c9_lowest_hit.assert_float(
            float(lowest_hit_value),
            context=f"[{report.filename}] Lowest BLAST hit:"
        )
        # Candidate species table rows
        # candidate_rows = candidate_pane.find_elements(By.CSS_SELECTOR, "div.mb-3 table tbody tr")
