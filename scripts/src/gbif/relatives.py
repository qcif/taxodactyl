"""Fetch species under the given taxon from GBIF API."""

import logging
from functools import cached_property

import pygbif

from src.utils import config
from src.utils.throttle import ENDPOINTS, Throttle

logger = logging.getLogger(__name__)
config = config.Config()

MODULE_NAME = 'GBIF API'

CANONICAL_TAXA = {
    "fungi": {"rank": "Kingdom", "canonical_name": "fungi"},
    "fungus": {"rank": "Kingdom", "canonical_name": "fungi"},
    "mycota": {"rank": "Kingdom", "canonical_name": "fungi"},
    "plant": {"rank": "Kingdom", "canonical_name": "plantae"},
    "plants": {"rank": "Kingdom", "canonical_name": "plantae"},
    "plantae": {"rank": "Kingdom", "canonical_name": "plantae"},
    "chlorophyta": {"rank": "Kingdom", "canonical_name": "plantae"},
    "animal": {"rank": "Kingdom", "canonical_name": "animalia"},
    "animals": {"rank": "Kingdom", "canonical_name": "animalia"},
    "animalia": {"rank": "Kingdom", "canonical_name": "animalia"},
    "metazoa": {"rank": "Kingdom", "canonical_name": "animalia"},
    "bacteria": {"rank": "Kingdom", "canonical_name": "bacteria"},
    "bacterium": {"rank": "Kingdom", "canonical_name": "bacteria"},
    "archaea": {"rank": "Kingdom", "canonical_name": "archaea"},
    "archaeabacteria": {"rank": "Kingdom", "canonical_name": "archaea"},
    "virus": {"rank": "Kingdom", "canonical_name": "viruses"},
    "viruses": {"rank": "Kingdom", "canonical_name": "viruses"},
    "viroid": {"rank": "Kingdom", "canonical_name": "viruses"},
    "viral": {"rank": "Kingdom", "canonical_name": "viruses"},
    "protozoa": {"rank": "Kingdom", "canonical_name": "protista"},
    "protozoan": {"rank": "Kingdom", "canonical_name": "protista"},
    "protist": {"rank": "Kingdom", "canonical_name": "protista"},
    "protists": {"rank": "Kingdom", "canonical_name": "protista"},
    "protista": {"rank": "Kingdom", "canonical_name": "protista"},
    "chromista": {"rank": "Kingdom", "canonical_name": "chromista"},
}


class GBIFRecordNotFound(Exception):
    pass


class RANK:
    SPECIES = 1
    GENUS = 2
    FAMILY = 3
    ORDER = 4
    CLASS = 5
    PHYLUM = 6
    KINGDOM = 7
    DOMAIN = 8

    @classmethod
    def from_string(cls, rank: str) -> str:
        return getattr(cls, rank.upper(), None)

    @classmethod
    def to_string(cls, rank: int) -> str:
        for name, value in cls.__dict__.items():
            if isinstance(value, int) and value == rank:
                return name.lower()
        return None


class RelatedTaxaGBIF:
    """Fetch taxonomic relatives for a given taxon from GBIF API."""

    INCLUDE_EXTINCT = False

    def __init__(self, taxon):
        self.taxon = taxon
        self.record = self._get_taxon_record(taxon)
        self.key = self.record.get('key')
        self.genus_key = self.record.get('genusKey')
        self.rank = RANK.from_string(self.record.get('rank'))

    def __str__(self):
        return f"{self.__class__.__name__}: {self.taxon} ({self.rank})"

    def __repr__(self):
        return self.__str__()

    def _get_taxon_record(self, taxon):
        kwargs = {
            'q': taxon,
            'limit': 20,
        }
        if canonical_taxon := CANONICAL_TAXA.get(taxon.lower()):
            kwargs["q"] = canonical_taxon['canonical_name']
            kwargs['rank'] = canonical_taxon['rank']
        throttle = Throttle(ENDPOINTS.GBIF_FAST)
        res = throttle.with_retry(
            pygbif.species.name_suggest,
            kwargs=kwargs,
        )
        for record in res:
            if self._is_accepted(record):
                logger.info(f"Record found for taxon"
                            f" '{taxon}' - rank:{record['rank']}"
                            f" genusKey:{record.get('genusKey')}")
                return record
        raise GBIFRecordNotFound(
            f"No GBIF record found for '{taxon}'. Taxonomic records cannot"
            " be retrieved for this species name - please check that this"
            " species name is correct.")

    def _is_accepted(self, record):
        status_key = 'status' if 'status' in record else 'taxonomicStatus'
        return (
            record[status_key] in config.GBIF_ACCEPTED_STATUS
            and (self.INCLUDE_EXTINCT or record.get('isExtinct') is not True)
        )

    def _filter_records(self, records):
        return [
            r for r in records
            if self._is_accepted(r)
            and 'canonicalName' in r
        ]

    @cached_property
    def relatives(self):
        """Fetch related species with self.genus_key."""
        i = 0
        end_of_records = False
        records = []
        kwargs = {
            'rank': 'species',
            'higherTaxonKey': self.genus_key,
            'limit': config.GBIF_LIMIT_RECORDS,
        }

        previous_first_name = None
        while not end_of_records:
            kwargs['offset'] = i * config.GBIF_LIMIT_RECORDS
            throttle = Throttle(ENDPOINTS.GBIF_SLOW)
            res = throttle.with_retry(
                pygbif.species.name_lookup,
                kwargs=kwargs,
            )
            new_records = self._filter_records(res['results'])
            if i > 5:
                first_name = new_records[0]['canonicalName']
                if first_name == previous_first_name:
                    logger.warning(
                        'GBIF API claims endofRecords=False after >5 requests,'
                        ' but the same canonicalName was returned twice.'
                        ' Exiting early to avoid infinite loop '
                        f' - {len(records)} records have been fetched.'
                        f' Taxon: {self.taxon}, Genus key: {self.genus_key}.'
                    )
                previous_first_name = first_name
            records += new_records
            end_of_records = res['endOfRecords']
            i += 1

        return records

    def for_country(self, country_code):
        i = 0
        end_of_records = False
        records = []
        while not end_of_records:
            kwargs = {
                'genusKey': self.genus_key,
                'country': country_code,
                'facet': "speciesKey",
                'facetLimit': config.GBIF_LIMIT_RECORDS,
                'offset': i * config.GBIF_LIMIT_RECORDS,
                'limit': 1,  # don't need every occurence for each species
            }
            throttle = Throttle(ENDPOINTS.GBIF_FAST)
            res = throttle.with_retry(
                pygbif.occurrences.search,
                kwargs=kwargs,
            )
            records += res['results']
            try:
                end_of_records = (
                    len(res['facets'][0]['counts'])
                    < config.GBIF_LIMIT_RECORDS)
            except (KeyError, IndexError):
                end_of_records = True
            i += 1

        species_facets = res.get("facets", [])
        species_counts = (
            species_facets[0].get("counts", [])
            if species_facets
            else []
        )

        # Retrieve species names for unique speciesKeys
        species_keys = []
        for species in species_counts:
            species_key = species.get("name")
            if species_key:
                species_keys.append(int(species_key))

        return [
            r for r in self.relatives
            if r['speciesKey'] in species_keys
        ]
