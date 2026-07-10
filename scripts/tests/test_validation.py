"""Test input validation functions."""

import logging
import tempfile
import unittest
from pathlib import Path

from p0_validation import (
    OUTPUT_FASTA_FILENAME,
    TAXDB_EXPECT_FILES,
    _validate_fasta,
    _validate_metadata,
    _validate_metadata_country,
    _validate_metadata_host,
    _validate_metadata_locus,
    _validate_metadata_preliminary_id,
    _validate_metadata_sample_id,
    _validate_metadata_taxa_of_interest,
    _validate_taxdbs,
)

from src.utils.errors import FASTAFormatError, MetadataFormatError

logging.disable(logging.CRITICAL)

TEST_DATA_DIR = Path(__file__).parent / 'test-data'
FASTA_VALID = TEST_DATA_DIR / 'validation/queries.fasta'
FASTA_INVALID_RESIDUE = TEST_DATA_DIR / 'validation/invalid_residues.fasta'
FASTA_INVALID_LENGTH = TEST_DATA_DIR / 'validation/invalid_max_length.fasta'
FASTA_INVALID_COUNT = TEST_DATA_DIR / 'validation/invalid_max_count.fasta'
FASTA_INVALID_DUPLICATE_ID = (
    TEST_DATA_DIR / 'validation/invalid_duplicate.fasta')
METADATA_VALID = TEST_DATA_DIR / 'validation/metadata.csv'
METADATA_INVALID_COLUMNS = (
    TEST_DATA_DIR / 'validation/metadata_invalid_columns.csv')
METADATA_INVALID_LOCUS = (
    TEST_DATA_DIR / 'validation/metadata_invalid_locus.csv')
METADATA_MISSING_SAMPLE_ID = (
    TEST_DATA_DIR / 'validation/metadata_missing_sample_id.csv')
METADATA_MISSING_SEQUENCE_ID = (
    TEST_DATA_DIR / 'validation/metadata_missing_sequence_id.csv')
METADATA_MISSING_TOI_COUNTRY = (
    TEST_DATA_DIR / 'validation/metadata_missing_toi_country.csv')
METADATA_MISSING_HOST = (
    TEST_DATA_DIR / 'validation/metadata_missing_host.csv')
METADATA_MISSING_OPTIONAL_COLS = (
    TEST_DATA_DIR / 'validation/metadata_missing_optional_cols.csv')
METADATA_WITH_SEQUENCES = (
    TEST_DATA_DIR / 'validation/metadata_with_sequences.csv')
METADATA_NO_SEQUENCES = (
    TEST_DATA_DIR / 'validation/metadata_no_sequences.csv')
METADATA_SEQUENCES_WITH_WHITESPACE = (
    TEST_DATA_DIR / 'validation/metadata_sequences_with_whitespace.csv')
METADATA_EXPECT_IDS = [
    'LC438549.1',
    'ON075825.1',
    'PP466915.1',
    'JQ585746.1',
    'LC547004.1',
]
MOCK_TAXONKIT_DIR = Path(tempfile.gettempdir())
MOCK_TAXONKIT_DIR.mkdir(exist_ok=True, parents=True)


class ValidationTestCase(unittest.TestCase):

    def test_it_can_validate_fasta_input(self):
        _validate_fasta(FASTA_VALID)
        with self.assertRaises(FASTAFormatError):
            _validate_fasta(FASTA_INVALID_RESIDUE)
        with self.assertRaises(FASTAFormatError):
            _validate_fasta(FASTA_INVALID_LENGTH)
        with self.assertRaises(FASTAFormatError):
            _validate_fasta(FASTA_INVALID_COUNT)
        with self.assertRaises(FASTAFormatError):
            _validate_fasta(FASTA_INVALID_DUPLICATE_ID)

    def test_it_can_validate_metadata_csv(self):
        _validate_metadata(METADATA_VALID, METADATA_EXPECT_IDS)
        _validate_metadata(METADATA_MISSING_TOI_COUNTRY, METADATA_EXPECT_IDS)
        _validate_metadata(METADATA_MISSING_HOST, METADATA_EXPECT_IDS)
        _validate_metadata(METADATA_MISSING_OPTIONAL_COLS, METADATA_EXPECT_IDS)
        with self.assertRaises(MetadataFormatError):
            _validate_metadata(METADATA_INVALID_COLUMNS, METADATA_EXPECT_IDS)
        with self.assertRaises(MetadataFormatError):
            _validate_metadata(METADATA_MISSING_SAMPLE_ID, METADATA_EXPECT_IDS)
        with self.assertRaises(MetadataFormatError):
            _validate_metadata(
                METADATA_MISSING_SEQUENCE_ID,
                METADATA_EXPECT_IDS
            )

    def test_it_creates_fasta_from_csv_sequences(self):
        """Test that FASTA file is created when sequences in CSV."""
        output_path = Path('output') / OUTPUT_FASTA_FILENAME
        # Clean up any existing output file
        if output_path.exists():
            output_path.unlink()

        # Validate metadata with sequences (seq_ids=None means expect seqs)
        _validate_metadata(
            METADATA_WITH_SEQUENCES,
            None,
        )

        # Check that FASTA file was created
        self.assertTrue(
            output_path.exists(),
            f'{output_path} should be created'
        )

        # Verify FASTA content
        from Bio import SeqIO
        with open(output_path, 'r') as f:
            sequences = list(SeqIO.parse(f, 'fasta'))
        self.assertEqual(len(sequences), 5)
        self.assertEqual(sequences[0].id, 'LC438549.1')
        self.assertEqual(sequences[1].id, 'ON075825.1')

        # Clean up
        output_path.unlink()

    def test_it_sanitizes_sequences_when_creating_fasta(self):
        """Test that whitespace and hyphens are removed from sequences."""
        output_path = Path('output') / OUTPUT_FASTA_FILENAME
        # Clean up any existing output file
        if output_path.exists():
            output_path.unlink()

        # Validate metadata with sequences containing whitespace/hyphens
        # seq_ids=None means expect sequences in CSV
        _validate_metadata(
            METADATA_SEQUENCES_WITH_WHITESPACE,
            None,
        )

        # Check that FASTA file was created
        self.assertTrue(
            output_path.exists(),
            f'{output_path} should be created'
        )

        # Verify sequences have no whitespace or hyphens
        from Bio import SeqIO
        with open(output_path, 'r') as f:
            sequences = list(SeqIO.parse(f, 'fasta'))

        # Check each sequence for whitespace and hyphens
        for seq in sequences:
            seq_str = str(seq.seq)
            self.assertNotIn(' ', seq_str, 'Spaces should be removed')
            self.assertNotIn('\n', seq_str, 'Newlines should be removed')
            self.assertNotIn('\t', seq_str, 'Tabs should be removed')
            self.assertNotIn('-', seq_str, 'Hyphens should be removed')
            # Verify only valid DNA characters remain
            self.assertTrue(
                all(c in 'ACGTMRWSYKVHDBN' for c in seq_str),
                f'Sequence should only contain valid DNA chars: {seq_str}'
            )

        # Verify specific sequences are correctly sanitized
        seq1 = str(sequences[0].seq)
        self.assertTrue(
            seq1.startswith('GGTAAAAAAAATGAGT'),
            'First sequence should start with clean DNA'
        )

        # Clean up
        output_path.unlink()

    def test_it_raises_error_when_no_fasta_and_no_sequence_column(self):
        """Test validation error when no FASTA and CSV has no sequences."""
        with self.assertRaises(MetadataFormatError) as context:
            _validate_metadata(
                METADATA_NO_SEQUENCES,
                None,
            )
        self.assertIn(
            'Sequence column is expected',
            str(context.exception)
        )

    def test_it_allows_no_sequence_column_when_fasta_provided(self):
        """Test no errors when FASTA provided and no sequence column."""
        # FASTA was provided (seq_ids provided), CSV doesn't need sequences
        _validate_metadata(
            METADATA_NO_SEQUENCES,
            METADATA_EXPECT_IDS,
        )

    def test_it_can_validate_metadata_sample_id(self):
        _validate_metadata_sample_id('abcd_1234-blah.blah')
        with self.assertRaises(MetadataFormatError):
            _validate_metadata_sample_id('abcd_1234-blah blah blah')

    def test_it_can_validate_metadata_locus(self):
        _validate_metadata_locus('COI')
        _validate_metadata_locus('coi')
        _validate_metadata_locus('cox')
        _validate_metadata_locus('NA')
        _validate_metadata_locus('', bold=True)
        with self.assertRaises(MetadataFormatError):
            _validate_metadata_locus('GGG')
        with self.assertRaises(MetadataFormatError) as exc:
            _validate_metadata_locus('')
            self.assertIn('NA', str(exc.exception))

    def test_it_can_validate_metadata_preliminary_id(self):
        _validate_metadata_preliminary_id('Homo')
        _validate_metadata_preliminary_id('Homo sapiens')
        with self.assertRaises(MetadataFormatError):
            _validate_metadata_preliminary_id('Homo-sapiens')

    def test_it_can_validate_metadata_taxa_of_interest(self):
        _validate_metadata_taxa_of_interest('Homo sapiens')
        _validate_metadata_taxa_of_interest('Homo sapiens|Pan troglodytes')
        with self.assertRaises(MetadataFormatError):
            _validate_metadata_taxa_of_interest('Homo sapiens,Pan troglodytes')

    def test_it_can_validate_metadata_country(self):
        _validate_metadata_country('canada')
        with self.assertRaises(MetadataFormatError):
            _validate_metadata_country('canada and mexico')

    def test_it_can_validate_metadata_host(self):
        _validate_metadata_host('Cut flowers Rosa')

    def test_it_can_validate_taxdbs_path(self):
        for required_file in TAXDB_EXPECT_FILES:
            path = MOCK_TAXONKIT_DIR / required_file
            path.touch()
        _validate_taxdbs(MOCK_TAXONKIT_DIR)
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            _validate_taxdbs(MOCK_TAXONKIT_DIR)
