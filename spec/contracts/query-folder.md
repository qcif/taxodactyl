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
| `query_title.txt` | P1 / P1-BOLD | P6 (via config) | text |
| `all_hits.json` | P1 / P1-BOLD | P3, P6 | [hits.md](hits.md) |
| `all_hits.fasta` | P1 / P1-BOLD | P3 | [hits.md](hits.md) |
| `candidates.json` | P3 | P4, P5, P6 | [candidates.md](candidates.md) |
| `candidates.csv` | P3 | P3 (copy), user | [candidates.md](candidates.md) |
| `candidates.fasta` | P3 | P6 | FASTA |
| `candidates_phylogeny.fasta` | P3 | MAFFT, P6 | FASTA |
| `candidates_count.txt` | P3 | Nextflow gate (NF-WF-051) | integer |
| `assigned_taxonomy.csv` | P3 (Flag 1A only) | P6 | = `candidates.csv` |
| `preliminary_id_match.csv` | P3 (Flag 7A only) | — | `rank,taxon…` |
| `taxa_of_concern_detected.csv` | P3 (TOIs given) | P6 | [candidates.md](candidates.md) |
| `candidates_identity_boxplot.png` | P3 (> max candidates) | P6 | PNG |
| `1.flag`, `2.flag`, `7.flag` | P3 | P6 | [../python/shared/flags.md](../python/shared/flags.md) |
| `4.flag` | P4 | P6 | same |
| `aggregated_sources.json` | P4 | P6 | [coverage-and-sources.md](coverage-and-sources.md) |
| `5.1.flag`, `5.2.flag`, `5.3.flag` | P5 | P6 | same |
| `db_coverage.json` | P5 | P6 | [coverage-and-sources.md](coverage-and-sources.md) |
| `map_<target>.png` | P5 | P6 | PNG |
| `candidates_phylogeny.msa` | MAFFT_ALIGN | — (published only) | PHYLIP |
| `id_mapping.tsv` | MAFFT_ALIGN | FASTME | `HIT<n>\t<id>` |
| `candidates_phylogeny.nwk` | FASTME (published copy) / moved in by REPORT | P6 | Newick |
| `errors/*.json` | P4, P5, `taxonomy.extract` | P6 | [coverage-and-sources.md](coverage-and-sources.md) |
| `report_[BOLD_]<sample_id>_<ts>.html` | P6 | user | HTML |
| `run.log` | every script (in cwd, not the folder) | Nextflow `run.log` | text |

Run-level files read by P3/P6 from `<output_dir>` (not the query folder):
`taxonomy.csv` (P2), `timestamp.txt`, `BOLD` marker, `sequences.fasta`,
`metadata.csv`.

## 3. Rules

| ID | Requirement |
|---|---|
| QF-001 | The folder name is the only key linking Nextflow channels to Python state; it MUST NOT be altered by any step. |
| QF-002 | The sample id embedded in the name is the FASTA record id (P0-002) and MUST equal the id used to join query sequences in Nextflow (NF-WF-042). |
| QF-003 | A step MUST NOT delete or rewrite files produced by an earlier step (append-only), except `*.flag` upserts (FLG-002). |
| QF-004 | Filenames MUST come from configuration (CFG-010); the matrix above uses the shipped defaults. |
| QF-005 | Sample ids containing characters other than `[A-Za-z0-9_.\-]` are rejected by P0 (P0-020), because they become part of folder and report names. |
