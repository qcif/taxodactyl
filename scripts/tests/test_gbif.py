import json
import logging
import unittest
from pathlib import Path
from unittest.mock import patch

from src.gbif.relatives import RelatedTaxaGBIF

TEST_DATA_DIR = Path(__file__).parent / 'test-data'
GBIF_NAME_LOOKUP_RESPONSE = TEST_DATA_DIR / 'gbif_related_species.json'
GBIF_OCCURRENCE_RESPONSE = TEST_DATA_DIR / 'gbif_related_country.json'

logging.disable(logging.CRITICAL)


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
        self.assertEqual(taxon.genus_key, 4732783)
        mock_search.assert_called_once()

    @patch('src.utils.cache.get', return_value=None)
    @patch('pygbif.species.name_lookup')
    @patch('pygbif.occurrences.search')
    def test_request_country(
        self,
        mock_occurence_search,
        mock_search,
        mock_cache_get,
    ):
        mock_search.return_value = json.loads(
            GBIF_NAME_LOOKUP_RESPONSE.read_text())
        mock_search.__name__ = 'name_lookup'
        mock_occurence_search.return_value = json.loads(
            GBIF_OCCURRENCE_RESPONSE.read_text())
        mock_occurence_search.__name__ = 'search'
        relatives = RelatedTaxaGBIF('Cheiloxena aitori')
        species_for_country = relatives.for_country('AU')
        mock_search.assert_called_once_with(
            rank='species',
            higherTaxonKey=4732783,
            limit=500,
            offset=0,
        )
        self.assertEqual(len(species_for_country), 5)

    @patch('src.utils.cache.get', return_value=None)
    @patch('pygbif.species.name_suggest')
    def test_classification_filter(
        self,
        mock_suggest,
        mock_cache_get,
    ):
        """Test RelatedTaxaGBIF with classification parameter."""
        classification = {
            'gbif': 1,
            'ncbi': {
                'rank': 'kingdom',
                'taxon': 'animalia',
            },
        }
        mock_suggest.__name__ = 'name_suggest'
        mock_suggest.return_value = [
            {
                'canonicalName': 'Prunella',
                'class': 'Magnoliopsida',
                'classKey': 220,
                'family': 'Lamiaceae',
                'familyKey': 2497,
                'genus': 'Prunella',
                'genusKey': 2926553,
                'key': 2926553,
                'kingdom': 'Plantae',
                'kingdomKey': 6,
                'nameKey': 9275915,
                'nubKey': 2926553,
                'order': 'Lamiales',
                'orderKey': 408,
                'parent': 'Lamiaceae',
                'parentKey': 2497,
                'phylum': 'Tracheophyta',
                'phylumKey': 7707728,
                'rank': 'GENUS',
                'scientificName': 'Prunella L.',
                'status': 'ACCEPTED',
                'synonym': False
            },
            {
                'canonicalName': 'Prunella',
                'class': 'Aves',
                'classKey': 212,
                'family': 'Prunellidae',
                'familyKey': 5273,
                'genus': 'Prunella',
                'genusKey': 2495070,
                'key': 2495070,
                'kingdom': 'Animalia',
                'kingdomKey': 1,
                'nameKey': 9275927,
                'nubKey': 2495070,
                'order': 'Passeriformes',
                'orderKey': 729,
                'parent': 'Prunellidae',
                'parentKey': 5273,
                'phylum': 'Chordata',
                'phylumKey': 44,
                'rank': 'GENUS',
                'scientificName': 'Prunella Vieillot, 1816',
                'status': 'ACCEPTED',
                'synonym': False,
            },
        ]

        taxon = RelatedTaxaGBIF(
            'Prunella',
            classification=classification,
        )

        self.assertEqual(taxon.key, 2495070)
        self.assertEqual(taxon.genus_key, 2495070)
        mock_suggest.assert_called_once_with(
            q='Prunella',
            limit=20,
        )


if __name__ == '__main__':
    unittest.main()
