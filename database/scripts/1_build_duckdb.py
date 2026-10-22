import argparse
import gzip
from pathlib import Path

import duckdb

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


def insert_record_batch(database_connection, record_batch, reject_log_file):
    inserted_rows = 0
    rejected_rows = 0

    database_batch = []

    for batch_record in record_batch:
        database_batch.append(batch_record[1:])

    database_connection.execute("BEGIN TRANSACTION")

    try:
        database_connection.executemany(
            """
            INSERT INTO records (accession, taxid, length, title)
            VALUES (?, ?, ?, ?)
            """,
            database_batch,
        )

        database_connection.execute("COMMIT")
        inserted_rows = len(record_batch)

    except duckdb.ConstraintException:
        database_connection.execute("ROLLBACK")

        for batch_record in record_batch:
            try:
                database_connection.execute(
                    """
                    INSERT INTO records (accession, taxid, length, title)
                    VALUES (?, ?, ?, ?)
                    """,
                    batch_record[1:]
                )

                inserted_rows += 1

            except duckdb.ConstraintException:
                rejected_rows += 1
                reject_log_file.write(
                    f"{batch_record[0]}\tduplicate accession "
                    f"{batch_record[1]}\n"
                )

    return inserted_rows, rejected_rows


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

reject_log_file = reject_log_path.open("w", encoding="utf-8")

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
batch_size = 50_000
record_batch = []
MIN_DUCKDB_INTEGER = -2_147_483_648
MAX_DUCKDB_INTEGER = 2_147_483_647

with gzip.open(input_path, "rt", encoding="utf-8") as metadata_file:
    for metadata_line in metadata_file:
        processed_count += 1

        metadata_fields = metadata_line.rstrip("\n").split("\t")

        if len(metadata_fields) == 4:
            accession, taxid, sequence_length, title = metadata_fields
            if accession.strip() == "":
                rejected_count += 1
                reject_log_file.write(
                    f"{processed_count}\tmissing accession\n"
                )
            elif taxid.strip() == "":
                rejected_count += 1
                reject_log_file.write(
                    f"{processed_count}\tmissing taxid\n"
                )
            else:
                try:
                    taxid = int(taxid)
                    sequence_length = int(sequence_length)

                    if not (
                       MIN_DUCKDB_INTEGER <= taxid <= MAX_DUCKDB_INTEGER
                       and MIN_DUCKDB_INTEGER <= sequence_length <= MAX_DUCKDB_INTEGER
                       ):
                        rejected_count += 1
                        reject_log_file.write(
                            f"{processed_count}\tnumeric value outside INTEGER range\n"
                        )
                    else:
                        record_batch.append(
                            (processed_count, accession,
                             taxid, sequence_length, title)
                        )
                        valid_count += 1

                        if len(record_batch) == batch_size:
                            batch_inserted, batch_rejected = insert_record_batch(
                                database_connection,
                                record_batch,
                                reject_log_file,
                            )
                            inserted_count += batch_inserted
                            rejected_count += batch_rejected
                            record_batch.clear()

                except ValueError:
                    rejected_count += 1
                    reject_log_file.write(
                        f"{processed_count}\tinvalid numeric metadata\n"
                    )
                    print("Invalid numeric metadata")
        else:
            rejected_count += 1
            reject_log_file.write(
                f"{processed_count}\texpected 4 fields\n")
            print("Invalid metadata row")
        if processed_count % progress_interval == 0:
            print("Processed so far:", processed_count)
        if row_limit is not None and processed_count >= row_limit:
            break
if record_batch:
    batch_inserted, batch_rejected = insert_record_batch(
        database_connection,
        record_batch,
        reject_log_file,
    )
    inserted_count += batch_inserted
    rejected_count += batch_rejected
    record_batch.clear()

print("Processed rows:", processed_count)
print("Valid rows:", valid_count)
print("Rejected rows:", rejected_count)
print("Records in batch:", len(record_batch))
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
