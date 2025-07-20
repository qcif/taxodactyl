"""Collect and aggregate sources from BLAST/BOLD hits."""

import logging

from src.entrez import genbank
from src.utils import errors

logger = logging.getLogger(__name__)


class BOLDCollectorsSource:
    """Source for BOLD hits that do not have a GB ID."""

    def __init__(self, hit: dict):
        self.bold_id = hit['hit_id']
        self.bold_url = hit['url']
        self.collectors = hit['collectors'].strip().lower()

    def __bool__(self) -> bool:
        return bool(self.collectors)

    def __str__(self) -> str:
        return self.collectors

    def to_json(self) -> dict:
        return {
            'bold_id': self.bold_id,
            'bold_url': self.bold_url,
            'collectors': self.collectors,
            'publications': [],
        }

    def matches(self, other) -> bool:
        """Return True if other has a collectors source that matches self."""
        if not isinstance(other, (BOLDCollectorsSource, str)):
            return False
        return str(self) == str(other)


def sources_per_species(species, hits) -> list[dict]:
    aggregated_sources = {}
    accession_sources = genbank.fetch_sources([
        hit["accession"] for hit in hits
        if hit["accession"]
    ])
    for sp_ix, spec in enumerate(species):
        species_str = spec["species"]
        independent_sources = []
        for hit_ix, hit in enumerate(hits):
            if hit["species"] == species_str:
                if not hit["accession"] and 'collectors' in hit:
                    # It's a BOLD hit without a GB ID
                    source = BOLDCollectorsSource(hit)
                elif hit["accession"] in accession_sources:
                    source = accession_sources[hit["accession"]]
                else:
                    msg = (
                        f"Accession {hit['accession']} not found in GenBank."
                    ) if hit["accession"] else (
                        f"Publications cannot be retrieved for Hit[{hit_ix}]"
                        " as no GenBank accession is provided for this record."
                    )
                    logger.warning(msg)
                    source = None
                    errors.write(
                        errors.LOCATIONS.SOURCE_DIVERSITY_ACCESSION_ERROR,
                        msg,
                        context={
                            "index": hit_ix,
                            "hit_id": hit['hit_id'],
                            "species": species_str,
                            "accession": hit["accession"],
                        },
                    )

                if source is not None:
                    matched = False
                    for j, independent_source in enumerate(
                        independent_sources
                    ):
                        for src in independent_source:
                            if source.matches(src):
                                independent_sources[j].append(source)
                                matched = True
                                break
                    if not matched:
                        independent_sources.append([source])

                hits[hit_ix]["source"] = source

        species[sp_ix]['independent_sources'] = len(independent_sources)
        species[sp_ix]['hit_count'] = hit_ix + 1
        aggregated_sources[species_str] = independent_sources

    return species, hits, aggregated_sources
