from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement


def open_modal(
    driver: WebDriver,
    button_text: str,
    modal_id: str,
    modal_title: str = None,
    timeout: int = 10
) -> WebElement:
    """
    Click a button to open a modal, wait for it to appear,
    and optionally asserts the modal title.

    Returns the modal WebElement.
    """
    wait = WebDriverWait(driver, timeout)

    button = wait.until(
        EC.element_to_be_clickable((By.LINK_TEXT, button_text))
    )
    button.click()

    modal = wait.until(EC.visibility_of_element_located((By.ID, modal_id)))
    assert modal.value_of_css_property(
        "display") != "none", f"Modal {modal_id} did not appear"
    if modal_title:
        title_element = modal.find_element(By.CLASS_NAME, "modal-title")
        assert modal_title in title_element.text, (
            f"Expected modal title '{modal_title}'"
        )

    return modal


def run_sample_modal(driver, report):
    modal = open_modal(driver, button_text="View", modal_id="inputFastaModal")
    modal_content = modal.text
    
    component = report.input_sequence_modal

    component.sample_id.assert_value(modal_content)
    component.dna_sequence.assert_value(modal_content)
    modal.find_element(By.XPATH, ".//button[text()='Close']").click()
    # Wait until the modal is fully hidden before continuing
    WebDriverWait(driver, 10).until(
        lambda d: modal.value_of_css_property("display") == "none"
    )
