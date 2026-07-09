"""Orchestrator that runs every per-component collector against a driver.

Populates the observed values on the provided Report in-place. Used by:
- test_reports.py (paired with report.assert_all())
- testkit.py ingest and promote
"""

from lib.sample_metadata import collect_sample_metadata
from lib.overview import collect_overview
from lib.candidate import collect_candidate
from lib.database_coverage import collect_database_coverage
from lib.toi import collect_toi


def collect_all(driver, report):
    collect_sample_metadata(driver, report)
    collect_overview(driver, report)
    collect_candidate(driver, report)
    collect_database_coverage(driver, report)
    collect_toi(driver, report)
