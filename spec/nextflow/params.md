# Spec: Nextflow parameters

"Consumer" below is where the parameter actually takes effect —
determined from code, not from schema descriptions.

| ID | Requirement |
|---|---|
| NF-PA-001 | Every user-facing parameter MUST be declared in **both** `conf/params.config` (default) and `nextflow_schema.json` (validation). |
| NF-PA-002 | With `validate_params` true (default), parameters MUST be validated against the schema before any process runs. Required by schema: `metadata`, `outdir`, `db_type`, `taxdb`. |
| NF-PA-003 | A parameter forwarded as an optional CLI flag is treated as unset when falsy (NF-PR-004). Parameters where `0` is schema-valid but has no effect: `min_nt` (min 0), `db_coverage_toi_limit` (min 0). |
| NF-PA-004 | `metadata` MUST match `^\S+\.csv$` and exist; `sequences` MUST match `^\S+\.(fasta\|fas\|fna\|fa)$` and exist. |

## 1. Input / output

| Param | Type / default | Constraint | Consumer |
|---|---|---|---|
| `metadata` | path, none (required) | `.csv`, exists | `PREPARE_INPUTS` |
| `sequences` | path, none | fasta ext, exists | `PREPARE_INPUTS` (absent ⇒ P0 reads `sequence` column) |
| `outdir` | dir, `output` | — | publishDir everywhere; bind mounts; trace/report paths |
| `db_type` | enum, `blast_core_nt` | `blast_core_nt`\|`bold` | branch (NF-WF-030); `--bold` on P0/P3/P5/P6 |
| `blastdb` | path, none | required if `blast_core_nt` (NF-WF-013) | `BLAST_BLASTN`, `BLAST_BLASTDBCMD` |
| `taxdb` | dir, none (schema-required) | — | bind; P0 `--taxdb-dir`; env `TAXONKIT_DATA` |
| `blast_xml` | path, none | `.xml`, exists | `MOCK_BLASTN` only (with `mock_blast`) |
| `mock_blast` | bool, `false` | hidden | workflow branch (NF-WF-031) |
| `allowed_loci_file` | path, `${projectDir}/scripts/config/loci.json` | `.json`, exists | `VALIDATE_INPUT`, `EVALUATE_DATABASE_COVERAGE`, `REPORT` (bind parent dir + `--allowed-loci-file` to P0) |
| `analyst_name` | string, none | — | `REPORT --analyst-name` |
| `facility_name` | string, none | — | `REPORT --facility-name` |

## 2. Input-size limits (P0)

| Param | Default | Consumer |
|---|---|---|
| `fasta_max_sequences` | 150 | `VALIDATE_INPUT --fasta-max-sequences` |
| `fasta_max_length` | 3000 | `--fasta-max-length` |
| `fasta_min_length` | 20 | `--fasta-min-length` |

## 3. Candidate selection (P3)

| Param | Default | Range | Consumer flag |
|---|---|---|---|
| `min_identity` | 0.935 | 0–1 | `--min-identity` |
| `min_identity_strict` | 0.985 | 0–1 | `--min-identity-strict` |
| `min_nt` | 300 | ≥0 | `--min-alignment-length` |
| `min_q_coverage` | 0.85 | 0–1 | `--min-query-coverage` |
| `median_identity_warning_factor` | 0.95 | 0–1 | `--median-identity-warning-factor` |
| `max_candidates_for_analysis` | 3 | ≥1 | P3 `--max-candidates-analysis` **and** the workflow's source-diversity gate (NF-WF-051) |
| `phylogeny_min_seqs` | 20 | ≥1 | `--phylogeny-min-seqs` |
| `phylogeny_max_seqs` | 50 | ≥1 | `--phylogeny-max-seqs` |
| `phylogeny_species_max_seqs` | 3 | ≥1 | `--phylogeny-species-max-seqs` |
| `phylogeny_candidate_max_seqs` | 5 | ≥1 | `--phylogeny-candidate-max-seqs` |
| `phylogeny_min_hit_identity` | 0.935 | 0–1 | **none** (computed, not passed — NF-D-004) |

## 4. Database coverage (P5) and sources (P4)

| Param | Default | Consumer flag |
|---|---|---|
| `db_cov_min_a` | 5 | P5 `--db-cov-target-min-a` |
| `db_cov_min_b` | 1 | P5 `--db-cov-target-min-b` |
| `db_cov_related_min_a` | 90 | `--db-cov-related-min-a` (1–100) |
| `db_cov_related_min_b` | 10 | `--db-cov-related-min-b` (1–100) |
| `db_cov_country_missing_a` | 1 | `--db-cov-country-missing-a` |
| `db_coverage_max_candidates` | 3 | `--db-coverage-max-candidates` |
| `db_coverage_toi_limit` | 10 | `--db-coverage-toi-limit` |
| `gbif_accepted_status` | `accepted,doubtful` (`^(\S+,)*\S+$`) | `--gbif-accepted-status` |
| `gbif_limit_records` | 500 | `--gbif-limit-records` |
| `gbif_max_occurrence_records` | 5000 | `--gbif-max-occurrence-records` |
| `min_source_count` | 5 | P4 `--min-source-count` |

NF-PA-010: start-up validation enforces `db_cov_min_a > db_cov_min_b` and
`db_cov_related_min_a > db_cov_related_min_b` only (NF-WF-013). No other
inter-parameter ordering (e.g. `min_identity < min_identity_strict`) is
checked in Nextflow.

## 5. BOLD

| Param | Default | Consumer |
|---|---|---|
| `bold_database_name` | `COX1_SPECIES_PUBLIC` | `BOLD_SEARCH --bold-database` |
| `bold_skip_orientation` | 0 (`0`\|`1`, hidden) | env `BOLD_SKIP_ORIENTATION` |

## 6. Report

| Param | Default | Consumer |
|---|---|---|
| `blast_database_name_for_report` | `BLAST Core Nt` in `params.config`; schema default text `NCBI Core Nt'` (stray quote) — **config wins** | `REPORT --database-name` |
| `blast_max_target_seqs_for_report` | 2000 | `EXTRACT_HITS --blast-max-target-seqs` (display only; NF-D-005) |
| `report_debug` | 0 (`0`\|`1`) | `REPORT --report-debug` |

## 7. External services and environment

| Param | Default | Consumer |
|---|---|---|
| `ncbi_api_key` | none | env `NCBI_API_KEY` = param, else launcher's `NCBI_API_KEY`, else `''` |
| `ncbi_user_email` | none (email pattern) | env `USER_EMAIL` (`''` if unset) |
| `logging_debug` | 0 | env `LOGGING_DEBUG` |
| `app_data_dir` | `~/.local/share/taxodactyl` | bound at `/var/lib/taxodactyl` (NF-WF-011) |
| `temp_root_dir` | `(TMPDIR ∥ java.io.tmpdir ∥ ~) + /taxodactyl_tmp` | `beforeScript mkdir -p`; bind on P4/P5; `--temp-root` |
| `temp_dir_name` | none (`^\S+$`) | P4/P5 `--temp-dir-name` |

`SECRET_KEY` (local vault) is read from the **launcher's environment** by
`conf/env.config`; it is not a parameter.

## 8. Notifications, tracing, framework

`email`, `email_on_fail`, `plaintext_email`, `monochrome_logs`,
`trace_file` (default `<outdir>/pipeline_info/execution_trace_<suffix>.txt`),
`trace_report_suffix` (default: launch time `yyyy-MM-dd_HH-mm-ss`),
`validate_params`, `version`, `help`, `help_full`, `show_hidden`,
`pipelines_testdata_base_path`, `custom_config_*`, `config_profile_*`.

**Declared but inert:** `publish_dir_mode` (schema only; all `publishDir`
directives hard-code `mode: 'copy'`).

## 9. Defects / inconsistencies

| ID | Item |
|---|---|
| NF-D-004 | `phylogeny_min_hit_identity` has no effect. |
| NF-D-007 | Schema `errorMessage` texts drift from defaults: `phylogeny_min_hit_identity` says "Default: 0.95" (actual 0.935); `phylogeny_max_seqs` says "Default: 10" (actual 50). |
| NF-D-008 | `analyst_name`, `facility_name`, `blast_xml`, `allowed_loci_file`-related placeholders are absent from `params.config`; they rely on Nextflow returning `null` for undefined params. |
| NF-D-009 | `conf/test.config` (`-profile test`) sets `db_type = 'bold'`, which cannot run (NF-D-002). |
| NF-D-010 | Schema's `taxdb` is required, but `params.config` default is `null` and the schema description does not state it is required for BOLD too (P0 always needs it). |

---

## Provenance

**Initially derived from:** `conf/params.config` (defaults), `nextflow_schema.json` (validation), `conf/env.config`, and every `params.*` reference in `workflows/`, `modules/`, `subworkflows/local/`. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
