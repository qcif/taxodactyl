#!/usr/bin/env python3

"""Run database coverage mode (p0 -> p5 -> p6) end to end on a set of taxa.

Covers one taxon for each major classification (animal, bacteria, plant,
virus, fungi), against the live GBIF and NCBI APIs. There are no sequences.

Set KEEP_OUTPUTS=1 to retain the output directory after the test run.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PYTHON_ROOT = Path(__file__).parents[2]
INPUT_CSV = (
    PYTHON_ROOT / 'tests/test-data/integration/coverage/coverage.csv')
TEMPDIR_PREFIX = 'integration_test_coverage_'
TIMESTAMP = '20260101 000000'
N_TAXA = 5
FLAG_IDS = ('5.1', '5.2', '5.3')
REQUIRED_ENV_VARS = ('USER_EMAIL', 'NCBI_API_KEY', 'TAXONKIT_DATA')


def print_green(text: str):
    print(f"\033[32m{text}\033[0m")


class IntegrationTestCoverage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        for var in REQUIRED_ENV_VARS:
            if var not in os.environ:
                raise EnvironmentError(
                    f"Environment variable {var} is not set. Please set it"
                    " before running integration tests.")
        cls.wdir = Path(tempfile.mkdtemp(prefix=TEMPDIR_PREFIX))
        (cls.wdir / 'timestamp.txt').write_text(TIMESTAMP + '\n')
        print(f"Output directory: {cls.wdir}")

    @classmethod
    def tearDownClass(cls):
        if os.getenv('KEEP_OUTPUTS') == '1':
            print(f"KEEP_OUTPUTS=1; output retained at: {cls.wdir}")
        else:
            shutil.rmtree(cls.wdir, ignore_errors=True)

    def _run(self, script: str, *args):
        cmd = [sys.executable, str(PYTHON_ROOT / script), *map(str, args)]
        result = subprocess.run(
            cmd,
            cwd=PYTHON_ROOT,
            capture_output=True,
            text=True,
            env={**os.environ, 'PYTHONPATH': str(PYTHON_ROOT)},
        )
        self.assertEqual(
            result.returncode, 0,
            f"{script} failed:\n{result.stdout}\n{result.stderr}")

    def test_coverage_mode(self):
        coverage_csv = self.wdir / 'coverage.csv'

        self._run(
            'p0_validation_coverage.py',
            '--coverage-taxa', INPUT_CSV,
            '--taxdb-dir', os.environ['TAXONKIT_DATA'],
            '--output-dir', self.wdir,
        )
        self.assertTrue(coverage_csv.exists())
        query_dirs = sorted(self.wdir.glob('query_*'))
        self.assertEqual(len(query_dirs), N_TAXA)

        with ThreadPoolExecutor(max_workers=N_TAXA) as pool:
            list(pool.map(
                lambda d: self._run(
                    'p5_db_coverage.py', d,
                    '--coverage-taxa', coverage_csv,
                    '--output-dir', self.wdir,
                ),
                query_dirs,
            ))
        for query_dir in query_dirs:
            with self.subTest(query_dir=query_dir.name):
                json.loads((query_dir / 'db_coverage.json').read_text())
                for flag_id in FLAG_IDS:
                    self.assertTrue((query_dir / f'{flag_id}.flag').exists())

        self._run(
            'p6_report.py',
            '--coverage-taxa', coverage_csv,
            '--output-dir', self.wdir,
        )
        reports = list(self.wdir.glob('report_coverage_*.html'))
        self.assertEqual(len(reports), 1)
        html = reports[0].read_text()
        self.assertNotIn('Analysis did not complete', html)
        print_green(f"\nTest passed. Report: {reports[0]}")


if __name__ == '__main__':
    unittest.main()
