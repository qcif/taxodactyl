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
    _break_tie,
    is_root_taxon,
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
    @patch('src.gbif.api.name_suggest', return_value=[])
    def test_not_found_message_mentions_col(
        self,
        mock_suggest,
        mock_cache_get,
    ):
        """A name with no COL record is explained, not called incorrect."""
        mock_suggest.__name__ = 'name_suggest'
        with self.assertRaises(GBIFRecordNotFound) as ctx:
            RelatedTaxaGBIF('Apple hammerhead viroid')
        message = str(ctx.exception)
        self.assertIn('Catalogue of Life (COL)', message)
        self.assertIn('Apple hammerhead viroid', message)
        self.assertNotIn('check that this species name is correct', message)

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


class TestIsRootTaxon(unittest.TestCase):

    def test_kingdom_domain_and_root_names(self):
        for name in ('Fungi', 'fungi', ' Viruses ', 'metazoa'):
            with self.subTest(name=name):
                self.assertTrue(is_root_taxon(name))

    def test_lower_taxa_and_partial_matches(self):
        for name in ('Drosophila', 'Fungus gnat'):
            with self.subTest(name=name):
                self.assertFalse(is_root_taxon(name))


class TestNameSuggestWrapper(unittest.TestCase):
    """api.name_suggest exists specifically because pygbif silently drops
    `datasetKey` (see api.py docstring), so its request-building must be
    tested directly against the underlying `gbif_GET` call rather than
    through a mock of `name_suggest` itself."""

    @patch('src.gbif.api.gbif_GET')
    def test_name_suggest_builds_expected_request(self, mock_gbif_get):
        api.name_suggest(q='Prunella', limit=20, higher_taxon_key=296374190)

        mock_gbif_get.assert_called_once_with(
            api.GBIF_SUGGEST_URL,
            {
                'q': 'Prunella',
                'rank': None,
                'limit': 20,
                'datasetKey': api.COL_CHECKLIST_KEY,
                'higherTaxonKey': 296374190,
            },
        )


if __name__ == '__main__':
    unittest.main()


# Duplicate accepted COL genus records named 'Drosophila' (issue #351).
DROSOPHILA_KEY = 298353264
DROSOPHILA_EMPTY_KEY = 314480147
DROSOPHILA_SUGGEST = {
    DROSOPHILA_KEY: {
        'key': DROSOPHILA_KEY,
        'scientificName': 'Drosophila Fallén, 1823',
        'canonicalName': 'Drosophila',
        'genusKey': DROSOPHILA_KEY,
        'kingdomKey': 296374190,
        'rank': 'GENUS',
        'status': 'ACCEPTED',
    },
    DROSOPHILA_EMPTY_KEY: {
        'key': DROSOPHILA_EMPTY_KEY,
        'scientificName': 'Drosophila Fallen-Nominotypical',
        'canonicalName': 'Drosophila',
        'genusKey': DROSOPHILA_EMPTY_KEY,
        'kingdomKey': 296374190,
        'rank': 'GENUS',
        'status': 'ACCEPTED',
    },
}
DROSOPHILA_USAGE = {
    DROSOPHILA_KEY: {
        'authorship': 'Fallén, 1823',
        'publishedIn': 'Fallén, C.F. (1823) Geomyzides Sveciae.',
        'taxonID': 'BXWZ6',
    },
    DROSOPHILA_EMPTY_KEY: {
        'authorship': 'Fallen-Nominotypical',
        'publishedIn': None,
        'taxonID': '87FQG',
    },
}


def _record(**data):
    data.setdefault('canonicalName', 'Taxon')
    data.setdefault('rank', 'GENUS')
    data.setdefault('status', 'ACCEPTED')
    return GBIFRecord(data)


@patch('src.utils.cache.get', return_value=None)
@patch('pygbif.species.name_usage')
@patch('src.gbif.api.name_suggest')
class TestDuplicateNameTieBreak(unittest.TestCase):
    """Same-name, same-rank accepted records are chosen deterministically."""

    def _setup(self, mock_suggest, mock_name_usage, suggest_keys):
        mock_suggest.__name__ = 'name_suggest'
        mock_suggest.return_value = [
            dict(DROSOPHILA_SUGGEST[key]) for key in suggest_keys
        ]
        mock_name_usage.__name__ = 'name_usage'
        mock_name_usage.side_effect = (
            lambda key, **kw: dict(DROSOPHILA_USAGE[key]))

    def test_empty_duplicate_listed_first_is_rejected(
        self, mock_suggest, mock_name_usage, mock_cache_get,
    ):
        self._setup(
            mock_suggest, mock_name_usage,
            [DROSOPHILA_EMPTY_KEY, DROSOPHILA_KEY])
        taxon = RelatedTaxaGBIF('Drosophila')
        self.assertEqual(taxon.key, DROSOPHILA_KEY)
        self.assertEqual(taxon.record.taxon_id, 'BXWZ6')
        self.assertIsNone(taxon.from_synonym)
        self.assertEqual(
            taxon.tie_break['chosen'],
            (DROSOPHILA_KEY, 'Drosophila Fallén, 1823'))
        self.assertEqual(
            taxon.tie_break['rejected'],
            [(DROSOPHILA_EMPTY_KEY, 'Drosophila Fallen-Nominotypical')])
        # One enrichment lookup per tied record; none for the taxonID.
        self.assertEqual(mock_name_usage.call_count, 2)

    def test_opposite_order_gives_same_record(
        self, mock_suggest, mock_name_usage, mock_cache_get,
    ):
        self._setup(
            mock_suggest, mock_name_usage,
            [DROSOPHILA_KEY, DROSOPHILA_EMPTY_KEY])
        taxon = RelatedTaxaGBIF('Drosophila')
        self.assertEqual(taxon.key, DROSOPHILA_KEY)
        self.assertEqual(
            taxon.tie_break['rejected'][0][0], DROSOPHILA_EMPTY_KEY)

    def test_single_record_has_no_tie_break(
        self, mock_suggest, mock_name_usage, mock_cache_get,
    ):
        self._setup(mock_suggest, mock_name_usage, [DROSOPHILA_KEY])
        with patch(
            'src.gbif.relatives.api.get_col_taxon_id',
            return_value='BXWZ6',
        ) as mock_taxon_id:
            taxon = RelatedTaxaGBIF('Drosophila')
        self.assertEqual(taxon.key, DROSOPHILA_KEY)
        self.assertIsNone(taxon.tie_break)
        mock_taxon_id.assert_called_once_with(DROSOPHILA_KEY)
        mock_name_usage.assert_not_called()

    def test_same_name_different_rank_is_not_a_tie(
        self, mock_suggest, mock_name_usage, mock_cache_get,
    ):
        self._setup(
            mock_suggest, mock_name_usage,
            [DROSOPHILA_EMPTY_KEY, DROSOPHILA_KEY])
        for rank in ('SUBGENUS', 'SPECIES'):
            with self.subTest(rank=rank):
                mock_suggest.return_value[1]['rank'] = rank
                mock_name_usage.reset_mock()
                with patch(
                    'src.gbif.relatives.api.get_col_taxon_id',
                    return_value='87FQG',
                ):
                    taxon = RelatedTaxaGBIF('Drosophila')
                self.assertEqual(taxon.key, DROSOPHILA_EMPTY_KEY)
                self.assertIsNone(taxon.tie_break)
                mock_name_usage.assert_not_called()


class TestBreakTie(unittest.TestCase):
    """Each tie-break signal works on its own, in priority order."""

    def test_nominotypical_marker_rejected(self):
        a = _record(key=1, scientificName='Taxon Nominotypical, 1900')
        b = _record(key=2, scientificName='Taxon')
        self.assertIs(_break_tie([a, b]), b)

    def test_nominotypical_marker_in_authorship_rejected(self):
        a = _record(key=1, authorship='Smith-NOMINOTYPICAL')
        b = _record(key=2, authorship='Smith')
        self.assertIs(_break_tie([a, b]), b)

    def test_authorship_with_year_preferred(self):
        for authorship in ('Fallén, 1823', '(Linnaeus, 1758)'):
            with self.subTest(authorship=authorship):
                a = _record(key=1, authorship='Fallen')
                b = _record(key=2, authorship=authorship)
                self.assertIs(_break_tie([a, b]), b)

    def test_authorship_year_from_scientific_name(self):
        """suggest has no `authorship`, so derive it from scientificName."""
        a = _record(key=1, scientificName='Taxon Smith')
        b = _record(key=2, scientificName='Taxon Smith, 1900')
        self.assertIs(_break_tie([a, b]), b)

    def test_published_in_preferred(self):
        a = _record(key=1, publishedIn='')
        b = _record(key=2, publishedIn='Smith (1900) Journal.')
        self.assertIs(_break_tie([a, b]), b)

    def test_falls_back_to_suggest_order(self):
        a = _record(key=1, authorship='Smith, 1900')
        b = _record(key=2, authorship='Jones, 1901')
        self.assertIs(_break_tie([a, b]), a)
        self.assertIs(_break_tie([b, a]), b)

    def test_signal_priority(self):
        """Nominotypical outranks year, which outranks publishedIn."""
        nominotypical = _record(
            key=1, authorship='Nominotypical, 1900', publishedIn='X')
        no_year = _record(key=2, authorship='Smith', publishedIn='X')
        year = _record(key=3, authorship='Smith, 1900')
        self.assertIs(_break_tie([nominotypical, no_year]), no_year)
        self.assertIs(_break_tie([no_year, year]), year)
