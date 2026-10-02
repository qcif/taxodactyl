# Phase 1 Observations

## 2026-09-21 - core_nt metadata extraction

- `blastdbcmd -info` reported 122,597,681 BLAST sequences.
- The full metadata extraction using accession, taxid, length and title produced 134,731,779 rows.
- The compressed output passed `gzip -t`.
- All 134,731,779 extracted rows contained exactly four tab-separated fields.
- Investigation found that one BLAST OID can be associated with multiple accessions.
- For example, OID 19 returned both `MW989214.1` and `MZ064816.1`.
- Both records had taxid `2697049` and length `29763`, but different accessions and titles.
- Therefore, the accession-level metadata row count can be higher than the sequence count reported by `blastdbcmd -info`.

## 2026-09-22 - Development sample

- Created `core_nt_sample.tsv.gz` from the full metadata extraction.
- The sample contains 2,000,000 records.
- The compressed sample size is approximately 75 MB.
- Validation confirmed that all 2,000,000 rows contain exactly four tab-separated fields.
- Copied the sample from the QCIF VM to the local Windows development environment for Python/database development.
- The sample is a head sample rather than a random sample, so it is suitable for initial development but may not represent the full diversity of `core_nt`.

## 2026-10-01 - Step 5 loader prototype

- Started working on the Step 5 metadata loader using the 2-million-row development sample.
- The compressed TSV file is now being read sequentially with `gzip`, so the full file is not loaded into memory at once.
- Added checks to confirm that each row contains the expected four fields: accession, taxid, length and title.
- Added conversion of `taxid` and `length` to integers, with invalid numeric values counted as rejected records.
- Added counters for processed, valid and rejected rows, along with progress updates while the file is being read.
- Added a batch buffer and tested the flow using batches of 100 records.
- Connected the loader to DuckDB and inserted valid batches into the `records` table using `executemany()`.
- Tested the loader on 1,000 rows. All 1,000 rows were valid and inserted successfully, with no rejected records.
- Verified the result directly in DuckDB using `SELECT COUNT(*)`; the `records` table contained 1,000 rows, matching the loader's inserted count.