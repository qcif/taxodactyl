# Spec: Nextflow error handling and failure isolation

**Sources:** `conf/process.config`, `conf/azure.config`, `conf/misc.config`,
`main.nf`, `workflows/taxodactyl.nf`.

## 1. Model

The workflow uses **process-level ignore**, not an application-level
"failed sample" status. A failing task produces no output; whatever depends
on it silently receives nothing.

| ID | Requirement |
|---|---|
| NF-ER-001 | `process.errorStrategy` MUST be `ignore` for all processes on all executors (local and Azure). |
| NF-ER-002 | `workflow.failOnIgnore` MUST be `true`, so an ignored task failure still yields a non-zero final exit status even though sibling queries continue. |
| NF-ER-003 | Failed/aborted task logs MUST be copied to `<outdir>/errors/` (NF-WF-004..009). This is the only per-task failure record shipped with results. |
| NF-ER-004 | A failure in a **per-query** process (`EXTRACT_CANDIDATES`, `MAFFT_ALIGN`, `FASTME`, `EVALUATE_*`, `REPORT`) MUST NOT stop or alter any other query's processing (queries are independent channel items). |
| NF-ER-005 | A failure in a **run-wide** process (`PREPARE_INPUTS`, `VALIDATE_INPUT`, `BLAST_BLASTN`, `EXTRACT_HITS`, `BLAST_BLASTDBCMD`, `EXTRACT_TAXONOMY`, `BOLD_SEARCH`) MUST be treated as run failure: no downstream process receives input, so no reports are produced. |
| NF-ER-006 | A failure in `EVALUATE_SOURCE_DIVERSITY` or `EVALUATE_DATABASE_COVERAGE` for a query removes that query from the report join (NF-WF-061) — see below. |

## 2. Failure matrix

| Failing process | Effect on that query | Effect on run |
|---|---|---|
| `PREPARE_INPUTS`, `VALIDATE_INPUT` | all queries | no output; exit ≠ 0 |
| `BLAST_BLASTN`, `EXTRACT_HITS`, `BLAST_BLASTDBCMD`, `EXTRACT_TAXONOMY` | all queries | no reports |
| `EXTRACT_CANDIDATES` | no candidates, no alignment, no coverage, no report | other queries unaffected |
| `MAFFT_ALIGN` / `FASTME` | no tree ⇒ **no report** (inner join) | others unaffected |
| `EVALUATE_DATABASE_COVERAGE` | no `db_coverage.json` ⇒ **no report** | others unaffected |
| `EVALUATE_SOURCE_DIVERSITY` | no `4.flag`/sources ⇒ **no report** (join needs `independent_sources_files`) | others unaffected |
| `REPORT` | no HTML | others unaffected |

**Consequence (NF-D-003).** Every non-skip failure between candidate
extraction and report is invisible in the results tree except under
`errors/`. Errors that Python catches (API failures inside P4/P5) are the
exception: they are written as `errors/*` files inside the query folder,
the process still succeeds, and the report renders them
(see `python/shared/errors.md`).

## 3. Timeouts and resources

`time` limits are enforced by the executor (local/HPC) or Azure Batch task
constraints; a timeout is an ordinary task failure (NF-ER-001..006). See
[config-profiles.md](config-profiles.md) for values and NF-D-011 for the
placeholder memory defaults.

## 4. Requirements that this design does NOT provide (candidates for future spec work)

1. A run-level summary of per-query outcome (ok / partial / failed).
2. A report (even a minimal one) for a query whose analysis failed.
3. Retry logic for transient failures at process level (Python retries
   only external HTTP calls — see `python/shared/throttle.md`).
