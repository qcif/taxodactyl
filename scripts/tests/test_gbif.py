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

    @patch('pygbif.species.name_lookup')
    def test_it_can_fetch_the_correct_relatives(self, mock_search):
        mock_search.return_value = json.loads(
            GBIF_NAME_LOOKUP_RESPONSE.read_text())
        taxon = RelatedTaxaGBIF('Cheiloxena aitori')
        self.assertEqual(len(taxon.relatives), 8)
        self.assertEqual(taxon.genus_key, 4732783)
        mock_search.assert_called_once()

    @patch('pygbif.species.name_lookup')
    @patch('pygbif.occurrences.search')
    def test_request_country(self, mock_occurence_search, mock_search):
        mock_search.return_value = json.loads(
            GBIF_NAME_LOOKUP_RESPONSE.read_text())
        mock_occurence_search.return_value = json.loads(
            GBIF_OCCURRENCE_RESPONSE.read_text())
        relatives = RelatedTaxaGBIF('Cheiloxena aitori')
        species_for_country = relatives.for_country('AU')
        mock_search.assert_called_once_with(
            rank='species',
            higherTaxonKey=4732783,
            limit=500,
            offset=0,
        )
        self.assertEqual(len(species_for_country), 5)


if __name__ == '__main__':
    unittest.main()
