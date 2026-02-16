import os
import pytest
import pandas as pd
from types import SimpleNamespace
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

@pytest.fixture
def driver():
    options = Options()
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    yield driver
    driver.quit()

def csv_to_namespace(csv_path):
    df = pd.read_csv(csv_path)

    reports = [c for c in df.columns if c.endswith(".html")]
    root = SimpleNamespace()

    for component in df["Component"].unique():
        comp_ns = SimpleNamespace()
        comp_df = df[df["Component"] == component]

        for report in reports:
            report_ns = SimpleNamespace()

            for _, row in comp_df.iterrows():
                val = row[report]

                # Convert list/int based on Type column
                if pd.isna(val):
                    val = None
                elif row["Type"] == "list":
                    val = val.split("|")
                elif row["Type"] == "int":
                    val = int(val)

                setattr(report_ns, row["Assertion ID"], val)

            setattr(comp_ns, report, report_ns)

        setattr(root, component, comp_ns)

    return root

def test_sample_modal(driver):
    # Load expected values from CSV
    expected = csv_to_namespace("assertions.csv")

    # Loop over all sample modal reports dynamically
    for report_filename in expected.input_sequence_modal.__dict__:
        report_expectations = getattr(expected.input_sequence_modal, report_filename)

        report_path = os.path.abspath(f"reports/{report_filename}")
        assert os.path.exists(report_path), f"Report file not found: {report_path}"

        driver.get(f"file://{report_path}")
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
