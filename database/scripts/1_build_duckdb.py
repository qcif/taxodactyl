import gzip
import duckdb 
from pathlib import Path

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
                    f"{batch_record[0]}\tduplicate accession {batch_record[1]}\n"
                )

    return inserted_rows, rejected_rows


sample_metadata_path = Path.home() / "Downloads" / "core_nt_sample.tsv.gz"

test_database_path = Path.home() / "Downloads" / "offline_genbank_test.duckdb"

reject_log_path = Path.home() / "Downloads" / "offline_genbank_rejects.tsv"

reject_log_file = reject_log_path.open("w",encoding="utf-8")

reject_log_file.write("row_number\treason\n")

database_connection = duckdb.connect (str(test_database_path))

database_connection.execute("DROP TABLE IF EXISTS records")

database_connection.execute("""
CREATE TABLE records(
accession TEXT PRIMARY KEY,
taxid INTEGER,
length INTEGER,
title TEXT)
""")

print(sample_metadata_path)

processed_count = 0

valid_count = 0

rejected_count = 0

inserted_count = 0

test_row_limit = 2_000_000

progress_interval = 100_000

batch_size = 50_000

record_batch = []

with gzip.open(sample_metadata_path, "rt", encoding="utf-8") as metadata_file:
    for metadata_line in metadata_file:
        processed_count += 1

        metadata_fields = metadata_line.rstrip("\n").split("\t")

        if len(metadata_fields) == 4:
            accession, taxid, sequence_length, title = metadata_fields
            if taxid.strip() =="":
                rejected_count+=1
                reject_log_file.write(
                    f"{processed_count}\tmissing taxid\n"
                )
            else:
                try:
                            taxid = int(taxid)
                            sequence_length = int(sequence_length)
                            record_batch.append((processed_count,accession,taxid,sequence_length,title))
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
        if processed_count == test_row_limit:
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