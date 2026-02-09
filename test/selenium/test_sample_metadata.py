import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def test_view_query_dna_sequence_modal():
    report_path = os.path.abspath(
        "reports/1_report_SME25-218_2025-12-11_07_30_03.html"
    )

    options = Options()
    # options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    options.timeouts = { 'script': 2000 }

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    wait = WebDriverWait(driver, 10)

    try:
        # 1. Open the report
        driver.get(f"file://{report_path}")

        # 2. Click on the "View" link in the Sample metadata table
        view_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "View")))
        view_link.click()

        # 3. Assert that the modal #inputFastaModal appears (display != none)
        modal = wait.until(EC.visibility_of_element_located((By.ID, "inputFastaModal")))
        assert modal.value_of_css_property("display") != "none", "Modal did not appear"

        # 4. Assert that the modal contains given text
        modal_text = modal.text
        assert ">SME25-218" in modal_text, "Modal does not contain sample header"
        assert "CCAAAAAATCA" in modal_text, "Modal does not contain DNA sequence"

        # 5. Click the "Close" button
        close_button = modal.find_element(By.XPATH, ".//button[text()='Close']")
        close_button.click()

        # 6. Assert that the modal has closed (display: none)
        wait.until(lambda d: d.find_element(By.ID, "inputFastaModal").value_of_css_property("display") == "none")

        print("Test passed: Modal opens, displays correct text, and closes successfully.")

    finally:
        driver.quit()

# Run the test
if __name__ == "__main__":
    test_view_query_dna_sequence_modal()
