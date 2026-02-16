from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from setup import driver, csv_to_namespace

def test_sample_modal(driver):
    expected = csv_to_namespace(Path("assertions.csv"))

    for report_filename in expected.input_sequence_modal.__dict__:
        report_expectations = getattr(expected.input_sequence_modal, report_filename)

        report_path = Path("reports") / report_filename
        assert report_path.exists(), f"Report file not found: {report_path}"

        driver.get(report_path.resolve().as_uri())
        wait = WebDriverWait(driver, 10)


        # 1. Click on the "View" link dynamically
        view_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "View")))
        view_link.click()

        # 3. Wait for modal to appear
        modal = wait.until(EC.visibility_of_element_located((By.ID, "inputFastaModal")))
        assert modal.value_of_css_property("display") != "none", "Modal did not appear"

        # 4. Verify modal content dynamically from CSV
        expected_header = getattr(report_expectations, "1_sample_id")
        expected_sequence = getattr(report_expectations, "2_dna_sequence")

        modal_text = modal.text
        modal_text = modal.text
        if expected_header:
            assert expected_header in modal_text, f"Modal does not contain sample header '{expected_header}'"
        if expected_sequence:
            assert expected_sequence in modal_text, f"Modal does not contain DNA sequence '{expected_sequence}'"
            
        # 5. Close modal
        close_button = modal.find_element(By.XPATH, ".//button[text()='Close']")
        close_button.click()

        # 6. Verify modal is closed
        wait.until(lambda d: d.find_element(By.ID, "inputFastaModal").value_of_css_property("display") == "none")

        print(f"All assertions passed for report: {report_filename}")