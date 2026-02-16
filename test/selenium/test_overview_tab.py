import os
import pytest
import pandas as pd
from types import SimpleNamespace
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
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


def test_overview_tab(driver):
    # 1. Convert CSV into nested namespace
    expected = csv_to_namespace("assertions.csv")

    # 2. Loop over all reports dynamically
    for report_name in expected.overview_tab.__dict__.keys():
        report_expectations= getattr(expected.overview_tab, report_name)

        # 3. Compute report path (assumes HTML files stored under 'test/reports/')
        report_path = os.path.abspath(f"reports/{report_name}")
        assert os.path.exists(report_path), f"Report file not found: {report_path}"

        driver.get(f"file://{report_path}")
        wait = WebDriverWait(driver, 10)

        # click the Overview tab 
        overview_tab = wait.until(
            EC.element_to_be_clickable((By.ID, "results-summary-tab"))
            )
        overview_tab.click()


        overview_pane = wait.until(
            EC.presence_of_element_located((By.ID, "results-summary"))
        )
        wait.until(lambda d: "show" in overview_pane.get_attribute("class"))

        # 1. Conclusion text
        expected_conclusion = getattr(report_expectations, "1_conclusion_text").lower()
        actual_overview_text = overview_pane.text.lower()

        assert expected_conclusion in actual_overview_text, (
            f"Conclusion '{expected_conclusion}' not found in Overview tab"
        )

        # 2. Species list
        expected_species = getattr(report_expectations, "2_species_found")
      
        visible_table_rows = wait.until(lambda d: [
            row for row in d.find_elements(By.CSS_SELECTOR, "#results-summary tbody tr")
            if row.is_displayed() and row.text.strip()
        ])

        visible_row_texts = [row.text for row in visible_table_rows]

        if expected_species is not None:
            for species in expected_species:
                assert any(species in row_text for row_text in visible_row_texts), (
                    f"Species '{species}' not found in Overview table"
                )
              
         # 3. TOI row count
        expected_count = getattr(report_expectations,"3_toi_row_count")

        tbodies = overview_pane.find_elements(By.TAG_NAME, "tbody")
        assert tbodies, "No tbody elements found in Overview tab"

        toi_rows = tbodies[-1].find_elements(By.TAG_NAME, "tr")
        assert len(toi_rows) == expected_count

        
        # 4. Detect green tick in first row
        detected_cell = toi_rows[0].find_elements(By.TAG_NAME, "td")[1]
        green_tick = detected_cell.find_elements(
            By.CSS_SELECTOR, ".text-success svg.bi-check-circle-fill"
        )
        assert green_tick is not None

        # 5. Flag 2A in second row
        expected_flag = getattr(report_expectations, "5_flag_text")
        
        if expected_flag is not None:
            assert expected_flag in toi_rows[-1].text, (
                f"Expected '{expected_flag}' but found '{toi_rows[-1].text}'"
            )

        print(f"All assertions passed for report: {report_name}")

