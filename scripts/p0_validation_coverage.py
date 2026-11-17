"""Validate the coverage taxa CSV for database coverage mode.

Writes a validated, de-duplicated coverage.csv and one query directory per
taxon, which downstream processes fan out over.
"""

import argparse
import csv
import logging
from pathlib import Path

from p0_validation import (
    _validate_metadata_classification,
    _validate_metadata_country,
    _validate_metadata_locus,
    _validate_metadata_taxa_of_interest,
    _validate_taxdbs,
)

from src.utils import existing_path
from src.utils import errors
from src.utils.config import Config
from src.utils.config.mappings import CLI_ARGS
from src.utils.errors import MetadataFormatError

config = Config()
logger = logging.getLogger(__name__)

OUTPUT_CSV_FILENAME = 'coverage.csv'
CSV_ENCODING = 'utf-8-sig'
ROW_FIELDS = ('taxon', 'locus', 'country', 'classification')


def main():
    args = _parse_args()
    config.update_from_args(args)
    _validate_taxdbs(args.taxdb_dir)
    validate_coverage_taxa(args.coverage_taxa)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Validate database coverage mode input."
    )
    parser.add_argument(
        f"--{CLI_ARGS['output_dir'].cli_name}",
        type=existing_path,
        default=config.output_dir,
        help=f"Path to output directory. Defaults to {config.output_dir}.",
    )
    parser.add_argument(
        f"--{CLI_ARGS['coverage_taxa_csv'].cli_name}",
        type=existing_path,
        help="Path to coverage taxa CSV input file.",
        required=True,
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
    return parser.parse_args()


def validate_coverage_taxa(path: Path) -> list[dict]:
    """Validate the CSV and write coverage.csv plus the query dirs.

    Returns the validated, de-duplicated rows.
    """
    rows = _read_rows(path)
    for i, row in enumerate(rows):
        try:
            _validate_row(row)
        except Exception as exc:
            raise MetadataFormatError(
                f"Error in row {i + 1} (taxon: {row['taxon']}): {exc}"
            ) from exc

    rows = _drop_duplicates(rows)
    if len(rows) > config.coverage_taxa_max:
        raise MetadataFormatError(
            f"too many taxa provided ({len(rows)} after removing duplicates)."
            f" A maximum of {config.coverage_taxa_max} taxa is allowed in"
            " database coverage mode."
        )

    _write_outputs(rows)
    return rows


def _read_rows(path: Path) -> list[dict]:
    """Read and normalise rows, keyed by the standard field names."""
    header = config.inputs.coverage_csv_header
    try:
        with path.open(newline='', encoding=CSV_ENCODING) as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            raw_rows = list(reader)
    except (csv.Error, UnicodeDecodeError) as exc:
        raise MetadataFormatError(f"could not read CSV file: {exc}") from exc

    missing = [
        header[field]
        for field in config.inputs.coverage_csv_required_fields
        if header[field] not in fieldnames
    ]
    if missing:
        raise MetadataFormatError(
            "missing required column(s): " + ', '.join(missing) + '.')
    if not raw_rows:
        raise MetadataFormatError("the CSV file contains no taxa.")

    return [
        {
            field: (raw.get(header[field]) or '').strip()
            for field in ROW_FIELDS
        }
        for raw in raw_rows
    ]


def _validate_row(row: dict):
    """Validate one row, before hashing (which assumes valid values)."""
    taxon = row['taxon']
    if not taxon:
        raise MetadataFormatError('a value is required for the taxon column.')
    if '|' in taxon:
        raise MetadataFormatError(
            f'Invalid taxon "{taxon}": only one taxon name is permitted per'
            ' row.'
        )
    _validate_metadata_taxa_of_interest(taxon)
    if not row['locus'] and not config.is_bold:
        raise MetadataFormatError(
            'a value is required for the locus column. To count whole-genome'
            ' records with no locus, please enter "NA".'
        )
    _validate_metadata_locus(row['locus'], bold=config.is_bold)
    _validate_metadata_country(row['country'])
    _validate_metadata_classification(row['classification'])


def _drop_duplicates(rows: list[dict]) -> list[dict]:
    """Keep the first row for each sample ID, warning about the rest."""
    seen = {}
    kept = []
    for i, row in enumerate(rows):
        sample_id = config.coverage_sample_id(row)
        if sample_id in seen:
            msg = (
                f"Row {i + 1} duplicates row {seen[sample_id] + 1} and was"
                f" ignored (taxon: {row['taxon']}, locus:"
                f" {row['locus'] or 'NA'}, country:"
                f" {row['country'] or '-'})."
            )
            logger.warning(msg)
            errors.write(errors.LOCATIONS.DB_COVERAGE, msg)
            continue
        seen[sample_id] = i
        kept.append(row)
    return kept


def _write_outputs(rows: list[dict]):
    """Write the validated CSV, then one query dir per row."""
    header = config.inputs.coverage_csv_header
    out_path = config.output_dir / OUTPUT_CSV_FILENAME
    with out_path.open('w', newline='') as f:
        writer = csv.DictWriter(
            f, fieldnames=[header[field] for field in ROW_FIELDS])
        writer.writeheader()
        for row in rows:
            writer.writerow({
                header[field]: row[field]
                for field in ROW_FIELDS
            })
    logger.info(f"{len(rows)} validated taxa written to {out_path}")

    # Query dirs are indexed by row number in the validated CSV
    config.inputs.coverage_taxa_csv = out_path
    config.__dict__.pop('coverage_rows', None)
    config.__dict__.pop('metadata', None)
    for ix, row in enumerate(rows):
        config.create_query_dir(ix, row['taxon'])


if __name__ == '__main__':
    main()
