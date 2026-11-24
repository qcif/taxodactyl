# Offline Genbank

A local database of Genbank metadata, derived from local BLAST database(s)
and enriched with Genbank metadata.

## record_locus sparse storage

The `record_locus` table uses sparse storage. Only `present` and `unknown`
assessments are stored.

If an `(accession, locus_id)` pair has no row in `record_locus`, it represents
`absent`.

This avoids storing the full records × 31 loci cross product.

## Step 7: TaxID-level locus counts

`database/scripts/3_build_taxid_locus.py` builds the `taxid_locus` and
`build_info` tables from the Step 5 (`records`) and Step 6 (`loci` and
`record_locus`) tables in the existing DuckDB database.

### Requirements

- Python with `duckdb` installed.
- TaxonKit available on the machine running Step 7.
- An NCBI taxonomy dump containing `nodes.dmp`, `names.dmp`, `merged.dmp`,
  and `delnodes.dmp`.

The script runs TaxonKit locally; it does not use SSH or a persistent taxonomy
cache.

### Running Step 7

With the project Python environment activated, run the following from the
repository root to validate the source tables:

```bash
python database/scripts/3_build_taxid_locus.py \
  --db /path/to/core_nt_full.duckdb \
  --check-only
```

Then build the TaxID-level tables:

```bash
python database/scripts/3_build_taxid_locus.py \
  --db /path/to/core_nt_full.duckdb \
  --taxonkit /path/to/taxonkit \
  --taxdb /path/to/taxdump \
  --extraction-date YYYY-MM-DD \
  --core-nt-version "description from blastdbcmd -info"
```

Use the actual metadata extraction date and BLAST database description for
the two provenance arguments. The optional `--batch-size` argument (default:
`100000`) controls how many distinct TaxIDs are fetched from DuckDB at once.
TaxIDs are passed through a single TaxonKit process, and its output is parsed
once into a temporary TSV file.

### Output and TaxID handling

`taxid_locus` has one row per original TaxID in `records`. Each row contains:

- `taxid`, `resolved_taxid`, and `resolution_status`;
- taxonomy ranks from `rank_domain` to `rank_species`;
- `n_records` and numbered `locus_N` columns containing `present` counts.

`resolution_status` is one of `current`, `merged`, `deleted`, or `not_found`.
Original TaxIDs are retained so records can be traced back to the source.
For merged entries, `resolved_taxid` stores the current TaxID.

A query on `taxid` matches the original ID only. To include records originally
assigned to TaxIDs that were later merged, query `resolved_taxid` instead:

```sql
SELECT COALESCE(SUM(n_records), 0) AS n_records
FROM taxid_locus
WHERE resolved_taxid = 74109;
```

Taxonomy-rank queries can use columns such as `rank_genus` or `rank_species`.
Deleted and unresolved TaxIDs retain their record counts but may have no
rank values.

Locus IDs come from `database/scripts/config/locus_ids.json`. New active
loci use new IDs. The current Step 7 implementation keeps zero-filled
`locus_N` columns for retired IDs to keep the numbered schema stable.

`build_info` stores build provenance, table counts, `present` and `unknown`
pair totals, the derived `absent` pair total, and TaxID resolution counts.
The `absent` total follows the sparse title-classification convention; it
does not establish biological absence. The taxdump label is based on the
modification time of `nodes.dmp`, not an official taxonomy release identifier.

### Validation and rebuilds

Step 7 checks source-table consistency, permanent locus IDs, orphaned and
duplicate record–locus pairs, taxonomy coverage, and aggregate counts.
The output tables are replaced within a DuckDB transaction after validation.
Temporary taxonomy files are removed after the run, and no persistent cache
is reused on subsequent builds.

The full database still requires the Step 8 acceptance queries and Step 9
verification checks; successful development-sample tests do not replace
full-dataset validation.
