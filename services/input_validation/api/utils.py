import tempfile
import sys
import os
import re
from pathlib import Path
from typing import List
import csv
from dataclasses import dataclass
from typing import Optional
import logging
logger = logging.getLogger("taxon.validate")

sys.path.append(
    str(Path(__file__).resolve().parents[3] / "scripts")
)
from p0_validation import validate_inputs

COUNTRY_SUGGESTIONS = {
    "turkey": 'Use ISO alpha-2 code "TR".',
    "türkiye": 'Use ISO alpha-2 code "TR".',
    "hawaii": 'Hawaii is a US state. Please use "US".',
}


@dataclass
class ValidationResult:
    ok: bool
    message: str
    error: Optional[str] = None
    exc: Optional[Exception] = None


@dataclass
class ParsedError:
    type: str
    message: str
    sample_id: Optional[str] = None
    value: Optional[str] = None


def save_upload_to_tempfile(upload_file) -> Path:
    # upload_file is Starlette UploadFile
    suffix = Path(upload_file.filename).suffix
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(path, 'wb') as out_f:
        content = upload_file.file.read()
        out_f.write(content)
    logger.debug("Saved upload to tempfile: %s", path)
    return Path(path)


def create_fasta_from_csv_sequence(metadata_csv: Path) -> Path:
    """
    Create a temporary FASTA file from a metadata CSV
    that contains a 'sequence' column.
    Returns the Path to the created FASTA file.
    """
    fd, fasta_path = tempfile.mkstemp(suffix=".fasta")
    os.close(fd)

    fasta_path = Path(fasta_path)

    with metadata_csv.open("r", encoding="utf-8") as f_csv, \
         fasta_path.open("w", encoding="utf-8") as f_fasta:

        reader = csv.DictReader(f_csv)

        for row in reader:
            sample_id = row.get("sample_id")
            sequence = row.get("sequence")

            if sample_id and sequence:
                f_fasta.write(f">{sample_id}\n")

                for i in range(0, len(sequence), 80):
                    f_fasta.write(sequence[i:i+80] + "\n")

    logger.debug(
        "Temporary FASTA created from CSV sequences: %s",
        fasta_path
    )

    return fasta_path


def run_p0_validation(
        metadata_csv: Path,
        query_fasta: Path) -> ValidationResult:
    """
    Run the p0_validation.py script as a subprocess
    and return (rc, stdout, stderr).
    script_path: path to scripts/p0_validation.py
    """
    try:
        logger.debug(
            "Calling validate_inputs | metadata=%s | fasta=%s",
            metadata_csv.name,
            query_fasta.name,
        )
        validate_inputs(
            metadata_csv=metadata_csv,
            query_fasta=query_fasta,
            ignore_seq_count=True,
        )
        return ValidationResult(
            ok=True,
            message="Validation passed",
        )
    except Exception as exc:
        # Capture exception message in stderr
        logger.error(
            "p0 validation exception",
            exc_info=True,
        )
        return ValidationResult(
            ok=False,
            message="Validation failed",
            error=str(exc),
            exc=exc,
        )


def parse_errors(stderr: str) -> ParsedError:
    """Try to parse known errors emitted by p0_validation
    and return structured info.
    """
    logger.debug("Parsing validation error output")
    missing_sample_id_msg = re.search(
        r'sample ID "(?P<sample_id>[^"]+)" '
        r'listed in metadata CSV file is not present',
        stderr)
    if missing_sample_id_msg:
        logger.info("Parsed error: metadata_missing_sample | %s",
                    missing_sample_id_msg.group("sample_id"))
        sample_id = missing_sample_id_msg.group("sample_id")
        message = (
            f'Sample ID "{sample_id}" appears in the metadata CSV '
            "but does not exist in the FASTA file.\n"
            "Please provide a valid taxonomic name or remove it."
        )
        return ParsedError(
            type="metadata_missing_sample",
            message=message,
            sample_id=missing_sample_id_msg.group("sample_id"),
        )

    invalid_toi_msg = re.search(
        r'Invalid Taxa of Interest: "(?P<value>[^"]+)"',
        stderr)
    if invalid_toi_msg:
        value = invalid_toi_msg.group("value")
        logger.info("Parsed error: invalid_taxa_of_interest | %s", value)
        message = (
            f'Taxa of Interest "{value}" is invalid. '
            "Please provide a valid taxonomic name or remove it."
        )
        return ParsedError(
            type="invalid_taxa_of_interest",
            value=value,
            message=message,
        )

    invalid_pmi_msg = re.search(
        r'Invalid Preliminary Morphology ID taxon "(?P<value>[^"]+)"',
        stderr
    )
    if invalid_pmi_msg:
        value = invalid_pmi_msg.group("value")
        logger.info("Parsed error: invalid_pmi | %s", value)
        message = (
            "The Preliminary Morphology ID is invalid,"
            "Only letters (A-Z) and spaces are allowed. "
            "Please fix this in the metadata CSV."
        )
        return ParsedError(
            type="invalid_pmi",
            value=value,
            message=message,
        )

    invalid_country_msg = re.search(
        r'The country provided could not be recognised: "(?P<value>[^"]+)"',
        stderr
    )
    if invalid_country_msg:
        value = invalid_country_msg.group("value")
        logger.info("Parsed error: invalid_country | %s", value)
        hint = COUNTRY_SUGGESTIONS.get(
            value.lower(),
            'Please replace it with a valid country name or ISO alpha-2 code.',
        )
        message = f'Country "{value}" is not recognised. {hint}'
        return ParsedError(
            type="invalid_country",
            value=value,
            message=message
        )

    invalid_column_msg = re.search(
        r'missing required column\(s\):(?P<columns>[A-Za-z0-9_, ]+)\.',
        stderr
    )
    if invalid_column_msg:
        cols = [
            c.strip()
            for c in invalid_column_msg.group("columns").split(",")
        ]
        logger.info("Parsed error: invalid_required_columns | %s", cols)
        message = f'Your CSV is missing required column(s): {", ".join(cols)}.'
        return ParsedError(
            type="invalid_required_columns",
            message=message,
            value=cols,
        )

    invalid_locus_msg = re.search(
        r'Locus "(?P<value>[^"]+)" is not in the list of permitted loci',
        stderr
    )
    if invalid_locus_msg:
        value = invalid_locus_msg.group("value")
        logger.info("Parsed error: invalid_locus | %s", value)
        message = (
            f'Locus "{value}" is invalid. '
            f'Please replace it with one of the permitted loci.'
        )
        return ParsedError(
            type="invalid_locus",
            value=value,
            message=message,
        )

    invalid_classification_msg = re.search(
        r'Invalid classification "(?P<value>[^"]+)"',
        stderr
    )

    if invalid_classification_msg:
        value = invalid_classification_msg.group("value")
        logger.info("Parsed error: invalid_classification | %s", value)

        message = (
            f'Classification "{value}" is invalid. '
            "Please replace it with one of the permitted values "
            "(animalia, plantae, fungi, chromista, "
            "bacteria, archaea, viruses)."
        )

        return ParsedError(
            type="invalid_classification",
            value=value,
            message=message,
        )

    # Generic FASTA errors
    fasta_min_count_err = re.search(
        r'sequence of length (?P<actual>\d+)bp does not meet '
        r'the minimum allowed length of (?P<min>\d+)bp '
        r'\(sequence #(?P<seq_num>\d+) (?P<seq_id>[^\)]+)\)',
        stderr
    )

    if fasta_min_count_err:
        actual = fasta_min_count_err.group("actual")
        minimum = fasta_min_count_err.group("min")
        seq_id = fasta_min_count_err.group("seq_id")

        logger.info(
            "Parsed error: invalid_fasta | seq=%s | len=%s | min=%s",
            seq_id, actual, minimum
        )

        message = (
            "The uploaded FASTA file contains an invalid sequence.\n\n"
            f"• Sequence ID: {seq_id}\n"
            f"• Sequence length: {actual} bp\n"
            f"• Minimum required length: {minimum} bp\n\n"
        )

        return ParsedError(
            type="invalid_fasta",
            message=message,
            sample_id=seq_id,
            value={
                "actual_length": int(actual),
                "minimum_length": int(minimum),
            }
        )

    fasta_max_length_err = re.search(
        r'sequence of length (?P<actual>\d+)bp exceeds '
        r'the maximum allowed length of (?P<max>\d+)bp '
        r'\(sequence #(?P<seq_num>\d+) (?P<seq_id>[^\)]+)\)',
        stderr
    )

    if fasta_max_length_err:
        actual = fasta_max_length_err.group("actual")
        maximum = fasta_max_length_err.group("max")
        seq_id = fasta_max_length_err.group("seq_id")

        logger.info(
            "Parsed error: invalid_fasta_max | seq=%s | len=%s | max=%s",
            seq_id, actual, maximum
        )

        message = (
            "The uploaded FASTA file contains a sequence that is too long.\n\n"
            f"• Sequence ID: {seq_id}\n"
            f"• Sequence length: {actual} bp\n"
            f"• Maximum allowed length: {maximum} bp\n\n"
        )

        return ParsedError(
            type="invalid_fasta",
            message=message,
            sample_id=seq_id,
            value={
                "actual_length": int(actual),
                "maximum_length": int(maximum),
            }
        )

    fasta_invalid_residues_err = re.search(
        r"FASTA format error: "
        r"invalid DNA in sequence #(?P<seq_num>\d+) (?P<seq_id>[\w\.\-]+): "
        r"FASTA format error: "
        r"Illegal DNA residue '(?P<residue>[^']+)' "
        r"at position (?P<pos>\d+)\.\s+"
        r"Permitted characters: (?P<permitted>\{[^\}]+\})",
        stderr
    )
    if fasta_invalid_residues_err:
        residue = fasta_invalid_residues_err.group("residue")
        pos = fasta_invalid_residues_err.group("pos")
        seq_id = fasta_invalid_residues_err.group("seq_id")
        permitted = fasta_invalid_residues_err.group("permitted")

        logger.info(
            "Parsed error: invalid_fasta (illegal residue) | "
            "seq=%s | residue=%s | pos=%s | permitted=%s",
            seq_id, residue, pos, permitted
        )

        message = (
            "The uploaded FASTA file contains an invalid DNA residue.\n\n"
            f"• Sequence ID: {seq_id}\n"
            f"• Illegal residue: '{residue}' at position {pos}\n"
            f"• Permitted characters: {permitted}\n\n"

        )

        return ParsedError(
            type="invalid_fasta",
            message=message,
            sample_id=seq_id,
            value={
                "residue": residue,
                "position": int(pos),
            }
        )

    # Fallback
    logger.error("Unknown validation error")
    return ParsedError(
        type="unknown",
        message=stderr.strip(),
    )


def find_taxa_zero_rows(metadata_csv_path: Path) -> List[int]:
    """
    Return indexes (0-based, data rows only) where taxa_of_interest == '0'
    """
    logger.debug("Scanning for taxa_of_interest == 0")
    bad_rows: list[int] = []

    with open(metadata_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if row.get("taxa_of_interest") == "0":
                logger.debug(
                    "taxa_of_interest=0 | row=%s | sample_id=%s",
                    idx,
                    row.get("sample_id"),
                )
                bad_rows.append(idx)

    logger.info("taxa_of_interest zero rows found | count=%s", len(bad_rows))
    return bad_rows


def find_invalid_pmi(metadata_csv_path: Path) -> List[int]:
    """
    Return indexes (0-based, data rows only) where preliminary_id
    contains invalid characters (anything not A-z or space)
    """
    logger.debug("Scanning for invalid PMI")
    invalid_pmi_rows: list[int] = []

    with open(metadata_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        col_name = 'preliminary_id'
        for idx, row in enumerate(reader):
            value = row.get(col_name, "").strip()
            if re.search(r'[^A-z ]', value):
                logger.debug(
                    "Invalid PMI | row=%s | value=%s | sample_id=%s",
                    idx,
                    value,
                    row.get("sample_id"),
                )
                invalid_pmi_rows.append(idx)

    logger.info("Invalid PMI rows found | count=%s", len(invalid_pmi_rows))
    return invalid_pmi_rows


def find_invalid_country_rows(
    metadata_csv_path: Path,
    bad_value: str
) -> List[int]:
    """
    Return indexes (0-based, data rows only) where country == bad_value
    """
    logger.debug("Scanning for invalid country | %s", bad_value)
    bad_rows: list[int] = []

    with open(metadata_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            value = (row.get("country") or "").strip()
            if value.lower() == bad_value.lower():
                logger.debug(
                    "Invalid country | row=%s | value=%s | sample_id=%s",
                    idx,
                    value,
                    row.get("sample_id"),
                )
                bad_rows.append(idx)

    logger.info("Invalid country rows found | count=%s", len(bad_rows))
    return bad_rows


def find_invalid_locus_rows(
    metadata_csv_path: Path,
    bad_value: str
) -> List[int]:
    """
    Return indexes (0-based, data rows only) where locus == bad_value
    """
    logger.debug("Scanning for invalid locus | %s", bad_value)
    bad_rows: list[int] = []

    with open(metadata_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            value = (row.get("locus") or "").strip()
            if value.lower() == bad_value.lower():
                logger.debug(
                    "Invalid locus | row=%s | value=%s | sample_id=%s",
                    idx,
                    value,
                    row.get("sample_id"),
                )
                bad_rows.append(idx)

    logger.info("Invalid locus rows found | count=%s", len(bad_rows))
    return bad_rows


def find_metadata_sample_mismatch_rows(
    metadata_csv_path: Path,
    missing_sample_id: str
) -> List[int]:
    """
    Find missing sample id in CSV and FASTA.
    """
    logger.debug(
        "Scanning for metadata sample_id not in FASTA | %s",
        missing_sample_id,
    )
    bad_rows: list[int] = []

    with open(metadata_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if (row.get("sample_id") or "").strip() == missing_sample_id:
                logger.debug(
                    "Metadata sample mismatch | row=%s | sample_id=%s",
                    idx,
                    missing_sample_id,
                )
                bad_rows.append(idx)

    logger.info(
        "Metadata sample mismatch rows found | sample_id=%s | count=%s",
        missing_sample_id,
        len(bad_rows),
    )
    return bad_rows


def find_invalid_classification_rows(
    metadata_csv_path: Path,
    bad_value: str
) -> List[int]:
    """
    Return indexes (0-based, data rows only)
    where classification == bad_value
    """
    logger.debug("Scanning for invalid classification | %s", bad_value)
    bad_rows: list[int] = []

    with open(metadata_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            value = (row.get("classification") or "").strip()
            if value.lower() == bad_value.lower():
                logger.debug(
                    "Invalid classification | row=%s "
                    "| value=%s | sample_id=%s",
                    idx,
                    value,
                    row.get("sample_id"),
                )
                bad_rows.append(idx)

    logger.info(
        "Invalid classification rows found | count=%s",
        len(bad_rows),
    )
    return bad_rows
