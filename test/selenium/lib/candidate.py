from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from lib.report import (
    Collector,
    TabCollector,
    extract_flag_badge,
    first_h_text,
)


WAIT_TIMEOUT = 10

STRONG_ID_THRESHOLD = 98.5
MODERATE_ID_THRESHOLD = 93.5
WEAK_ID_THRESHOLD = 93.5

CLASSIFICATION_TARGETS = {
    "STRONG MATCH": "strong_hits",
    "MODERATE MATCH": "moderate_hits",
    "NO MATCH": "weak_hits",
    "WEAK MATCH": "weak_hits",
}

CANDIDATE_TAB_ID = "candidate-species-tab"
CANDIDATE_PANE_ID = "results-candidate-species"

NA_PLACEHOLDER = "NA"


def strip_percent(text):
    return text.strip().replace("%", "")


def find_modal_button(cell):
    """Return the modal-opening button in a table cell, or None.

    Cells render an `NA` badge instead of a button when the underlying
    data is unavailable (no publication records, or too many candidates
    for coverage analysis).
    """
    buttons = cell.find_elements(By.TAG_NAME, "button")
    return buttons[0] if buttons else None


def open_modal_from_button(driver, button, attr):
    wait = WebDriverWait(driver, WAIT_TIMEOUT)
    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center'});", button)
    wait.until(EC.element_to_be_clickable(button))
    driver.execute_script("arguments[0].click();", button)

    target = button.get_attribute(attr)
    modal_id = (
        target.split("'")[1] if attr == "onclick" else target.replace("#", "")
    )
    return wait.until(EC.visibility_of_element_located((By.ID, modal_id)))


def close_modal(modal, driver):
    modal.find_element(By.CSS_SELECTOR, "button.btn-close").click()
    WebDriverWait(driver, WAIT_TIMEOUT).until(
        EC.invisibility_of_element(modal)
    )


def text_of(parent, selector):
    return parent.find_element(By.CSS_SELECTOR, selector).text.strip()


def extract_taxonomy_value(modal, label):
    for row in modal.find_elements(
        By.CSS_SELECTOR, "#selectedHitTaxonomy tbody tr"
    ):
        header = row.find_element(By.CSS_SELECTOR, "th").text.strip()
        value = row.find_element(By.CSS_SELECTOR, "td").text.strip()
        if header == label:
            return value if value else "No data"
    return "No data"


def _classification_counts(candidate_pane):
    counts = {"strong_hits": None,
              "moderate_hits": None,
              "weak_hits": None}
    table = candidate_pane.find_element(
        By.CSS_SELECTOR, "table.table.tight.font-small")
    for row in table.find_elements(By.TAG_NAME, "tr"):
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 4:
            continue
        classification = cells[0].text.strip().upper()
        key = CLASSIFICATION_TARGETS.get(classification)
        if key:
            counts[key] = int(cells[2].text.strip())
    return counts


class CandidateTabCollector(TabCollector):
    component_id = "candidate_tab"
    tab_id = CANDIDATE_TAB_ID
    pane_id = CANDIDATE_PANE_ID

    def collect(self, driver, report):
        pane = self._open(driver)
        report.set_observed(self.component_id, self._collect_dict(pane))
        CandidateTableCollector().collect_from(pane, driver, report)
        BlastModalCollector().collect_from(pane, driver, report)
        TreeModalCollector().collect_from(pane, driver, report)

    def _extract_tab_title(self, pane):
        return first_h_text(pane, "h2")

    def _extract_candidate_flag_text(self, pane):
        return extract_flag_badge(pane)

    def _extract_strong_alginment_identity(self, pane):
        return STRONG_ID_THRESHOLD

    def _extract_moderate_alginment_identity(self, pane):
        return MODERATE_ID_THRESHOLD

    def _extract_weak_alginment_identity(self, pane):
        return WEAK_ID_THRESHOLD

    def _extract_strong_hits(self, pane):
        return _classification_counts(pane)["strong_hits"]

    def _extract_moderate_hits(self, pane):
        return _classification_counts(pane)["moderate_hits"]

    def _extract_weak_hits(self, pane):
        return _classification_counts(pane)["weak_hits"]

    def _extract_lowest_hit(self, pane):
        badges = pane.find_elements(
            By.CSS_SELECTOR, "span.badge.bg-secondary.text-light")
        if not badges:
            return None
        return float(badges[0].text.strip().replace("%", ""))


class CandidateTableCollector(Collector):
    """Populates `candidate_tab_table` + `publication_modal.candidates[i]`.

    Not opened directly — invoked with the candidate pane by
    CandidateTabCollector.collect().
    """
    component_id = "candidate_tab_table"

    def collect_from(self, pane, driver, report):
        species_table = pane.find_element(
            By.CSS_SELECTOR,
            "table.table.table-striped.freeze-header.sortable",
        )
        rows = species_table.find_elements(By.CSS_SELECTOR, "tbody tr")

        cols = {
            "species": [], "no_of_hits": [], "top_identity": [],
            "median_identity": [], "min_identity": [], "top_e_value": [],
            "publication": [],
        }

        i = 0
        pub_i = 0
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 8:
                continue

            species_name = cells[0].text.strip()
            cols["species"].append(species_name)
            cols["no_of_hits"].append(cells[1].text.strip())
            cols["top_identity"].append(strip_percent(cells[2].text))
            cols["median_identity"].append(strip_percent(cells[3].text))
            cols["min_identity"].append(strip_percent(cells[4].text))
            cols["top_e_value"].append(cells[5].text.strip())

            button = find_modal_button(cells[-1])
            if button is None:
                cols["publication"].append(NA_PLACEHOLDER)
                i += 1
                continue

            pub_row = _open_publication_modal(button, driver)
            cols["publication"].append(pub_row["count"])

            report.get_or_extend_group_row(
                "publication_modal", "candidates", pub_i, name=species_name,
            )
            report.set_observed(
                "publication_modal",
                {
                    "title": [pub_row["title"]],
                    "source": [pub_row["source"]],
                    "count": [pub_row["count"]],
                },
                index=pub_i, group="candidates",
            )
            pub_i += 1
            i += 1

        report.set_observed(self.component_id, cols)


def _open_publication_modal(button, driver):
    modal = open_modal_from_button(driver, button, attr="onclick")
    row = {
        "title": text_of(modal, "h5.modal-title"),
        "source": text_of(modal, "p.lead.px-3.fw-bold"),
        "count": str(len(modal.find_elements(By.CSS_SELECTOR, "div.source"))),
    }
    close_modal(modal, driver)
    return row


class BlastModalCollector(Collector):
    component_id = "blast_modal"

    def collect_from(self, candidate_pane, driver, report):
        button = candidate_pane.find_element(
            By.CSS_SELECTOR,
            'button[data-bs-target="#blastHitsModal"]',
        )
        modal = open_modal_from_button(driver, button, attr="data-bs-target")

        first_row = modal.find_element(By.CSS_SELECTOR, "tbody tr")
        cells = first_row.find_elements(By.TAG_NAME, "td")
        # Render the alignment + taxonomy panes for the first hit
        driver.execute_script("showBlastHit(0);")
        alignment_pre = modal.find_elements(
            By.CSS_SELECTOR, "#selectedHitAlignment")
        alignment_rendered = bool(
            alignment_pre
            and alignment_pre[0].get_attribute("innerText").strip()
        )

        report.set_observed(self.component_id, {
            "title": text_of(modal, "h5.modal-title"),
            "rank": int(cells[0].text.strip()),
            "accession": cells[1].text.strip(),
            "subject": cells[2].text.strip(),
            "length": int(cells[3].text.strip()),
            "identity": float(strip_percent(cells[4].text)),
            "bitscore": float(cells[5].text.strip()),
            "evalue": cells[6].text.strip(),
            "coverage": float(strip_percent(cells[7].text)),
            "alignment_text": alignment_rendered,
            "char_more_than_10": len(cells[2].text.strip()) > 10,
            "domain": extract_taxonomy_value(modal, "Domain"),
            "kingdom": extract_taxonomy_value(modal, "Kingdom"),
            "phylum": extract_taxonomy_value(modal, "Phylum"),
            "class": extract_taxonomy_value(modal, "Class"),
            "order": extract_taxonomy_value(modal, "Order"),
            "family": extract_taxonomy_value(modal, "Family"),
            "genus": extract_taxonomy_value(modal, "Genus"),
            "species": extract_taxonomy_value(modal, "Species"),
        })
        close_modal(modal, driver)


class TreeModalCollector(Collector):
    component_id = "tree_modal"

    def collect_from(self, candidate_pane, driver, report):
        buttons = candidate_pane.find_elements(
            By.CSS_SELECTOR,
            'button[data-bs-target="#distanceTreeModal"]',
        )
        if not buttons:
            return

        modal = open_modal_from_button(
            driver, buttons[0], attr="data-bs-target"
        )
        report.set_observed(self.component_id, {
            "title": text_of(modal, "h5.modal-title"),
            "min_node": driver.execute_script(
                "return Object.keys(leafNames).length;"),
        })
        close_modal(modal, driver)
