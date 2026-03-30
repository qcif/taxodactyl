from utils import open_tab
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Dict, Any, Iterable, List, Tuple
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement


WAIT_TIMEOUT = 10


def strip_percent(text):
    return text.strip().replace("%", "")


def merge_modal_data(
    target: Dict[str, list],
    current: Dict[str, Any],
    stringify_keys: Iterable[str] = (),
) -> None:
    """
    Merge a single modal's data into a target dictionary of lists.

    Each key in `current` is appended to the corresponding list in `target`.
    If a key is in `stringify_keys`, its value is converted to a string.

    Args:
        target: Dictionary where values are lists (accumulated results).
        current: Dictionary containing one modal's data.
        stringify_keys: Keys whose values should be converted to string.

    Returns:
        None (modifies target in place).
    """
    for key, value in current.items():
        target[key].append(str(value) if key in stringify_keys else value)


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


def extract_flag_text(modal, css_selector):
    flag_text = modal.find_element(By.CSS_SELECTOR, css_selector) \
        .find_element(By.TAG_NAME, "strong").text.strip()
    return flag_text.replace("Flag ", "").replace(":", "")


def extract_big_number(modal):
    return int(text(modal, By.CSS_SELECTOR, "div.big-number.alert-success")
               .split()[0])


def extract_plotly_chart_data(modal, driver):
    plot_div = modal.find_element(By.CSS_SELECTOR, "div.js-plotly-plot")
    return driver.execute_script("""
        const plot = arguments[0];
        return {
            x: plot.data[0].x,
            y: plot.data[0].y
        };
    """, plot_div)


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
) -> Tuple[
    Dict[str, List[str]],
    Dict[str, List[str]],
    Dict[str, List[str]]
]:
    """
    Extracts species table data and related modal data from the candidate tab.

    Args:
        candidate_pane : The main container of the candidate tab.
        driver : Selenium WebDriver instance.

    Returns:
        Tuple containing three dictionaries:

        1. species_data:
            {
                "species": List[str],
                "no_of_hits": List[str],
                "top_identity": List[str],
                "median_identity": List[str],
                "min_identity": List[str],
                "top_e_value": List[str],
            }

        2. coverage_modal_data:
            {
                "title": List[str],
                "flag1": List[str],
                "record_count": List[str],
                "record_text": List[str],
                "flag2": List[str],
                "species_count": List[str],
                "species_total": List[str],
                "min_bar_count": List[str],
                "first_bar_species": List[str],
                "first_bar_count": List[str],
                "final_text": List[str],
            }

        3. publication_modal_data:
            {
                "title": List[str],
                "source": List[str],
                "source_count": List[str],
            }
    """

    species_table = candidate_pane.find_element(
        By.CSS_SELECTOR, "table.table.table-striped.freeze-header.sortable"
    )
    rows = species_table.find_elements(By.CSS_SELECTOR, "tbody tr")

    species_data = {
        "species": [],
        "no_of_hits": [],
        "top_identity": [],
        "median_identity": [],
        "min_identity": [],
        "top_e_value": [],
    }

    coverage_modal_data = {
        "title": [],
        "flag1": [],
        "record_count": [],
        "record_text": [],
        "flag2": [],
        "species_count": [],
        "species_total": [],
        "min_bar_count": [],
        "first_bar_species": [],
        "first_bar_count": [],
        "final_text": [],
    }

    publication_modal_data = {
        "title": [],
        "source": [],
        "source_count": [],
    }

    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 8:
            continue

        species_data["species"].append(cells[0].text.strip())
        species_data["no_of_hits"].append(cells[1].text.strip())
        species_data["top_identity"].append(strip_percent(cells[2].text))
        species_data["median_identity"].append(strip_percent(cells[3].text))
        species_data["min_identity"].append(strip_percent(cells[4].text))
        species_data["top_e_value"].append(cells[5].text.strip())

        merge_modal_data(
            coverage_modal_data,
            collect_coverage_modal_data(cells, driver),
            stringify_keys={
                "record_count",
                "min_bar_count",
                "first_bar_count"
                },
        )

        merge_modal_data(
            publication_modal_data,
            collect_publication_modal_data(cells, driver),
        )

    return species_data, coverage_modal_data, publication_modal_data


def collect_coverage_modal_data(
    cells: List[WebElement],
    driver: WebDriver
) -> Dict[str, str]:
    """
    Extracts coverage modal data from a species table row.

    Args:
        cells (List[WebElement]): List of <td> elements from a species
        table row.
            The 7th cell (index 6) contains the button that opens the
            coverage modal.
        driver (WebDriver): Selenium WebDriver instance.

    Returns:
        Dict[str, str]: Extracted modal data including:
            - title
            - flag1 / flag2
            - record_count
            - record_text
            - species_count / species_total
            - min_bar_count
            - first_bar_species
            - first_bar_count
            - final_text
    """
    modal = open_modal_from_button(driver, cells[6].find_element(
        By.TAG_NAME, "button"),
        attr="onclick")

    data = {
        "title": text(modal, By.CSS_SELECTOR, "h5.modal-title"),
        "flag1": extract_flag_text(modal, "p.alert.alert-success"),
        "record_count": extract_big_number(modal),
        "record_text": text(modal, By.CSS_SELECTOR, "p.my-3"),
        "flag2": extract_flag_text(modal, "p.alert.alert-warning"),
        "species_count": text(
            modal,
            By.CSS_SELECTOR,
            "span.small-number span[class^='relatedHasReference']",
        ),
        "species_total": text(
            modal,
            By.CSS_SELECTOR,
            "span.small-number span[class^='relatedCount']",
        ),
    }

    chart_data = extract_plotly_chart_data(modal, driver)
    x_values = [int(v) for v in chart_data["x"]]
    y_values = [str(v).strip() for v in chart_data["y"]]

    data["min_bar_count"] = len(x_values)
    data["first_bar_species"] = y_values[-1]
    data["first_bar_count"] = max(x_values)
    data["final_text"] = modal.find_element(
        By.CSS_SELECTOR,
        "div[id^='dbCovCountry'] p.alert.alert-info"
    ).text.strip()

    close_modal(modal, driver)
    return data


def collect_publication_modal_data(
    cells: list[WebElement],
    driver: WebDriver
) -> Dict[str, str]:
    """
    Extracts publication modal data from a table row.

    Args:
        cells (list[WebElement]): List of <td> elements from a species
        table row.
            The last cell is expected to contain the button that opens
            the publication modal.
        driver (WebDriver): Selenium WebDriver instance.

    Returns:
        Dict[str, str]:
            {
                "title": Modal title text,
                "source": Main publication source text,
                "source_count": Number of source entries (as string),
            }
    """
    modal = open_modal_from_button(driver, cells[-1].find_element(
        By.TAG_NAME, "button"),
        attr="onclick")

    data = {
        "title": text(modal, By.CSS_SELECTOR, "h5.modal-title"),
        "source": text(modal, By.CSS_SELECTOR, "p.lead.px-3.fw-bold"),
        "source_count": str(len(modal.find_elements(
            By.CSS_SELECTOR, "div.source"))),
    }

    close_modal(modal, driver)
    return data


def collect_blast_modal_data(
    candidate_pane: WebElement,
    driver: WebDriver
) -> Dict[str, str]:
    """
    Extracts BLAST modal data from the candidate tab.

    Args:
        candidate_pane (WebElement): Candidate tab container element.
        driver (WebDriver): Selenium WebDriver instance.

    Returns:
        Dict[str, str]: Extracted BLAST result data including:
            - title
            - rank
            - accession
            - subject
            - length
            - identity
            - bitscore
            - evalue
            - coverage
            - alignment_text (bool-like)
            - char_more_than_10 (bool-like)
            - taxonomy fields (domain → species)
    """
    button = candidate_pane.find_element(
        By.CSS_SELECTOR,
        'button[data-bs-target="#blastHitsModal"]'
    )
    modal = open_modal_from_button(driver, button, attr="data-bs-target")

    first_row = modal.find_element(By.CSS_SELECTOR, "tbody tr")
    cells = first_row.find_elements(By.TAG_NAME, "td")
    taxonomy_text = modal.text

    data = {
        "title": text(modal, By.CSS_SELECTOR, "h5.modal-title"),
        "rank": cells[0].text.strip(),
        "accession": cells[1].text.strip(),
        "subject": cells[2].text.strip(),
        "length": cells[3].text.strip(),
        "identity": strip_percent(cells[4].text),
        "bitscore": cells[5].text.strip(),
        "evalue": cells[6].text.strip(),
        "coverage": strip_percent(cells[7].text),
        "alignment_text": "Sequence alignment" in taxonomy_text,
        "char_more_than_10": len(cells[2].text.strip()) > 10,
        "domain": extract_taxonomy_value(modal, "Domain"),
        "kingdom": extract_taxonomy_value(modal, "Kingdom"),
        "phylum": extract_taxonomy_value(modal, "Phylum"),
        "class": extract_taxonomy_value(modal, "Class"),
        "order": extract_taxonomy_value(modal, "Order"),
        "family": extract_taxonomy_value(modal, "Family"),
        "genus": extract_taxonomy_value(modal, "Genus"),
        "species": extract_taxonomy_value(modal, "Species"),
    }

    close_modal(modal, driver)
    return data


def collect_homology_modal_data(
    candidate_pane: WebElement,
    driver: WebDriver
) -> Dict[str, int] | None:
    """
    Extracts homology tree modal data if available.

    Args:
        candidate_pane (WebElement): Candidate tab container element.
        driver (WebDriver): Selenium WebDriver instance.

    Returns:
        Dict[str, int] | None:
            {
                "title": Modal title,
                "min_node": Number of nodes (leaf count)
            }
        Returns None if the homology modal button is not present.
    """
    buttons = candidate_pane.find_elements(
        By.CSS_SELECTOR,
        'button[data-bs-target="#distanceTreeModal"]'
    )

    if not buttons:
        return None

    button = buttons[0]

    modal = open_modal_from_button(driver, button, attr="data-bs-target")

    data = {
        "title": text(modal, By.CSS_SELECTOR, "h5.modal-title"),
        "min_node": driver.execute_script(
            "return Object.keys(leafNames).length;"),
    }
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


def assert_species_table(table, species_data):
    table.species.assert_value(species_data["species"])
    table.no_of_hits.assert_value(species_data["no_of_hits"])
    table.top_identity.assert_value(species_data["top_identity"])
    table.median_identity.assert_value(species_data["median_identity"])
    table.min_identity.assert_value(species_data["min_identity"])
    table.top_e_value.assert_value(species_data["top_e_value"])


def assert_coverage_modal_data(db_coverage, modal_data):
    for i, candidate in enumerate(db_coverage.candidate):
        candidate.title.assert_value([modal_data["title"][i]])
        candidate.flag_text1.assert_value([modal_data["flag1"][i]])
        candidate.record_count.assert_value([modal_data["record_count"][i]])
        candidate.record_text.assert_value([modal_data["record_text"][i]])
        candidate.flag_text2.assert_value([modal_data["flag2"][i]])
        candidate.species_count.assert_value([modal_data["species_count"][i]])
        candidate.species_total.assert_value([modal_data["species_total"][i]])
        for count in modal_data["min_bar_count"]:
            candidate.min_bar_count.assert_value(int(count))
        candidate.first_bar_species.assert_value(
            [modal_data["first_bar_species"][i]])
        candidate.first_bar_count.assert_value(
            [modal_data["first_bar_count"][i]])
        candidate.final_text.assert_value([modal_data["final_text"][i]])


def assert_publication_modal_data(pub_modal, modal_data):
    for i, candidate in enumerate(pub_modal.candidates):
        candidate.title.assert_value([modal_data["title"][i]])
        candidate.source.assert_value([modal_data["source"][i]])
        candidate.count.assert_value([modal_data["source_count"][i]])


def assert_blast_modal_data(blast_modal, blast_data):
    blast_modal.title.assert_value(blast_data["title"])
    blast_modal.rank.assert_value(int(blast_data["rank"]))
    blast_modal.accession.assert_value(blast_data["accession"])
    blast_modal.subject.assert_value(blast_data["subject"])
    blast_modal.length.assert_value(int(blast_data["length"]))
    blast_modal.identity.assert_value(float(blast_data["identity"]))
    blast_modal.bitscore.assert_value(float(blast_data["bitscore"]))
    blast_modal.evalue.assert_value(blast_data["evalue"])
    blast_modal.coverage.assert_value(float(blast_data["coverage"]))
    blast_modal.alignment_text.assert_value(str(
        blast_data["alignment_text"]).upper())
    blast_modal.char_more_than_10.assert_value(str(
        blast_data["char_more_than_10"]).upper())
    blast_modal.domain.assert_value(blast_data["domain"])
    blast_modal.kingdom.assert_value(blast_data["kingdom"])
    blast_modal.phylum.assert_value(blast_data["phylum"])
    getattr(blast_modal, 'class').assert_value(blast_data["class"])
    blast_modal.order.assert_value(blast_data["order"])
    blast_modal.family.assert_value(blast_data["family"])
    blast_modal.genus.assert_value(blast_data["genus"])
    blast_modal.species.assert_value(blast_data["species"])


def assert_homology_modal_data(tree_modal, homology_data):
    tree_modal.title.assert_value(homology_data["title"])
    tree_modal.min_node.assert_value(homology_data["min_node"])


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

    species_data, coverage_modal_data, publication_modal_data = (
        collect_species_and_modal_data(candidate_pane, driver)
    )

    assert_species_table(report.candidate_tab_table, species_data)
    assert_coverage_modal_data(report.database_coverage, coverage_modal_data)
    assert_publication_modal_data(
        report.publication_modal, publication_modal_data)

    blast_data = collect_blast_modal_data(candidate_pane, driver)
    assert_blast_modal_data(report.blast_modal, blast_data)

    homology_data = collect_homology_modal_data(candidate_pane, driver)
    if homology_data:
        assert_homology_modal_data(report.tree_modal, homology_data)
