
# Creating a subset BLAST database

For test purposes, a small BLAST database can be created from the full database for a test case. It requires that the test case has been run with the database that will be used to subset from. 

#### Extract accession IDs

Use `bin/extract_accessions.py` to extract accession IDs from the output `blast_result.xml` for the test case.

Alternatively, use the `accessions.txt` file from the `TAXODACTYL:EXTRACT_HITS` work folder.

#### Create `.fasta` of sequences

From database directory (`/home/ubuntu/blastdbs/2026-05-12`), do:
```bash
blastdbcmd \
	-db core_nt \ # Name of database
	-entry_batch /path/to/accessions \
	-outfmt "%f" \
	-target_only > test_case_subset_core_nt.fasta
```

#### Create accession-to-taxid map for the same entries

```bash
blastdbcmd \
	-db core_nt \
	-entry_batch /path/to/accessions \
	-outfmt "%a %T" \
	-target_only > test_case_subset_core_nt.taxid_map.tsv
```

#### Build a new subset BLAST DB 

```bash
makeblastdb \
	-in test_case_subset_core_nt.fasta \
	-dbtype nucl \
	-parse_seqids \
	-taxid_map test_case_subset_core_nt.taxid_map.tsv \
	-out test_case_subset_core_nt
```

#### Notes
- This creates a real BLAST DB with only those records.  
- Keep `-parse_seqids`, otherwise accession lookups by `blastdbcmd` may fail.  
- Keep `-target_only` when preparing the `.fasta` and `.tsv` so redundant group members are excluded from the list (can result in concatenated headers where lookups fail).

Example accessions file to use for `-entry_batch`:
```
KT852368
KJ085144
ON754481
KR476578
MG469846
MN549844
...
```

