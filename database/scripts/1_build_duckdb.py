import argparse
import gzip
from itertools import islice
from pathlib import Path

import duckdb
import pandas as pd

argument_parser = argparse.ArgumentParser(
    description="Build the Phase 1 DuckDB records table from compressed metadata."
)

argument_parser.add_argument(
    "--in",
    dest="input_path",
    required=True,
    type=Path,
    help="Path to the compressed metadata TSV file.",
)

argument_parser.add_argument(
    "--out",
    dest="output_path",
    required=True,
    type=Path,
    help="Path to the output DuckDB database file.",
)

argument_parser.add_argument(
    "--limit",
    dest="row_limit",
    type=int,
    default=None,
    help="Optional maximum number of metadata rows to process.",
)


def validate_metadata_chunk(
    lines,
    processed_before_chunk,
    min_integer,
    max_integer,
):
    raw_lines = pd.Series(lines, dtype="object")
    tab_counts = raw_lines.str.count("\t")
    valid_structure_mask = tab_counts.eq(3)
    rejected_frames = []
    malformed_indices = raw_lines.index[~valid_structure_mask]
    if len(malformed_indices) > 0:
        malformed_rows = pd.DataFrame({
            "row_number": processed_before_chunk + malformed_indices + 1,
            "reason": "expected 4 fields",
        })
        rejected_frames.append(malformed_rows)
    valid_lines = raw_lines[valid_structure_mask]
    if valid_lines.empty:
        valid_records = pd.DataFrame(columns=[
            "row_number",
            "accession",
            "taxid",
            "length",
            "title",
        ])
        rejected_rows = pd.concat(rejected_frames, ignore_index=True)
        return valid_records, rejected_rows
    records = (
        valid_lines
        .str.rstrip("\n")
        .str.split("\t", n=3, expand=True)
    )
    records.columns = ["accession", "taxid", "length", "title"]
    records["row_number"] = processed_before_chunk + records.index + 1
    records["taxid_numeric"] = pd.to_numeric(records["taxid"], errors="coerce")
    records["length_numeric"] = pd.to_numeric(
        records["length"], errors="coerce"
    )
    taxid_integer_format = records["taxid"].str.strip(
    ).str.fullmatch(r"[+-]?\d+")
    length_integer_format = records["length"].str.strip(
    ).str.fullmatch(r"[+-]?\d+")
    missing_accession = records["accession"].str.strip().eq("")
    missing_taxid = ~missing_accession & records["taxid"].str.strip().eq("")
    invalid_numeric = (
        ~missing_accession
        & ~missing_taxid
        & (
            ~taxid_integer_format
            | ~length_integer_format
            | records["taxid_numeric"].isna()
            | records["length_numeric"].isna()
        )
    )
    out_of_range = (
        ~missing_accession
        & ~missing_taxid
        & ~invalid_numeric
        & (
            (records["taxid_numeric"] < min_integer)
            | (records["taxid_numeric"] > max_integer)
            | (records["length_numeric"] < min_integer)
            | (records["length_numeric"] > max_integer)
        )
    )
    valid_mask = ~(
        missing_accession
        | missing_taxid
        | invalid_numeric
        | out_of_range
    )
    rejection_rules = [
        (missing_accession, "missing accession"),
        (missing_taxid, "missing taxid"),
        (invalid_numeric, "invalid numeric metadata"),
        (out_of_range, "numeric value outside INTEGER range"),
    ]
    for mask, reason in rejection_rules:
        if mask.any():
            rejected_frames.append(pd.DataFrame({
                "row_number": records.loc[mask, "row_number"],
                "reason": reason,
            }))
    valid_records = records.loc[
        valid_mask,
        ["row_number", "accession", "taxid_numeric", "length_numeric", "title"],
    ].copy()

    valid_records = valid_records.rename(
        columns={"taxid_numeric": "taxid", "length_numeric": "length"}
    )
    valid_records["taxid"] = valid_records["taxid"].astype("int64")
    valid_records["length"] = valid_records["length"].astype("int64")
    if rejected_frames:
        rejected_rows = pd.concat(
            rejected_frames,
            ignore_index=True,
        ).sort_values("row_number")
    else:
        rejected_rows = pd.DataFrame(columns=["row_number", "reason"])
    return valid_records, rejected_rows


def insert_valid_chunk(database_connection, valid_records):
    if valid_records.empty:
        return 0, pd.DataFrame(columns=["row_number", "accession"])

    database_connection.register("valid_chunk", valid_records)
    duplicate_rows = database_connection.execute("""
        WITH ranked AS (
            SELECT
                row_number,
                accession,
                ROW_NUMBER() OVER (
                    PARTITION BY accession
                    ORDER BY row_number
                ) AS accession_rank
            FROM valid_chunk
        )
        SELECT ranked.row_number, ranked.accession
        FROM ranked
        LEFT JOIN records
            ON records.accession = ranked.accession
        WHERE records.accession IS NOT NULL
           OR ranked.accession_rank > 1
        ORDER BY ranked.row_number
    """).fetchdf()
    database_connection.execute("""
        INSERT INTO records (accession, taxid, length, title)
        SELECT
            ranked.accession,
            ranked.taxid,
            ranked.length,
            ranked.title
        FROM (
            SELECT
                accession,
                taxid,
                length,
                title,
                row_number,
                ROW_NUMBER() OVER (
                    PARTITION BY accession
                    ORDER BY row_number
                ) AS accession_rank
            FROM valid_chunk
        ) AS ranked
        LEFT JOIN records
            ON records.accession = ranked.accession
        WHERE ranked.accession_rank = 1
        AND records.accession IS NULL
    """)
    inserted_rows = len(valid_records) - len(duplicate_rows)
    database_connection.unregister("valid_chunk")
    return inserted_rows, duplicate_rows


arguments = argument_parser.parse_args()

input_path = arguments.input_path
database_path = arguments.output_path
row_limit = arguments.row_limit

reject_log_path = Path("rejected.tsv").resolve()

try:
    with gzip.open(input_path, "rt", encoding="utf-8") as input_file:
        input_file.read(1)
except (OSError, UnicodeDecodeError) as error:
    raise SystemExit(
        f"Unable to read input file '{input_path}': {error}"
    )

reject_log_file = reject_log_path.open("w", encoding="utf-8", newline="")

reject_log_file.write("row_number\treason\n")

database_connection = duckdb.connect(str(database_path))

database_connection.execute("DROP TABLE IF EXISTS records")

database_connection.execute("""
CREATE TABLE records(
accession TEXT PRIMARY KEY,
taxid INTEGER,
length INTEGER,
title TEXT)
""")

print(input_path)

processed_count = 0
valid_count = 0
rejected_count = 0
inserted_count = 0

progress_interval = 100_000
chunk_size = 50_000
MIN_DUCKDB_INTEGER = -2_147_483_648
MAX_DUCKDB_INTEGER = 2_147_483_647
with gzip.open(input_path, "rt", encoding="utf-8") as metadata_file:
    while True:
        if row_limit is not None:
            remaining_rows = row_limit - processed_count

            if remaining_rows <= 0:
                break

            rows_to_read = min(chunk_size, remaining_rows)
        else:
            rows_to_read = chunk_size

        lines = list(islice(metadata_file, rows_to_read))

        if not lines:
            break

        processed_before_chunk = processed_count
        processed_count += len(lines)

        valid_records, rejected_rows = validate_metadata_chunk(
            lines,
            processed_before_chunk,
            MIN_DUCKDB_INTEGER,
            MAX_DUCKDB_INTEGER,
        )

        valid_count += len(valid_records)
        rejected_count += len(rejected_rows)
        chunk_inserted, duplicate_rows = insert_valid_chunk(
            database_connection,
            valid_records,
        )

        inserted_count += chunk_inserted
        rejected_count += len(duplicate_rows)
        if not duplicate_rows.empty:
            duplicate_log = duplicate_rows.copy()
            duplicate_log["reason"] = (
                "duplicate accession "
                + duplicate_log["accession"].astype(str)
            )

        else:
            duplicate_log = pd.DataFrame(columns=["row_number", "reason"])

        chunk_rejections = pd.concat(
            [
                rejected_rows[["row_number", "reason"]],
                duplicate_log[["row_number", "reason"]],
            ],
            ignore_index=True,
        ).sort_values("row_number")

        if not chunk_rejections.empty:
            chunk_rejections.to_csv(
                reject_log_file,
                sep="\t",
                header=False,
                index=False,
            )
        if processed_count % progress_interval == 0:
            print("Processed so far:", processed_count)
print("Processed rows:", processed_count)
print("Valid rows:", valid_count)
print("Rejected rows:", rejected_count)
print("Inserted rows:", inserted_count)

database_row_count = database_connection.execute(
    "SELECT COUNT(*) FROM records"
).fetchone()[0]

# SANITY CHECKS:

distinct_accession_count = database_connection.execute(
    "SELECT COUNT(DISTINCT accession) FROM records"
).fetchone()[0]

distinct_taxid_count = database_connection.execute(
    "SELECT COUNT(DISTINCT taxid) FROM records"
).fetchone()[0]

min_max_length = database_connection.execute(
    "SELECT MIN(length), MAX(length) FROM records"
).fetchone()

print("Database rows:", database_row_count)

print("Distinct accessions:", distinct_accession_count)

print("Distinct taxids:", distinct_taxid_count)

print("Min length:", min_max_length[0])

print("Max length:", min_max_length[1])


reject_log_file.close()
