import json
import logging
import unittest
from pathlib import Path
from unittest.mock import patch

from src.gbif import api
from src.gbif.relatives import (
    GBIFRecord,
    GBIFRecordNotFound,
    RelatedTaxaGBIF,
)

TEST_DATA_DIR = Path(__file__).parent / 'test-data'
GBIF_NAME_LOOKUP_RESPONSE = TEST_DATA_DIR / 'gbif_related_species.json'
GBIF_OCCURRENCE_RESPONSE = TEST_DATA_DIR / 'gbif_related_country.json'

logging.disable(logging.CRITICAL)

# Cheiloxena, resolved live against the COL checklist (see
# scripts/tasks/01-gbif-api-refactor.md).
GENUS_KEY = 291531514       # v1 usage key
GENUS_TAXON_ID = 'MT4JJ'    # COL taxonID


class TestFetchRelatedSpecies(unittest.TestCase):

    @patch('src.utils.cache.get', return_value=None)
    @patch('pygbif.species.name_lookup')
    def test_it_can_fetch_the_correct_relatives(
        self,
        mock_search,
        mock_cache_get,
    ):
        mock_search.return_value = json.loads(
            GBIF_NAME_LOOKUP_RESPONSE.read_text())
        mock_search.__name__ = 'name_lookup'
        taxon = RelatedTaxaGBIF('Cheiloxena aitori')
        self.assertEqual(len(taxon.relatives), 8)
        self.assertEqual(taxon.genus_key, GENUS_KEY)
        mock_search.assert_called_once()

    @patch('src.utils.cache.get', return_value=None)
    @patch('pygbif.species.name_lookup')
    @patch('pygbif.species.name_usage')
    @patch('pygbif.occurrences.search')
    def test_request_country(
        self,
        mock_occurence_search,
        mock_name_usage,
        mock_search,
        mock_cache_get,
    ):
        mock_search.return_value = json.loads(
            GBIF_NAME_LOOKUP_RESPONSE.read_text())
        mock_search.__name__ = 'name_lookup'
        mock_name_usage.__name__ = 'name_usage'
        mock_name_usage.return_value = {'taxonID': GENUS_TAXON_ID}
        mock_occurence_search.return_value = json.loads(
            GBIF_OCCURRENCE_RESPONSE.read_text())
        mock_occurence_search.__name__ = 'search'
        relatives = RelatedTaxaGBIF('Cheiloxena aitori')
        species_for_country = relatives.for_country('AU')

        mock_search.assert_called_once_with(
            rank='species',
            higherTaxonKey=GENUS_KEY,
            datasetKey=api.COL_CHECKLIST_KEY,
            limit=500,
            offset=0,
        )
        occurrence_call_kwargs = mock_occurence_search.call_args.kwargs
        self.assertEqual(
            occurrence_call_kwargs['checklistKey'], api.COL_CHECKLIST_KEY)
        self.assertEqual(
            occurrence_call_kwargs['genusKey'], GENUS_TAXON_ID)
        self.assertIsInstance(occurrence_call_kwargs['genusKey'], str)
        self.assertEqual(len(species_for_country), 5)

    @patch('src.utils.cache.get', return_value=None)
    @patch('src.gbif.api.name_suggest')
    def test_classification_filter(
        self,
        mock_suggest,
        mock_cache_get,
    ):
        """Test RelatedTaxaGBIF with classification parameter.

        Filtering by classification now happens server-side via
        `higherTaxonKey`, so this is a request-shape test: GBIF is trusted
        to return only records under the given classification.
        """
        classification = {
            'gbif_col': 'N',
            'ncbi': {
                'rank': 'kingdom',
                'taxon': 'animalia',
            },
        }
        mock_suggest.__name__ = 'name_suggest'
        mock_suggest.return_value = [
            {
                'canonicalName': 'Prunella',
                'class': 'Aves',
                'classKey': 299343440,
                'family': 'Prunellidae',
                'familyKey': 299375658,
                'genus': 'Prunella',
                'genusKey': 299375662,
                'key': 299375662,
                'kingdom': 'Animalia',
                'kingdomKey': 296374190,
                'order': 'Passeriformes',
                'orderKey': 299358380,
                'parent': 'Prunellidae',
                'parentKey': 299375658,
                'phylum': 'Chordata',
                'phylumKey': 299312263,
                'rank': 'GENUS',
                'scientificName': 'Prunella Vieillot, 1816',
                'status': 'ACCEPTED',
                'synonym': False,
            },
        ]

        with patch(
            'src.gbif.relatives.api.get_usage_key',
            return_value=296374190,
        ) as mock_get_usage_key, patch(
            'src.gbif.relatives.api.get_col_taxon_id',
            return_value='N4KV',
        ):
            taxon = RelatedTaxaGBIF(
                'Prunella',
                classification=classification,
            )

        mock_get_usage_key.assert_called_once_with('N')
        self.assertEqual(taxon.key, 299375662)
        self.assertEqual(taxon.genus_key, 299375662)
        mock_suggest.assert_called_once_with(
            q='Prunella',
            limit=20,
            higher_taxon_key=296374190,
        )

    @patch('src.utils.cache.get', return_value=None)
    @patch('src.gbif.api.name_suggest')
    def test_extinct_records_are_excluded(
        self,
        mock_suggest,
        mock_cache_get,
    ):
        """GBIFRecord.is_extinct must read `extinct`, not `isExtinct`."""
        mock_suggest.__name__ = 'name_suggest'
        mock_suggest.return_value = [
            {
                'key': 1,
                'canonicalName': 'Palaeotherium magnum',
                'genusKey': 1,
                'kingdomKey': 296374190,
                'rank': 'SPECIES',
                'status': 'ACCEPTED',
                'extinct': True,
            },
        ]
        with self.assertRaises(GBIFRecordNotFound):
            RelatedTaxaGBIF('Palaeotherium magnum')

    @patch('src.utils.cache.get', return_value=None)
    @patch('pygbif.species.name_usage')
    @patch('src.gbif.api.name_suggest')
    def test_synonym_resolved_via_accepted_key(
        self,
        mock_suggest,
        mock_name_usage,
        mock_cache_get,
    ):
        """Synonym records with `acceptedKey` should use it directly,
        rather than guessing from speciesKey/genusKey/etc."""
        mock_suggest.__name__ = 'name_suggest'
        mock_suggest.return_value = [
            {
                'key': 100,
                'canonicalName': 'Old name',
                'genusKey': 1,
                'speciesKey': 999,  # would be picked if acceptedKey ignored
                'kingdomKey': 296374190,
                'rank': 'SPECIES',
                'status': 'SYNONYM',
                'acceptedKey': 200,
            },
        ]
        mock_name_usage.__name__ = 'name_usage'
        mock_name_usage.return_value = {
            'key': 200,
            'canonicalName': 'New name',
            'genusKey': 1,
            'kingdomKey': 296374190,
            'rank': 'SPECIES',
            'status': 'ACCEPTED',
            'taxonID': 'ABCDE',
        }
        taxon = RelatedTaxaGBIF('Old name')
        self.assertEqual(taxon.key, 200)
        mock_name_usage.assert_called_once_with(key=200, limit=1)

    @patch('src.utils.cache.get', return_value=None)
    @patch('pygbif.species.name_usage')
    @patch('pygbif.occurrences.search')
    @patch('src.gbif.api.name_suggest')
    def test_for_country_matches_string_facets_to_taxon_id(
        self,
        mock_suggest,
        mock_occurrence_search,
        mock_name_usage,
        mock_cache_get,
    ):
        """Occurrence facets return COL taxon IDs (strings), which must be
        matched against `taxon_id`, not cast to `int` and matched against
        the legacy `species_key`."""
        mock_suggest.__name__ = 'name_suggest'
        mock_suggest.return_value = [
            {
                'key': GENUS_KEY,
                'canonicalName': 'Cheiloxena aitori',
                'genusKey': GENUS_KEY,
                'kingdomKey': 296374190,
                'rank': 'SPECIES',
                'status': 'ACCEPTED',
            },
        ]
        mock_name_usage.__name__ = 'name_usage'
        mock_name_usage.return_value = {'taxonID': GENUS_TAXON_ID}
        mock_occurrence_search.__name__ = 'search'
        mock_occurrence_search.return_value = {
            'results': [],
            'endOfRecords': True,
            'facets': [
                {
                    'field': 'SPECIES_KEY',
                    'counts': [{'name': 'MT4KV', 'count': 3}],
                },
            ],
        }

        taxon = RelatedTaxaGBIF('Cheiloxena aitori')
        taxon.__dict__['relatives'] = [
            GBIFRecord({
                'key': 2,
                'canonicalName': 'Cheiloxena westwoodii',
                'taxonID': 'MT4KV',
                'rank': 'SPECIES',
                'status': 'ACCEPTED',
            }),
            GBIFRecord({
                'key': 3,
                'canonicalName': 'Cheiloxena other',
                'taxonID': 'ZZZZZ',
                'rank': 'SPECIES',
                'status': 'ACCEPTED',
            }),
        ]

        result = taxon.for_country('AU')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].taxon_id, 'MT4KV')


if __name__ == '__main__':
    unittest.main()
