"""Fetch species under the given taxon from GBIF API."""

import logging
from functools import cached_property

import pygbif

from src.gbif import api
from src.utils import config
from src.utils.throttle import ENDPOINTS, Throttle

logger = logging.getLogger(__name__)
config = config.Config()

MODULE_NAME = 'GBIF API'

KINGDOM_TAXA = {
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


class GBIFRecord:
    """Wrap a GBIF API record dict with typed attribute access."""

    def __init__(self, data: dict):
        self.data = data
        self.key = data.get('key')
        self.rank = data.get('rank')
        self.status = data.get(
            'status',
            data.get('taxonomicStatus'),
        )
        self.genus_key = data.get('genusKey')
        self.kingdom_key = data.get('kingdomKey')
        self.species_key = data.get('speciesKey')
        self.taxon_id = data.get('taxonID')
        self.is_extinct = data.get('extinct', data.get('isExtinct'))
        self.canonical_name = _get_scientific_name(data)

    def get(self, key, default=None):
        """Delegate to underlying data dict for ad-hoc access."""
        return self.data.get(key, default)

    def __getitem__(self, key):
        return self.data[key]

    def __contains__(self, key):
        return key in self.data

    def to_json(self):
        """Return the original API dict for JSON serialization."""
        return self.data

    def __repr__(self):
        return f"GBIFRecord({self.canonical_name})"


class RANK:
    NONE = 0
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
        return getattr(cls, rank.upper(), cls.NONE)

    @classmethod
    def to_string(cls, rank: int) -> str:
        for name, value in cls.__dict__.items():
            if isinstance(value, int) and value == rank:
                return name.lower()
        return None


class RelatedTaxaGBIF:
    """Fetch taxonomic relatives for a given taxon from GBIF API.

    If GBIF determines that the given taxon is a synonym, the accepted record
    will be set as the `record` for this taxon. The original taxon
    is stored in `from_synonym`, while the key, genus, genus_key, rank and
    canonical_name fields are all taken from the accepted record.
    """

    INCLUDE_EXTINCT = False

    def __init__(self, taxon, classification=None):
        self.classification = (
            classification['gbif_col']
            if classification
            else None
        )
        self.from_synonym = None
        self.taxon = taxon
        self.record = self._get_taxon_record(taxon)
        self.key = self.record.key
        self.genus_key = self.record.genus_key
        self.genus = self.record.get('genus')
        self.rank = RANK.from_string(self.record.rank)
        self.canonical_name = self.record.canonical_name
        self.taxid = None

    def __str__(self):
        return f"{self.__class__.__name__}: {self.taxon} ({self.rank})"

    def __repr__(self):
        return self.__str__()

    def _get_taxon_record(self, taxon):
        kwargs = {
            'q': taxon,
            'limit': 20,
        }
        if kingdom_taxon := KINGDOM_TAXA.get(taxon.lower()):
            kwargs["q"] = kingdom_taxon['canonical_name']
            kwargs['rank'] = kingdom_taxon['rank']
        if self.classification:
            kwargs['higher_taxon_key'] = api.get_usage_key(
                self.classification)
        throttle = Throttle(ENDPOINTS.GBIF_FAST)
        res_name = throttle.with_retry(
            api.name_suggest,
            kwargs=kwargs,
            with_cache=True,
            task_description=f"GBIF name_suggest: {kwargs}",
        )
        for raw_record in res_name:
            record = GBIFRecord(raw_record) if raw_record else None

            if raw_record.get('status') == 'SYNONYM':
                # Replace the synonym record with its accepted name record
                synonym_key = self._get_synonym_key(raw_record)
                canonical_record = throttle.with_retry(
                    pygbif.species.name_usage,
                    kwargs={
                        'key': synonym_key,
                        'limit': 1,
                    },
                    with_cache=True,
                    task_description=(
                        f"GBIF name_usage: synonym_key={synonym_key}"
                    ),
                )
                if canonical_record:
                    logger.info(
                        f"Taxon '{taxon}' is a SYNONYM."
                        " Using accepted name"
                        f" '{_get_scientific_name(canonical_record)}'."
                    )
                    record = GBIFRecord(canonical_record)
                    self.from_synonym = taxon

            if record and self._is_accepted(record):
                if record.taxon_id is None:
                    # /v1/species/suggest (unlike /v1/species/search or
                    # /v1/species/{key}) doesn't return taxonID at all, so
                    # the common non-synonym path needs an extra lookup.
                    record.taxon_id = api.get_col_taxon_id(record.key)
                logger.info(
                    f"Record found for taxon"
                    f" '{taxon}' - rank:{record.rank}"
                    f" genusKey:{record.genus_key}")
                return record

        raise GBIFRecordNotFound(
            f"No GBIF record found for '{taxon}'. Taxonomic records cannot"
            " be retrieved. Please check that this species name is correct.")

    def _is_accepted(self, record):
        if not record:
            return False
        return bool(
            record.status in config.gbif_accepted_status
            and (self.INCLUDE_EXTINCT or record.is_extinct is not True)
            and RANK.from_string(record.rank)
        )

    def _filter_records(self, records):
        wrapped = [
            r if isinstance(r, GBIFRecord) else GBIFRecord(r)
            for r in records
        ]
        return [
            r for r in wrapped
            if self._is_accepted(r)
            and r.canonical_name
        ]

    def _get_synonym_key(self, record):
        if record.get('acceptedKey'):
            return record['acceptedKey']
        for key in (
            'speciesKey',
            'genusKey',
            'familyKey',
            'orderKey',
            'classKey',
            'phylumKey',
            'kingdomKey',
        ):
            if record.get(key):
                return record[key]

    @cached_property
    def relatives(self):
        """Fetch related species with self.genus_key."""
        i = 0
        record_count = 0
        excluded_count = 0
        end_of_records = False
        records = []
        excluded_records = []
        kwargs = {
            'rank': 'species',
            'higherTaxonKey': self.genus_key,
            'datasetKey': api.COL_CHECKLIST_KEY,
            'limit': config.gbif_limit_records,
        }

        previous_first_name = None
        while not end_of_records:
            kwargs['offset'] = i * config.gbif_limit_records
            throttle = Throttle(ENDPOINTS.GBIF_SLOW)
            res = throttle.with_retry(
                pygbif.species.name_lookup,
                kwargs=kwargs,
                with_cache=True,
                task_description=(
                    f"GBIF name_lookup: higherTaxonKey={self.genus_key},"
                    f" offset={kwargs['offset']}"
                ),
            )
            new_records = self._filter_records(res['results'])
            record_count += len(new_records)
            excluded_count += len(res['results']) - len(new_records)
            canonical_names = [
                r.canonical_name for r in new_records
            ]
            excluded_records += [
                r for r in res['results']
                if _get_scientific_name(r) not in canonical_names
            ]
            if i > 5 and new_records:
                first_name = new_records[0].canonical_name
                if first_name == previous_first_name:
                    logger.warning(
                        'GBIF API claims endofRecords=False after >5 requests,'
                        ' but the same canonicalName was returned twice.'
                        ' Exiting early to avoid infinite loop '
                        f' - {len(records)} records have been fetched.'
                        f' Taxon: {self.taxon}, Genus key: {self.genus_key}.'
                    )
                    break
                previous_first_name = first_name
            records += new_records
            end_of_records = res['endOfRecords']
            i += 1

        logger.info(
            f"Fetched {record_count} records for taxon '{self.taxon}'"
            f" (genusKey: {self.genus_key})."
            f" Excluded {excluded_count} records that did not meet criteria."
        )
        if record_count == 0:
            excluded_records_str = '\n'.join([
                _get_scientific_name(r) for r in excluded_records
            ])
            logger.debug(f"Excluded records:\n{excluded_records_str}")

        return records

    @cached_property
    def genus_taxon_id(self):
        """Resolve self.genus_key (a v1 usage key) to its COL taxonID.

        The occurrence API only accepts COL taxonIDs for `genusKey`, not
        v1 usage keys, so this extra lookup is needed before querying
        `for_country()`.
        """
        return api.get_col_taxon_id(self.genus_key)

    def for_country(self, country_code):
        i = 0
        end_of_records = False
        records = []
        while not end_of_records:
            kwargs = {
                'genusKey': self.genus_taxon_id,
                'checklistKey': api.COL_CHECKLIST_KEY,
                'country': country_code,
                'facet': "speciesKey",
                'facetLimit': config.gbif_limit_records,
                'offset': i * config.gbif_limit_records,
                'limit': 1,  # don't need every occurence for each species
            }
            throttle = Throttle(ENDPOINTS.GBIF_FAST)
            res = throttle.with_retry(
                pygbif.occurrences.search,
                kwargs=kwargs,
                with_cache=True,
                task_description=(
                    f"GBIF occurrences.search:"
                    f" genusKey={self.genus_taxon_id},"
                    f" country={country_code},"
                    f" offset={kwargs['offset']}"
                ),
            )
            records += res['results']
            try:
                end_of_records = (
                    len(res['facets'][0]['counts'])
                    < config.gbif_limit_records)
            except (KeyError, IndexError):
                end_of_records = True
            i += 1

        species_facets = res.get("facets", [])
        species_counts = (
            species_facets[0].get("counts", [])
            if species_facets
            else []
        )

        # Retrieve COL taxon IDs for unique species facets
        species_ids = [
            species["name"]
            for species in species_counts
            if species.get("name")
        ]

        return [
            r for r in self.relatives
            if r.taxon_id in species_ids
        ]


def _get_scientific_name(record: dict) -> str:
    """Return either the canonicalName, scientificName or species field."""
    for k in (
        'canonicalName',
        'scientificName',
        'species',
    ):
        if record.get(k):
            return record[k]
    return None
