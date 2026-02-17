from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from setup import driver, parse_csv
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

# Helper function to open a modal
def open_modal(
    driver: WebDriver,
    button_text: str,
    modal_id: str,
    modal_title: str = None,
    timeout: int = 10
) -> WebElement:
    """
    Clicks a button to open a modal, waits for it to appear,
    and optionally asserts the modal title.

    Returns the modal WebElement.
    """
    wait = WebDriverWait(driver, timeout)

    # 1. Wait for the button to be clickable and click it
    button = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, button_text)))
    button.click()

    # 2. Wait for the modal to appear
    modal = wait.until(EC.visibility_of_element_located((By.ID, modal_id)))
    assert modal.value_of_css_property("display") != "none", f"Modal {modal_id} did not appear"

    # 3. Optionally assert modal title
    if modal_title:
        title_element = modal.find_element(By.CLASS_NAME, "modal-title")
        assert modal_title in title_element.text, f"Expected modal title '{modal_title}'"

    return modal


# Test function
def test_sample_modal(driver):
    reports = parse_csv(Path("assertions.csv"))

    for report in reports:
        report_path = Path("reports") / report.filename
        assert report_path.exists(), f"Missing report: {report.filename}"

        driver.get(report_path.resolve().as_uri())

        # Open modal using the helper function
        modal = open_modal(driver, button_text="View", modal_id="inputFastaModal")

        modal_text = modal.text

        # Access component and assertions
        component = report.input_sequence_modal
        if component is None:
            continue

        # Sample ID
        sample_id_assertion = component.i1_sample_id
        if sample_id_assertion and sample_id_assertion.expected:
            assert sample_id_assertion.expected in modal_text, (
                f"Missing sample ID '{sample_id_assertion.expected}' in {report.filename}"
            )

        # DNA Sequence
        dna_assertion = component.i2_dna_sequence 
        if dna_assertion and dna_assertion.expected:
            assert dna_assertion.expected in modal_text, (
                f"Missing DNA sequence '{dna_assertion.expected}' in {report.filename}"
            )

        # Close the modal
        close_button = modal.find_element(By.XPATH, ".//button[text()='Close']")
        close_button.click()
        WebDriverWait(driver, 10).until(
            lambda d: modal.value_of_css_property("display") == "none"
        )

        print(f"All assertions passed for {report.filename}")
