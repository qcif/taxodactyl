# Contract: the per-query folder

The unit of work in Taxodactyl is the **query folder**
`query_<NNN>_<sample_id>` (NNN = 1-based position in `sequences.fasta`,
zero-padded to 3; CFG-024). Nextflow keys every channel by this name; the
Python entrypoints read and write files inside it. This file is the
producer/consumer matrix; formats are in the sibling contracts.

## 1. Lifecycle

1. **Created** by P1 (BLAST) or P1-BOLD (one folder per query, even with no hits).
2. **Extended** by P3, P4, P5 (each process receives the folder's files
   staged from upstream and writes new files next to them, NF-PR-006).
3. **Read** by MAFFT/FastME (only the phylogeny FASTA), and by P6 (all files).
4. Only a subset is copied to `<outdir>` ([outputs.md](outputs.md)).

## 2. File matrix

| File (default name) | Producer | Consumers | Format |
|---|---|---|---|
| `query_title.txt` | [P1](../python/p1-parse-blast.md) / [P1-BOLD](../python/p1-bold-search.md) | [P6](../python/p6-report.md) (via config) | text |
| `all_hits.json` | [P1](../python/p1-parse-blast.md) / [P1-BOLD](../python/p1-bold-search.md) | [P3](../python/p3-assign-taxonomy.md), [P6](../python/p6-report.md) | [hits.md](hits.md) |
| `all_hits.fasta` | [P1](../python/p1-parse-blast.md) / [P1-BOLD](../python/p1-bold-search.md) | [P3](../python/p3-assign-taxonomy.md) | [hits.md](hits.md) |
| `candidates.json` | [P3](../python/p3-assign-taxonomy.md) | [P4](../python/p4-source-diversity.md), [P5](../python/p5-db-coverage.md), [P6](../python/p6-report.md) | [candidates.md](candidates.md) |
| `candidates.csv` | [P3](../python/p3-assign-taxonomy.md) | P3 (copy to `assigned_taxonomy.csv`), analyst | [candidates.md](candidates.md) |
| `candidates.fasta` | [P3](../python/p3-assign-taxonomy.md) | [P6](../python/p6-report.md) | FASTA |
| `candidates_phylogeny.fasta` | [P3](../python/p3-assign-taxonomy.md) | MAFFT_ALIGN, [P6](../python/p6-report.md) | FASTA |
| `candidates_count.txt` | [P3](../python/p3-assign-taxonomy.md) | Nextflow gate ([workflow.md NF-WF-051](../nextflow/workflow.md)) | integer |
| `assigned_taxonomy.csv` | [P3](../python/p3-assign-taxonomy.md) (Flag 1A only) | [P6](../python/p6-report.md) | = `candidates.csv` |
| `preliminary_id_match.csv` | [P3](../python/p3-assign-taxonomy.md) (Flag 7A only) | — (unread) | `rank,taxon…` |
| `taxa_of_concern_detected.csv` | [P3](../python/p3-assign-taxonomy.md) (TOIs given) | [P6](../python/p6-report.md) | [candidates.md](candidates.md) |
| `candidates_identity_boxplot.png` | [P3](../python/p3-assign-taxonomy.md) (> max candidates) | [P6](../python/p6-report.md) | PNG |
| `1.flag`, `2.flag`, `7.flag` | [P3](../python/p3-assign-taxonomy.md) | [P6](../python/p6-report.md) | [../python/shared/flags.md](../python/shared/flags.md) |
| `4.flag` | [P4](../python/p4-source-diversity.md) | [P6](../python/p6-report.md) | same |
| `aggregated_sources.json` | [P4](../python/p4-source-diversity.md) | [P6](../python/p6-report.md) | [coverage-and-sources.md](coverage-and-sources.md) |
| `5.1.flag`, `5.2.flag`, `5.3.flag` | [P5](../python/p5-db-coverage.md) | [P6](../python/p6-report.md) | same |
| `db_coverage.json` | [P5](../python/p5-db-coverage.md) | [P6](../python/p6-report.md) | [coverage-and-sources.md](coverage-and-sources.md) |
| `map_<target>.png` | [P5](../python/p5-db-coverage.md) | [P6](../python/p6-report.md) | PNG |
| `candidates_phylogeny.msa` | `MAFFT_ALIGN` ([processes.md](../nextflow/processes.md)) | — (published only) | PHYLIP |
| `id_mapping.tsv` | `MAFFT_ALIGN` | `FASTME` | `HIT<n>\t<id>` |
| `candidates_phylogeny.nwk` | `FASTME` (published copy) / moved in by `REPORT` | [P6](../python/p6-report.md) | Newick |
| `errors/*.json` | [P4](../python/p4-source-diversity.md), [P5](../python/p5-db-coverage.md), [`taxonomy.extract`](../python/p2-extract-taxonomy.md) | [P6](../python/p6-report.md) | [coverage-and-sources.md](coverage-and-sources.md) |
| `report_[BOLD_]<sample_id>_<ts>.html` | [P6](../python/p6-report.md) | analyst | HTML |
| `run.log` | every script (in cwd, not the folder) | Nextflow `run.log` ([workflow.md NF-WF-073](../nextflow/workflow.md)) | text |

Run-level files read by P3/P6 from `<output_dir>` (not the query folder):
`taxonomy.csv` ([P2](../python/p2-extract-taxonomy.md)), `timestamp.txt`,
`BOLD` marker, `sequences.fasta`, `metadata.csv`.

## 3. Rules

| ID | Requirement |
|---|---|
| QF-001 | The folder name is the only key linking Nextflow channels to Python state; it MUST NOT be altered by any step. |
| QF-002 | The sample id embedded in the name is the FASTA record id (P0-002) and MUST equal the id used to join query sequences in Nextflow (NF-WF-042). |
| QF-003 | A step MUST NOT delete or rewrite files produced by an earlier step (append-only), except `*.flag` upserts (FLG-002). |
| QF-004 | Filenames MUST come from configuration (CFG-010); the matrix above uses the shipped defaults. |
| QF-005 | Sample ids containing characters other than `[A-Za-z0-9_.\-]` are rejected by P0 (P0-020), because they become part of folder and report names. |

---

## Provenance

**Initially derived from:** cross-reference compilation of every producer/consumer spec listed in the matrix above — each already derived from source, v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
