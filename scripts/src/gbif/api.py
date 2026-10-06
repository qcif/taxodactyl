"""Shared constants and helpers for querying GBIF against the COL backbone.

GBIF has migrated from the legacy GBIF Backbone Taxonomy
(``d7dddbf4-2cf0-4f39-9b2a-bb099caae36c``) to the Catalogue of Life
eXtended Release (COL) as its default taxonomic backbone. The v1 API
endpoints (``/v1/species/suggest``, ``/v1/species/search``,
``/v1/species/{key}``) still return the same flat schema when queried
against COL via ``datasetKey``/``checklistKey`` - only the key spaces
change (see module docstrings in relatives.py and taxonomy.py).
"""

import pygbif
from pygbif.gbifutils import gbif_GET

from src.utils.throttle import ENDPOINTS, Throttle

COL_CHECKLIST_KEY = '7ddf754f-d193-4cc9-b351-99906754a03b'
GBIF_SUGGEST_URL = 'https://api.gbif.org/v1/species/suggest'


def name_suggest(q=None, rank=None, limit=20, higher_taxon_key=None):
    """Call /v1/species/suggest against the COL checklist.

    pygbif.species.name_suggest documents a `datasetKey` argument but
    drops it before building the request (pygbif 0.6.5, 0.6.6 and
    current master: pygbif/species/name_suggest.py:4,39-40), so results
    come back from every checklist instead of just COL. Upstream issue
    to be filed. Call the endpoint directly until that's fixed.
    """
    args = {
        'q': q,
        'rank': rank,
        'limit': limit,
        'datasetKey': COL_CHECKLIST_KEY,
        'higherTaxonKey': higher_taxon_key,
    }
    return gbif_GET(GBIF_SUGGEST_URL, args)


def get_col_taxon_id(usage_key) -> str:
    """Resolve a v1 usage key to its COL taxonID (cached)."""
    throttle = Throttle(ENDPOINTS.GBIF_FAST)
    record = throttle.with_retry(
        pygbif.species.name_usage,
        kwargs={'key': usage_key},
        with_cache=True,
        task_description=f"GBIF name_usage: key={usage_key}",
    )
    return record.get('taxonID')


def get_usage_key(col_id) -> int:
    """Resolve a COL taxonID to its current v1 usage key (cached).

    The v1 integer key is an internal GBIF ID that may be reassigned
    when GBIF reloads the COL checklist, so it's resolved at runtime
    from the stable COL taxonID rather than stored directly.
    """
    throttle = Throttle(ENDPOINTS.GBIF_FAST)
    res = throttle.with_retry(
        pygbif.species.name_usage,
        kwargs={'datasetKey': COL_CHECKLIST_KEY, 'sourceId': col_id},
        with_cache=True,
        task_description=f"GBIF name_usage: sourceId={col_id}",
    )
    return res['results'][0]['key']
