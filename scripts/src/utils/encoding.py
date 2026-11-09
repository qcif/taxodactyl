"""Detect and repair the text encoding of user-provided CSV files."""

import codecs
import csv
import logging
from pathlib import Path

from src.utils.errors import MetadataFormatError

logger = logging.getLogger(__name__)

ZIP_MAGIC = b'PK\x03\x04'
UTF16_BOMS = (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)
ENCODING_UTF8 = 'utf-8'
ENCODING_UTF8_BOM = 'utf-8-sig'
ENCODING_UTF16 = 'utf-16'
# Tried in order after UTF-8. Excel on Windows typically writes cp1252;
# latin-1 maps every byte so it is the last resort and never fails.
FALLBACK_ENCODINGS = ('cp1252', 'latin-1')
EXCEL_WORKBOOK_ERROR = (
    'the file appears to be an Excel workbook (.xlsx) with a .csv extension.'
    ' Please re-export it using "CSV UTF-8 (Comma delimited)".'
)
# Greek small beta is often typed as German eszett, e.g. "ß-tub".
ESZETT = 'ß'
BETA = 'β'
BETA_ASCII = 'beta'  # sample IDs must be ASCII


def decode_csv_bytes(data: bytes) -> tuple[str, str]:
    """Decode CSV bytes of unknown encoding.

    Returns (text, encoding), where encoding is the name of the codec that
    was used. Raises MetadataFormatError if the data is an Excel workbook.
    """
    if data.startswith(ZIP_MAGIC):
        raise MetadataFormatError(EXCEL_WORKBOOK_ERROR)
    if data.startswith(UTF16_BOMS):
        return data.decode(ENCODING_UTF16), ENCODING_UTF16
    if data.startswith(codecs.BOM_UTF8):
        return data.decode(ENCODING_UTF8_BOM), ENCODING_UTF8_BOM
    for encoding in (ENCODING_UTF8, *FALLBACK_ENCODINGS):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise AssertionError('unreachable: latin-1 decodes any byte sequence')


def normalise_csv_encoding(path: Path) -> str | None:
    """Convert a CSV file to UTF-8 (no BOM, LF line endings) in place.

    Files that are already plain UTF-8 are left untouched. Returns the name
    of the source encoding if the file was rewritten, otherwise None.
    """
    text, encoding = decode_csv_bytes(path.read_bytes())
    if encoding == ENCODING_UTF8:
        return None
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    path.write_text(text, encoding=ENCODING_UTF8, newline='')
    logger.warning(
        'Metadata CSV was encoded as %s and has been converted to UTF-8.',
        encoding,
    )
    return encoding


def fix_eszett_in_column(
    path: Path,
    column: str,
    replacement: str = BETA,
) -> bool:
    """Replace "ß" with the replacement in the named column of a UTF-8 CSV.

    Returns True if the file was changed.
    """
    with path.open(newline='', encoding=ENCODING_UTF8) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    changed = False
    for row in rows:
        value = row.get(column)
        if value and ESZETT in value:
            row[column] = value.replace(ESZETT, replacement)
            changed = True

    if changed:
        with path.open('w', newline='', encoding=ENCODING_UTF8) as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        logger.warning(
            'Replaced "%s" with "%s" in metadata column "%s".',
            ESZETT, replacement, column,
        )
    return changed


def fix_eszett_in_fasta_headers(path: Path) -> bool:
    """Replace "ß" with "beta" in FASTA header lines, rewriting as UTF-8.

    Keeps sequence IDs consistent with sample IDs fixed in the metadata CSV.
    Returns True if the file was changed.
    """
    text, _ = decode_csv_bytes(path.read_bytes())
    lines = text.splitlines(keepends=True)
    changed = False
    for i, line in enumerate(lines):
        if line.startswith('>') and ESZETT in line:
            lines[i] = line.replace(ESZETT, BETA_ASCII)
            changed = True
    if changed:
        path.write_text(''.join(lines), encoding=ENCODING_UTF8, newline='')
        logger.warning(
            'Replaced "%s" with "%s" in FASTA sequence IDs.',
            ESZETT, BETA_ASCII,
        )
    return changed
