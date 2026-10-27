# Spec: Nextflow workflow (`TAXODACTYL`)

**Scope:** `main.nf`, `workflows/taxodactyl.nf`,
`subworkflows/local/utils_nfcore_taxodactyl_pipeline/main.nf`. Line
references are to the tree described in
[README.md § Version](../README.md#version).
**Companion specs:** [processes.md](processes.md), [params.md](params.md),
[config-profiles.md](config-profiles.md), [error-handling.md](error-handling.md),
[nf-core-conformance.md](nf-core-conformance.md), [../contracts/](../contracts/).

Requirement keywords: MUST / SHOULD / MAY as in RFC 2119. IDs are stable;
cite them from tasks and tests. "**Defect**" entries record where the
current code contradicts the requirement that its own structure implies —
they are inputs to the backlog, not permission to rely on the behaviour.

---

## 1. Purpose

Orchestrate the per-query taxonomic-assignment analysis: validate inputs,
search a reference database, extract candidate species, build a
phylogenetic tree, evaluate publication diversity and database coverage,
and render one HTML report per query. The workflow contains **no analysis
logic**; every analytical decision is made inside the Python entrypoints
([../python/](../python/)) or inside BLAST/MAFFT/FastME.

## 2. Entry point (`main.nf`)

| ID | Requirement |
|---|---|
| NF-WF-001 | `main.nf` MUST run, in order: `PIPELINE_INITIALISATION`, `TAXODACTYL`, `PIPELINE_COMPLETION`. |
| NF-WF-002 | `PIPELINE_INITIALISATION` receives `params.version, validate_params, monochrome_logs, args, outdir, metadata`. |
| NF-WF-003 | `PIPELINE_COMPLETION` receives `email, email_on_fail, plaintext_email, outdir, monochrome_logs`. |
| NF-WF-004 | On `workflow.onComplete`, the workflow MUST parse the Nextflow trace file (`params.trace_file`) and, for every row whose `status` is not `COMPLETED` or `CACHED`, copy that task's `.command.out`, `.command.err`, `.command.log` to `<outdir>/errors/<PROCESS>/<tag>.<out\|err\|log>`. |
| NF-WF-005 | The process name used in the destination path MUST be the task name with any `(tag)` suffix removed and `:` replaced by `/`. The `<tag>` is the text inside the first parentheses of the task name, or the `task_id` if there is none. |
| NF-WF-006 | If a source log file does not exist, the destination file MUST be written containing `[no .command.<stream> found in <workDir>]`. |
| NF-WF-007 | The copy MUST use an input-stream copy (not `Path→Path`) so it works on Azure Blob NIO paths. |
| NF-WF-008 | If `params.trace_file` is empty or the file is missing, log collection MUST be skipped with a warning; it MUST NOT fail the run. |
| NF-WF-009 | If no failed/aborted tasks exist, `<outdir>/errors/` MUST NOT be created. (`mkdirs` is called only inside the per-row loop after the status filter.) |

## 3. Start-up (`TAXODACTYL`, before any process)

| ID | Requirement |
|---|---|
| NF-WF-010 | The workflow MUST write `timestamp.txt` containing `workflow.start` formatted `yyyyMMdd HHmmss` in the JVM default time zone, and expose it as a value channel (`ch_workflow_timestamp`). |
| NF-WF-011 | The workflow MUST attempt to create `params.app_data_dir`. If it exists as a directory afterwards, it MUST set JVM property `taxodactyl.bind_app_data` to `" --bind <dir>:/var/lib/taxodactyl"`; otherwise it MUST set it to `""` and warn. Failure MUST NOT abort the run. |
| NF-WF-012 | The workflow MUST attempt to create `params.temp_root_dir`; failure MUST warn only. |
| NF-WF-013 | `PIPELINE_INITIALISATION` MUST fail the run (before any process) if: `db_type == blast_core_nt` and `blastdb` is unset/empty; `db_cov_min_a <= db_cov_min_b`; or `db_cov_related_min_a <= db_cov_related_min_b`. |
| NF-WF-014 | `PIPELINE_INITIALISATION` MUST honour `--version` (print `<name> v<version>[-g<sha7>]` and exit 0), validate params against `nextflow_schema.json` when `validate_params` is true, and, under `conda`/`mamba` profiles, warn on missing `conda-forge`/`bioconda` channel ordering. |
| NF-WF-015 | `PIPELINE_INITIALISATION` MUST reject `db_type == 'bold'` in custom parameter validation, before the BLAST-database and coverage-threshold checks and before any process is scheduled. The error MUST state that `--db_type bold` is temporarily disabled and direct users to `--db_type blast_core_nt` with `--blastdb`. The parameter remains recognized; repair or retirement remains open under D-01. |

Note: `metadata` is passed to `PIPELINE_INITIALISATION` but not used inside
it; sample-sheet content validation is **not** performed in Nextflow (see
`python/p0-validation.md`).

## 4. Data flow

Notation: `ch_x` = channel; `[k, files]` = tuple keyed by query folder name
(`query_NNN_<sample_id>`, produced by the Python layer — see
[../contracts/query-folder.md](../contracts/query-folder.md)).

```
params.sequences? ─┐
params.metadata ───┴─► PREPARE_INPUTS ─► ch_sequences_prepared / ch_metadata_prepared
params.allowed_loci_file ─► ch_allowed_loci
                              │
                              ▼
                        VALIDATE_INPUT ─► ready, sequences.fasta, metadata.csv, log
                              │  (.first() applied to sequences, metadata)
        ┌─────────────────────┴───────────────────────────────┐
   db_type == 'bold'                                   db_type == 'blast_core_nt'
   BOLD_SEARCH ─► hits, taxonomy                       BLAST_BLASTN | MOCK_BLASTN ─► blast xml
                                                       EXTRACT_HITS ─► accessions, hits files
                                                       BLAST_BLASTDBCMD ─► taxids.csv
                                                       EXTRACT_TAXONOMY ─► taxonomy
        └─────────────────────┬───────────────────────────────┘
                              ▼
                     EXTRACT_CANDIDATES  (per query)
        ┌──────────┬──────────┴──────────┬────────────────────┐
   MAFFT_ALIGN  EVALUATE_SOURCE_    EVALUATE_DATABASE_    (candidate files)
      │         DIVERSITY (gated)    COVERAGE (all)
    FASTME              │                  │
        └───────────────┴────── joins ─────┘
                              ▼
                           REPORT (per query)
      all process logs ─► run.log ─► PREPARE_LOG (publishes <outdir>/run.log)
```

### 4.1 Input preparation

| ID | Requirement |
|---|---|
| NF-WF-020 | The workflow MUST pass to `PREPARE_INPUTS` a list containing `file(params.sequences)` when `params.sequences` is set, else an empty list, plus `file(params.metadata)`. |
| NF-WF-021 | `ch_sequences_prepared` MUST be `PREPARE_INPUTS.out.sequences` or, if it emits nothing, a single empty list `[]`. |
| NF-WF-022 | The loci-file channel MUST be `channel.fromPath(params.allowed_loci_file)` when the param is truthy; otherwise a placeholder path (`assets/NO_FILE_PLACEHOLDER`) falling back to `file('OPTIONAL_FILE')`. |
| NF-WF-023 | `VALIDATE_INPUT` MUST receive (sequences, metadata, loci file). Its `sequences` and `metadata` outputs MUST be converted to value channels with `.first()`; every downstream process uses those, never the raw inputs. |

**Defect NF-D-001.** `assets/NO_FILE_PLACEHOLDER` does not exist in the
repository (only `assets/optional_input/NO_SEQUENCES` and
`QUERY_FOLDER/QUERY_FILE` do), and `VALIDATE_INPUT` stages the loci file as
`loci.json`, so its `name != 'OPTIONAL_FILE'` test is always true. The
"no loci file" branch is therefore unreachable in practice; the default
`allowed_loci_file` in `conf/params.config` always supplies a path. Do not
rely on the placeholder path.

### 4.2 Search branch selection

| ID | Requirement |
|---|---|
| NF-WF-030 | Within `TAXODACTYL`, `params.db_type == 'bold'` selects the retained BOLD branch; any other value selects BLAST. The pipeline entry point rejects BOLD before invoking this workflow (NF-WF-015). (`nextflow_schema.json` restricts values to `blast_core_nt`, `bold`.) |
| NF-WF-031 | BLAST branch: if `params.mock_blast && params.blast_xml` then `MOCK_BLASTN(ch_sequences, ready, file(params.blast_xml))` MUST replace `BLAST_BLASTN`; otherwise `BLAST_BLASTN(ch_sequences, ready)` runs. `mock_blast` without `blast_xml` silently runs real BLAST. |
| NF-WF-032 | BLAST branch: `EXTRACT_HITS(blast_xml, sequences, metadata)` MUST run once for the whole run; its three per-query output lists MUST be `flatten()`ed, keyed by `file.parent.name`, and `groupTuple()`d into `[query_folder, [hits.fasta, hits.json, query_title.txt]]`. |
| NF-WF-033 | BLAST branch: `BLAST_BLASTDBCMD(hits_accessions)` then `EXTRACT_TAXONOMY(taxids.csv, sequences, metadata)`; the taxonomy file becomes a value channel via `.first()`. |
| NF-WF-034 | BOLD branch: `BOLD_SEARCH(sequences, metadata, ready)`; `ch_hits_files = out.hits`, `ch_taxonomy_file = out.taxonomy.first()`. |

**Defect NF-D-002 (BOLD mode cannot run).** Two independent static
faults, either sufficient on its own:
1. `EXTRACT_HITS.out.extract_hits_log` is referenced unconditionally when
   building `ch_all_logs`. In BOLD mode `EXTRACT_HITS` is never invoked, so
   Nextflow raises an "output attribute accessed before invocation" error.
2. `BOLD_SEARCH.out.hits` (`path("query_*")`) is not regrouped into
   `[query_folder, files]` as the BLAST branch is, but
   `EXTRACT_CANDIDATES` declares `tuple val(query_folder), path(...)` input.

These faults remain unresolved. The pipeline now intentionally rejects BOLD
during initialization (NF-WF-015); `conf/test.config` (`-profile test`)
still selects BOLD and therefore exercises that guard. Restoring BOLD
execution requires resolving D-01 and these faults. BOLD-specific statements
below describe the retained process/script contracts, not an end-to-end
verified run.

### 4.3 Candidate extraction and per-query fan-out

| ID | Requirement |
|---|---|
| NF-WF-040 | `EXTRACT_CANDIDATES(ch_hits_files, ch_taxonomy_file, ch_sequences, ch_metadata)` MUST run once per query folder tuple. |
| NF-WF-041 | The query sequences channel MUST be `ch_sequences.splitFasta(record:[id:true, sequence:true])` mapped to `[id, sequence with newlines removed]`. |
| NF-WF-042 | Candidate-for-alignment tuples MUST be re-keyed by the sample id obtained by removing the first match of `query_\d\d\d_` from the folder name, then joined with the query-sequence channel (`combine by:0`) to yield `[query_folder, candidates_phylogeny.fasta, query_sequence]`. A query whose FASTA id does not equal the sample-id part of its folder name is dropped from alignment silently. |
| NF-WF-043 | `MAFFT_ALIGN` then `FASTME` MUST run on that tuple stream. |

**Defect NF-D-015.** `combine(by:0)` is not a lookup that errors on a
miss: a channel item with no partner on the other side simply never
produces an output tuple. The two sides of this join are *independently
derived* copies of what should be the same id — one from stripping
`query_\d\d\d_` off the folder name, one from Nextflow's own FASTA-id
tokenization — rather than one canonical id carried through both paths.
If they ever disagree, that query is dropped here with **no task failure
and no `errors/` entry** — unlike an ordinary ignored task failure
(`OUT-D-002`), which at least leaves a log there, there is no trace of
this anywhere in the outputs. *To confirm*: whether any input that passes
P0 validation on the Nextflow-launched path (where the space and
duplicate-id auto-fixes are disabled and mismatches are rejected instead,
`P0-042`; the `ß` → `beta` rename does run, but renames CSV and FASTA ids
together, `P0-046`) can actually trigger this
today, or whether it is presently a structural risk without a confirmed
live trigger — the risk exists either way, because nothing enforces that
the two derivations stay in sync. [decisions.md `D-02`](../decisions.md)
should cover this case too: a run-level summary that only names failed
*tasks* wouldn't catch a join that simply never ran.

### 4.4 Source-diversity gating

| ID | Requirement |
|---|---|
| NF-WF-050 | For each query, the workflow MUST read `candidates_count.txt` (name from `ext.candidates_count_file`) as an integer `n`. |
| NF-WF-051 | If `1 <= n <= params.max_candidates_for_analysis`, the query MUST be sent to `EVALUATE_SOURCE_DIVERSITY` with `[query_folder, all candidate files]`. |
| NF-WF-052 | Otherwise (`n < 1` or `n > max`) the query MUST be recorded as skipped and MUST appear in the report join with an empty source-diversity file list and empty error list. |
| NF-WF-053 | `EVALUATE_DATABASE_COVERAGE` MUST run for every query regardless of `n`; any candidate-count gating is internal to `p5_db_coverage.py`. |

### 4.5 Report join

| ID | Requirement |
|---|---|
| NF-WF-060 | `ch_files_for_report` MUST be built by chaining `combine(..., by: 0)` in this order onto `ch_hits_files`: candidates files; db-coverage files (`db_coverage.json` + `5*.flag` + `map*png`); db-coverage errors; FastME newick; independent-sources files; independent-sources errors; then non-keyed value channels: collated `software_versions.yml`, params JSON, timestamp. |
| NF-WF-061 | Every keyed combine is an **inner join**: a query lacking any one keyed element (e.g. FastME produced no tree, coverage produced no JSON) MUST be assumed absent from the report stream — it gets no HTML report, and this is not reported by the workflow itself. |
| NF-WF-062 | For every query in `ch_candidates_files`, the workflow MUST inject an empty `[]` entry into both error channels so that absence of errors does not drop the query from the join. |
| NF-WF-063 | Skipped-source-diversity queries MUST be injected with an empty `[]` file list (NF-WF-052). |
| NF-WF-064 | `REPORT(ch_files_for_report, ch_taxonomy_file, ch_metadata, ch_sequences)` MUST run once per joined tuple. |

**Consequence of NF-WF-061.** A single ignored failure in `MAFFT_ALIGN`,
`FASTME`, `EVALUATE_DATABASE_COVERAGE` or `EXTRACT_CANDIDATES` removes
that query's report while the run continues — this is deliberate
(`CONSTITUTION.md` rule 8), not a defect: a report built on an
incomplete evaluation would be misleading. What's still a real gap
(`OUT-D-002`) is discoverability: the only trace is `<outdir>/errors/`
(NF-WF-004) and an overall non-zero exit status
(`workflow.failOnIgnore`, see [error-handling.md](error-handling.md)) —
nothing names *which* query it was without an analyst counting reports
and then searching `errors/`.

### 4.6 Provenance and logs

| ID | Requirement |
|---|---|
| NF-WF-070 | `ch_params_json` MUST be a value channel of the path returned by `dumpParametersToJSON(params.outdir)`, which serialises **all** `params` to `<outdir>/pipeline_info/params_<yyyy-MM-dd_HH-mm-ss>.json` (via a hidden temp file in `launchDir`, deleted afterwards). |
| NF-WF-071 | `ch_versions` MUST be `MAFFT_ALIGN.out.versions` + `FASTME.out.versions` in BOLD mode, and `ch_blast_versions` + `BLAST_BLASTDBCMD.out.versions` + MAFFT + FastME in BLAST mode. `softwareVersionsToYAML` output MUST be collected (sorted, newline-separated) into `software_versions.yml` and `.first()`ed. |
| NF-WF-072 | The Python-process versions (the `daff_tax_assign` image / script version) are **not** collected into `software_versions.yml`. |
| NF-WF-073 | `run.log` MUST be the concatenation, each item's text followed by `\n---------\n`, of: `VALIDATE_INPUT`, `EXTRACT_HITS`, `EXTRACT_CANDIDATES`, `EVALUATE_SOURCE_DIVERSITY`, `EVALUATE_DATABASE_COVERAGE`, `REPORT` logs, plus `BOLD_SEARCH` (bold) or `EXTRACT_TAXONOMY` (blast). Concatenation order is arrival order, not sorted. `PREPARE_LOG` publishes it to `<outdir>/run.log`. |

### 4.7 Emitted channels

The workflow MUST emit (names are relied on by `nf-test`, see
`../tests.md`): `ch_hits_for_report`, `ch_candidates_for_report`,
`ch_db_coverage_json`, `ch_db_coverage_flags`, `ch_db_coverage_maps`,
`ch_source_diversity_for_report`, `ch_homology_trees`, `ch_html_report`,
`ch_collated_versions`, `ch_params_json`, `ch_workflow_timestamp`.

- `ch_hits_for_report` = `ch_hits_files`;
  `ch_candidates_for_report` = `ch_candidates_files` (the earlier mixed
  definition of the same name — flags, csv, fasta, json, boxplot, etc. —
  is dead code, overwritten before use).

**Defect NF-D-016.** The first definition of `ch_candidates_for_report`
(the mixed flags/csv/fasta/json/boxplot tuple) is never read — every
consumer sees the later, simpler reassignment to `ch_candidates_files`.
Not just inert: a future edit to the *first* definition (the more
plausible one to touch, since it's the one carrying the richer tuple
shape) would silently have no effect, which is a maintenance hazard
beyond ordinary dead code.

- `ch_source_diversity_for_report` = independent-sources files, each file
  list sorted by file name.

## 5. Non-goals

- No analysis in Groovy: thresholds and rules live in Python.
- No sample-sheet parsing or validation in Nextflow. The metadata CSV's
  content is checked only by P0
  ([contracts/inputs.md](../contracts/inputs.md)): since `3339050`
  nf-schema validates just the `--metadata` path, and the unused
  `samplesheetToList` import (`NF-D-017`, a residual of the nf-core
  template's samplesheet path) has been removed.
- No cross-query aggregation, and no run-level summary report.
- No `stub:` blocks exist in any process; `-stub-run` is not a supported
  test path — tracked as an open enhancement, not a defect:
  [decisions.md `D-41`](../decisions.md).

## 6. Open questions

1. Should the workflow publish a run-level summary of per-query outcome
   (ok / failed / no report), so an analyst can see which queries need
   repeating, while keeping deliberate report suppression
   ([decisions.md `D-02`](../decisions.md))?
2. Should `params.mock_blast` without `params.blast_xml` be a start-up
   error (NF-WF-031)?
3. Is `phylogeny_min_hit_identity` intended to reach `p3_assign_taxonomy.py`
   (see [processes.md](processes.md) `EXTRACT_CANDIDATES`)?

---

## Provenance

**Initially derived from:** source code (not docs) — `main.nf`, `workflows/taxodactyl.nf`, `subworkflows/local/utils_nfcore_taxodactyl_pipeline/main.nf`. See [README.md Version](../README.md#version) for the exact commit.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
