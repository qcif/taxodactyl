"""Test that kingdom/domain-level DB coverage targets are not assessed."""

import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.coverage import assess
from src.coverage.targets import fetch_target_taxa
from src.gbif.relatives import RANK
from src.utils import errors
from src.utils.config import Config

logging.disable(logging.CRITICAL)

config = Config()
COVERAGE_CSV = (
    'taxon,locus,country,classification\n'
    'Fungi,COI,Australia,fungi\n'
)
ROOT_TAXON = 'Fungi'
EXPECTED_MESSAGE = (
    'Database coverage is not assessed for taxa at kingdom or domain rank'
    ' (Fungi), because they are too broad for this analysis to be'
    ' meaningful.'
)
DB_COVERAGE_FLAG_IDS = ('5.1', '5.2', '5.3')


def _fake_gbif_target(name, canonical_name, rank):
    record = MagicMock()
    record.taxon = name
    record.canonical_name = canonical_name
    record.rank = rank
    record.key = 1234
    record.from_synonym = None
    record.tie_break = None
    record.genus = canonical_name
    return record


class CoverageModeTestCase(unittest.TestCase):
    """Run against a one-row coverage CSV in a temporary output dir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.original = (
            config.output_dir,
            config.inputs.coverage_taxa_csv,
        )
        config.output_dir = self.out
        config.inputs.coverage_taxa_csv = self.out / 'coverage.csv'
        config.inputs.coverage_taxa_csv.write_text(COVERAGE_CSV)
        self.addCleanup(self._restore)
        self._reset_cache()
        self.query_dir = config.get_query_dir(0)
        self.query_dir.mkdir(parents=True, exist_ok=True)

    def _reset_cache(self):
        config.__dict__.pop('coverage_rows', None)
        config.__dict__.pop('metadata', None)

    def _restore(self):
        config.output_dir, config.inputs.coverage_taxa_csv = self.original
        self._reset_cache()

    def _error_files(self):
        return list((self.query_dir / config.errors_dir).glob('*.json'))

    def _flag_values(self, flag_id):
        path = self.query_dir / f'{flag_id}.flag'
        return [
            (f['target'], f['target_type'], f['value'])
            for f in json.loads(path.read_text())
        ]


class FetchTargetTaxaTestCase(CoverageModeTestCase):

    @patch('src.gbif.api.name_suggest')
    def test_kingdom_name_is_not_looked_up(self, mock_suggest):
        records = fetch_target_taxa([ROOT_TAXON], self.query_dir)
        mock_suggest.assert_not_called()
        self.assertEqual(records.root_taxa, [ROOT_TAXON])
        self.assertEqual(records.all_taxa, {})
        self.assertEqual(records.original_taxa, {})
        self.assertEqual(records.original_to_canonical, {})
        self.assertEqual(self._error_files(), [])

    @patch('src.coverage.targets.RelatedTaxaGBIF')
    def test_root_taxa_kept_in_order_without_duplicates(self, mock_cls):
        mock_cls.side_effect = lambda name, **kw: _fake_gbif_target(
            name, name, RANK.GENUS)
        records = fetch_target_taxa(
            ['Viruses', 'Drosophila', ' fungi ', 'Viruses'],
            self.query_dir,
        )
        self.assertEqual(records.root_taxa, ['Viruses', ' fungi '])
        self.assertEqual(list(records.lower_taxa), ['Drosophila'])
        mock_cls.assert_called_once()

    @patch('src.coverage.targets.RelatedTaxaGBIF')
    def test_name_resolving_to_root_rank_is_not_assessed(self, mock_cls):
        for rank in (RANK.KINGDOM, RANK.DOMAIN, RANK.UNRANKED):
            with self.subTest(rank=rank):
                mock_cls.side_effect = None
                mock_cls.return_value = _fake_gbif_target(
                    'Eumycota', 'Fungi', rank)
                records = fetch_target_taxa(['Eumycota'], self.query_dir)
                self.assertEqual(records.root_taxa, ['Eumycota'])
                self.assertEqual(records.all_taxa, {})
                self.assertEqual(records.higher_taxa, {})
                self.assertEqual(self._error_files(), [])

    @patch('src.coverage.targets.RelatedTaxaGBIF')
    def test_family_to_phylum_targets_still_assessed(self, mock_cls):
        mock_cls.return_value = _fake_gbif_target(
            'Aphididae', 'Aphididae', RANK.FAMILY)
        records = fetch_target_taxa(['Aphididae'], self.query_dir)
        self.assertEqual(records.root_taxa, [])
        self.assertEqual(list(records.higher_taxa), ['Aphididae'])


class AssessRootTaxonTestCase(CoverageModeTestCase):

    @patch('src.coverage.fetch.get_related_coverage')
    @patch('src.coverage.fetch.get_target_coverage')
    @patch('src.taxonomy.extract.taxids')
    @patch('src.gbif.api.name_suggest')
    def test_root_only_query_is_reported_not_assessed(
        self,
        mock_suggest,
        mock_taxids,
        mock_target_cov,
        mock_related_cov,
    ):
        results, is_error = assess.assess_coverage(
            self.query_dir, is_bold=False)
        for mock in (
            mock_suggest,
            mock_taxids,
            mock_target_cov,
            mock_related_cov,
        ):
            mock.assert_not_called()
        self.assertFalse(is_error)
        self.assertEqual(
            results['coverage']['pmi'][ROOT_TAXON],
            {
                'target': None,
                'related': None,
                'country': None,
                'not_assessed': EXPECTED_MESSAGE,
            },
        )
        self.assertEqual(
            results['ncbi_urls'][ROOT_TAXON],
            {'blast': None, 'taxonomy': None},
        )
        for flag_id in DB_COVERAGE_FLAG_IDS:
            self.assertEqual(
                self._flag_values(flag_id),
                [(ROOT_TAXON, 'pmi', 'NA')],
            )
        self.assertEqual(self._error_files(), [])
        self.assertFalse(
            (self.query_dir / config.get_map_filename_for_target(
                ROOT_TAXON)).exists())


class SetFlagsTestCase(CoverageModeTestCase):

    def test_root_taxon_na_while_failed_target_stays_err(self):
        empty = {'target': None, 'related': None, 'country': None}
        coverage = {
            'candidate': {},
            'toi': {'Drosophila': dict(empty)},
            'pmi': {ROOT_TAXON: dict(empty)},
        }
        assess._set_flags(
            coverage, self.query_dir, {}, root_taxa=[ROOT_TAXON])
        for flag_id in DB_COVERAGE_FLAG_IDS:
            values = set(self._flag_values(flag_id))
            self.assertEqual(values, {
                (ROOT_TAXON, 'pmi', 'NA'),
                ('Drosophila', 'toi', 'ERR'),
            })


if __name__ == '__main__':
    unittest.main()


class TieBreakErrorTestCase(CoverageModeTestCase):
    """Duplicate COL records with the same name are noted in the report."""

    @patch('src.coverage.targets.RelatedTaxaGBIF')
    def test_tie_break_writes_one_db_coverage_error(self, mock_cls):
        target = _fake_gbif_target('Drosophila', 'Drosophila', RANK.GENUS)
        target.tie_break = {
            'chosen': (298353264, 'Drosophila Fallén, 1823'),
            'rejected': [(314480147, 'Drosophila Fallen-Nominotypical')],
            'name': 'Drosophila',
            'rank': 'GENUS',
        }
        mock_cls.return_value = target
        fetch_target_taxa(['Drosophila'], self.query_dir)

        error_files = self._error_files()
        self.assertEqual(len(error_files), 1)
        error = json.loads(error_files[0].read_text())
        self.assertEqual(error['location'], errors.LOCATIONS.DB_COVERAGE)
        self.assertEqual(error['context'], {'target': 'Drosophila'})
        self.assertEqual(
            error['message'],
            "GBIF returned 2 accepted records named 'Drosophila' (genus)."
            " Using key 298353264 'Drosophila Fallén, 1823'; ignoring"
            " 314480147 'Drosophila Fallen-Nominotypical'.",
        )

    @patch('src.coverage.targets.RelatedTaxaGBIF')
    def test_no_tie_break_writes_no_error(self, mock_cls):
        mock_cls.return_value = _fake_gbif_target(
            'Drosophila', 'Drosophila', RANK.GENUS)
        fetch_target_taxa(['Drosophila'], self.query_dir)
        self.assertEqual(self._error_files(), [])
