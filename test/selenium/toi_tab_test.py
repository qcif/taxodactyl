from selenium.webdriver.common.by import By

from utils import open_tab


def extract_toi_table_data(toi_pane):
    toi_table = toi_pane.find_element(
        By.CSS_SELECTOR,
        "table.table.table-striped"
    )
    toi_rows = toi_table.find_elements(By.CSS_SELECTOR, "tbody tr")

    table_data = {
        "row_count": len(toi_rows),
        "toi": [],
        "match_rank": [],
        "match_taxon": [],
        "match_species": [],
        "match_accession": [],
        "match_identity": [],
    }

    for row in toi_rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 7:
            continue

        table_data["toi"].append(cells[0].text.strip())
        table_data["match_rank"].append(cells[1].text.strip())
        table_data["match_taxon"].append(cells[2].text.strip())
        table_data["match_species"].append(cells[3].text.strip())
        table_data["match_accession"].append(cells[4].text.strip())
        table_data["match_identity"].append(
            cells[5].text.strip().replace("%", "")
        )

    return table_data


def assert_toi_header(component, pane_text):
    component.toi_flag_text.assert_value(pane_text)
    component.toi_outcome.assert_value(pane_text)
    component.toi_reasoning.assert_value(pane_text)


def assert_toi_table(toi_tab, toi_table, table_data):
    """Assert the TOI results table against YAML expectations.

    `toi_tab` holds header-level assertions (e.g. row count), while
    `toi_table` holds per-column assertions where each expected value is a
    list with one entry per table row — the order must match the rendered
    row order. Columns with an identity percentage have the '%' suffix
    stripped before comparison.

    Row-count is checked via `toi_tab.toi_number_of_rows`; rows with fewer
    than 7 cells are silently skipped by `extract_toi_table_data`.
    """
    toi_tab.toi_number_of_rows.assert_value(table_data["row_count"])
    toi_table.toi.assert_value(table_data["toi"])
    toi_table.match_rank.assert_value(table_data["match_rank"])
    toi_table.match_taxon.assert_value(table_data["match_taxon"])
    toi_table.match_species.assert_value(table_data["match_species"])
    toi_table.match_accession.assert_value(table_data["match_accession"])
    toi_table.match_identity.assert_value(table_data["match_identity"])


def run_toi_tab(driver, report):
    toi_pane = open_tab(
        driver,
        tab_id="taxa-of-interest-tab",
        pane_id="results-taxa-of-interest",
    )

    component = report.toi_tab
    pane_text = toi_pane.text

    assert_toi_header(component, pane_text)

    toi_table = report.toi_table
    if not any(toi_table.toi_match.expected or []):
        return

    table_data = extract_toi_table_data(toi_pane)
    assert_toi_table(component, toi_table, table_data)
