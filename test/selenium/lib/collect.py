"""Orchestrator that runs every per-component collector against a driver.

Populates the observed values on the provided Report in-place. Used by:
- test_reports.py (paired with report.assert_all())
- testkit.py ingest and promote
"""

from lib.sample_metadata import InputSequenceModalCollector
from lib.overview import OverviewCollector
from lib.candidate import CandidateTabCollector
from lib.database_coverage import DatabaseCoverageCollector
from lib.toi import ToiTabCollector


COLLECTORS = (
    InputSequenceModalCollector,
    OverviewCollector,
    CandidateTabCollector,
    DatabaseCoverageCollector,
    ToiTabCollector,
)


def collect_all(driver, report):
    for cls in COLLECTORS:
        cls().collect(driver, report)
