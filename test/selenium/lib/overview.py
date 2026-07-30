import re

from selenium.webdriver.common.by import By

from lib.report import TabCollector


def get_badge_count(container, label):
    """Extract the integer count from a badge whose text contains `label`."""
    for badge in container.find_elements(By.CSS_SELECTOR, "span.badge"):
        text = badge.text.strip()
        if label.lower() in text.lower():
            match = re.search(r"\d+", text)
            if match:
                return int(match.group())
    return None


def _flag_badges(container) -> list:
    """All 'Flag X' badges within `container`, in DOM order."""
    out = []
    for badge in container.find_elements(By.CSS_SELECTOR, "span.badge"):
        text = badge.text.strip()
        if text.startswith("Flag "):
            out.append(text)
    return out


class OverviewCollector(TabCollector):
    component_id = "overview_tab"
    tab_id = "results-summary-tab"
    pane_id = "results-summary"

    def _extract_conclusion_text(self, pane):
        alerts = pane.find_elements(By.CSS_SELECTOR, "div.alert")
        if not alerts:
            return ""
        strongs = alerts[0].find_elements(By.TAG_NAME, "strong")
        return strongs[0].text.strip() if strongs else ""

    def _extract_species_found(self, pane):
        names = []
        for row in pane.find_elements(By.CSS_SELECTOR, "tbody tr"):
            if not row.is_displayed():
                continue
            cells = row.find_elements(By.TAG_NAME, "td")
            if not cells:
                continue
            name = cells[0].text.strip()
            # Skip empty cells, flag/alert rows (multi-line or contain "Flag ")
            if not name or "\n" in name or name.startswith("Flag "):
                continue
            if name not in names:
                names.append(name)
        return names

    def _extract_toi_row_count(self, pane):
        tbodies = pane.find_elements(By.TAG_NAME, "tbody")
        if not tbodies:
            return 0
        return len(tbodies[-1].find_elements(By.TAG_NAME, "tr"))

    def _extract_toi_green_tick_first_row(self, pane):
        tbodies = pane.find_elements(By.TAG_NAME, "tbody")
        if not tbodies:
            return False
        rows = tbodies[-1].find_elements(By.TAG_NAME, "tr")
        if not rows:
            return False
        cells = rows[0].find_elements(By.TAG_NAME, "td")
        if len(cells) < 2:
            return False
        return bool(cells[1].find_elements(
            By.CSS_SELECTOR, ".text-success svg.bi-check-circle-fill"
        ))

    def _extract_conclusion_flag(self, pane):
        flags = _flag_badges(pane)
        return flags[0] if len(flags) > 0 else ""

    def _extract_preliminary_flag(self, pane):
        flags = _flag_badges(pane)
        return flags[1] if len(flags) > 1 else ""

    def _extract_toi_flag(self, pane):
        flags = _flag_badges(pane)
        return flags[2] if len(flags) > 2 else ""

    def _extract_matching_species_strong(self, pane):
        return get_badge_count(pane, "Strong")

    def _extract_matching_species_moderate(self, pane):
        return get_badge_count(pane, "Moderate")

    def _extract_matching_species_weak(self, pane):
        return get_badge_count(pane, "Weak")
