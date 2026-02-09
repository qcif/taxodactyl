import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def test_overview_tab():
    report_path = os.path.abspath(
    "reports/1_report_SME25-218_2025-12-11_07_30_03.html"
    )

    options = Options()
    options.add_argument("--window-size=1920,1080")
    options.timeouts = { 'script': 2000 }

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    wait = WebDriverWait(driver, 10)

    try:
        # Open the report
        driver.get(f"file://{report_path}")

        # Step 1: Click the "2. Overview" tab
        overview_tab = wait.until(
            EC.element_to_be_clickable((By.ID, "results-summary-tab"))
        )
        overview_tab.click()
        
        # Step 2: Check for warning box
        box_warning = wait.until(
            EC.visibility_of_element_located((By.CLASS_NAME, "box-warning"))
        )

        assert "inconclusive" in box_warning.text.lower(), \
            f"Unexpected warning text: {box_warning.text}"

        # Step 3: First tbody checks
        first_tbody = driver.find_element(By.TAG_NAME, "tbody")
        rows = first_tbody.find_elements(By.TAG_NAME, "tr")
        assert len(rows) >= 2, "First tbody has less than 2 rows"

        species_elements = driver.find_elements(
        By.CSS_SELECTOR,
            "#results-summary tbody tr td:first-child em"
        )

        species_names = [el.text.strip() for el in species_elements]
        print("Species found:", species_names)

        assert "Drosophila simulans" in species_names
        assert "Drosophila mauritiana" in species_names

        # Step 4: Last tbody checks
        
        overview_pane = wait.until(
            EC.visibility_of_element_located(
                (By.ID, "results-summary")  # This is the actual tab content container
            )
        )

        tbodies = overview_pane.find_elements(By.TAG_NAME, "tbody")
        assert tbodies, "No tbody elements found in Overview tab"

        last_rows = tbodies[-1].find_elements(By.TAG_NAME, "tr")
        assert len(last_rows) == 2, f"Expected 2 rows, got {len(last_rows)}"

        # First row: green tick
        detected_cell = last_rows[0].find_elements(By.TAG_NAME, "td")[1]
        green_tick = detected_cell.find_elements(By.CSS_SELECTOR, ".text-success svg.bi-check-circle-fill")
        assert green_tick, "Green tick not found in first row Detected? column"

        # Last row: Flag 2A 
        assert "Flag 2A" in last_rows[-1].text, "Flag 2A not found in last row"
    finally:
        #close the browser
        driver.quit()
        print("Browser closed")

if __name__ == "__main__":
    test_overview_tab()
