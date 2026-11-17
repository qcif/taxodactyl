"""Test rendering of the database coverage mode report."""

import logging
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import p5_db_coverage
from src.coverage import assess_coverage
from src.report import report
from src.utils.config import Config

logging.disable(logging.CRITICAL)

config = Config()
FIXTURE_DIR = Path(__file__).parent / 'test-data/coverage_report'
TIMESTAMP = '20261013 092000'
REPORT_GLOB = 'report_coverage_*.html'
# Fixture rows, in CSV order. The second taxon has no analysis outputs.
TAXA = [
    'Homo sapiens',
    'Bactrocera',
    'Aphididae',
    'Aphididiae',
]
INCOMPLETE_TAXON = 'Bactrocera'
INCOMPLETE_TEXT = 'Analysis did not complete for this taxon'
ROOT_TAXON = 'Fungi'
ROOT_TAXON_ROW = 'Fungi,COI,Australia,fungi\n'
NOT_ASSESSED_HTML = (
    'Database coverage is not assessed for taxa at kingdom or domain rank'
    ' (<em>Fungi</em>), because they are too broad for this analysis to be'
    ' meaningful.'
)
GENERIC_NO_DATA_TEXT = 'an error was encountered during the analysis'
ISSUES_TEXT = 'Issues encountered'


class ReportCoverageTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'out'
        shutil.copytree(FIXTURE_DIR, cls.out)
        (cls.out / config.timestamp_filename).write_text(TIMESTAMP + '\n')
        cls.original = (
            config.output_dir,
            config.inputs.coverage_taxa_csv,
        )
        config.output_dir = cls.out
        config.inputs.coverage_taxa_csv = cls.out / 'coverage.csv'
        config.__dict__.pop('coverage_rows', None)
        config.__dict__.pop('metadata', None)
        report.render_coverage()
        paths = list(cls.out.glob(REPORT_GLOB))
        assert len(paths) == 1, paths
        cls.html = paths[0].read_text()

    @classmethod
    def tearDownClass(cls):
        config.output_dir, config.inputs.coverage_taxa_csv = cls.original
        config.__dict__.pop('coverage_rows', None)
        config.__dict__.pop('metadata', None)
        cls.tmp.cleanup()

    def _rows(self):
        table = self.html[self.html.index('<table class="table tight border'):]
        table = table[:table.index('</table>')]
        body = table[table.index('<tbody>'):]
        return re.findall(r'<tr>.*?</tr>', body, re.DOTALL)

    def test_one_row_per_taxon_in_order(self):
        rows = self._rows()
        self.assertEqual(len(rows), len(TAXA))
        for row, taxon in zip(rows, TAXA):
            self.assertIn(f'<em>{taxon}</em>', row)

    def test_heading_counts_taxa(self):
        self.assertIn(f'Taxa assessed: <code>{len(TAXA)}</code>', self.html)
        self.assertNotIn('Sample ID:', self.html)

    def test_badges_styled_by_flag(self):
        rows = self._rows()
        # Aphididae is a higher taxon: record count, flag NA (secondary)
        self.assertRegex(rows[2], r'badge bg-secondary')
        # Homo sapiens has record counts, and coverage percents
        self.assertRegex(rows[0], r'badge bg-success')
        self.assertRegex(rows[0], r'\d+%')

    def test_incomplete_taxon_fallback_row(self):
        rows = self._rows()
        self.assertIn(INCOMPLETE_TEXT, rows[1])
        self.assertEqual(self.html.count(INCOMPLETE_TEXT), 1)
        self.assertNotIn('data-bs-target="#pmi-', rows[1])

    def test_per_row_locus_and_country(self):
        rows = self._rows()
        self.assertIn('COI', rows[0])
        self.assertIn('Australia', rows[0])
        self.assertIn('COI', rows[2])

    def test_modal_per_completed_taxon(self):
        modal_ids = re.findall(r'id="(pmi-\w+Modal)"', self.html)
        completed = len(TAXA) - 1
        self.assertEqual(len(modal_ids), completed)
        self.assertEqual(len(set(modal_ids)), completed)
        for modal_id in modal_ids:
            self.assertIn(f'data-bs-target="#{modal_id}"', self.html)

    def test_modal_wording_and_js_keys(self):
        self.assertIn('for this taxon in the coverage CSV', self.html)
        self.assertNotIn('in <code>metadata.csv</code>', self.html)
        # Charts are keyed by sample ID, not taxon
        sample_id = config.get_sample_id(0)
        self.assertIn(f"DB_COVERAGE['pmi']['{sample_id}']", self.html)
        self.assertNotIn(
            "DB_COVERAGE['pmi']['Homo sapiens']", self.html)

    def test_inputs_and_flags_modals(self):
        self.assertIn('id="coverageInputModal"', self.html)
        self.assertIn('id="flagsModal"', self.html)
        self.assertIn('id="errorModal"', self.html)


class ReportRootTaxonTestCase(unittest.TestCase):
    """A kingdom-level taxon is shown as not assessed, not as an error."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'out'
        shutil.copytree(FIXTURE_DIR, cls.out)
        (cls.out / config.timestamp_filename).write_text(TIMESTAMP + '\n')
        csv_path = cls.out / 'coverage.csv'
        csv_path.write_text(csv_path.read_text() + ROOT_TAXON_ROW)
        cls.original = (
            config.output_dir,
            config.inputs.coverage_taxa_csv,
        )
        config.output_dir = cls.out
        config.inputs.coverage_taxa_csv = csv_path
        config.__dict__.pop('coverage_rows', None)
        config.__dict__.pop('metadata', None)
        query_dir = config.get_query_dir(len(TAXA))
        query_dir.mkdir(exist_ok=True)
        with (
            patch('src.gbif.api.name_suggest') as mock_suggest,
            patch('src.taxonomy.extract.taxids') as mock_taxids,
        ):
            results, _ = assess_coverage(query_dir, is_bold=False)
        assert not mock_suggest.called and not mock_taxids.called
        p5_db_coverage.write_db_coverage(query_dir, results)
        report.render_coverage()
        paths = list(cls.out.glob(REPORT_GLOB))
        assert len(paths) == 1, paths
        cls.html = paths[0].read_text()
        modal = cls.html[cls.html.index(
            f'Database coverage of Target taxon <em>{ROOT_TAXON}</em>'):]
        end = modal.find('class="modal fade"')
        cls.modal = modal if end < 0 else modal[:end]

    @classmethod
    def tearDownClass(cls):
        config.output_dir, config.inputs.coverage_taxa_csv = cls.original
        config.__dict__.pop('coverage_rows', None)
        config.__dict__.pop('metadata', None)
        cls.tmp.cleanup()

    def test_modal_shows_not_assessed_message(self):
        self.assertIn(NOT_ASSESSED_HTML, ' '.join(self.modal.split()))
        self.assertIn('alert alert-secondary', self.modal)
        self.assertNotIn(GENERIC_NO_DATA_TEXT, self.modal)
        self.assertNotIn(ISSUES_TEXT, self.modal)

    def test_summary_row_is_na(self):
        table = self.html[self.html.index('<table class="table tight border'):]
        table = table[:table.index('</table>')]
        rows = re.findall(r'<tr>.*?</tr>', table, re.DOTALL)
        row = next(r for r in rows if f'<em>{ROOT_TAXON}</em>' in r)
        self.assertNotIn(INCOMPLETE_TEXT, row)
        self.assertIn('btn btn-secondary', row)
        self.assertNotRegex(row, r'bg-(danger|warning|success)')


if __name__ == '__main__':
    unittest.main()
