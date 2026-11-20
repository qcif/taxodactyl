"""Validate user inputs."""

import argparse
import csv
import os
import re
from collections import defaultdict
from pathlib import Path
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.Data import IUPACData

from src.utils import countries, existing_path
from src.utils.config import Config
from src.utils.config.config import LOCUS_GENE_SUFFIX_RE
from src.utils.config.mappings import CLI_ARGS
from src.utils.encoding import (
    BETA,
    BETA_ASCII,
    fix_eszett_in_column,
    fix_eszett_in_fasta_headers,
    normalise_csv_encoding,
)
from src.utils.errors import FASTAFormatError, MetadataFormatError

import logging
logger = logging.getLogger("taxon.validate")
logging.basicConfig(
    level=logging.INFO,  # change to DEBUG when debugging
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


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
# Characters not permitted in the locus suffix of a multi-locus sample ID
LOCUS_SUFFIX_ILLEGAL_CHARS_RE = re.compile(r'[^A-Za-z0-9.\-]+')


def main():
    args = _parse_args()
    config.update_from_args(args)
    _validate_taxdbs(args.taxdb_dir)
    _autofix_metadata_encoding(args.metadata_csv, args.query_fasta)
    _autofix_multi_locus_sample_ids(args.metadata_csv, args.query_fasta)
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
    _autofix_metadata_encoding(metadata_csv, query_fasta)
    _autofix_sample_id_spaces(
        metadata_path=metadata_csv,
        fasta_path=query_fasta,
    )
    _autofix_multi_locus_sample_ids(metadata_csv, query_fasta)
    _autofix_duplicate_fasta_ids(query_fasta)
    ids = _validate_fasta(args.query_fasta, ignore_seq_count=ignore_seq_count)
    _validate_metadata(
        args.metadata_csv,
        ids,
        bold=args.bold,
    )


def _autofix_metadata_encoding(
    metadata_path: Path,
    fasta_path: Path | None = None,
):
    """Convert the metadata CSV to UTF-8 and fix "ß" typed for "β".

    Locus names get the Greek letter (ß-tub -> β-tub). Sample IDs must be
    ASCII so become "beta", in the FASTA headers too, so that they match.
    """
    normalise_csv_encoding(metadata_path)
    header = config.inputs.metadata_csv_header
    fix_eszett_in_column(metadata_path, header['locus'])
    if fix_eszett_in_column(metadata_path, header['sample_id'], BETA_ASCII):
        if fasta_path:
            fix_eszett_in_fasta_headers(fasta_path)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Validate user input."
    )
    parser.add_argument(
        f"--{CLI_ARGS['output_dir'].cli_name}",
        type=existing_path,
        default=config.output_dir,
        help=f"Path to output directory. Defaults to {config.output_dir}.",
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
        required=False,
    )
    parser.add_argument(
        f"--{CLI_ARGS['taxdb_dir'].cli_name}",
        type=existing_path,
        help="Path to NCBI taxdump directory (for taxonkit).",
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
    Each row['sample_id'] must be unique
    Locus must be listed in ALLOWED_LOCI
    Must contain required columns (see config.py - colnames configurable)
      - which are required?
    TOI list column should be pipe-delimited if multiple - validate chars?

    If sequence column exists, validate that it contains valid DNA sequences
    and write them to OUTPUT_FASTA_FILENAME.
    """
    expect_seq_col = seq_ids is None
    sample_ids = []
    sample_id_rows = {}
    columns = config.inputs.metadata_csv_header
    with path.open(encoding='utf-8') as f:
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
        if sample_id in sample_id_rows:
            raise MetadataFormatError(
                f'Duplicate sample ID "{sample_id}" in rows'
                f' {sample_id_rows[sample_id]} and {i + 1} of the metadata'
                ' CSV file. Each sample ID must be unique. A sample ID may'
                ' only be repeated to submit the same sample at different'
                ' loci, with one row (and one FASTA sequence) per locus.'
            )
        sample_id_rows[sample_id] = i + 1
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
            _validate_metadata_classification(
                row.get(columns['classification']))
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

    sample_id_col = config.inputs.metadata_csv_header["sample_id"]
    for row in rows:
        sample_id = row.get(sample_id_col)
        if sample_id and " " in sample_id:
            fixed_sample_id = sample_id.replace(" ", "_")
            row[sample_id_col] = fixed_sample_id
            changed = True

    if changed:
        with metadata_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    csv_sample_ids = {
        row[sample_id_col] for row in rows if row.get(sample_id_col)
    }

    # --- FASTA ---
    records = list(SeqIO.parse(fasta_path, "fasta"))
    fasta_changed = False
    for rec in records:
        description = rec.description.strip()
        candidate_sample_id = description.replace(" ", "_")
        if (
            candidate_sample_id in csv_sample_ids and
            rec.id != candidate_sample_id
        ):
            logger.debug("[FASTA BEFORE FIX] rec.id:", repr(rec.id))
            logger.debug(
                "[FASTA BEFORE FIX] rec.description.strip():",
                repr(description)
            )
            logger.info(
                f"[FASTA FIX] {rec.id} -> {candidate_sample_id}"
            )
            rec.id = candidate_sample_id
            rec.name = candidate_sample_id
            rec.description = candidate_sample_id
            fasta_changed = True
            logger.info(
                f"[FASTA FIX] Updated sequence ID: "
                f"{candidate_sample_id}")

    if fasta_changed:
        SeqIO.write(records, fasta_path, "fasta")

    return changed or fasta_changed


def _autofix_multi_locus_sample_ids(
    metadata_path: Path,
    fasta_path: Path | None = None,
) -> bool:
    """Rename a sample ID repeated at different loci to "<id>_<locus>".

    Users may submit one sample at several loci, which repeats its sample ID
    across metadata rows (and FASTA records). Each of those rows is renamed
    to "<sample_id>_<locus>". FASTA records with that ID are renamed in the
    order they appear: the nth record gets the nth row's new ID.

    A repeated ID is left unchanged, to be rejected by validation, when two
    of its rows share a locus, a locus is blank, the FASTA holds a different
    number of records with that ID, or a new ID is already in use.

    Returns True if any sample ID was renamed.
    """
    header = config.inputs.metadata_csv_header
    sample_id_col = header['sample_id']
    locus_col = header['locus']
    with metadata_path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if sample_id_col not in fieldnames or locus_col not in fieldnames:
        return False

    row_ixs = defaultdict(list)
    for i, row in enumerate(rows):
        if row[sample_id_col]:
            row_ixs[row[sample_id_col]].append(i)
    fasta_records = (
        list(SeqIO.parse(fasta_path, 'fasta'))
        if fasta_path
        else None
    )
    taken_ids = set(row_ixs)
    renames = {}
    for sample_id, ixs in row_ixs.items():
        if len(ixs) < 2:
            continue
        new_ids = _multi_locus_sample_ids(
            sample_id,
            [rows[i][locus_col] for i in ixs],
        )
        if not new_ids:
            continue
        if taken_ids & set(new_ids):
            logger.warning(
                f'Sample ID "{sample_id}" is repeated at different loci but'
                ' could not be renamed: one of the new IDs'
                f' {new_ids} is already in use.'
            )
            continue
        if fasta_records is not None:
            fasta_count = sum(rec.id == sample_id for rec in fasta_records)
            if fasta_count != len(ixs):
                logger.warning(
                    f'Sample ID "{sample_id}" is repeated at different loci'
                    f' but could not be renamed: it has {len(ixs)} metadata'
                    f' rows and {fasta_count} FASTA sequences.'
                )
                continue
        taken_ids.update(new_ids)
        renames[sample_id] = new_ids

    if not renames:
        return False

    for sample_id, new_ids in renames.items():
        for i, new_id in zip(row_ixs[sample_id], new_ids):
            rows[i][sample_id_col] = new_id
        logger.warning(
            f'Sample ID "{sample_id}" is repeated at different loci and was'
            f' renamed to: {", ".join(new_ids)}'
        )
    with metadata_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    if fasta_records is not None:
        new_id_queues = {
            sample_id: iter(new_ids)
            for sample_id, new_ids in renames.items()
        }
        for rec in fasta_records:
            if rec.id in new_id_queues:
                new_id = next(new_id_queues[rec.id])
                rec.id = rec.name = rec.description = new_id
        SeqIO.write(fasta_records, fasta_path, 'fasta')

    return True


def _multi_locus_sample_ids(
    sample_id: str,
    loci: list[str],
) -> list[str] | None:
    """Return "<sample_id>_<locus>" for each locus, if the loci all differ.

    Loci are compared by their canonical allowed locus, so synonyms (e.g.
    COI and COX1) count as the same locus. Returns None if any locus is
    blank or two loci are the same.
    """
    if any(not locus.strip() for locus in loci):
        return None
    keys = []
    for locus in loci:
        resolved = config._resolve_locus(locus)
        keys.append(
            resolved.name.lower()
            if resolved
            else _locus_suffix(locus).lower()
        )
    new_ids = [f'{sample_id}_{_locus_suffix(locus)}' for locus in loci]
    if (
        len(set(keys)) < len(keys)
        or len(set(new_ids)) < len(new_ids)
    ):
        return None
    return new_ids


def _locus_suffix(locus: str) -> str:
    """Make a locus safe to append to a sample ID (e.g. "β-tub gene")."""
    locus = LOCUS_GENE_SUFFIX_RE.sub('', locus.strip())
    locus = locus.replace(BETA, BETA_ASCII)
    return LOCUS_SUFFIX_ILLEGAL_CHARS_RE.sub('_', locus).strip('_')


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
