# Contract: candidate and evidence files

**Producers:** [P3](../python/p3-assign-taxonomy.md) (all files below
except where noted), [P4](../python/p4-source-diversity.md) (reads
`candidates.json`, produces files in
[coverage-and-sources.md](coverage-and-sources.md) instead).
**Consumers:** [P4](../python/p4-source-diversity.md),
[P5](../python/p5-db-coverage.md) (`candidates.json` species list only),
[P6](../python/p6-report.md) (everything), MAFFT_ALIGN
(`candidates_phylogeny.fasta` only).

## 1. `candidates.json`

```json
{ "hits": [...], "species": [...], "hit_counts": {"strong":{}, "moderate":{}, "filtered":{}} }
```
Detailed in [p3 §6.1](../python/p3-assign-taxonomy.md). Semantics:

| ID | Guarantee |
|---|---|
| CAN-001 | `species` = one record per **selected** species (strict if any, else moderate), highest-identity hit first, with `hit_count`, `min_identity`, `median_identity`, `median_bs_class`. |
| CAN-002 | `hits` = every filtered hit of a selected species (candidate or not) with `is_candidate_hit`. |
| CAN-003 | `len(species)` equals the integer in `candidates_count.txt`. |
| CAN-004 | `hit_counts.filtered` counts filtered hits below the moderate threshold ("no match"). |

## 2. `candidates.csv` / `assigned_taxonomy.csv`

BLAST header `species,taxid,accession,hit_subject,identity,query_coverage,alignment_length,e_value,bitscore`;
BOLD header `species,hit_id,accession,sequence_description,similarity,bin_uri,url`.
One row per selected-species hit. `assigned_taxonomy.csv` is a copy, only
when Flag 1 = A (its **first row** is read by P6 as the identified hit).
This is the only machine-readable result published to the output directory.

## 3. `taxa_of_concern_detected.csv`

Header `Taxon of interest,Match rank,Match taxon,Match species,Match accession,Match identity`;
one row per TOI in metadata order; match columns empty when not detected;
`Match identity` like `98.7%` (unrounded float, P3-D-010).

## 4. `candidates_phylogeny.fasta`

Sampled hit sequences (id as in `all_hits.fasta`), no query. MAFFT prepends
the query as `QUERY`; ids are temporarily renamed `HIT<n>` and restored
(NF-PR-080..083). See [p3 §9](../python/p3-assign-taxonomy.md).

## 5. `candidates_count.txt`

Decimal integer without newline.

---

## Provenance

**Initially derived from:** [p3-assign-taxonomy.md](../python/p3-assign-taxonomy.md) §6, §9, [p4-source-diversity.md](../python/p4-source-diversity.md) §1 — each already derived from source, v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
