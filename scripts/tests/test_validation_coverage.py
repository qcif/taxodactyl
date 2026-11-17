"""Test validation of the coverage taxa CSV."""

import csv
import json
import logging
import tempfile
import unittest
from pathlib import Path

from p0_validation_coverage import validate_coverage_taxa

from src.utils.config import Config
from src.utils.errors import MetadataFormatError

logging.disable(logging.CRITICAL)

config = Config()
TEST_DATA_DIR = Path(__file__).parent / 'test-data'
COVERAGE_CSV = TEST_DATA_DIR / 'coverage/coverage.csv'
HEADER = 'taxon,locus,country,classification\n'
MAX_TAXA = 100


class ValidationCoverageTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'out'
        self.out.mkdir()
        self.original = (
            config.output_dir,
            config.inputs.coverage_taxa_csv,
        )
        config.output_dir = self.out
        self.addCleanup(self._restore)

    def _restore(self):
        config.output_dir, config.inputs.coverage_taxa_csv = self.original
        config.__dict__.pop('coverage_rows', None)
        config.__dict__.pop('metadata', None)

    def _validate(self, content: str = None, path: Path = None):
        if path is None:
            path = Path(self.tmp.name) / 'input.csv'
            path.write_text(content)
        config.inputs.coverage_taxa_csv = path
        config.__dict__.pop('coverage_rows', None)
        return validate_coverage_taxa(path)

    def _query_dirs(self):
        return sorted(self.out.glob('query_*'))

    def test_valid_csv_fixture(self):
        rows = self._validate(path=COVERAGE_CSV)
        self.assertEqual(len(rows), 4)
        self.assertEqual(
            [r['taxon'] for r in rows],
            ['Drosophila melanogaster', 'Bactrocera', 'Aphididae',
             'Aphididiae'],
        )

    def test_writes_validated_csv_and_query_dirs(self):
        self._validate(path=COVERAGE_CSV)
        with (self.out / 'coverage.csv').open() as f:
            written = list(csv.DictReader(f))
        self.assertEqual(len(written), 4)
        dirs = self._query_dirs()
        self.assertEqual(len(dirs), 4)
        for ix, (d, row) in enumerate(zip(dirs, written)):
            self.assertTrue(d.name.startswith(f'query_{ix + 1:03}_'))
            title = (d / config.query_title_file).read_text()
            self.assertEqual(title, row['taxon'])

    def test_duplicate_dropped_with_error_file(self):
        rows = self._validate(path=COVERAGE_CSV)
        self.assertEqual(rows[1]['country'], 'Australia')  # first kept
        errs = list((self.out / config.errors_dir).glob('*.json'))
        self.assertEqual(len(errs), 1)
        msg = json.loads(errs[0].read_text())['message']
        self.assertIn('Row 5 duplicates row 2', msg)
        self.assertIn('bactrocera', msg)

    def test_same_taxon_different_locus_kept(self):
        rows = self._validate(
            HEADER + 'Bactrocera,COI,,\nBactrocera,16S,,\n')
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(self._query_dirs()), 2)

    def test_empty_csv(self):
        with self.assertRaises(MetadataFormatError):
            self._validate(HEADER)

    def test_missing_required_columns(self):
        with self.assertRaises(MetadataFormatError):
            self._validate('locus\nCOI\n')
        with self.assertRaises(MetadataFormatError):
            self._validate('taxon\nBactrocera\n')

    def test_optional_columns_may_be_absent(self):
        rows = self._validate('taxon,locus\nBactrocera,COI\n')
        self.assertEqual(rows[0]['country'], '')

    def test_blank_taxon(self):
        with self.assertRaises(MetadataFormatError):
            self._validate(HEADER + ',COI,,\n')

    def test_bad_characters(self):
        for taxon in ('Bactrocera;DROP', 'Bactrocera|Aedes', 'Aedes 123'):
            with self.subTest(taxon=taxon):
                with self.assertRaises(MetadataFormatError):
                    self._validate(HEADER + f'"{taxon}",COI,,\n')

    def test_bad_locus_country_classification(self):
        for line in (
            'Bactrocera,notalocus,,',
            'Bactrocera,COI,Atlantis,',
            'Bactrocera,COI,,minerals',
        ):
            with self.subTest(line=line):
                with self.assertRaises(MetadataFormatError):
                    self._validate(HEADER + line + '\n')

    def test_blank_locus_requires_na(self):
        with self.assertRaises(MetadataFormatError):
            self._validate(HEADER + 'Bactrocera,,,\n')
        rows = self._validate(HEADER + 'Bactrocera,NA,,\n')
        self.assertEqual(len(rows), 1)

    def test_row_number_in_error(self):
        with self.assertRaises(MetadataFormatError) as ctx:
            self._validate(HEADER + 'Aedes,COI,,\nBactrocera,bad,,\n')
        self.assertIn('row 2', str(ctx.exception))

    def test_limit_applies_after_deduplication(self):
        taxa = [f'Taxon{chr(65 + i // 26)}{chr(65 + i % 26)}'
                for i in range(MAX_TAXA)]
        lines = ''.join(f'{t},COI,,\n' for t in taxa)
        rows = self._validate(HEADER + lines + f'{taxa[0].lower()},COI,,\n')
        self.assertEqual(len(rows), MAX_TAXA)

    def test_limit_exceeded(self):
        lines = ''.join(
            f'Taxon{chr(65 + i // 26)}{chr(65 + i % 26)},COI,,\n'
            for i in range(MAX_TAXA + 1)
        )
        with self.assertRaises(MetadataFormatError) as ctx:
            self._validate(HEADER + lines)
        self.assertIn(str(MAX_TAXA), str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
