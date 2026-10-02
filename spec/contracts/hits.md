# Contract: hits and taxonomy files

Producers: [P1](../python/p1-parse-blast.md), [P1-BOLD](../python/p1-bold-search.md),
[P2](../python/p2-extract-taxonomy.md). Consumers: P3, P6.

## 1. `all_hits.json` (BLAST)

Schema in [../python/p1-parse-blast.md §3](../python/p1-parse-blast.md). Key
guarantees consumers rely on:

| ID | Guarantee |
|---|---|
| HIT-001 | Top-level keys `query_title`, `query_length`, `hits`. |
| HIT-002 | `hits` sorted by `identity` descending; each hit has `hit_id`, `hit_subject`, `accession` (no version), `alignment_length`, `subject_length`, `query_coverage`, `bitscore`, `e_value`, `identity` (0–1, 3 dp), `hsps[]`. |
| HIT-003 | After P3 (in `candidates.json`, not in this file) hits gain `taxonomy`, `species`, `taxid`, `ncbi_blast_url`, `is_candidate_hit`. |

## 2. `all_hits.json` (BOLD)

Additional top-level keys `query_index, query_id, query_frame, query_strand,
query_sequence, query_orientation`; hits carry `similarity` and a copy in
`identity`, `species`, `taxonomy` (no `accession` guaranteed non-empty), and
no alignment statistics. See [../python/p1-bold-search.md §4](../python/p1-bold-search.md).

## 3. `all_hits.fasta`

Record id = accession (BLAST) or BOLD `hit_id`; description = hit subject /
taxonomic identification; sequence = **last HSP's aligned subject string
including gaps** (BLAST, P1-D-001) or full nucleotides with gaps removed
(BOLD). Written only when the query has hits.

## 4. `accessions.txt`, `taxids.csv`, `taxonomy.csv`

| File | Format |
|---|---|
| `accessions.txt` | one version-less accession per line, unique, unordered; trailing newline |
| `taxids.csv` (blastdbcmd) | `accession,taxid`, no header; accession may carry a version |
| `taxonomy.csv` | header `accession,taxid,domain,superkingdom,kingdom,phylum,class,order,family,genus,species`; accession version-stripped; **one row per accession whose taxid resolved** (unresolved accessions are absent); rank cells empty when the lineage lacks the rank |

| ID | Requirement |
|---|---|
| HIT-010 | A consumer MUST treat a hit with no `taxonomy.csv` row as "taxonomy unknown", never as an error and never as a candidate (P3-003). |
