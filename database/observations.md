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

## 2026-10-15 - Step 5 DuckDB loader development test

- Tested the Step 5 DuckDB loader using the 2,000,000-row `core_nt_sample.tsv.gz` development sample.
- I have used a batch size of 50,000 records.
- Processed 2,000,000 rows successfully.
- 2,000,000 rows passed metadata validation.
- 0 rows were rejected.
- 2,000,000 records were inserted into the `records` table.
- DuckDB row count was 2,000,000.
- Distinct accession count was 2,000,000, matching the database row count.
- Distinct taxid count was 142,630.
- Minimum sequence length observed was 6.
- Maximum sequence length observed was 97,909,271.
- Duplicate-accession handling was tested separately using a controlled test file. The failed batch was rolled back and retried row-by-row, with the duplicate written to the reject log.
- The 2-million-row run output was also saved locally to `step5_2m_run.log`.
## Step 6 locus classification

- Loaded the locus registry from `scripts/config/loci.json`.
- The registry contains 31 distinct loci and 82 synonym rows.
- Both ambiguous and non-ambiguous synonyms are matched against record titles for Phase 1.
- Matching is case-insensitive and handles differences in spaces and hyphens.
- Word boundaries are used to avoid false-positive substring matches such as `act` inside `bacterial` or `its` inside `units`.
- Complete-genome titles are treated as `unknown` for all 31 loci because the title alone cannot reliably determine which individual loci are present.
- In the 2,000,000-record development sample, 53,210 records were identified as complete-genome records.
- These records produced 1,649,510 `unknown` rows, which equals 53,210 records × 31 loci.
- The `record_locus` table uses sparse storage. Only `present` and `unknown` rows are stored; a missing `(accession, locus_id)` pair represents `absent`.
- The final 2,000,000-record development run produced 2,066,022 rows in `record_locus`.
- Of these, 416,512 rows were classified as `present` and 1,649,510 rows as `unknown`.
- Final validation found 0 duplicate `(accession, locus_id)` pairs.
- Final validation found 0 orphan accessions in `record_locus`.
- All `record_locus` rows use `title` as the evidence source.
- The final database contained 31 distinct locus IDs and 82 locus synonym rows.
- During development, the initial matching approach was too slow for larger runs.
- The implementation was optimized to process records in 50,000-row batches, use Pandas for title processing, use a combined synonym matcher, and bulk insert sparse results into DuckDB.
- The optimized implementation successfully processed the complete 2,000,000-record development sample.