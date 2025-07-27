import unittest
from unittest.mock import patch, Mock
from pathlib import Path
import tempfile
import shutil
from Bio import SeqIO

from src.bold.id_engine import (
    BoldSearch,
    BOLDIGGER_NO_MATCH_STR,
    BOLDIGGER_OUTPUT_DIRNAME,
)

# Test data file paths
TEST_DATA_SUBDIR = "test-data"
BOLDIGGER_DATA_SUBDIR = "boldigger3_data"
QUERIES_BOLD_RESULTS_FILENAME = "queries_bold_results_part_1.xlsx"
QUERIES_FASTA_FILENAME = "queries.fasta"
TEST_FASTA_FILENAME = "test_queries.fasta"

# Test constants
FIRST_SEQUENCE_INDEX = 0
SEQUENCE_PREVIEW_LENGTH = 50
EXPECTED_URL_PREFIX = "https://portal.boldsystems.org/record/"

# Mock test values
TEST_DATABASE_ID = 1
TEST_MODE_ID = 1
TEST_DATABASE_ID_ALT = 2
TEST_MODE_ID_ALT = 3
TEST_THRESHOLDS = [90, 95, 99]
MOCK_PROCESS_RETURNCODE = 0

# Test strings
EXISTING_QUERY_ID = "existing_query"
EXISTING_HIT_VALUE = "hit"
BOLDIGGER_FAILURE_MSG = "BOLDigger3 failed"


class TestBoldSearch(unittest.TestCase):
    """Test cases for BoldSearch class methods."""

    def setUp(self):
        """Set up test fixtures."""
        test_dir = Path(__file__).parent
        self.test_data_path = (
            test_dir / TEST_DATA_SUBDIR / BOLDIGGER_DATA_SUBDIR
            / QUERIES_BOLD_RESULTS_FILENAME
        )
        self.fasta_path = test_dir / TEST_DATA_SUBDIR / QUERIES_FASTA_FILENAME
        # Read actual query sequences from FASTA file
        with open(self.fasta_path, "r") as fasta_file:
            self.query_sequences = list(SeqIO.parse(fasta_file, "fasta"))
        self.query_seqids = [seq.id for seq in self.query_sequences]

        # Set up expected test values using first sequence
        self.expected_query_id = self.query_sequences[FIRST_SEQUENCE_INDEX].id
        self.expected_query_seq = self.query_sequences[FIRST_SEQUENCE_INDEX]

        # Create a minimal BoldSearch instance for testing
        self.bold_search = BoldSearch.__new__(BoldSearch)
        self.bold_search.query_sequences = self.query_sequences
        self.bold_search.query_seqids = self.query_seqids

    def test_parse_bold_xlsx_basic_functionality(self):
        """Test that _parse_bold_xlsx correctly parses the XLSX file."""
        results = self.bold_search._parse_bold_xlsx(self.test_data_path)

        # Check that results is a dictionary
        self.assertIsInstance(results, dict)

        # Check that we have results for our query sequence
        self.assertIn(self.expected_query_id, results)

        # Check query annotations are present
        query_result = results[self.expected_query_id]
        self.assertEqual(query_result["query_id"], self.expected_query_id)
        self.assertEqual(
            query_result["query_title"], self.expected_query_seq.description
        )
        self.assertEqual(query_result["query_index"], FIRST_SEQUENCE_INDEX)
        self.assertEqual(
            query_result["query_length"], len(self.expected_query_seq.seq)
        )
        # Check first characters of sequence
        expected_seq_start = (
            str(self.expected_query_seq.seq)[:SEQUENCE_PREVIEW_LENGTH]
        )
        actual_seq_start = (
            str(query_result["query_sequence"])[:SEQUENCE_PREVIEW_LENGTH]
        )
        self.assertEqual(actual_seq_start, expected_seq_start)

        # Check that hits are present
        self.assertIn("hits", query_result)
        self.assertIsInstance(query_result["hits"], list)
        self.assertGreater(len(query_result["hits"]), 0)

        # Check that all FASTA sequence IDs are present in results
        expected_ids = set(self.query_seqids)
        self.assertEqual(set(results.keys()), expected_ids)

    def test_parse_bold_xlsx_hit_structure(self):
        """Test that hits have the correct structure and required fields."""
        results = self.bold_search._parse_bold_xlsx(self.test_data_path)

        # Get the first hit for testing
        hits = results[self.expected_query_id]["hits"]
        self.assertGreater(len(hits), 0)

        first_hit = hits[0]

        # Check required fields are present
        required_fields = [
            "hit_id", "bin_uri", "taxonomic_identification", "identity",
            "url", "country", "nucleotide", "identified_by", "phylum",
            "class", "order", "family", "genus", "species"
        ]

        for field in required_fields:
            self.assertIn(field, first_hit)

        # Check URL format
        self.assertTrue(first_hit["url"].startswith(EXPECTED_URL_PREFIX))

        # Check nucleotide sequence has no dashes
        self.assertNotIn("-", first_hit["nucleotide"])

    def test_parse_bold_xlsx_taxonomic_identification(self):
        """Test taxonomic identification logic."""
        results = self.bold_search._parse_bold_xlsx(self.test_data_path)
        hits = results[self.expected_query_id]["hits"]

        for hit in hits:
            taxonomic_id = hit["taxonomic_identification"]
            genus = hit["genus"]
            species = hit["species"]

            # Handle NaN values
            import pandas as pd
            species_is_valid = (
                species and not pd.isna(species) and str(species).strip()
            )
            genus_is_valid = (
                genus and not pd.isna(genus) and str(genus).strip()
            )

            if species_is_valid:
                # If species is present, taxonomic_identification should be
                # the species
                self.assertEqual(taxonomic_id, species)
            elif genus_is_valid:
                # If no species but genus exists, should be "genus sp."
                self.assertEqual(taxonomic_id, f"{genus} sp.")
            else:
                # If neither species nor genus is valid,
                # taxonomic_identification should be empty string or " sp."
                self.assertTrue(taxonomic_id in ["", " sp."])

    def test_parse_bold_xlsx_no_match_filtering(self):
        """Test that no-match entries are filtered out."""
        results = self.bold_search._parse_bold_xlsx(self.test_data_path)
        hits = results[self.expected_query_id]["hits"]

        # Ensure no hits have 'no-match' as phylum
        for hit in hits:
            self.assertNotEqual(hit["phylum"], BOLDIGGER_NO_MATCH_STR)

    def test_parse_bold_xlsx_append_to_existing_results(self):
        """Test that results can be appended to existing results dictionary."""
        # Create initial results
        initial_results = {
            EXISTING_QUERY_ID: {
                "query_id": EXISTING_QUERY_ID,
                "hits": [{"existing": EXISTING_HIT_VALUE}]
            }
        }

        # Parse XLSX and append to existing results
        results = self.bold_search._parse_bold_xlsx(
            self.test_data_path, initial_results
        )

        # Check that existing results are preserved
        self.assertIn(EXISTING_QUERY_ID, results)
        existing_hit_value = results[EXISTING_QUERY_ID]["hits"][0]["existing"]
        self.assertEqual(existing_hit_value, EXISTING_HIT_VALUE)

        # Check that new results are added
        self.assertIn(self.expected_query_id, results)

    def test_parse_bold_xlsx_empty_results_dict(self):
        """Test parsing with an empty results dictionary."""
        results = self.bold_search._parse_bold_xlsx(self.test_data_path, {})

        self.assertIsInstance(results, dict)
        self.assertIn(self.expected_query_id, results)

    def test_parse_bold_xlsx_sequence_consistency(self):
        """Test that parsed results match the input FASTA sequences."""
        results = self.bold_search._parse_bold_xlsx(self.test_data_path)

        # Check that each sequence from FASTA matches the parsed result
        for i, seq_record in enumerate(self.query_sequences):
            seq_id = seq_record.id
            if seq_id in results:
                result = results[seq_id]
                self.assertEqual(result["query_id"], seq_id)
                self.assertEqual(result["query_title"], seq_record.description)
                self.assertEqual(result["query_index"], i)
                self.assertEqual(result["query_length"], len(seq_record.seq))
                self.assertEqual(
                    str(result["query_sequence"]), str(seq_record.seq)
                )

    @patch('src.bold.id_engine.subprocess.run')
    @patch('src.bold.id_engine.config')
    def test_bold_sequence_search(self, mock_config, mock_subprocess):
        """Test _bold_sequence_search method with mocked BOLDigger3."""
        # Set up temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Mock config.output_dir
            mock_config.output_dir = temp_path
            mock_config.BOLDIGGER_KEEP_OUTPUTS = False

            # Create BOLDigger working directory
            wdir = temp_path / BOLDIGGER_OUTPUT_DIRNAME
            wdir.mkdir(parents=True, exist_ok=True)

            # Create the boldigger3_data subdirectory and mock output file
            boldigger_data_dir = wdir / BOLDIGGER_DATA_SUBDIR
            boldigger_data_dir.mkdir(parents=True, exist_ok=True)

            # Copy the test data file to the expected output location
            mock_output_file = (
                boldigger_data_dir / QUERIES_BOLD_RESULTS_FILENAME
            )
            test_xlsx_path = self.test_data_path
            shutil.copy2(test_xlsx_path, mock_output_file)

            # Mock successful subprocess.run
            mock_subprocess.return_value = Mock(
                returncode=MOCK_PROCESS_RETURNCODE
            )

            # Create a test BoldSearch instance
            test_fasta = temp_path / TEST_FASTA_FILENAME
            test_fasta.write_text(self.fasta_path.read_text())

            bold_search = BoldSearch.__new__(BoldSearch)
            bold_search.fasta_file = test_fasta
            bold_search.database = TEST_DATABASE_ID
            bold_search.mode = TEST_MODE_ID
            bold_search.thresholds = None
            bold_search.query_sequences = self.query_sequences
            bold_search.query_seqids = self.query_seqids

            # Call the method under test
            results = bold_search._bold_sequence_search()

            # Verify subprocess was called with correct arguments
            mock_subprocess.assert_called_once()
            call_args = mock_subprocess.call_args[0][0]
            self.assertEqual(call_args[0], "boldigger3")
            self.assertEqual(call_args[1], "identify")
            self.assertEqual(call_args[3], "--db")
            self.assertEqual(call_args[4], "1")
            self.assertEqual(call_args[5], "--mode")
            self.assertEqual(call_args[6], "1")

            # Verify results structure
            self.assertIsInstance(results, dict)
            self.assertGreater(len(results), 0)

            # Verify that results contain expected sequence IDs
            expected_ids = set(self.query_seqids)
            result_keys = set(results.keys())
            self.assertTrue(expected_ids.issubset(result_keys))

            # Verify working directory was cleaned up
            # (since BOLDIGGER_KEEP_OUTPUTS=False)
            self.assertFalse(wdir.exists())

    @patch('src.bold.id_engine.subprocess.run')
    @patch('src.bold.id_engine.config')
    def test_bold_sequence_search_with_thresholds(
        self, mock_config, mock_subprocess
    ):
        """Test _bold_sequence_search method with thresholds parameter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            mock_config.output_dir = temp_path
            mock_config.BOLDIGGER_KEEP_OUTPUTS = False

            # Create directories and output file
            wdir = temp_path / BOLDIGGER_OUTPUT_DIRNAME
            boldigger_data_dir = wdir / BOLDIGGER_DATA_SUBDIR
            boldigger_data_dir.mkdir(parents=True, exist_ok=True)

            mock_output_file = (
                boldigger_data_dir / QUERIES_BOLD_RESULTS_FILENAME
            )
            shutil.copy2(self.test_data_path, mock_output_file)

            mock_subprocess.return_value = Mock(
                returncode=MOCK_PROCESS_RETURNCODE
            )

            # Create test instance with thresholds
            test_fasta = temp_path / TEST_FASTA_FILENAME
            test_fasta.write_text(self.fasta_path.read_text())

            bold_search = BoldSearch.__new__(BoldSearch)
            bold_search.fasta_file = test_fasta
            bold_search.database = TEST_DATABASE_ID_ALT
            bold_search.mode = TEST_MODE_ID_ALT
            bold_search.thresholds = TEST_THRESHOLDS
            bold_search.query_sequences = self.query_sequences
            bold_search.query_seqids = self.query_seqids

            # Call the method
            bold_search._bold_sequence_search()

            # Verify thresholds were included in subprocess call
            call_args = mock_subprocess.call_args[0][0]
            self.assertIn("--thresholds", call_args)
            threshold_idx = call_args.index("--thresholds")
            expected_thresholds = [str(t) for t in TEST_THRESHOLDS]
            self.assertEqual(
                call_args[threshold_idx + 1:threshold_idx + 4],
                expected_thresholds
            )

    @patch('src.bold.id_engine.subprocess.run')
    @patch('src.bold.id_engine.config')
    def test_bold_sequence_search_subprocess_error(
        self, mock_config, mock_subprocess
    ):
        """Test _bold_sequence_search method handles subprocess errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            mock_config.output_dir = temp_path

            # Mock subprocess failure
            mock_subprocess.side_effect = Exception(BOLDIGGER_FAILURE_MSG)

            # Create test instance
            test_fasta = temp_path / TEST_FASTA_FILENAME
            test_fasta.write_text(self.fasta_path.read_text())

            bold_search = BoldSearch.__new__(BoldSearch)
            bold_search.fasta_file = test_fasta
            bold_search.database = TEST_DATABASE_ID
            bold_search.mode = TEST_MODE_ID
            bold_search.thresholds = None
            bold_search.query_sequences = self.query_sequences
            bold_search.query_seqids = self.query_seqids

            # Verify RuntimeError is raised
            with self.assertRaises(RuntimeError) as context:
                bold_search._bold_sequence_search()

            self.assertIn("Error running BOLDigger3", str(context.exception))

    @patch('src.bold.id_engine.subprocess.run')
    @patch('src.bold.id_engine.config')
    def test_bold_sequence_search_no_results(
        self, mock_config, mock_subprocess
    ):
        """Test _bold_sequence_search method handles no output files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            mock_config.output_dir = temp_path

            # Create working directory but no output files
            wdir = temp_path / BOLDIGGER_OUTPUT_DIRNAME
            wdir.mkdir(parents=True, exist_ok=True)

            mock_subprocess.return_value = Mock(
                returncode=MOCK_PROCESS_RETURNCODE
            )

            # Create test instance
            test_fasta = temp_path / TEST_FASTA_FILENAME
            test_fasta.write_text(self.fasta_path.read_text())

            bold_search = BoldSearch.__new__(BoldSearch)
            bold_search.fasta_file = test_fasta
            bold_search.database = TEST_DATABASE_ID
            bold_search.mode = TEST_MODE_ID
            bold_search.thresholds = None
            bold_search.query_sequences = self.query_sequences
            bold_search.query_seqids = self.query_seqids

            # Verify RuntimeError is raised when no results found
            with self.assertRaises(RuntimeError) as context:
                bold_search._bold_sequence_search()

            expected_msg = "No results found in BOLDigger outputs"
            self.assertIn(expected_msg, str(context.exception))


if __name__ == "__main__":
    unittest.main()
