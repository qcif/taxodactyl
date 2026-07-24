"""Harvest a new integration test case from a completed NF workflow run.

Given a ``.nextflow.log`` (local or ``host:path``) and a target
``--query`` sample id, this subpackage resolves the workflow's outdir +
profile from the log's first line, locates every required file
(published or task-scratch), filters the multi-query files down to just
the chosen query, and writes a case dir under
``scripts/tests/test-data/integration/blast/<name>/``.

Public API (re-exported here so ``from tests.integration.kit.harvest
import …`` keeps working):
"""

from .core import HarvestResult, harvest
from .errors import HarvestError
from .filters import filter_blast_xml, filter_fasta, filter_metadata_csv
from .paths import RemotePath

__all__ = [
    "HarvestError",
    "HarvestResult",
    "RemotePath",
    "filter_blast_xml",
    "filter_fasta",
    "filter_metadata_csv",
    "harvest",
]
