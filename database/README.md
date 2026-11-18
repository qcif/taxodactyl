# Offline Genbank

A local database of Genbank metadata, derived from local BLAST database(s)
and enriched with Genbank metadata.

## record_locus sparse storage

The `record_locus` table uses sparse storage. Only `present` and `unknown`
assessments are stored.

If an `(accession, locus_id)` pair has no row in `record_locus`, it represents
`absent`.

This avoids storing the full records × 31 loci cross product.