from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from lib.report import open_tab


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


def strip_percent(text):
    return text.strip().replace("%", "")


def open_modal_from_button(driver, button, attr):
    wait = WebDriverWait(driver, WAIT_TIMEOUT)
    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center'});",
        button)
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


def text(parent, by, selector):
    return parent.find_element(by, selector).text.strip()


def get_lowest_hit(candidate_pane):
    badge = candidate_pane.find_element(
        By.CSS_SELECTOR,
        "span.badge.bg-secondary")
    return float(badge.text.strip().replace("%", ""))


def extract_taxonomy_value(modal, label):
    rows = modal.find_elements(
        By.CSS_SELECTOR,
        "#selectedHitTaxonomy tbody tr"
    )

    for row in rows:
        header = row.find_element(By.CSS_SELECTOR, "th").text.strip()
        value = row.find_element(By.CSS_SELECTOR, "td").text.strip()

        if header == label:
            return value if value else "No data"

    return "No data"


def extract_classification_counts(candidate_pane):
    counts = {"strong_hits": None,
              "moderate_hits": None,
              "weak_hits": None}
    table = candidate_pane.find_element(
        By.CSS_SELECTOR,
        "table.table.tight.font-small")
    for row in table.find_elements(By.TAG_NAME, "tr"):
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 4:
            continue
        classification = cells[0].text.strip().upper()
        key = CLASSIFICATION_TARGETS.get(classification)
        if key:
            counts[key] = int(cells[2].text.strip())
    return counts


def collect_species_table(
    candidate_pane: WebElement,
    driver: WebDriver,
    report,
):
    species_table = candidate_pane.find_element(
        By.CSS_SELECTOR, "table.table.table-striped.freeze-header.sortable"
    )
    rows = species_table.find_elements(By.CSS_SELECTOR, "tbody tr")

    species = []
    no_of_hits = []
    top_identity = []
    median_identity = []
    min_identity = []
    top_e_value = []
    publication_counts = []

    for i, row in enumerate(rows):
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 8:
            continue

        species_name = cells[0].text.strip()
        species.append(species_name)
        no_of_hits.append(cells[1].text.strip())
        top_identity.append(strip_percent(cells[2].text))
        median_identity.append(strip_percent(cells[3].text))
        min_identity.append(strip_percent(cells[4].text))
        top_e_value.append(cells[5].text.strip())

        pub = _open_and_read_publication_modal(cells, driver)
        publication_counts.append(pub["source_count"])

        row_ns = report.get_or_extend_group_row(
            "publication_modal", "candidates", i, name=species_name,
        )
        row_ns_dict = {
            "title": [pub["title"]],
            "source": [pub["source"]],
            "count": [pub["source_count"]],
        }
        for key, value in row_ns_dict.items():
            assertion = getattr(row_ns, key, None)
            if assertion is not None:
                assertion.set_observed(value)

    report.set_observed("candidate_tab_table", {
        "species": species,
        "no_of_hits": no_of_hits,
        "top_identity": top_identity,
        "median_identity": median_identity,
        "min_identity": min_identity,
        "top_e_value": top_e_value,
        "publication": publication_counts,
    })


def _open_and_read_publication_modal(cells, driver):
    modal = open_modal_from_button(
        driver, cells[-1].find_element(By.TAG_NAME, "button"), attr="onclick"
    )
    data = {
        "title": text(modal, By.CSS_SELECTOR, "h5.modal-title"),
        "source": text(modal, By.CSS_SELECTOR, "p.lead.px-3.fw-bold"),
        "source_count": str(len(modal.find_elements(
            By.CSS_SELECTOR, "div.source"))),
    }
    close_modal(modal, driver)
    return data


def collect_blast_modal(candidate_pane, driver, report):
    button = candidate_pane.find_element(
        By.CSS_SELECTOR,
        'button[data-bs-target="#blastHitsModal"]'
    )
    modal = open_modal_from_button(driver, button, attr="data-bs-target")

    first_row = modal.find_element(By.CSS_SELECTOR, "tbody tr")
    cells = first_row.find_elements(By.TAG_NAME, "td")
    # Render the alignment + taxonomy panes for the first hit
    driver.execute_script("showBlastHit(0);")
    alignment_pre = modal.find_elements(
        By.CSS_SELECTOR, "#selectedHitAlignment")
    alignment_rendered = bool(
        alignment_pre and alignment_pre[0].get_attribute("innerText").strip()
    )

    report.set_observed("blast_modal", {
        "title": text(modal, By.CSS_SELECTOR, "h5.modal-title"),
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


def collect_tree_modal(candidate_pane, driver, report):
    buttons = candidate_pane.find_elements(
        By.CSS_SELECTOR,
        'button[data-bs-target="#distanceTreeModal"]'
    )
    if not buttons:
        return

    modal = open_modal_from_button(driver, buttons[0], attr="data-bs-target")

    report.set_observed("tree_modal", {
        "title": text(modal, By.CSS_SELECTOR, "h5.modal-title"),
        "min_node": driver.execute_script(
            "return Object.keys(leafNames).length;"),
    })
    close_modal(modal, driver)


def collect_candidate(driver, report):
    pane = open_tab(
        driver,
        tab_id="candidate-species-tab",
        pane_id="results-candidate-species",
    )
    pane_text = pane.text

    counts = extract_classification_counts(pane)

    report.set_observed("candidate_tab", {
        "tab_title": pane_text,
        "candidate_flag_text": pane_text,
        "strong_alginment_identity": STRONG_ID_THRESHOLD,
        "moderate_alginment_identity": MODERATE_ID_THRESHOLD,
        "weak_alginment_identity": WEAK_ID_THRESHOLD,
        "strong_hits": counts["strong_hits"],
        "moderate_hits": counts["moderate_hits"],
        "weak_hits": counts["weak_hits"],
        "lowest_hit": get_lowest_hit(pane),
    })

    collect_species_table(pane, driver, report)
    collect_blast_modal(pane, driver, report)
    collect_tree_modal(pane, driver, report)
