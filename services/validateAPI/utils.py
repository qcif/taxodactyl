import tempfile
import sys
import os
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any
import csv
from Bio import SeqIO

sys.path.append(
    str(Path(__file__).resolve().parents[2] / "scripts")
)
from p0_validation import validate_inputs


def save_upload_to_tempfile(upload_file) -> Path:
    # upload_file is Starlette UploadFile
    suffix = Path(upload_file.filename).suffix
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(path, 'wb') as out_f:
        content = upload_file.file.read()
        out_f.write(content)
    return Path(path)


def run_p0_validation(
        script_path: Path,
        metadata_csv: Path,
        query_fasta: Path,
        taxdb_dir: Path | None = None,
        extra_args: list[str] = []) -> Tuple[int, str, str]:
    """
    Run the p0_validation.py script as a subprocess
    and return (rc, stdout, stderr).
    script_path: path to scripts/p0_validation.py
    """
    try:
        validate_inputs(
            metadata_csv=metadata_csv,
            query_fasta=query_fasta,
            ignore_seq_count=True,
        )
        return 0, "Validation passed", ""
    except Exception as exc:
        # Capture exception message in stderr
        return 1, "", str(exc)


def parse_errors(stderr: str) -> Dict[str, Any]:
    """Try to parse known errors emitted by p0_validation
    and return structured info.
    """
    validate_err_msg = re.search(
        r'sample ID "(?P<sample_id>[^"]+)" '
        r'listed in metadata CSV file is not present',
        stderr)
    if validate_err_msg:
        return {
            "type": "metadata_missing_sample",
            "message": stderr.strip(),
            "sample_id": validate_err_msg.group('sample_id')
        }

    validate_err_msg2 = re.search(
        r'Invalid sample ID "(?P<sample_id>[^"]+)"',
        stderr)
    if validate_err_msg2:
        return {
            "type": "invalid_sample_id",
            "message": stderr.strip(),
            "sample_id": validate_err_msg2.group('sample_id')
        }

    validate_err_msg3 = re.search(
        r'Invalid Taxa of Interest: "(?P<value>[^"]+)"',
        stderr)
    if validate_err_msg3:
        value = validate_err_msg3.group("value")
        return {
            "type": "invalid_taxa_of_interest",
            "value": value,
            "message": (
                f'Taxa of Interest "{value}" is invalid. '
                "Please provide a valid taxonomic name or remove it."
            )
        }

    validate_err_msg4 = re.search(
        r'Invalid Preliminary Morphology ID taxon "(?P<value>[^"]+)"',
        stderr
    )
    if validate_err_msg4:
        value = validate_err_msg4.group("value")
        return {
            "type": "invalid_pmi",
            "value": value,
            "message": (
                "The Preliminary Morphology ID is invalid,"
                "Only letters (A–Z) and spaces are allowed. "
                "Please fix this in the metadata CSV."
            )
        }

    validate_err_msg5 = re.search(
        r'The country provided could not be recognised: "(?P<value>[^"]+)"',
        stderr
    )
    if validate_err_msg5:
        value = validate_err_msg5.group("value")
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
        return {
            "type": "invalid_country",
            "value": value,
            "message": message
        }

    # Generic FASTA errors
    if 'FASTAFormatError' in stderr:
        return {"type": "fasta_error", "message": stderr.strip()}

    # Fallback
    return {"type": "unknown", "message": stderr.strip()}


def fix_sample_id_spaces(
        metadata_path: Path,
        fasta_path: Path,
        bad_sample_id: str):
    """
    Replace spaces with underscores in sample_id
    in BOTH metadata CSV and FASTA.
    """
    fixed_sample_id = bad_sample_id.replace(" ", "_")

    # Fix CSV
    with open(metadata_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    changed = False
    for row in rows:
        space_in_id = row.get("sample_id", "")
        if " " in space_in_id:
            row["sample_id"] = space_in_id.replace(" ", "_")
            changed = True

    if changed:
        with open(metadata_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # Fix FASTA
    records = list(SeqIO.parse(fasta_path, "fasta"))
    changed = False
    for rec in records:
        print("[DEBUG] rec.id:", repr(rec.id))
        print("[DEBUG] rec.name:", repr(rec.name))
        print("[DEBUG] rec.description.strip():",
              repr(rec.description.strip()))
        if " " in rec.description.strip():
            new_id = rec.description.strip().replace(" ", "_")
            rec.id = new_id
            rec.name = new_id
            rec.description = new_id
            changed = True
            print("[DEBUG] rec.id:", repr(rec.id))
            print("[DEBUG] rec.description.strip():",
                  repr(rec.description.strip()))

    if not changed:
        print(f"[WARN] No FASTA record matched '{bad_sample_id}'")

    SeqIO.write(records, fasta_path, "fasta")

    return fixed_sample_id


def find_taxa_zero_rows(metadata_csv_path: Path) -> List[int]:
    """
    Return indexes (0-based, data rows only) where taxa_of_interest == '0'
    """
    bad_rows: list[int] = []

    with open(metadata_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if row.get("taxa_of_interest") == "0":
                bad_rows.append(idx)

    return bad_rows


def find_invalid_pmi(metadata_csv_path: Path) -> List[int]:
    """
    Return indexes (0-based, data rows only) where preliminary_id
    contains invalid characters (anything not A-z or space)
    """
    brackets_rows: list[int] = []

    with open(metadata_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        col_name = 'preliminary_id'
        for idx, row in enumerate(reader):
            value = row.get(col_name, "").strip()
            if re.search(r'[^A-z ]', value):
                brackets_rows.append(idx)

    return brackets_rows


def find_invalid_country_rows(
    metadata_csv_path: Path,
    bad_value: str
) -> List[int]:
    """
    Return indexes (0-based, data rows only) where country == bad_value
    """
    bad_rows: list[int] = []

    with open(metadata_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            value = (row.get("country") or "").strip()
            if value.lower() == bad_value.lower():
                bad_rows.append(idx)

    return bad_rows
