"""Get records stats from BOLD API.

API Docs: https://v4.boldsystems.org/index.php/resources/api
"""

import logging

import requests

from src.utils.throttle import ENDPOINTS, Throttle

logger = logging.getLogger(__name__)

STATS_URL = "https://v4.boldsystems.org/index.php/API_Public/stats"


def fetch_bold_records_count(taxon: str, rank=None) -> dict:
    """Fetch records for a given taxon from BOLD API.

    TODO: high ranks seem to be useless - or at least very slow response.
    Consider returning NA if rank is higher than family level.

    """
    if rank and rank.lower() not in (
        'species',
        'genus',
        'family',
        'order',
    ):
        logger.warning(
            f'Cannot retrieve BOLD record count for taxon at rank={rank}.'
            'Rank must be at family level or lower.'
        )
        return None

    logger.debug(f'Fetching BOLD record count for taxon "{taxon}" at'
                 f' rank={rank}')
    params = {
        "taxon": taxon,
        "format": "json",
    }
    try:
        throttle = Throttle(ENDPOINTS.BOLD)
        res = throttle.with_retry(
            requests.get,
            args=[STATS_URL],
            kwargs={
                'params': params,
            },
        )
        res.raise_for_status()
        data = res.json()
        if data['records_with_species_name'] == 0:
            logger.debug(f'No BOLD records found for taxon "{taxon}".'
                         ' Returning count=0.')
            return 0
        if rank:
            # Pull out the query taxon at the given rank
            taxa_at_rank = (
                data.get(rank.lower(), {})
                .get('drill_down', {})
                .get('entity', [])
            )
            taxon_records = [
                t for t in taxa_at_rank
                if t['name'].lower() == taxon.lower()
            ]
            if taxon_records:
                count = int(taxon_records[0]['records'])
                logger.debug(f'Returning {rank}-level BOLD record count for'
                             f' taxon "{taxon}": {count}')
                return count
            logger.warning(f'No {rank}-level BOLD record count found for'
                           f' taxon "{taxon}". Returning count=0.')
            return 0

        count = int(data['records_with_species_name'])
        logger.debug(f'Returning generic BOLD record count for'
                     f' taxon "{taxon}": {count}')
        return count

    except requests.RequestException as e:
        logger.error(f"Error fetching records for {taxon}: {e}")
        return None
