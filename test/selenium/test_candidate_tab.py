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
        candidate_pane = open_tab(driver, tab_id="candidate-species-tab", pane_id="results-candidate-species")

        # Access component
        component = getattr(report, "candidate_tab", None)
        if component is None:
            continue

        # Tab title
        title_assertion = getattr(component, "c1_tab_title", None)
        if title_assertion and title_assertion.expected:
            expected_text = title_assertion.expected.lower()
            actual_text = candidate_pane.text.lower()
            assert expected_text in actual_text, (
                f"Title is '{expected_text}' not found in {report.filename}"
            )
        #flag text
        flag_assertion = getattr(component, "c2_candidate_flag_text", None)
        if flag_assertion and flag_assertion.expected:
            flag_element = wait.until(
                EC.visibility_of_element_located((
                    By.XPATH,
                    f"//span[contains(@class,'badge') and normalize-space(text())='{flag_assertion.expected}']"
                ))
            )
            print(f"actual",flag_element.text)
            assert flag_element.is_displayed(), (
                f"Expected flag '{flag_assertion.expected}' not visible in {report.filename}"
            )
            print(f"Flag '{flag_assertion.expected}' successfully found in {report.filename}")
    