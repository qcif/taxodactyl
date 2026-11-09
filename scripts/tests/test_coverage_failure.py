"""Test that unexpected failures in coverage mode reach the report."""

import json
import logging
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import p5_db_coverage
from src.report import report
from src.utils.config import Config

logging.disable(logging.CRITICAL)

config = Config()
FIXTURE_DIR = Path(__file__).parent / 'test-data/coverage_report'
TAXON = 'Bactrocera'
QUERY_DIR_NAME = 'query_002_bactrocera_7caedf7c'
BOOM = 'GBIF API exploded'


class CoverageFailureTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'out'
        shutil.copytree(FIXTURE_DIR, self.out)
        (self.out / config.timestamp_filename).write_text(
            '20261013 092000\n')
        self.query_dir = self.out / QUERY_DIR_NAME
        self.original = (
            config.output_dir,
            config.inputs.coverage_taxa_csv,
        )
        config.output_dir = self.out
        config.inputs.coverage_taxa_csv = self.out / 'coverage.csv'
        self.addCleanup(self._restore)
        self._reset_cache()

    def _reset_cache(self):
        config.__dict__.pop('coverage_rows', None)
        config.__dict__.pop('metadata', None)

    def _restore(self):
        config.output_dir, config.inputs.coverage_taxa_csv = self.original
        self._reset_cache()

    def _run_p5(self):
        argv = [
            'p5_db_coverage.py', str(self.query_dir),
            '--coverage-taxa', str(self.out / 'coverage.csv'),
            '--output-dir', str(self.out),
        ]
        with (
            patch.object(sys, 'argv', argv),
            patch.object(
                p5_db_coverage, 'assess_coverage',
                side_effect=RuntimeError(BOOM),
            ),
        ):
            p5_db_coverage.main()

    def test_failure_is_logged_with_err_outputs(self):
        self._run_p5()
        path = self.query_dir / config.db_coverage_json
        data = json.loads(path.read_text())
        self.assertIsNone(data['coverage']['pmi'][TAXON]['target'])
        for flag_id in ('5.1', '5.2', '5.3'):
            path = self.query_dir / f'{flag_id}.flag'
            flags = json.loads(path.read_text())
            self.assertEqual(flags[0]['value'], 'ERR')
        errs = [
            json.loads(p.read_text())
            for p in (self.query_dir / config.errors_dir).glob('*.json')
        ]
        self.assertEqual(len(errs), 1)
        self.assertIn(BOOM, errs[0]['message'])
        self.assertEqual(errs[0]['context'], {'target': TAXON})

    def test_failure_is_shown_in_the_report(self):
        self._run_p5()
        report.render_coverage()
        html = next(self.out.glob('report_coverage_*.html')).read_text()
        self.assertNotIn('Analysis did not complete', html)
        self.assertIn(BOOM, html)

    def test_task_killed_before_any_output(self):
        report.render_coverage()
        html = next(self.out.glob('report_coverage_*.html')).read_text()
        self.assertIn('Analysis did not complete for this taxon.', html)
        self.assertNotIn('see workflow errors', html)
        self.assertIn('No error details were recorded', html)


if __name__ == '__main__':
    unittest.main()
