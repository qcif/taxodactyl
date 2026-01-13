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
    validate_err_msg = re.search(
        r'sample ID "(?P<sample_id>[^"]+)" '
        r'listed in metadata CSV file is not present',
        stderr)
    if validate_err_msg:
        logger.info("Parsed error: metadata_missing_sample | %s",
                    validate_err_msg.group("sample_id"))
        return ParsedError(
            type="metadata_missing_sample",
            message=stderr.strip(),
            sample_id=validate_err_msg.group("sample_id"),
        )

    validate_err_msg2 = re.search(
        r'Invalid sample ID "(?P<sample_id>[^"]+)"',
        stderr)
    if validate_err_msg2:
        logger.info("Parsed error: invalid_sample_id | %s",
                    validate_err_msg2.group("sample_id"))
        return ParsedError(
            type="invalid_sample_id",
            message=stderr.strip(),
            sample_id=validate_err_msg2.group("sample_id"),
        )

    validate_err_msg3 = re.search(
        r'Invalid Taxa of Interest: "(?P<value>[^"]+)"',
        stderr)
    if validate_err_msg3:
        value = validate_err_msg3.group("value")
        logger.info("Parsed error: invalid_taxa_of_interest | %s", value)
        message = f'Taxa of Interest "{value}" is invalid. '
        "Please provide a valid taxonomic name or remove it.",
        return ParsedError(
            type="invalid_taxa_of_interest",
            value=value,
            message=message,
        )

    validate_err_msg4 = re.search(
        r'Invalid Preliminary Morphology ID taxon "(?P<value>[^"]+)"',
        stderr
    )
    if validate_err_msg4:
        value = validate_err_msg4.group("value")
        logger.info("Parsed error: invalid_pmi | %s", value)
        message = "The Preliminary Morphology ID is invalid,"
        "Only letters (A–Z) and spaces are allowed. "
        "Please fix this in the metadata CSV."
        return ParsedError(
            type="invalid_pmi",
            value=value,
            message=message,
        )

    validate_err_msg5 = re.search(
        r'The country provided could not be recognised: "(?P<value>[^"]+)"',
        stderr
    )
    if validate_err_msg5:
        value = validate_err_msg5.group("value")
        logger.info("Parsed error: invalid_country | %s", value)
        suggestions = {
            "turkey": 'Use ISO alpha-2 code "TR".',
            "türkiye": 'Use ISO alpha-2 code "TR".',
            "hawaii": 'Hawaii is a US state. Please use "US".',
        }
        hint = suggestions.get(value.lower())
        message = (
            f'Country "{value}" is not recognised. '
            + (hint if hint else
                'Please replace it with a valid country name '
                'or ISO alpha-2 code.')
        )
        return ParsedError(
            type="invalid_country",
            value=value,
            message=message
        )

    validate_err_msg7 = re.search(
        r'missing required column\(s\):(?P<columns>[A-Za-z0-9_, ]+)\.',
        stderr
    )
    if validate_err_msg7:
        cols = [
            c.strip()
            for c in validate_err_msg7.group("columns").split(",")
        ]
        logger.info("Parsed error: invalid_required_columns | %s", cols)
        return ParsedError(
            type="invalid_required_columns",
            message=stderr.strip(),
            value=cols,
        )

    validate_err_msg8 = re.search(
        r'Locus "(?P<value>[^"]+)" is not in the list of permitted loci',
        stderr
    )
    if validate_err_msg8:
        value = validate_err_msg8.group("value")
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
            "Please fix the sequence length in your local FASTA file "
            "and upload the corrected file again."
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
        r'sequence of length (?P<actual>\d+)bp exceeds the maximum allowed length of (?P<max>\d+)bp '
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
            "Please shorten the sequence in your local FASTA file "
            "and upload the corrected file again."
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
