from dataclasses import dataclass, field, fields
from utils import open_tab
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Iterable, List, Tuple
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement


WAIT_TIMEOUT = 10


@dataclass
class SpeciesData:
    species: List[str] = field(default_factory=list)
    no_of_hits: List[str] = field(default_factory=list)
    top_identity: List[str] = field(default_factory=list)
    median_identity: List[str] = field(default_factory=list)
    min_identity: List[str] = field(default_factory=list)
    top_e_value: List[str] = field(default_factory=list)


@dataclass
class PublicationModalRow:
    title: str
    source: str
    source_count: str


@dataclass
class PublicationModalData:
    title: List[str] = field(default_factory=list)
    source: List[str] = field(default_factory=list)
    source_count: List[str] = field(default_factory=list)


@dataclass
class BlastModalData:
    title: str
    rank: str
    accession: str
    subject: str
    length: str
    identity: str
    bitscore: str
    evalue: str
    coverage: str
    alignment_text: bool
    char_more_than_10: bool
    domain: str
    kingdom: str
    phylum: str
    class_: str
    order: str
    family: str
    genus: str
    species: str


@dataclass
class HomologyModalData:
    title: str
    min_node: int


def strip_percent(text):
    return text.strip().replace("%", "")


def merge_modal_data(
    target,
    current,
    stringify_keys: Iterable[str] = (),
) -> None:
    """
    Merge a single modal's data into a target dataclass of lists.

    Each field in `current` is appended to the corresponding list field in
    `target`. If a field name is in `stringify_keys`, its value is converted
    to a string before appending.
    """
    for f in fields(current):
        key = f.name
        value = getattr(current, key)
        getattr(target, key).append(str(value) if key in stringify_keys else value)


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


def collect_species_and_modal_data(
    candidate_pane: WebElement,
    driver: WebDriver
) -> Tuple[SpeciesData, PublicationModalData]:
    species_table = candidate_pane.find_element(
        By.CSS_SELECTOR, "table.table.table-striped.freeze-header.sortable"
    )
    rows = species_table.find_elements(By.CSS_SELECTOR, "tbody tr")

    species_data = SpeciesData()
    publication_modal_data = PublicationModalData()

    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 8:
            continue

        species_data.species.append(cells[0].text.strip())
        species_data.no_of_hits.append(cells[1].text.strip())
        species_data.top_identity.append(strip_percent(cells[2].text))
        species_data.median_identity.append(strip_percent(cells[3].text))
        species_data.min_identity.append(strip_percent(cells[4].text))
        species_data.top_e_value.append(cells[5].text.strip())

        merge_modal_data(
            publication_modal_data,
            collect_publication_modal_data(cells, driver),
        )

    return species_data, publication_modal_data


def collect_publication_modal_data(
    cells: list[WebElement],
    driver: WebDriver
) -> PublicationModalRow:
    modal = open_modal_from_button(driver, cells[-1].find_element(
        By.TAG_NAME, "button"),
        attr="onclick")

    row = PublicationModalRow(
        title=text(modal, By.CSS_SELECTOR, "h5.modal-title"),
        source=text(modal, By.CSS_SELECTOR, "p.lead.px-3.fw-bold"),
        source_count=str(len(modal.find_elements(
            By.CSS_SELECTOR, "div.source"))),
    )

    close_modal(modal, driver)
    return row


def collect_blast_modal_data(
    candidate_pane: WebElement,
    driver: WebDriver
) -> BlastModalData:
    button = candidate_pane.find_element(
        By.CSS_SELECTOR,
        'button[data-bs-target="#blastHitsModal"]'
    )
    modal = open_modal_from_button(driver, button, attr="data-bs-target")

    first_row = modal.find_element(By.CSS_SELECTOR, "tbody tr")
    cells = first_row.find_elements(By.TAG_NAME, "td")
    taxonomy_text = modal.text

    data = BlastModalData(
        title=text(modal, By.CSS_SELECTOR, "h5.modal-title"),
        rank=cells[0].text.strip(),
        accession=cells[1].text.strip(),
        subject=cells[2].text.strip(),
        length=cells[3].text.strip(),
        identity=strip_percent(cells[4].text),
        bitscore=cells[5].text.strip(),
        evalue=cells[6].text.strip(),
        coverage=strip_percent(cells[7].text),
        alignment_text="Sequence alignment" in taxonomy_text,
        char_more_than_10=len(cells[2].text.strip()) > 10,
        domain=extract_taxonomy_value(modal, "Domain"),
        kingdom=extract_taxonomy_value(modal, "Kingdom"),
        phylum=extract_taxonomy_value(modal, "Phylum"),
        class_=extract_taxonomy_value(modal, "Class"),
        order=extract_taxonomy_value(modal, "Order"),
        family=extract_taxonomy_value(modal, "Family"),
        genus=extract_taxonomy_value(modal, "Genus"),
        species=extract_taxonomy_value(modal, "Species"),
    )

    close_modal(modal, driver)
    return data


def collect_homology_modal_data(
    candidate_pane: WebElement,
    driver: WebDriver
) -> HomologyModalData | None:
    buttons = candidate_pane.find_elements(
        By.CSS_SELECTOR,
        'button[data-bs-target="#distanceTreeModal"]'
    )

    if not buttons:
        return None

    modal = open_modal_from_button(driver, buttons[0], attr="data-bs-target")

    data = HomologyModalData(
        title=text(modal, By.CSS_SELECTOR, "h5.modal-title"),
        min_node=driver.execute_script(
            "return Object.keys(leafNames).length;"),
    )
    close_modal(modal, driver)
    return data


def assert_static_content(candidate_pane, component):
    pane_text = candidate_pane.text
    component.tab_title.assert_value(pane_text)
    component.candidate_flag_text.assert_value(pane_text)
    component.strong_alginment_identity.assert_value(98.5)
    component.moderate_alginment_identity.assert_value(93.5)
    component.weak_alginment_identity.assert_value(93.5)


def assert_classification_table(candidate_pane, component):
    table = candidate_pane.find_element(
        By.CSS_SELECTOR,
        "table.table.tight.font-small")
    target_map = {
        "STRONG MATCH": component.strong_hits,
        "MODERATE MATCH": component.moderate_hits,
        "NO MATCH": component.weak_hits,
        "WEAK MATCH": component.weak_hits,
    }

    for row in table.find_elements(By.TAG_NAME, "tr"):
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 4:
            continue

        classification = cells[0].text.strip().upper()
        target = target_map.get(classification)
        if target:
            target.assert_value(int(cells[2].text.strip()))


def assert_species_table(table, species_data: SpeciesData):
    table.species.assert_value(species_data.species)
    table.no_of_hits.assert_value(species_data.no_of_hits)
    table.top_identity.assert_value(species_data.top_identity)
    table.median_identity.assert_value(species_data.median_identity)
    table.min_identity.assert_value(species_data.min_identity)
    table.top_e_value.assert_value(species_data.top_e_value)


def assert_publication_modal_data(pub_modal, modal_data: PublicationModalData):
    for i, candidate in enumerate(pub_modal.candidates):
        candidate.title.assert_value([modal_data.title[i]])
        candidate.source.assert_value([modal_data.source[i]])
        candidate.count.assert_value([modal_data.source_count[i]])


def assert_blast_modal_data(blast_modal, blast_data: BlastModalData):
    blast_modal.title.assert_value(blast_data.title)
    blast_modal.rank.assert_value(int(blast_data.rank))
    blast_modal.accession.assert_value(blast_data.accession)
    blast_modal.subject.assert_value(blast_data.subject)
    blast_modal.length.assert_value(int(blast_data.length))
    blast_modal.identity.assert_value(float(blast_data.identity))
    blast_modal.bitscore.assert_value(float(blast_data.bitscore))
    blast_modal.evalue.assert_value(blast_data.evalue)
    blast_modal.coverage.assert_value(float(blast_data.coverage))
    blast_modal.alignment_text.assert_value(str(
        blast_data.alignment_text).upper())
    blast_modal.char_more_than_10.assert_value(str(
        blast_data.char_more_than_10).upper())
    blast_modal.domain.assert_value(blast_data.domain)
    blast_modal.kingdom.assert_value(blast_data.kingdom)
    blast_modal.phylum.assert_value(blast_data.phylum)
    getattr(blast_modal, 'class').assert_value(blast_data.class_)
    blast_modal.order.assert_value(blast_data.order)
    blast_modal.family.assert_value(blast_data.family)
    blast_modal.genus.assert_value(blast_data.genus)
    blast_modal.species.assert_value(blast_data.species)


def assert_homology_modal_data(tree_modal, homology_data: HomologyModalData):
    tree_modal.title.assert_value(homology_data.title)
    tree_modal.min_node.assert_value(homology_data.min_node)


def run_candidate_tab(driver, report):
    candidate_pane = open_tab(
        driver,
        tab_id="candidate-species-tab",
        pane_id="results-candidate-species",
    )
    component = report.candidate_tab

    assert_static_content(candidate_pane, component)
    assert_classification_table(candidate_pane, component)
    component.lowest_hit.assert_value(get_lowest_hit(candidate_pane))

    species_data, publication_modal_data = (
        collect_species_and_modal_data(candidate_pane, driver)
    )

    assert_species_table(report.candidate_tab_table, species_data)
    assert_publication_modal_data(
        report.publication_modal, publication_modal_data)

    blast_data = collect_blast_modal_data(candidate_pane, driver)
    assert_blast_modal_data(report.blast_modal, blast_data)

    homology_data = collect_homology_modal_data(candidate_pane, driver)
    if homology_data:
        assert_homology_modal_data(report.tree_modal, homology_data)
