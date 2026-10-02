# Architecture

## 1. Two layers, one interface

```
                ┌───────────────────── Nextflow (DSL2) ─────────────────────┐
 user params ──►│ main.nf → TAXODACTYL workflow → 15 processes               │
                │   channels keyed by query folder name                      │
                └───────┬───────────────────────────────┬────────────────────┘
                        │ python /app/scripts/pN_*.py    │ blastn, blastdbcmd, mafft, fastme
                        ▼                                ▼
        ┌──────────── Python engine (scripts/) ───┐    off-the-shelf containers
        │ p0..p6 entrypoints → src/ packages      │
        │ Config singleton, Throttle, Cache, ...  │──► NCBI Entrez · GBIF · BOLD · taxonkit
        └───────────────────────────────────────────┘
```

| Layer | Owns | Does not own |
|---|---|---|
| Nextflow ([nextflow/](nextflow/)) | ordering, fan-out per query, joins, resources, containers, publishing, run-level error collection | any analytical decision |
| Python ([python/](python/)) | validation, parsing, thresholds, flags, evidence analyses, report | scheduling, retries of whole tasks, file publishing |
| Off-the-shelf tools | BLAST search, alignment, tree | — |

## 2. The interface between the layers (all of it)

| Mechanism | Detail | Spec |
|---|---|---|
| Command-line flags | each process builds `--flag value` only for truthy params | NF-PR-004, [params.md](nextflow/params.md) |
| Environment variables | `conf/env.config`, Azure env | [config-profiles.md §5](nextflow/config-profiles.md) |
| Files in the query folder | named by `default.yml`, exposed as `task.ext.*` | [contracts/](contracts/) |
| Run-level files | `sequences.fasta`, `metadata.csv`, `taxonomy.csv`, `timestamp.txt`, `BOLD` marker | [contracts/query-folder.md](contracts/query-folder.md) |
| Exit status | non-zero = task failure; Python catches non-fatal API errors and writes `errors/*.json` instead | [error-handling.md](nextflow/error-handling.md), [errors.md](python/shared/errors.md) |

There is no other channel: Python never calls Nextflow and Nextflow never
imports Python.

## 3. Per-query model

The whole pipeline after the search is data-parallel over **query
folders** (`query_NNN_<sample_id>`). One process instance handles one
query; instances are independent and unordered. The only cross-query
processes are the run-wide steps (`VALIDATE_INPUT`, BLAST, `EXTRACT_HITS`,
`BLAST_BLASTDBCMD`, `EXTRACT_TAXONOMY`, and REPORT-side value channels).

## 4. Cross-cutting infrastructure (Python)

| Concern | Module | Behaviour | Spec |
|---|---|---|---|
| Configuration | `utils/config` | singleton; YAML + env + CLI precedence; filenames; per-query helpers | [config.md](python/shared/config.md) |
| External API rate | `utils/throttle` | SQLite or Redis token windows, 429 backoff, retry | [throttle.md](python/shared/throttle.md) |
| Response caching | `utils/cache`, `coalesce` | SQLite or Azure Blob; Redis lease coalescing | [cache.md](python/shared/cache.md) |
| Non-fatal errors | `utils/errors` | JSON files rendered in report | [errors.md](python/shared/errors.md) |
| Secrets | `utils/secrets` | local Fernet file or Azure Key Vault | [secrets.md](python/shared/secrets.md) |
| Flags | `utils/flags` | outcome records + text from `flags.csv` | [flags.md](python/shared/flags.md) |

## 5. Data-flow summary

`sequences.fasta` + `metadata.csv` → *(BLAST)* `blast_result.xml` →
*(P1)* per-query `all_hits.{json,fasta}` + `accessions.txt` →
*(blastdbcmd, P2)* `taxonomy.csv` → *(P3)* candidates, phylogeny FASTA,
flags 1/2/7 → *(MAFFT, FastME)* tree ∥ *(P4)* `aggregated_sources.json`,
flag 4 ∥ *(P5)* `db_coverage.json`, flags 5.x, maps → *(P6)* HTML report.
Full producer/consumer matrix: [contracts/query-folder.md](contracts/query-folder.md).

## 6. Design properties (and where they fail today)

| Property | Intent | Reality |
|---|---|---|
| Per-query isolation | one failure never affects another query | holds, but a failure silently removes that query's report (NF-D-003) |
| Non-silent degradation | missing evidence is shown, not hidden | holds for P5; P4 errors never reach the report (ERR-D-001); taxonomy gaps silently reduce candidates (P3-D-002) |
| Config-driven behaviour | thresholds, text, loci in config | mostly; some thresholds hard-coded (P3-D-004, NF-PR-030), some params inert (NF-D-004, P5-D-003) |
| Environment independence | same code on laptop/HPC/Azure | via backends; requires shared filesystem on HPC (THR-001) |
| Reproducibility | pinned tools and reference data | tools pinned; reference data unversioned; image not reproducible (IMG-D-001); no reference-data provenance in report |
| No secrets at rest in outputs | | **violated**: API key in report and params JSON (P6-D-001) |
