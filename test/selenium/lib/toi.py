from selenium.webdriver.common.by import By

from lib.report import open_tab


def extract_toi_table_data(toi_pane):
    tables = toi_pane.find_elements(
        By.CSS_SELECTOR,
        "table.table.table-striped"
    )
    data = {
        "row_count": 0,
        "toi": [],
        "match_rank": [],
        "match_taxon": [],
        "match_species": [],
        "match_accession": [],
        "match_identity": [],
    }
    if not tables:
        return data

    toi_rows = tables[0].find_elements(By.CSS_SELECTOR, "tbody tr")
    data["row_count"] = len(toi_rows)

    for row in toi_rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if not cells:
            continue

        data["toi"].append(cells[0].text.strip())
        if len(cells) >= 7:
            data["match_rank"].append(cells[1].text.strip())
            data["match_taxon"].append(cells[2].text.strip())
            data["match_species"].append(cells[3].text.strip())
            data["match_accession"].append(cells[4].text.strip())
            data["match_identity"].append(
                cells[5].text.strip().replace("%", "")
            )

    return data


def collect_toi(driver, report):
    pane = open_tab(
        driver,
        tab_id="taxa-of-interest-tab",
        pane_id="results-taxa-of-interest",
    )
    pane_text = pane.text
    table = extract_toi_table_data(pane)

    report.set_observed("toi_tab", {
        "toi_flag_text": pane_text,
        "toi_outcome": pane_text,
        "toi_reasoning": pane_text,
        "toi_number_of_rows": table["row_count"],
    })

    report.set_observed("toi_table", {
        "toi": table["toi"],
        "match_rank": table["match_rank"],
        "match_taxon": table["match_taxon"],
        "match_species": table["match_species"],
        "match_accession": table["match_accession"],
        "match_identity": table["match_identity"],
    })
