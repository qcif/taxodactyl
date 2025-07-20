"""Validate user inputs."""

import argparse
import csv
import os
import re
from pathlib import Path

from Bio import SeqIO
from Bio.Data import IUPACData

from src.utils import countries, existing_path
from src.utils.config import Config
from src.utils.errors import FASTAFormatError, MetadataFormatError

config = Config()

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


def main():
    args = _parse_args()
    _validate_taxdbs(args.taxdb_dir)
    ids = _validate_fasta(args.query_fasta)
    _validate_metadata(args.metadata_csv, ids, bold=args.bold)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Validate user input."
    )
    parser.add_argument(
        "--metadata_csv",
        type=existing_path,
        help="Path to metadata.csv input file.",
        required=True,
    )
    parser.add_argument(
        "--query_fasta",
        type=existing_path,
        help="Path to queries.fasta input file.",
        required=True,
    )
    parser.add_argument(
        "--taxdb_dir",
        type=existing_path,
        help="Path to queries.fasta input file.",
        required=True,
    )
    parser.add_argument(
        "--bold",
        action="store_true",
        help="Validate inputs for a BOLD analysis (accept blank locus field).",
    )
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
    def assert_dna(sequence: str):
        sequence = sequence.upper()
        illegal_residues = set(sequence) - DNA_CHARS
        if illegal_residues:
            residue = illegal_residues.pop()
            position = sequence.index(residue)
            raise FASTAFormatError(
                f"Illegal DNA residue '{residue}' at position {position}."
                f" Permitted characters: {DNA_CHARS}"
            )

    count = 0
    seq_ids = []
    with path.open() as f:
        sequences = SeqIO.parse(f, 'fasta')
        for seq in sequences:
            if seq.id in seq_ids:
                raise FASTAFormatError(
                    f"Duplicate sequence ID: '{seq.id}' (sequence"
                    f" ##{count + 1})."
                    " Sequences must have unique identifiers that match a row"
                    " in the metadata CSV input."
                )
            seq_ids.append(seq.id)
            count = len(seq_ids)
            try:
                assert_dna(seq.seq)
            except FASTAFormatError as exc:
                raise FASTAFormatError(
                    f'invalid DNA in sequence ##{count}'
                ) from exc
            if count > config.INPUTS.FASTA_MAX_SEQUENCES:
                raise FASTAFormatError(
                    f"too many query sequences provided. A maximum of"
                    f" {config.INPUTS.FASTA_MAX_SEQUENCES} sequences is"
                    " allowed."
                )
            length = len(seq.seq)
            if length < config.INPUTS.FASTA_MIN_LENGTH_NT:
                raise FASTAFormatError(
                    f"sequence of length {length}bp does not meet the"
                    " minimum allowed length of"
                    f" {config.INPUTS.FASTA_MAX_LENGTH_NT}bp (sequence"
                    f" ##{count})"
                )
            if length > config.INPUTS.FASTA_MAX_LENGTH_NT:
                raise FASTAFormatError(
                    f"sequence of length {length}bp exceeds the maximum"
                    f" allowed length of {config.INPUTS.FASTA_MAX_LENGTH_NT}bp"
                    f" (sequence ##{count})"
                )

    return seq_ids


def _validate_metadata(path: Path, seq_ids: list[str], bold=False):
    """Assert that input metadata CSV is valid.

    Each row['sample_id'] must match a sequence ID
    Locus must be listed in ALLOWED_LOCI
    Must contain required columns (see config.py - colnames configurable)
      - which are required?
    TOI list column should be pipe-delimited if multiple - validate chars?
    """
    sample_ids = []
    columns = config.INPUTS.METADATA_CSV_HEADER
    with path.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)  # skip header row
    for i, row in enumerate(rows):
        missing_cols = set(columns.values()) - set(row.keys())
        if missing_cols:
            raise MetadataFormatError(
                "missing required column(s):" + ', '.join(missing_cols) + '.')
        sample_id = row[columns['sample_id']]
        if sample_id not in seq_ids:
            raise MetadataFormatError(
                f'sample ID "{sample_id}" listed in metadata CSV file is not'
                f' present in FASTA sequence IDs. All sample IDs must match a'
                ' FASTA sequence.'
            )
        for col_id, colname in columns.items():
            if (
                col_id in config.INPUTS.METADATA_CSV_REQUIRED_FIELDS
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
        _validate_metadata_sample_id(row[columns['sample_id']])
        _validate_metadata_locus(row[columns['locus']], bold=bold)
        _validate_metadata_preliminary_id(row[columns['preliminary_id']])
        _validate_metadata_taxa_of_interest(row[columns['taxa_of_interest']])
        _validate_metadata_country(row[columns['country']])
        _validate_metadata_host(row[columns['host']])
        sample_ids.append(sample_id)

    missing_ids = set(seq_ids) - set(sample_ids)
    if missing_ids:
        raise MetadataFormatError(
            'FASTA Sequence ID(s) were not found in the provided metadata CSV'
            ' file. All FASTA sequence IDs must match a sample ID in the'
            f' provided metadata CSV: {missing_ids}'
        )


def _validate_metadata_sample_id(value):
    """Alphanumeric, no spaces, limited special characters."""
    value = value.strip()
    invalid_match = re.search(r'[^A-z0-9_\-\.]', value)
    if invalid_match:
        char = invalid_match.group()
        raise MetadataFormatError(
            f'Invalid sample ID "{value}": character "{char}" is not'
            f' permitted in the sample ID.'
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
    value = value.strip()
    if not value:
        return None
    country_code = countries.get_code(value)
    if not country_code:
        raise MetadataFormatError(
            f'The country provided could not be recognised: "{value}"'
        )


def _validate_metadata_host(value):
    pass


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
