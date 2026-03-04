"""Validate user inputs."""

import argparse
import csv
import logging
import os
import re
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.Data import IUPACData

from src.utils import countries
from src.utils.config import Config
from src.utils.config.mappings import PARAMS
from src.utils.errors import FASTAFormatError, MetadataFormatError

config = Config()
logger = logging.getLogger(__name__)

DNA_CHARS = set(IUPACData.ambiguous_dna_letters)
TAXDB_EXPECT_FILES = {
    "citations.dmp",
    "delnodes.dmp",
    "division.dmp",
    "gc.prt",
    "gencode.dmp",
    "images.dmp",
    "merged.dmp",
    "names.dmp",
    "nodes.dmp",
}
# If sequences are included in the metadata CSV, we split them:
OUTPUT_FASTA_FILENAME = 'sequences.fasta'


def main():
    args = _parse_args()
    config.update_from_args(args)
    _validate_taxdbs(args.taxdb_dir)
    ids = _validate_fasta(args.query_fasta)
    _validate_metadata(
        args.metadata_csv,
        ids,
        bold=args.is_bold,
    )


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Validate user input."
    )
    parser = config.add_cli_args(parser, [
        PARAMS['metadata_csv'].required(),
        PARAMS['query_fasta'],
        PARAMS['taxdb_dir'].required(),
        PARAMS['allowed_loci_file'],
        PARAMS['fasta_max_sequences'],
        PARAMS['fasta_min_length'],
        PARAMS['fasta_max_length'],
        PARAMS['is_bold'],
    ])
    return parser.parse_args()


def _validate_fasta(path: Path) -> list[str]:
    """Assert that input FASTA file is valid.

    - Must be nucleotide (ambiguous IUPAC DNA)
    - Minimum seq length (50nt?)
    - Max sequences (show warning) - 120?
    - Max seq length (3000nt?)
    - Seq IDs must be unique
    - Seq IDs must match metadata CSV
    """
    if path is None:
        # Expect sequences to be included in CSV column
        return None

    count = 0
    seq_ids = []
    sanitized_sequences = []
    with path.open() as f:
        sequences = SeqIO.parse(f, 'fasta')
        for seq in sequences:
            if seq.id in seq_ids:
                raise FASTAFormatError(
                    f"Duplicate sequence ID: '{seq.id}' (sequence"
                    f" #{count + 1} {seq.id})."
                    " Sequences must have unique identifiers that match a row"
                    " in the metadata CSV input."
                )
            seq_ids.append(seq.id)
            count = len(seq_ids)
            try:
                _assert_is_dna(seq.seq)
            except FASTAFormatError as exc:
                raise FASTAFormatError(
                    f'invalid DNA in sequence #{count} {seq.id}: {exc}'
                ) from exc
            if count > config.inputs.fasta_max_sequences:
                raise FASTAFormatError(
                    f"too many query sequences provided. A maximum of"
                    f" {config.inputs.fasta_max_sequences} sequences is"
                    " allowed."
                )
            length = len(seq.seq)
            if length < config.inputs.fasta_min_length:
                raise FASTAFormatError(
                    f"sequence of length {length}bp does not meet the"
                    " minimum allowed length of"
                    f" {config.inputs.fasta_min_length}bp (sequence"
                    f" #{count} {seq.id})"
                )
            if length > config.inputs.fasta_max_length:
                raise FASTAFormatError(
                    f"sequence of length {length}bp exceeds the maximum"
                    f" allowed length of {config.inputs.fasta_max_length}bp"
                    f" (sequence #{count} {seq.id})"
                )
            sanitized_sequences.append(
                SeqIO.SeqRecord(
                    Seq(_sanitize_dna(seq.seq)),
                    id=seq.id,
                )
            )
    path = config.output_dir / OUTPUT_FASTA_FILENAME
    SeqIO.write(
        sanitized_sequences,
        path,
        'fasta',
    )
    logger.info(f'{count} sanitized sequences written to {path}')

    return seq_ids


def _assert_is_dna(sequence: str):
    sequence = _sanitize_dna(sequence)
    illegal_residues = set(sequence) - DNA_CHARS
    if illegal_residues:
        residue = illegal_residues.pop()
        position = sequence.index(residue)
        raise FASTAFormatError(
            f"Illegal DNA residue '{residue}' at position {position}."
            f" Permitted characters: {DNA_CHARS}"
        )


def _sanitize_dna(sequence) -> str:
    """Remove whitespace and convert to uppercase."""
    sequence = str(sequence)
    return re.sub(r'[\s-]+', '', sequence).upper()


def _validate_metadata(
    path: Path,
    seq_ids: list[str],
    bold=False,
):
    """Assert that input metadata CSV is valid.

    Each row['sample_id'] must match a sequence ID
    Locus must be listed in ALLOWED_LOCI
    Must contain required columns (see config.py - colnames configurable)
      - which are required?
    TOI list column should be pipe-delimited if multiple - validate chars?

    If sequence column exists, validate that it contains valid DNA sequences
    and write them to OUTPUT_FASTA_FILENAME.
    """
    expect_seq_col = seq_ids is None
    sample_ids = []
    columns = config.inputs.metadata_csv_header
    with path.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)  # skip header row
    for i, row in enumerate(rows):
        missing_cols = (
            set(config.inputs.metadata_csv_required_fields)
            - set(row.keys())
        )
        if missing_cols:
            raise MetadataFormatError(
                "missing required column(s):" + ', '.join(missing_cols) + '.')

        if expect_seq_col and columns['sequence'] not in row:
            raise MetadataFormatError(
                'Sequence column is expected but no sequence provided.'
                ' If you are not including sequences in the metadata CSV,'
                ' please provide a FASTA file with your sequences and ensure'
                ' that the sequence IDs match the sample IDs in the metadata'
                ' CSV.'
            )
        sample_id = row[columns['sample_id']]
        if seq_ids and sample_id not in seq_ids:
            raise MetadataFormatError(
                f'sample ID "{sample_id}" listed in metadata CSV file is not'
                f' present in FASTA sequence IDs. All sample IDs must match a'
                ' FASTA sequence.'
            )
        for col_id, colname in columns.items():
            if (
                col_id in config.inputs.metadata_csv_required_fields
                and not row[colname].strip()
            ):
                msg = (
                    f'a value is required for column "{colname}"'
                    f' (row {i + 1}).'
                )
                if col_id == 'locus':
                    msg += (
                        ' For samples with no locus (viruses and BOLD runs),'
                        ' please enter "NA".'
                    )
                raise MetadataFormatError(msg)

        try:
            _validate_metadata_sample_id(row[columns['sample_id']])
            _validate_metadata_locus(row[columns['locus']], bold=bold)
            _validate_metadata_preliminary_id(row[columns['preliminary_id']])
            _validate_metadata_taxa_of_interest(
                row.get(columns['taxa_of_interest']))
            _validate_metadata_country(row.get(columns['country']))
            _validate_metadata_host(row.get(columns['host']))
            _validate_metadata_sequence(row.get(columns['sequence']))
            _validate_metadata_classification(row.get(columns['classification']))
        except Exception as exc:
            raise MetadataFormatError(
                f'Error in row {i + 1} (sample ID: {sample_id}): {exc}'
            ) from exc

        sample_ids.append(sample_id)

    if expect_seq_col:
        _write_fasta_from_metadata(rows, columns)
    else:
        missing_ids = set(seq_ids) - set(sample_ids)
        if missing_ids:
            raise MetadataFormatError(
                'FASTA Sequence ID(s) were not found in the provided metadata'
                ' CSV file. All FASTA sequence IDs must match a sample ID in'
                f' the provided metadata CSV: {missing_ids}'
            )


def _write_fasta_from_metadata(rows, columns):
    """Write sequences from metadata CSV to FASTA file."""
    path = config.output_dir / OUTPUT_FASTA_FILENAME
    with path.open('w') as f:
        for row in rows:
            sample_id = row[columns['sample_id']]
            sequence = _sanitize_dna(row[columns['sequence']])
            f.write(f'>{sample_id}\n{sequence}\n')
    logger.info(
        f'metadata.csv sequences have been written to {path.absolute()}'
    )


def _validate_metadata_sequence(value):
    if value is None:
        return
    value = value.strip()
    if not value:
        return
    try:
        _assert_is_dna(value)
    except FASTAFormatError as exc:
        raise MetadataFormatError(
            f'Invalid DNA sequence in metadata: {exc}'
        ) from exc


def _validate_metadata_sample_id(value):
    """Alphanumeric, no spaces, limited special characters."""
    value = value.strip()
    invalid_match = re.search(r'[^A-z0-9_\-\.]', value)
    if invalid_match:
        char = invalid_match.group()
        raise MetadataFormatError(
            f'Invalid sample ID "{value}": character "{char}" is not'
            f' permitted in the sample ID. Must be alphanumeric, underscore or'
            ' dash.'
        )


def _validate_metadata_locus(value, bold=False):
    """This must match the list of allowed loci, if provided.
    The suffic " gene" will be stripped from the provided value prior to
    validation.
    """
    if not config.allowed_loci:
        return

    if bold and not value:
        return

    permitted_synonyms = ['na'] + [
        synonym
        for locus in config.allowed_loci
        for synonym in locus.synonyms
    ]

    value_lower = value.lower()
    value_stripped = re.sub(r' gene$', '', value_lower.strip())
    if value_stripped not in permitted_synonyms:
        raise MetadataFormatError(
            f'Locus "{value_lower}" is not in the list of permitted loci:\n- '
            + '\n- '.join([
                str(synonyms) for synonyms in config.allowed_loci
            ])
        )


def _validate_metadata_preliminary_id(value):
    """This should be a valid taxon name only."""
    value = value.strip()
    invalid_chars = re.search('[^A-z ]', value)
    if invalid_chars:
        raise MetadataFormatError(
            f'Invalid Preliminary Morphology ID taxon "{value}". This field'
            " must be a valid taxonomic name. Please remove any special"
            " characters."
        )


def _validate_metadata_taxa_of_interest(value):
    if value is None:
        return None
    value = value.strip()
    invalid_chars = re.search('[^A-z| ]', value)
    if invalid_chars:
        raise MetadataFormatError(
            f'Invalid Taxa of Interest: "{value}". This field'
            " must be a valid taxonomic name. Please remove any special"
            " characters. Multiple taxa can be specified with a pipe delimiter"
            " '|'."
        )


def _validate_metadata_country(value):
    if value is None or not value.strip():
        return None
    value = value.strip()
    country_code = countries.get_code(value)
    if not country_code:
        raise MetadataFormatError(
            f'The country provided could not be recognised: "{value}"'
        )


def _validate_metadata_host(value):
    pass


def _validate_metadata_classification(value):
    if value is None or not value.strip():
        return None
    value = value.strip().lower()
    if value not in config.HIGHER_CLASSIFICATIONS:
        raise MetadataFormatError(
            f'Invalid classification "{value}". Must be one of: '
            + ', '.join(config.HIGHER_CLASSIFICATIONS)
        )


def _validate_taxdbs(path):
    """Assert that taxdbs files exist in the provided location."""
    if not path.is_dir():
        raise FileNotFoundError(
            "Path provided for taxdb dir is not a dir. Please pass the path"
            f" to your taxdb directory. Received: {path}"
        )
    files = set(os.listdir(path))
    missing = TAXDB_EXPECT_FILES - files
    if missing:
        raise FileNotFoundError(
            "Taxonkit data directory is missing required files. The taxdb"
            " archive can be downloaded from NCBI: "
            + ', '.join(missing)
        )


if __name__ == '__main__':
    main()
