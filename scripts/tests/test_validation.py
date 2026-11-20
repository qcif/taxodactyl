"""Test input validation functions."""

import csv
import logging
import shutil
import tempfile
import unittest
from pathlib import Path

from Bio import SeqIO

from p0_validation import (
    OUTPUT_FASTA_FILENAME,
    TAXDB_EXPECT_FILES,
    _autofix_multi_locus_sample_ids,
    _locus_suffix,
    _validate_fasta,
    _validate_metadata,
    _validate_metadata_country,
    _validate_metadata_host,
    _validate_metadata_locus,
    _validate_metadata_preliminary_id,
    _validate_metadata_sample_id,
    _validate_metadata_taxa_of_interest,
    _autofix_metadata_encoding,
    _validate_taxdbs,
    config,
)

from src.utils.encoding import normalise_csv_encoding
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
METADATA_DUPLICATE_SAMPLE_ID = (
    TEST_DATA_DIR / 'validation/metadata_duplicate_sample_id.csv')
METADATA_WITH_SEQUENCES_DUPLICATE_SAMPLE_ID = TEST_DATA_DIR.joinpath(
    'validation/metadata_with_sequences_duplicate_sample_id.csv')
METADATA_LATIN1 = TEST_DATA_DIR / 'validation/metadata_latin1.csv'
METADATA_UTF8_BOM = TEST_DATA_DIR / 'validation/metadata_utf8_bom.csv'
METADATA_UTF16 = TEST_DATA_DIR / 'validation/metadata_utf16.csv'
XLSX_MAGIC_BYTES = b'PK\x03\x04' + bytes(32)
METADATA_EXPECT_IDS = [
    'LC438549.1',
    'ON075825.1',
    'PP466915.1',
    'JQ585746.1',
    'LC547004.1',
]
MULTI_LOCUS_SEQUENCES = [
    'ACGT' * 10,
    'TTGGCCAA' * 5,
    'GATTACA' * 6,
]
MOCK_TAXONKIT_DIR = Path(tempfile.gettempdir())
MOCK_TAXONKIT_DIR.mkdir(exist_ok=True, parents=True)


class ValidationTestCase(unittest.TestCase):

    def test_it_writes_fasta_headers_with_id_only(self):
        ids = _validate_fasta(FASTA_VALID)
        output_path = config.output_dir / OUTPUT_FASTA_FILENAME
        headers = [
            line[1:].rstrip('\n')
            for line in output_path.open()
            if line.startswith('>')
        ]
        self.assertEqual(headers, ids)

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

    def test_it_rejects_duplicate_metadata_sample_ids(self):
        with self.assertRaisesRegex(
            MetadataFormatError,
            'Duplicate sample ID "LC438549.1" in rows 1 and 2',
        ):
            _validate_metadata(
                METADATA_DUPLICATE_SAMPLE_ID,
                METADATA_EXPECT_IDS,
            )

    def test_it_rejects_duplicate_sample_ids_with_sequence_column(self):
        with self.assertRaisesRegex(
            MetadataFormatError,
            'Duplicate sample ID "LC438549.1" in rows 1 and 2',
        ):
            _validate_metadata(
                METADATA_WITH_SEQUENCES_DUPLICATE_SAMPLE_ID,
                None,
            )

    def _copy_to_tmp(self, source: Path) -> Path:
        tmp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp_dir)
        return Path(shutil.copy(source, tmp_dir))

    def test_it_converts_latin1_metadata_to_utf8(self):
        path = self._copy_to_tmp(METADATA_LATIN1)
        self.assertEqual(normalise_csv_encoding(path), 'cp1252')
        text = path.read_bytes().decode('utf-8')
        self.assertIn('ß-tub', text)
        self.assertNotIn('\r', text)

    def test_it_autofixes_eszett_locus_and_validates(self):
        path = self._copy_to_tmp(METADATA_LATIN1)
        _autofix_metadata_encoding(path)
        text = path.read_text(encoding='utf-8')
        self.assertIn('β-tub', text)
        self.assertNotIn('ß', text)
        _validate_metadata(path, METADATA_EXPECT_IDS)

    def test_it_replaces_eszett_in_sample_ids_and_fasta_headers(self):
        tmp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp_dir)
        csv_path = tmp_dir / 'metadata.csv'
        fasta_path = tmp_dir / 'queries.fasta'
        csv_path.write_bytes(
            'sample_id,locus,preliminary_id\r\n'
            'S1_ß-tub,ß-tub,Fungi\r\n'.encode('latin-1'))
        fasta_path.write_bytes('>S1_ß-tub\nACGT\n'.encode('latin-1'))
        _autofix_metadata_encoding(csv_path, fasta_path)
        self.assertIn(
            'S1_beta-tub,β-tub,Fungi', csv_path.read_text(encoding='utf-8'))
        self.assertEqual(
            fasta_path.read_text(encoding='utf-8'), '>S1_beta-tub\nACGT\n')

    def test_it_strips_utf8_bom_from_metadata(self):
        path = self._copy_to_tmp(METADATA_UTF8_BOM)
        self.assertEqual(normalise_csv_encoding(path), 'utf-8-sig')
        self.assertFalse(path.read_bytes().startswith(b'\xef\xbb\xbf'))
        _validate_metadata(path, METADATA_EXPECT_IDS)

    def test_it_converts_utf16_metadata_to_utf8(self):
        path = self._copy_to_tmp(METADATA_UTF16)
        self.assertEqual(normalise_csv_encoding(path), 'utf-16')
        _validate_metadata(path, METADATA_EXPECT_IDS)

    def test_it_leaves_utf8_metadata_untouched(self):
        path = self._copy_to_tmp(METADATA_VALID)
        before = path.read_bytes()
        self.assertIsNone(normalise_csv_encoding(path))
        self.assertEqual(path.read_bytes(), before)

    def test_it_rejects_excel_workbook_with_csv_extension(self):
        path = Path(tempfile.mkdtemp()) / 'metadata.csv'
        self.addCleanup(shutil.rmtree, path.parent)
        path.write_bytes(XLSX_MAGIC_BYTES)
        with self.assertRaisesRegex(MetadataFormatError, 'Excel workbook'):
            normalise_csv_encoding(path)

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


class MultiLocusSampleIdTestCase(unittest.TestCase):
    """A sample ID repeated at different loci is renamed <id>_<locus>."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp_dir)
        self.csv_path = self.tmp_dir / 'metadata.csv'
        self.fasta_path = self.tmp_dir / 'queries.fasta'

    def _write_csv(self, rows: list[str], sequences=False):
        header = 'sample_id,locus,preliminary_id'
        if sequences:
            header += ',sequence'
        self.csv_path.write_text('\n'.join([header] + rows) + '\n')

    def _write_fasta(self, ids: list[str]):
        self.fasta_path.write_text(''.join(
            f'>{seq_id}\n{MULTI_LOCUS_SEQUENCES[i]}\n'
            for i, seq_id in enumerate(ids)
        ))

    def _sample_ids(self) -> list[str]:
        with self.csv_path.open() as f:
            return [row['sample_id'] for row in csv.DictReader(f)]

    def test_it_renames_multi_locus_sample_ids_in_fasta_mode(self):
        self._write_csv([
            'S1,COI,Aedes aegypti',
            'S2,COI,Culex pipiens',
            'S1,ITS gene,Aedes aegypti',
        ])
        self._write_fasta(['S1', 'S2', 'S1'])
        self.assertTrue(
            _autofix_multi_locus_sample_ids(self.csv_path, self.fasta_path))
        self.assertEqual(self._sample_ids(), ['S1_COI', 'S2', 'S1_ITS'])
        fasta = {
            rec.id: str(rec.seq)
            for rec in SeqIO.parse(self.fasta_path, 'fasta')
        }
        self.assertEqual(fasta, {
            'S1_COI': MULTI_LOCUS_SEQUENCES[0],
            'S2': MULTI_LOCUS_SEQUENCES[1],
            'S1_ITS': MULTI_LOCUS_SEQUENCES[2],
        })
        ids = _validate_fasta(self.fasta_path)
        _validate_metadata(self.csv_path, ids)

    def test_it_renames_multi_locus_sample_ids_in_sequence_column(self):
        self._write_csv([
            f'S1,COI,Aedes aegypti,{MULTI_LOCUS_SEQUENCES[0]}',
            f'S1,β-tub,Aedes aegypti,{MULTI_LOCUS_SEQUENCES[1]}',
        ], sequences=True)
        self.assertTrue(_autofix_multi_locus_sample_ids(self.csv_path))
        self.assertEqual(self._sample_ids(), ['S1_COI', 'S1_beta-tub'])
        _validate_metadata(self.csv_path, None)
        fasta_ids = [
            rec.id for rec in SeqIO.parse(
                config.output_dir / OUTPUT_FASTA_FILENAME, 'fasta')
        ]
        self.assertEqual(fasta_ids, ['S1_COI', 'S1_beta-tub'])

    def _assert_rejected(self, pattern: str, fasta=True):
        csv_before = self.csv_path.read_text()
        fasta_before = self.fasta_path.read_text() if fasta else None
        with self.assertRaisesRegex(MetadataFormatError, pattern):
            _autofix_multi_locus_sample_ids(
                self.csv_path,
                self.fasta_path if fasta else None,
            )
        self.assertEqual(self.csv_path.read_text(), csv_before)
        if fasta:
            self.assertEqual(self.fasta_path.read_text(), fasta_before)

    def test_it_rejects_sample_id_repeated_at_same_locus(self):
        self._write_csv([
            'S1,COI,Aedes aegypti',
            'S1,COI,Culex pipiens',
        ])
        self._write_fasta(['S1', 'S1'])
        self._assert_rejected(
            'Sample ID "S1" is repeated at the same locus "COI" in rows 1'
            ' and 2')

    def test_it_rejects_sample_id_repeated_at_synonym_locus(self):
        # COX1 is a synonym of COI, so these rows share a locus
        self._write_csv([
            'S1,COI,Aedes aegypti',
            'S1,COX1,Culex pipiens',
        ])
        self._write_fasta(['S1', 'S1'])
        self._assert_rejected(
            r'same locus \("COI" and "COX1" are synonyms\) in rows 1 and 2')

    def test_it_rejects_sample_id_repeated_with_blank_locus(self):
        self._write_csv([
            'S1,COI,Aedes aegypti',
            'S1,,Aedes aegypti',
        ])
        self._write_fasta(['S1', 'S1'])
        self._assert_rejected(
            r'"S1" is repeated \(rows 1 and 2\), but row 2 has no locus')

    def test_it_rejects_when_fasta_count_differs(self):
        self._write_csv([
            'S1,COI,Aedes aegypti',
            'S1,ITS,Aedes aegypti',
        ])
        self._write_fasta(['S1'])
        self._assert_rejected(
            'FASTA file has 1 sequence\\(s\\) with this ID')

    def test_it_rejects_when_new_id_is_taken(self):
        self._write_csv([
            'S1,COI,Aedes aegypti',
            'S1,ITS,Aedes aegypti',
            'S1_ITS,ITS,Culex pipiens',
        ])
        self._assert_rejected(
            'must be renamed to "S1_ITS", but that sample ID is already used'
            ' in row 3',
            fasta=False,
        )

    def test_it_makes_locus_suffix_safe_for_sample_id(self):
        self.assertEqual(_locus_suffix('β-tub gene'), 'beta-tub')
        self.assertEqual(_locus_suffix(' 28S rRNA '), '28S_rRNA')
        self.assertEqual(_locus_suffix('EF-1a'), 'EF-1a')
