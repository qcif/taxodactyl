from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement


MODAL_ID = "inputFastaModal"


def open_modal(
    driver: WebDriver,
    button_text: str,
    modal_id: str,
    modal_title: str = None,
    timeout: int = 10
) -> WebElement:
    """Click a button to open a modal, wait for it, return the WebElement."""
    wait = WebDriverWait(driver, timeout)

    button = wait.until(
        EC.element_to_be_clickable((By.LINK_TEXT, button_text))
    )
    button.click()

    modal = wait.until(EC.visibility_of_element_located((By.ID, modal_id)))
    assert modal.value_of_css_property("display") != "none", (
        f"Modal {modal_id} did not appear"
    )
    if modal_title:
        title_element = modal.find_element(By.CLASS_NAME, "modal-title")
        assert modal_title in title_element.text, (
            f"Expected modal title '{modal_title}'"
        )

    return modal


SEQUENCE_PREVIEW_LEN = 20


def _parse_fasta(pre_text: str) -> tuple:
    lines = [ln.strip() for ln in pre_text.splitlines() if ln.strip()]
    sample_id = ""
    sequence = ""
    for line in lines:
        if line.startswith(">"):
            sample_id = line[1:].split()[0] if line[1:].strip() else ""
        else:
            sequence += line
    return sample_id, sequence


def collect_sample_metadata(driver, report):
    modal = open_modal(driver, button_text="View", modal_id=MODAL_ID)

    pre_elements = modal.find_elements(By.TAG_NAME, "pre")
    pre_text = pre_elements[0].text if pre_elements else modal.text
    sample_id, sequence = _parse_fasta(pre_text)

    report.set_observed("input_sequence_modal", {
        "sample_id": sample_id,
        "dna_sequence": sequence[:SEQUENCE_PREVIEW_LEN],
    })

    modal.find_element(By.XPATH, ".//button[text()='Close']").click()
    WebDriverWait(driver, 10).until(
        lambda d: modal.value_of_css_property("display") == "none"
    )
