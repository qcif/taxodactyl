#!/usr/bin/env python3

"""Run all modules against test cases in the test-data/integration directory.

Set SKIP_PASSED_TESTS=1 to skip previously passed tests.
Set KEEP_OUTPUTS=1 to retain output directories after the test run.

Use the ./run_tests.sh script to run this easily with the required environment
variables set.
"""

import gc
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from tests.integration.coverage_assert import assert_matches

PYTHON_ROOT = Path(__file__).parents[2]
TEST_DATA_DIR = PYTHON_ROOT / "tests/test-data"
COMPLETED_TESTS_FILE = "completed_tests.json"
TEMPDIR_PREFIX = "integration_test_"
QUERY_INDEX_FILENAME = 'query.index'  # optional query index to use (0-indexed)
EXPECTED_DIR = "expected"
DB_COVERAGE_FILENAME = "db_coverage.json"


def print_green(text: str):
    print(f"\033[32m{text}\033[0m")


class IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for var in (
            'USER_EMAIL',
            'NCBI_API_KEY',
            'TAXONKIT_DATA',
        ):
            if var not in os.environ:
                raise EnvironmentError(
                    f"Environment variable {var} is not set. "
                    "Please set it before running integration tests. You may"
                    " wish to set this in a venv/bin/activate script or in"
                    " your shell profile.")
        cls.scripts_root = PYTHON_ROOT / "scripts"
        cls.python = PYTHON_ROOT / "venv" / "bin" / "python"
        cls.taxdump_dir = Path.home() / ".taxonkit"
        cls.test_case_root = TEST_DATA_DIR / "integration/blast"

    def setUp(self):
        """Clean up old temp dirs and create a new one."""
        tmp_root = Path(tempfile.gettempdir())
        n_deleted = None
        for n_deleted, old_wdir in enumerate(
            tmp_root.glob(f"{TEMPDIR_PREFIX}*")
        ):
            if old_wdir.is_dir():
                shutil.rmtree(old_wdir, ignore_errors=True)
        if n_deleted:
            print(f"Deleted {n_deleted + 1} old temp directories at"
                  f" {tmp_root}/{TEMPDIR_PREFIX}*")
        self.wdir_root = Path(tempfile.mkdtemp(prefix=TEMPDIR_PREFIX))
        self.completed_tests_file = self.test_case_root / COMPLETED_TESTS_FILE
        self.test_cases = []
        if os.getenv("SKIP_PASSED_TESTS") == "1":
            self.completed_tests = self._read_completed_tests()
            if self.completed_tests:
                print("SKIP_PASSED_TESTS=1 has been set. Skipping previously"
                      " passed tests:")
                for test_case in self.completed_tests:
                    print(f"  - {test_case.name}")
            else:
                print("No previously passed tests found, running all tests.")
        else:
            self.completed_tests = []
            if self.completed_tests_file.exists():
                self.completed_tests_file.unlink()

    def tearDown(self):
        """Check if all tests passed and clean up."""
        if self.completed_tests:
            self._write_completed_tests()
            print("\nCompleted tests:")
            for test_case in self.completed_tests:
                print(f"  - {test_case.name}")

        if self._has_failed_tests():
            print(f"\nTest failed. Wdir has been retained: {self.wdir_root}")
            return

        print_green("\nTest passed.")
        if os.getenv("KEEP_OUTPUTS") == "1":
            print("\nKEEP_OUTPUTS=1; output dirs have been retained at:"
                  f" {self.wdir_root}")
        else:
            print(f"\nCleaning up: {self.wdir_root}")
            shutil.rmtree(self.wdir_root, ignore_errors=True)

    def _has_failed_tests(self):
        n_test_cases = (
            1 if os.getenv("RUN_TEST_CASE")
            else len(self.test_cases)
        )
        if len(self.completed_tests) != n_test_cases:
            return True
        return False

    def _read_completed_tests(self):
        """Read completed test cases from a file."""
        if not self.completed_tests_file.exists():
            return []

        with open(self.completed_tests_file, 'r') as f:
            case_names = json.load(f)
        return [
            self.test_case_root / name
            for name in case_names
        ]

    def _write_completed_tests(self):
        """Write completed test cases to a file."""
        with open(self.completed_tests_file, 'w') as f:
            case_names = [
                test_case.name
                for test_case in self.completed_tests
            ]
            json.dump(case_names, f, indent=2)
        print(f"Completed tests written to: {self.completed_tests_file}")

    def _assert_db_coverage(self, test_case: Path, query_dir: Path) -> None:
        """Compare produced db_coverage.json against a case fixture, if any.

        Rollout is incremental: cases without an ``expected/db_coverage.json``
        fixture skip cleanly with a log line.
        """
        fixture_path = test_case / EXPECTED_DIR / DB_COVERAGE_FILENAME
        if not fixture_path.exists():
            print(
                f"Test case {test_case.name}: no {EXPECTED_DIR}/"
                f"{DB_COVERAGE_FILENAME} fixture — skipping db_coverage"
                " assertion."
            )
            return
        actual_path = query_dir / DB_COVERAGE_FILENAME
        self.assertTrue(
            actual_path.exists(),
            f"Expected {actual_path} to exist after P5.",
        )
        with open(fixture_path) as f:
            expected = json.load(f)
        with open(actual_path) as f:
            actual = json.load(f)
        assert_matches(expected, actual)
        print_green(
            f"Test case {test_case.name}: db_coverage.json matches fixture."
        )

    def prepare_working_dir(self, test_case: Path) -> Path:
        """Copy test case files into a fresh working directory"""
        wdir = self.wdir_root / test_case.name
        shutil.copytree(test_case, wdir)
        return wdir

    def create_test_config(self, wdir: Path) -> Path:
        """Create a test-specific config file with correct file paths"""
        import yaml
        # Load base integration test config
        base_config_path = TEST_DATA_DIR / "test-config.yml"
        with open(base_config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        # Set test-specific file paths
        config_data['inputs']['query_fasta'] = str(wdir / "query.fasta")
        config_data['inputs']['metadata_csv'] = str(wdir / "metadata.csv")
        # Write test-specific config file
        test_config_path = wdir / "test_config.yml"
        with open(test_config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)
        return test_config_path

    def patch_and_run(self, module_name, patched_args, config_file=None):
        mock_args = Namespace(**patched_args)
        module_path = f"scripts.{module_name}"
        # Mock sys.argv BEFORE importing the module
        original_argv = sys.argv.copy()
        if config_file:
            sys.argv = ['script.py', '-c', str(config_file)]
        else:
            sys.argv = ['script.py']
        # Reset Config singleton before importing
        if 'src.utils.config' in sys.modules:
            from src.utils.config import Config
            Config._instance = None
            Config._initialized = False
        try:
            # Now import the module (this will create Config with correct argv)
            module = importlib.import_module(module_path)
            with patch.object(
                module,
                "_parse_args",
                return_value=mock_args,
            ):
                module.main()
        finally:
            # Restore original sys.argv
            sys.argv = original_argv

        # Ensure that modules are cleaned up after each step to avoid
        # cross-test contamination e.g. config instances
        for module in list(sys.modules):
            if module.startswith("scripts.") or module.startswith("src."):
                sys.modules.pop(module, None)
        gc.collect()

    def test_integration_cases(self):
        test_cases = [
            path for path in sorted(self.test_case_root.iterdir())
            if path.is_dir()
        ]
        self.test_cases = test_cases
        for test_case in test_cases:
            limit_test_case = os.getenv("RUN_TEST_CASE")
            if (
                limit_test_case
                and limit_test_case != test_case.name
            ):
                print(
                    f"Skipping test case '{test_case.name}' - env var "
                    f" RUN_TEST_CASE={limit_test_case} has been set.")
                continue

            if test_case in self.completed_tests:
                print_green(f"Skipping test case '{test_case.name}' - "
                            "previously passed.")
                continue

            with self.subTest(test_case=test_case.name):
                query_dir = None
                wdir = self.prepare_working_dir(test_case)
                config_file = self.create_test_config(wdir)
                query_ix_path = wdir / QUERY_INDEX_FILENAME
                query_ix = (
                    int(query_ix_path.read_text().strip()) + 1
                    if query_ix_path.exists()
                    else 1
                )

                self.patch_and_run(
                    "p0_validation",
                    {
                        "metadata_csv": wdir / "metadata.csv",
                        "query_fasta": wdir / "query.fasta",
                        "taxdb_dir": self.taxdump_dir,
                        "bold": False,
                    },
                    config_file=config_file,
                )
                print_green(f"\nTest case {test_case.name}: P0 PASS\n")

                self.patch_and_run(
                    "p1_parse_blast",
                    {
                        "blast_xml_path": wdir / "blast_result.xml",
                        "output_dir": wdir,
                    },
                    config_file=config_file,
                )
                print_green(f"\nTest case {test_case.name}: P1 PASS\n")

                self.patch_and_run(
                    "p2_extract_taxonomy",
                    {
                        "taxids_csv": wdir / "taxids.csv",
                        "output_dir": wdir,
                    },
                    config_file=config_file,
                )
                print_green(f"\nTest case {test_case.name}: P2 PASS\n")

                query_dir = next(
                    wdir.glob(f"query_{query_ix:03}*")
                )

                self.patch_and_run(
                    "p3_assign_taxonomy",
                    {
                        "query_dir": query_dir,
                        "output_dir": wdir,
                        "bold": False,
                    },
                    config_file=config_file,
                )
                print_green(f"\nTest case {test_case.name}: P3 PASS\n")

                candidates_count_file = next(
                    query_dir.glob("candidates_count.txt"))
                with open(candidates_count_file) as f:
                    candidates_count = int(f.read().strip())

                if candidates_count < 4:
                    self.patch_and_run(
                        "p4_source_diversity",
                        {
                            "query_dir": query_dir,
                            "output_dir": wdir,
                        },
                        config_file=config_file,
                    )
                    print_green(f"\nTest case {test_case.name}: P4 PASS\n")
                else:
                    print_green(
                        f"\nTest case {test_case.name}: P4 SKIPPED - "
                        f"{candidates_count=} > 3\n"
                    )

                self.patch_and_run(
                    "p5_db_coverage",
                    {
                        "query_dir": query_dir,
                        "output_dir": wdir,
                        "bold": False,
                    },
                    config_file=config_file,
                )
                print_green(f"\nTest case {test_case.name}: P5 PASS\n")

                self._assert_db_coverage(test_case, query_dir)

                # Copy newick tree into query dir
                nwk_file = next(wdir.glob("*.nwk"))
                shutil.copy2(nwk_file, query_dir)

                self.patch_and_run(
                    "p6_report",
                    {
                        "query_dir": query_dir,
                        "output_dir": wdir,
                        "bold": False,
                        "params_json": TEST_DATA_DIR / "params.json",
                        "versions_yml": TEST_DATA_DIR / "versions.yml",
                    },
                    config_file=config_file,
                )
                print_green(f"\nTest case {test_case.name}: P6 PASS\n")

                self.completed_tests.append(test_case)


if __name__ == "__main__":
    unittest.main()
