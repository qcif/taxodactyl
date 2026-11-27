# Offline GenBank Phase 1 — Final Handover

## Overview

This document summarises my Phase 1 work on the offline GenBank
metadata database, the checks I completed and the remaining issues.

## Completed work

I worked on three stages of the database pipeline:

- Step 5: Building the `records` table from compressed metadata.
- Step 6: Creating the locus registry and classifying record titles.
- Step 7: Resolving TaxIDs and building aggregated taxonomy counts.

The full build produced 134,731,779 accession-level records.
The sparse `record_locus` table contained 28,003,624 present and
113,701,366 unknown classifications.

The database uses 31 registered loci and 82 configured synonyms.
The taxonomy stage processed 2,197,804 distinct original TaxIDs.

## Verification

I ran the nine required acceptance-query groups and checked the
database totals and taxonomy aggregations.

All 20 sampled species counts matched NCBI Entrez. A separate
comparison of 20 species-locus title searches gave 17 exact matches.

For 20 benchmark queries, the median DuckDB response time was
0.017493 seconds, compared with 0.717895 seconds for Entrez.
The Entrez timing includes network latency, and these samples
do not establish overall accuracy or general performance.

## Locus registry correction

The registry previously used `ß-tub` while the locus configuration
used `β-tub`. I corrected the registry name while preserving ID 5.

I checked that all 31 configured names matched the registry and
that the locus IDs remained unique.

## Known limitations

- BLAST reports 122,597,681 sequences, while DuckDB contains
  134,731,779 accession-level records. I found examples of multiple
  accessions associated with a BLAST object, but have not reconciled
  the complete difference.
- Locus classification uses record titles rather than sequence-level
  validation. Some ambiguous matches need further domain review.
- A missing record-locus pair represents absence under the sparse
  classification convention, not proven biological absence.
- The individual build stages ran successfully, but a complete
  single-command rebuild from the original BLAST database has
  not yet been independently tested.

## Reproducing the work

The existing instructions are in `database/README.md` and
`database/phase1-offline-locus-counts.md`.

The full DuckDB database is not included in this pull request.
