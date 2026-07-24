from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from lib.report import Collector


MODAL_ID = "inputFastaModal"
SEQUENCE_PREVIEW_LEN = 20


def _open_input_modal(driver, timeout=10):
    wait = WebDriverWait(driver, timeout)
    button = wait.until(
        EC.element_to_be_clickable((By.LINK_TEXT, "View"))
    )
    button.click()
    modal = wait.until(EC.visibility_of_element_located((By.ID, MODAL_ID)))
    assert modal.value_of_css_property("display") != "none", (
        f"Modal {MODAL_ID} did not appear"
    )
    return modal


def _close_input_modal(modal, driver):
    modal.find_element(By.XPATH, ".//button[text()='Close']").click()
    WebDriverWait(driver, 10).until(
        lambda d: modal.value_of_css_property("display") == "none"
    )


def _parse_fasta(pre_text: str):
    sample_id = ""
    sequence = ""
    for line in (ln.strip() for ln in pre_text.splitlines() if ln.strip()):
        if line.startswith(">"):
            sample_id = line[1:].split()[0] if line[1:].strip() else ""
        else:
            sequence += line
    return sample_id, sequence


class InputSequenceModalCollector(Collector):
    component_id = "input_sequence_modal"

    def collect(self, driver, report):
        modal = _open_input_modal(driver)
        pre_elements = modal.find_elements(By.TAG_NAME, "pre")
        pre_text = pre_elements[0].text if pre_elements else modal.text
        sample_id, sequence = _parse_fasta(pre_text)

        # Extractors just read from the pre-parsed values above
        self._sample_id = sample_id
        self._sequence = sequence
        report.set_observed(self.component_id, self._collect_dict(modal))
        _close_input_modal(modal, driver)

    def _extract_sample_id(self, modal):
        return self._sample_id

    def _extract_dna_sequence(self, modal):
        return self._sequence[:SEQUENCE_PREVIEW_LEN]
