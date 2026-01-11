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
from src.utils.config.mappings import CLI_ARGS
from src.utils.errors import FASTAFormatError, MetadataFormatError

import logging
logger = logging.getLogger("taxon.validate")
logging.basicConfig(
    level=logging.INFO,  # change to DEBUG when debugging
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

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
    config.update_from_args(args)
    _validate_taxdbs(args.taxdb_dir)
    ids = _validate_fasta(args.query_fasta)
    _validate_metadata(args.metadata_csv, ids, bold=args.bold)


def validate_inputs(
    metadata_csv: Path,
    query_fasta: Path,
    bold: bool = False,
    ignore_seq_count: bool = False,
):
    """Validate user inputs provided programatically."""
    args = argparse.Namespace(
        metadata_csv=metadata_csv,
        query_fasta=query_fasta,
        bold=bold,
    )
    config.update_from_args(args)
    _autofix_sample_id_spaces(
        metadata_path=metadata_csv,
        fasta_path=query_fasta,
    )
    _autofix_duplicate_fasta_ids(query_fasta)
    ids = _validate_fasta(args.query_fasta, ignore_seq_count=ignore_seq_count)
    _validate_metadata(
        args.metadata_csv,
        ids,
        bold=args.bold,
    )


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Validate user input."
    )
    parser.add_argument(
        f"--{CLI_ARGS['metadata_csv'].cli_name}",
        type=existing_path,
        help="Path to metadata.csv input file.",
        required=True,
    )
    parser.add_argument(
        f"--{CLI_ARGS['query_fasta'].cli_name}",
        type=existing_path,
        help="Path to queries.fasta input file.",
        required=True,
    )
    parser.add_argument(
        f"--{CLI_ARGS['taxdb_dir'].cli_name}",
        type=existing_path,
        help="Path to queries.fasta input file.",
        required=True,
    )
    parser.add_argument(
        "--bold",  # doesn't map to config
        action="store_true",
        help="Validate inputs for a BOLD analysis (accept blank locus field).",
    )
    parser.add_argument(
        f"--{CLI_ARGS['allowed_loci_file'].cli_name}",
        type=existing_path,
        help="Path to JSON file containing allowed loci definitions",
    )
    parser.add_argument(
        f"--{CLI_ARGS['fasta_max_sequences'].cli_name}",
        type=int,
        help="Maximum number of sequences allowed",
    )
    parser.add_argument(
        f"--{CLI_ARGS['fasta_min_length'].cli_name}",
        type=int,
        help="Minimum sequence length in nucleotides",
    )
    parser.add_argument(
        f"--{CLI_ARGS['fasta_max_length'].cli_name}",
        type=int,
        help="Maximum sequence length in nucleotides",
    )
    return parser.parse_args()


def _validate_fasta(path: Path, ignore_seq_count=False) -> list[str]:
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
                    f" #{count + 1} {seq.id})."
                    " Sequences must have unique identifiers that match a row"
                    " in the metadata CSV input."
                )
            seq_ids.append(seq.id)
            count = len(seq_ids)
            try:
                assert_dna(seq.seq)
            except FASTAFormatError as exc:
                raise FASTAFormatError(
                    f'invalid DNA in sequence #{count} {seq.id}: {exc}'
                ) from exc
            if (
                count > config.inputs.fasta_max_sequences
                and not ignore_seq_count
            ):
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

    return seq_ids


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
    """
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
        sample_id = row[columns['sample_id']]
        if sample_id not in seq_ids:
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
        _validate_metadata_sample_id(row[columns['sample_id']])
        _validate_metadata_locus(row[columns['locus']], bold=bold)
        _validate_metadata_preliminary_id(row[columns['preliminary_id']])
        _validate_metadata_taxa_of_interest(
            row.get(columns['taxa_of_interest']))
        _validate_metadata_country(row.get(columns['country']))
        _validate_metadata_host(row.get(columns['host']))
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
            f' permitted in the sample ID. Must be alphanumeric, underscore or'
            ' dash.'
        )


def _autofix_sample_id_spaces(
    metadata_path: Path,
    fasta_path: Path,
) -> bool:
    """
    Replace spaces with underscores in sample_id
    in BOTH metadata CSV and FASTA.
    Returns True if any change was made.
    """
    changed = False

    # --- CSV ---
    with metadata_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    for row in rows:
        sample_id = row.get(config.inputs.metadata_csv_header["sample_id"])
        if sample_id and " " in sample_id:
            row[config.inputs.metadata_csv_header["sample_id"]] = (
                sample_id.replace(" ", "_")
            )
            changed = True

    if changed:
        with metadata_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # --- FASTA ---
    records = list(SeqIO.parse(fasta_path, "fasta"))
    fasta_changed = False
    for rec in records:
        if " " in rec.description.strip():
            logger.debug("[FASTA BEFORE FIX] rec.id:", repr(rec.id))
            logger.debug(
                "[FASTA BEFORE FIX] rec.description.strip():",
                repr(rec.description.strip())
            )
            new_id = rec.description.strip().replace(" ", "_")
            rec.id = new_id
            rec.name = new_id
            rec.description = new_id
            fasta_changed = True
            logger.info(f"[FASTA FIX] Updated sequence ID: {new_id}")

    if fasta_changed:
        SeqIO.write(records, fasta_path, "fasta")

    return changed or fasta_changed


def _autofix_duplicate_fasta_ids(fasta_path: Path) -> bool:
    """
    Remove duplicate FASTA sequence IDs.
    Keeps the first occurrence.
    Returns True if any duplicates were removed.
    """
    records = list(SeqIO.parse(fasta_path, "fasta"))
    seen = set()
    unique = []
    duplicate_id_counts = {}
    changed = False

    for rec in records:
        if rec.id in seen:
            changed = True
            duplicate_id_counts[rec.id] += 1
            continue
        seen.add(rec.id)
        duplicate_id_counts[rec.id] = 1
        unique.append(rec)

    for seq_id, n in duplicate_id_counts.items():
        if n > 1:
            logger.warning(f"Duplicate sample id {seq_id} appears {n} times")

    if changed:
        SeqIO.write(unique, fasta_path, "fasta")
        for seq_id, n in duplicate_id_counts.items():
            if n > 1:
                logger.info(
                    f"Duplicate sample id after auto removing: "
                    f"{seq_id}: 1 time"
                )

    return changed


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
