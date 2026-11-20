"""Test DB coverage target resolution: root targets (not assessed),
duplicate-name tie-breaks and targets missing from COL.
"""

import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.coverage import assess
from src.coverage.targets import fetch_target_taxa
from src.gbif.relatives import RANK, GBIFRecordNotFound
from src.taxonomy.extract import TaxonLineage
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

COL_MISSING_TARGET = 'Vitivirus GVL'
COL_MISSING_TAXID = '2956654'
COL_MISSING_CSV = (
    'taxon,locus,country,classification\n'
    f'{COL_MISSING_TARGET},,Australia,\n'
)
NCBI_GENUS = 'Vitivirus'
NCBI_LINEAGE = TaxonLineage([
    COL_MISSING_TAXID,
    f'Viruses;Riboviria;Tymovirales;Betaflexiviridae;{NCBI_GENUS};'
    f'{COL_MISSING_TARGET}',
    'superkingdom;clade;order;family;genus;species',
])
RELATED_SPECIES = {
    # species -> (taxid, GenBank count)
    'Vitivirus alphavitis': ('101', 12),
    'Vitivirus betavitis': ('102', 3),
    'Vitivirus gammavitis': ('103', 0),
}
IN_COUNTRY_SPECIES = ['Vitivirus alphavitis', 'Vitivirus gammavitis']
TARGET_COUNT = 230
GENUS_COL_KEY = 338017750


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

    coverage_csv = COVERAGE_CSV

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
        config.inputs.coverage_taxa_csv.write_text(self.coverage_csv)
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


def _fake_col_genus(name, rank=RANK.GENUS):
    record = _fake_gbif_target(name, name, rank)
    record.key = GENUS_COL_KEY
    record.relatives = []
    for species in RELATED_SPECIES:
        relative = MagicMock()
        relative.canonical_name = species
        record.relatives.append(relative)
    record.for_country.return_value = [
        r for r in record.relatives
        if r.canonical_name in IN_COUNTRY_SPECIES
    ]
    return record


def _fake_taxids(names, classification=None):
    known = {
        COL_MISSING_TARGET: COL_MISSING_TAXID,
        **{name: taxid for name, (taxid, _) in RELATED_SPECIES.items()},
    }
    return {name: known.get(name) for name in names}


def _fake_gb_count(locus, taxid, count=True):
    counts = {
        COL_MISSING_TAXID: TARGET_COUNT,
        **{taxid: n for taxid, n in RELATED_SPECIES.values()},
    }
    return counts[taxid]


@patch('src.coverage.fetch.genbank.fetch_gb_records',
       side_effect=_fake_gb_count)
@patch('src.taxonomy.extract.lineages',
       return_value={COL_MISSING_TAXID: NCBI_LINEAGE})
@patch('src.taxonomy.extract.taxids', side_effect=_fake_taxids)
@patch('src.coverage.targets.RelatedTaxaGBIF')
class ColMissingTargetTestCase(CoverageModeTestCase):
    """Targets missing from COL are assessed through NCBI (P5-012)."""

    coverage_csv = COL_MISSING_CSV

    def _set_col(self, mock_cls, genus_record=None):
        """COL has no record for the target; `genus_record` for its genus."""
        def lookup(name, **kwargs):
            if name == COL_MISSING_TARGET or genus_record is None:
                raise GBIFRecordNotFound(
                    f"'{name}' is not in the Catalogue of Life (COL)"
                    " taxonomy used by GBIF.")
            return genus_record
        mock_cls.side_effect = lookup

    def _errors(self, location=None):
        found = [
            json.loads(path.read_text())
            for path in self._error_files()
        ]
        return [
            e for e in found
            if location is None or e['location'] == location
        ]

    def _assess(self, is_bold=False):
        results, _ = assess.assess_coverage(self.query_dir, is_bold=is_bold)
        return results

    def test_target_resolved_by_ncbi_taxid(self, mock_cls, *mocks):
        self._set_col(mock_cls)
        records = fetch_target_taxa([COL_MISSING_TARGET], self.query_dir)
        target = records.col_missing_taxa[COL_MISSING_TARGET]
        self.assertEqual(target.taxid, COL_MISSING_TAXID)
        self.assertEqual(target.rank, RANK.SPECIES)
        self.assertEqual(target.ncbi_genus, NCBI_GENUS)
        self.assertEqual(records.all_taxa, {})
        self.assertEqual(records.original_taxa, {})

    def test_not_found_error_is_reworded(self, mock_cls, *mocks):
        self._set_col(mock_cls)
        fetch_target_taxa([COL_MISSING_TARGET], self.query_dir)
        [error] = self._errors(errors.LOCATIONS.DB_COVERAGE_NO_GBIF_RECORD)
        self.assertIn('Catalogue of Life (COL)', error['message'])
        self.assertIn(COL_MISSING_TAXID, error['message'])
        self.assertNotIn('could not be evaluated', error['message'])
        self.assertEqual(error['context'], {'target': COL_MISSING_TARGET})

    def test_phase_a_grades_target_count_only(
        self, mock_cls, mock_taxids, mock_lineages, mock_gb,
    ):
        self._set_col(mock_cls)
        results = self._assess()
        mock_gb.assert_called_once()
        self.assertEqual(mock_gb.call_args.args[1], COL_MISSING_TAXID)
        self.assertEqual(
            results['coverage']['pmi'][COL_MISSING_TARGET],
            {'target': TARGET_COUNT, 'related': None, 'country': None},
        )
        self.assertEqual(
            [self._flag_values(f) for f in DB_COVERAGE_FLAG_IDS],
            [
                [(COL_MISSING_TARGET, 'pmi', 'A')],
                [(COL_MISSING_TARGET, 'pmi', 'ERR')],
                [(COL_MISSING_TARGET, 'pmi', 'ERR')],
            ],
        )
        self.assertIn(
            COL_MISSING_TAXID,
            results['ncbi_urls'][COL_MISSING_TARGET]['taxonomy'],
        )
        self.assertEqual(
            self._errors(errors.LOCATIONS.DB_COVERAGE_RELATED), [])
        [info] = self._errors(errors.LOCATIONS.DB_COVERAGE)
        self.assertIn(
            f"its NCBI genus '{NCBI_GENUS}' is not in COL", info['message'])
        self.assertTrue(
            (self.query_dir / config.get_map_filename_for_target(
                COL_MISSING_TARGET)).exists())

    def test_no_taxid_makes_no_entrez_query(
        self, mock_cls, mock_taxids, mock_lineages, mock_gb,
    ):
        self._set_col(mock_cls)
        mock_taxids.side_effect = lambda names, **kw: {
            name: None for name in names}
        results = self._assess()
        mock_gb.assert_not_called()
        mock_lineages.assert_not_called()
        self.assertEqual(
            results['coverage']['pmi'][COL_MISSING_TARGET],
            {'target': None, 'related': None, 'country': None},
        )
        self.assertEqual(
            results['ncbi_urls'][COL_MISSING_TARGET],
            {'blast': None, 'taxonomy': None},
        )
        for flag_id in DB_COVERAGE_FLAG_IDS:
            self.assertEqual(
                self._flag_values(flag_id),
                [(COL_MISSING_TARGET, 'pmi', 'ERR')],
            )
        self.assertEqual(
            len(self._errors(errors.LOCATIONS.DB_COVERAGE_TAXONKIT_ERROR)),
            1,
        )

    def test_phase_b_uses_ncbi_genus_in_col(self, mock_cls, *mocks):
        self._set_col(mock_cls, _fake_col_genus(NCBI_GENUS))
        results = self._assess()
        coverage = results['coverage']['pmi'][COL_MISSING_TARGET]
        self.assertEqual(coverage['target'], TARGET_COUNT)
        self.assertEqual(
            coverage['related'],
            {name: n for name, (_, n) in RELATED_SPECIES.items()},
        )
        self.assertEqual(
            coverage['country'],
            {name: RELATED_SPECIES[name][1] for name in IN_COUNTRY_SPECIES},
        )
        self.assertEqual(coverage['genus'], NCBI_GENUS)
        self.assertEqual(list(results['coverage']['pmi']),
                         [COL_MISSING_TARGET])
        self.assertEqual(
            [self._flag_values(f) for f in DB_COVERAGE_FLAG_IDS],
            [
                [(COL_MISSING_TARGET, 'pmi', 'A')],
                [(COL_MISSING_TARGET, 'pmi', 'B')],  # 2/3 represented
                [(COL_MISSING_TARGET, 'pmi', 'B')],  # gammavitis has 0
            ],
        )
        [info] = self._errors(errors.LOCATIONS.DB_COVERAGE)
        self.assertEqual(
            info['message'],
            f"'{COL_MISSING_TARGET}' is not in COL; related-species checks"
            f" use its NCBI genus '{NCBI_GENUS}' (COL key {GENUS_COL_KEY}).",
        )

    def test_phase_b_rejects_non_genus_col_record(self, mock_cls, *mocks):
        self._set_col(
            mock_cls, _fake_col_genus(NCBI_GENUS, rank=RANK.SPECIES))
        results = self._assess()
        coverage = results['coverage']['pmi'][COL_MISSING_TARGET]
        self.assertEqual(
            coverage,
            {'target': TARGET_COUNT, 'related': None, 'country': None},
        )
        [info] = self._errors(errors.LOCATIONS.DB_COVERAGE)
        self.assertIn('not the same genus', info['message'])

    @patch('src.coverage.fetch.fetch_bold_records_count')
    def test_bold_skips_count_at_unsupported_rank(
        self, mock_bold, mock_cls, mock_taxids, mock_lineages, mock_gb,
    ):
        self._set_col(mock_cls)
        mock_lineages.return_value = {COL_MISSING_TAXID: TaxonLineage([
            COL_MISSING_TAXID,
            f'Viruses;{NCBI_GENUS};{COL_MISSING_TARGET}',
            'superkingdom;genus;no rank',
        ])}
        results = self._assess(is_bold=True)
        mock_bold.assert_not_called()
        mock_gb.assert_not_called()
        self.assertIsNone(
            results['coverage']['pmi'][COL_MISSING_TARGET]['target'])
        self.assertEqual(
            self._flag_values('5.1'),
            [(COL_MISSING_TARGET, 'pmi', 'ERR')],
        )
        messages = [
            e['message'] for e in self._errors(errors.LOCATIONS.DB_COVERAGE)
        ]
        self.assertTrue(any(
            'BOLD record counts are not available' in m for m in messages))


NEAR_MISS_TARGET = 'Grapevine virus'
NEAR_MISS_COL_NAME = 'Grapevine virus A'
NEAR_MISS_TAXID = '2934366'
NEAR_MISS_COUNT = 39
NEAR_MISS_CSV = (
    'taxon,locus,country,classification\n'
    f'{NEAR_MISS_TARGET},,Australia,\n'
)
# NCBI files 'Grapevine virus' under 'unclassified viruses', with no genus
NEAR_MISS_LINEAGE = TaxonLineage([
    NEAR_MISS_TAXID,
    f'Viruses;unclassified viruses;{NEAR_MISS_TARGET}',
    'acellular root;no rank;species',
])


def _near_miss_taxids(names, classification=None):
    known = {
        NEAR_MISS_TARGET: NEAR_MISS_TAXID,
        **{name: taxid for name, (taxid, _) in RELATED_SPECIES.items()},
    }
    return {name: known.get(name) for name in names}


def _near_miss_gb_count(locus, taxid, count=True):
    counts = {
        NEAR_MISS_TAXID: NEAR_MISS_COUNT,
        **{taxid: n for taxid, n in RELATED_SPECIES.values()},
    }
    return counts[taxid]


@patch('src.coverage.fetch.genbank.fetch_gb_records',
       side_effect=_near_miss_gb_count)
@patch('src.taxonomy.extract.lineages',
       return_value={NEAR_MISS_TAXID: NEAR_MISS_LINEAGE})
@patch('src.taxonomy.extract.taxids', side_effect=_near_miss_taxids)
@patch('src.coverage.targets.RelatedTaxaGBIF')
class NearMissColMatchTestCase(ColMissingTargetTestCase):
    """COL suggests a different taxon, but NCBI has the exact name."""

    coverage_csv = NEAR_MISS_CSV

    def _set_col(self, mock_cls, genus_record=None):
        """COL near-misses the target; `genus_record` for 'Vitivirus'."""
        closest = _fake_gbif_target(
            NEAR_MISS_TARGET, NEAR_MISS_COL_NAME, RANK.SPECIES)
        closest.genus = NCBI_GENUS

        def lookup(name, **kwargs):
            if name == NEAR_MISS_TARGET:
                return closest
            if genus_record is None:
                raise GBIFRecordNotFound(f"'{name}' is not in COL.")
            return genus_record
        mock_cls.side_effect = lookup

    def _p5_013_warnings(self):
        return [
            e for e in self._errors(errors.LOCATIONS.DB_COVERAGE)
            if 'first GBIF-accepted name' in e['message']
        ]

    def test_near_miss_with_ncbi_name_is_not_in_col(self, mock_cls, *mocks):
        self._set_col(mock_cls)
        records = fetch_target_taxa([NEAR_MISS_TARGET], self.query_dir)
        target = records.col_missing_taxa[NEAR_MISS_TARGET]
        self.assertEqual(target.taxid, NEAR_MISS_TAXID)
        self.assertEqual(target.closest_col_name, NEAR_MISS_COL_NAME)
        self.assertEqual(target.closest_col_genus, NCBI_GENUS)
        self.assertIsNone(target.ncbi_genus)
        self.assertEqual(records.all_taxa, {})
        self.assertEqual(records.original_to_canonical, {})
        self.assertEqual(self._p5_013_warnings(), [])
        [error] = self._errors(errors.LOCATIONS.DB_COVERAGE_NO_GBIF_RECORD)
        self.assertIn(
            f"its closest COL name, '{NEAR_MISS_COL_NAME}', is a different"
            " taxon", error['message'])
        self.assertIn(NEAR_MISS_TAXID, error['message'])

    def test_near_miss_without_ncbi_name_uses_col_name(
        self, mock_cls, mock_taxids, *mocks,
    ):
        self._set_col(mock_cls)
        mock_taxids.side_effect = lambda names, **kw: {
            name: None for name in names}
        records = fetch_target_taxa([NEAR_MISS_TARGET], self.query_dir)
        self.assertEqual(records.col_missing_taxa, {})
        self.assertEqual(list(records.lower_taxa), [NEAR_MISS_COL_NAME])
        self.assertEqual(len(self._p5_013_warnings()), 1)

    def test_genus_from_closest_col_match(self, mock_cls, mock_taxids,
                                          mock_lineages, mock_gb):
        self._set_col(mock_cls, _fake_col_genus(NCBI_GENUS))
        results = self._assess()
        self.assertEqual(
            [c.args[1] for c in mock_gb.call_args_list
             if c.args[1] == NEAR_MISS_TAXID],
            [NEAR_MISS_TAXID],
        )
        coverage = results['coverage']['pmi'][NEAR_MISS_TARGET]
        self.assertEqual(coverage['target'], NEAR_MISS_COUNT)
        self.assertEqual(coverage['genus'], NCBI_GENUS)
        self.assertEqual(
            coverage['related'],
            {name: n for name, (_, n) in RELATED_SPECIES.items()},
        )
        [info] = self._errors(errors.LOCATIONS.DB_COVERAGE)
        self.assertEqual(
            info['message'],
            f"'{NEAR_MISS_TARGET}' is not in COL and NCBI gives it no genus;"
            f" related-species checks use the genus '{NCBI_GENUS}' (COL key"
            f" {GENUS_COL_KEY}) of its closest COL match,"
            f" '{NEAR_MISS_COL_NAME}'.",
        )

    # Inherited cases that assume the target is entirely absent from COL
    # or has an NCBI genus do not apply here.
    test_target_resolved_by_ncbi_taxid = None
    test_not_found_error_is_reworded = None
    test_phase_a_grades_target_count_only = None
    test_no_taxid_makes_no_entrez_query = None
    test_phase_b_uses_ncbi_genus_in_col = None
    test_phase_b_rejects_non_genus_col_record = None
    test_bold_skips_count_at_unsupported_rank = None


if __name__ == '__main__':
    unittest.main()
