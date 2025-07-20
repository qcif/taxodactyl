"""Functions for getting taxonomic data."""

import pygbif

from src.utils.throttle import ENDPOINTS, Throttle


def fetch_kingdom(phylum: str) -> str:
    """Fetch kingdom for a given phylum from GBIF API."""
    kwargs = {
        'q': phylum,
        'rank': 'phylum',
        'limit': 1,
    }
    throttle = Throttle(ENDPOINTS.GBIF_FAST)
    res = throttle.with_retry(
        pygbif.species.name_suggest,
        kwargs=kwargs,
    )
    if res and len(res) > 0 and 'kingdom' in res[0]:
        return res[0]['kingdom']
    else:
        raise ValueError(f"GBIF returned no kingdom for phylum '{phylum}'")
