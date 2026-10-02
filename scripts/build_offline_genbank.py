import gzip
import duckdb 
from pathlib import Path


sample_metadata_path = Path.home() / "Downloads" / "core_nt_sample.tsv.gz"

test_database_path = Path.home() / "Downloads" / "offline_genbank_test.duckdb"

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

test_row_limit = 1000

progress_interval = 100

batch_size = 100

record_batch = []

with gzip.open(sample_metadata_path, "rt", encoding="utf-8") as metadata_file:
    for metadata_line in metadata_file:
        processed_count += 1

        metadata_fields = metadata_line.rstrip("\n").split("\t")

        if len(metadata_fields) == 4:
            accession, taxid, sequence_length, title = metadata_fields

            try:
                taxid = int(taxid)
                sequence_length = int(sequence_length)
                record_batch.append((accession,taxid,sequence_length,title))
                valid_count += 1
                if len(record_batch) == batch_size:
                    database_connection.executemany(
                          """
                            INSERT INTO records (accession, taxid, length, title)
                            VALUES (?, ?, ?, ?)
                            """,
                            record_batch,
                    )

                    inserted_count += len(record_batch)
                    record_batch.clear()
                
            except ValueError:
                rejected_count += 1
                print("Invalid numeric metadata")
        else:
            rejected_count += 1
            print("Invalid metadata row")
        if processed_count % progress_interval == 0:
            print("Processed so far:", processed_count)
        if processed_count == test_row_limit:
            break
        

print("Processed rows:", processed_count)
print("Valid rows:", valid_count)
print("Rejected rows:", rejected_count)
print("Records in batch:", len(record_batch))
print("Inserted rows:", inserted_count)

database_row_count = database_connection.execute(
    "SELECT COUNT(*) FROM records"
).fetchone()[0]

print("Database rows:", database_row_count)