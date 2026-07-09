from selenium.webdriver.common.by import By

from lib.report import (
    TabCollector,
    extract_flag_badge,
    extract_labelled_paragraph,
)


TOI_TAB_ID = "taxa-of-interest-tab"
TOI_PANE_ID = "results-taxa-of-interest"


def _toi_table_rows(pane):
    tables = pane.find_elements(
        By.CSS_SELECTOR, "table.table.table-striped")
    if not tables:
        return []
    return tables[0].find_elements(By.CSS_SELECTOR, "tbody tr")


class ToiTabCollector(TabCollector):
    component_id = "toi_tab"
    tab_id = TOI_TAB_ID
    pane_id = TOI_PANE_ID

    def collect(self, driver, report):
        pane = self._open(driver)
        report.set_observed(self.component_id, self._collect_dict(pane))
        ToiTableCollector().collect_from(pane, report)

    def _extract_toi_flag_text(self, pane):
        return extract_flag_badge(pane)

    def _extract_toi_outcome(self, pane):
        return extract_labelled_paragraph(pane, "Outcome")

    def _extract_toi_reasoning(self, pane):
        return extract_labelled_paragraph(pane, "Reasoning")

    def _extract_toi_number_of_rows(self, pane):
        return len(_toi_table_rows(pane))


class ToiTableCollector:
    component_id = "toi_table"

    def collect_from(self, pane, report):
        cols = {
            "toi": [], "match_rank": [], "match_taxon": [],
            "match_species": [], "match_accession": [], "match_identity": [],
        }
        for row in _toi_table_rows(pane):
            cells = row.find_elements(By.TAG_NAME, "td")
            if not cells:
                continue
            cols["toi"].append(cells[0].text.strip())
            if len(cells) >= 7:
                cols["match_rank"].append(cells[1].text.strip())
                cols["match_taxon"].append(cells[2].text.strip())
                cols["match_species"].append(cells[3].text.strip())
                cols["match_accession"].append(cells[4].text.strip())
                cols["match_identity"].append(
                    cells[5].text.strip().replace("%", "")
                )
        report.set_observed(self.component_id, cols)
