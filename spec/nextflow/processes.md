# Spec: Nextflow processes

**Scope:** every `process` in `modules/**/main.nf` (15). Derived from
source. Wiring between them is in [workflow.md](workflow.md); parameters in
[params.md](params.md); resources/containers in
[config-profiles.md](config-profiles.md).

## 0. Conventions common to all processes

| ID | Requirement |
|---|---|
| NF-PR-001 | Process names are the config selectors used by `conf/process.config` and `conf/azure.config`; renaming a process MUST update both. |
| NF-PR-002 | Internal file names MUST be read from `task.ext.*` (defined in `conf/filenames.config`, which loads Python-side names from `scripts/config/default.yml`), never hard-coded, for every file that crosses the Nextflow/Python boundary. Exceptions (hard-coded today, see defects): `sequences.fasta`, `metadata.csv`, `taxids.csv`, `id_mapping.tsv`, `4.flag`, `db_coverage.json`, `5*flag`, `map*png`, `errors/*`, `*_stat.txt`, `*.matrix.phy`, `query_*`. |
| NF-PR-003 | Python processes are invoked as `python /app/scripts/<pN_*.py>` — i.e. the script path is inside the container image, not staged from `bin/`. Changing a script therefore requires a new image (see [../deployment.md](../deployment.md)). |
| NF-PR-004 | A process's optional CLI flag MUST be emitted only when its parameter is truthy (`params.x ? "--flag ${params.x}" : ''`). A parameter set to `0`, `false`, empty string or `null` is therefore **indistinguishable from unset** and the Python default applies. |
| NF-PR-005 | Every process using `containerOptions` with `--bind` assumes Singularity/Apptainer syntax. Running under `-profile docker` is unsupported. |
| NF-PR-006 | Processes that consume a per-query bundle MUST `mkdir -p <query_folder>`, `mv` the staged input files into it, then delete the staging directory, so the Python script sees one flat query folder. |
| NF-PR-007 | The default error strategy is `ignore` ([error-handling.md](error-handling.md)). A process failing therefore yields no outputs for that task, not a run abort. |
| NF-PR-008 | No process defines a `stub:` block. |

## 1. `PREPARE_INPUTS`

- **Container:** none (`beforeScript` only) — runs in host shell / default image.
- **Input:** `sequences_file` (0 or 1 path), `metadata_file`.
- **Output:** `sequences.fasta` (optional, `emit: sequences`), `metadata.csv` (`emit: metadata`).
- **Behaviour:** copy the sequences file to `sequences.fasta` (only if a file was supplied and is not already named that); copy metadata to `metadata.csv`, or exit 1 with `ERROR: Metadata file not found` if it is already named `metadata.csv` but absent. Prints line counts.
- **Purpose:** guarantee inputs live in the work dir (needed for remote executors).

| ID | Requirement |
|---|---|
| NF-PR-010 | MUST NOT emit `sequences.fasta` when no sequences file was supplied (so downstream sees the `[]` fallback). |
| NF-PR-011 | MUST NOT modify content of either file. |

## 2. `VALIDATE_INPUT`

- **Label:** `daff_tax_assign`. `stageInMode 'copy'`.
- **Bind:** `params.taxdb`, parent dir of `params.allowed_loci_file`, `params.outdir`, plus app-data bind.
- **Input:** `sequences_file`, `metadata_file`, `allowed_loci_file` (staged as `loci.json`).
- **Output:** `ready` (value `true`), `sequences.fasta`, `metadata.csv`, log (`ext.log_filename`).
- **Command:** `python /app/scripts/p0_validation.py --output-dir ./ --taxdb-dir <taxdb> [--query-fasta <f> if size>0] --metadata-csv <f> [--bold] [--allowed-loci-file loci.json] [--fasta-max-sequences N] [--fasta-min-length N] [--fasta-max-length N]`.

| ID | Requirement |
|---|---|
| NF-PR-020 | `--query-fasta` MUST be passed only if the staged sequences file has non-zero size. |
| NF-PR-021 | The process MUST always produce `sequences.fasta` and `metadata.csv` (both non-optional outputs); a P0 run that does not is a process failure. See `python/p0-validation.md` for who writes them when sequences come from the metadata `sequence` column. |
| NF-PR-022 | `ready` MUST be emitted only on successful completion, so search processes cannot start before validation passes. |

## 3. `BLAST_BLASTN`

- **Label:** `blast` (`ncbi/blast:2.16.0`). **Bind:** parent of `params.blastdb`.
- **Input:** `fasta` (plain or `.gz`), `ready`.
- **Output:** `blast_result.xml` (`ext.blast_xml_filename`), `versions.yml`; publishes the XML to `<outdir>`.
- **`when:`** `task.ext.when == null || task.ext.when` (standard nf-core gate; unset in this repo).

Fixed command (values are **hard-coded**, not parameters):

```
blastn -num_threads ${task.cpus} -db ${params.blastdb} -query <fasta> \
  -outfmt 5 -out blast_result.xml -task megablast \
  -max_target_seqs 500 -evalue 0.05 -reward 1 -penalty -3
```

| ID | Requirement |
|---|---|
| NF-PR-030 | MUST run `megablast` with `-max_target_seqs 500`, `-evalue 0.05`, `-reward 1`, `-penalty -3`, XML output (`-outfmt 5`). Changing any is a scientific change (affects candidate selection) and needs a spec change. |
| NF-PR-031 | If the input FASTA has extension `gz`, MUST decompress to `<basename>` first. |
| NF-PR-032 | `versions.yml` MUST record `blast: <version>` derived from `blastn -version`. |

**Note.** `params.blast_max_target_seqs_for_report` (default 2000) does
not configure this BLAST run; it is only passed to `EXTRACT_HITS`
(`--blast-max-target-seqs`) for display. The effective search limit is the
hard-coded 500. The default report figure (2000) therefore disagrees with
what BLAST actually used (**defect NF-D-005**).

## 4. `MOCK_BLASTN`

- **Label:** `daff_tax_assign`. **Input:** `fasta`, `ready`, `test_output` (a BLAST XML).
- **Output:** `blast_result.xml`, `versions.yml` (`blast: 2.16.0+ (MOCK)`); publishes XML.
- **Behaviour:** copy `test_output` to the expected XML name if absent; exit 1 if the copy fails. Never reads the FASTA.

| ID | Requirement |
|---|---|
| NF-PR-040 | Interface (inputs 1–2, outputs) MUST stay identical to `BLAST_BLASTN` so the workflow can swap them. |
| NF-PR-041 | MUST report a `(MOCK)` version string so mocked runs are distinguishable in `software_versions.yml`. |

## 5. `EXTRACT_HITS` (P1, BLAST)

- **Label:** `daff_tax_assign`. **Bind:** outdir + app-data.
- **Input:** `blast_xml`, `sequences_file`, `metadata_file`.
- **Output:** `accessions.txt` (`ext.accessions_filename`) as `hits_accessions`; per-query `query_*/hits.fasta`, `query_*/hits.json`, `query_*/query_title.txt` as one tuple `hits_files`; log.
- **Publishes:** `query_*/hits.fasta` to `<outdir>`.
- **Command:** `python /app/scripts/p1_parse_blast.py <xml> --query-fasta <f> --metadata-csv <f> --output-dir ./ [--blast-max-target-seqs N]`, then for every `query_*/` create an empty `hits.fasta` if missing.

| ID | Requirement |
|---|---|
| NF-PR-050 | After P1 runs, every `query_*/` directory MUST contain a `hits.fasta` (empty if P1 wrote none) so the output glob and publishing are stable. |
| NF-PR-051 | All queries are processed in **one** task; per-query parallelism starts after this process. |

## 6. `BLAST_BLASTDBCMD`

- **Label:** `blast`. **Bind:** parent of `blastdb`.
- **Input:** `entry_batch` (`accessions.txt`). **Output:** `taxids.csv`, `versions.yml`.
- **Command:** `blastdbcmd -entry_batch <f> -db <blastdb> -outfmt "%a,%T" > taxids.csv`.

| ID | Requirement |
|---|---|
| NF-PR-060 | Output lines MUST be `accession,taxid` (no header). Downstream `p2` consumes this format. |

## 7. `EXTRACT_TAXONOMY` (P2)

- **Label:** `daff_tax_assign`. **Bind:** taxdb, outdir, app-data.
- **Input:** `taxids_csv`, `sequences_file`, `metadata_file`. **Output:** taxonomy file (`ext.taxonomy_file`), log.
- **Command:** `python /app/scripts/p2_extract_taxonomy.py --query-fasta <f> --metadata-csv <f> --output-dir ./ <taxids.csv>`.

## 8. `BOLD_SEARCH` (P1, BOLD)

- **Label:** `daff_tax_assign`. **Input:** `fasta`, `metadata`, `ready`.
- **Output:** BOLD taxonomy JSON (`ext.bold_taxonomy_json`), `query_*` dirs (`hits`), log. Publishes `query_*/hits.fasta`.
- **Command:** `python /app/scripts/p1_bold_search.py --output-dir ./ [--bold-database <name>] --query-fasta <f> --metadata-csv <f>`.
- **No container `bind`s** (taxdb is not mounted).

See **Defect NF-D-002** in [workflow.md](workflow.md): this process cannot be
wired successfully in the current workflow.

## 9. `EXTRACT_CANDIDATES` (P3)

- **Label:** `daff_tax_assign`. **Tag:** `<query_folder>`. **Bind:** outdir + app-data.
- **Input:** `tuple val(query_folder), path(hits_files, stageAs 'hits_files/*')`, `taxonomy_file`, `sequences_file`, `metadata_file`.
- **Command:** `python /app/scripts/p3_assign_taxonomy.py <query_folder> --query-fasta … --metadata-csv … --output-dir ./ [--bold] [--min-alignment-length min_nt] [--min-query-coverage min_q_coverage] [--min-identity] [--min-identity-strict] [--median-identity-warning-factor] [--max-candidates-analysis max_candidates_for_analysis] [--phylogeny-min-seqs] [--phylogeny-max-seqs] [--phylogeny-species-max-seqs] [--phylogeny-candidate-max-seqs]`.
- **Outputs** (all under `<query_folder>/`):

| Emit | Path | Optional |
|---|---|---|
| `candidates_for_source_diversity` | `[folder, candidates_count.txt, *]` | no |
| `candidates_files` | `[folder, *]` (whole folder contents) | no |
| `candidates_for_alignment` | `[folder, candidates_phylogeny.fasta]` | no |
| `candidates_flags` | `*.flag` | no |
| `candidates_fasta_files` / `csv` / `json` | `candidates.fasta` / `.csv` / `.json` | no |
| `candidates_boxplot_files` | boxplot image | yes |
| `assigned_taxonomy_files` | taxonomy-id CSV | yes |
| `preliminary_id_match_files` | PMI-match CSV | yes |
| `taxa_of_concern_detected_files` | TOI-detected CSV | yes |
| `extract_candidates_log` | run log | no |

- **Publishes:** `candidates_phylogeny.fasta`, `candidates.fasta`, `candidates.csv`, boxplot image.

| ID | Requirement |
|---|---|
| NF-PR-070 | `candidates_count.txt`, `candidates_phylogeny.fasta`, `candidates.{fasta,csv,json}` and at least one `*.flag` MUST exist after a successful run; missing any fails the task (non-optional globs). |
| NF-PR-071 | `--phylogeny-min-hit-identity` is computed but **not passed** (source comment: "Kept for parity … currently not passed"). The Python default (`0.935`) therefore always applies, and `params.phylogeny_min_hit_identity` has no effect (**defect NF-D-004**). |

## 10. `MAFFT_ALIGN`

- **Container:** mulled MAFFT (config, no label). **Tag:** query folder.
- **Input:** `[query_folder, candidate_fasta, query_sequence]`.
- **Output:** `[query_folder, <query_folder>/candidates_phylogeny.msa, <query_folder>/id_mapping.tsv]`, `versions.yml`. Publishes the `.msa`.
- **Algorithm (shell):**
  1. `sed '/^>/s/ .*//'` strips header text after the first space (workaround for upstream issue #24).
  2. Write `id_mapping.tsv` (`HIT<n>\t<original id>`) and rewrite headers to `>HIT<n>`.
  3. Build `temp.fasta` = `>QUERY` + query sequence, then the renamed candidates.
  4. `mafft --thread ${task.cpus} --phylipout temp.fasta > temp.msa`.
  5. Rewrite `HIT<n>` back to original ids in the alignment, padding/adding a trailing space to 11 characters (PHYLIP name width).

| ID | Requirement |
|---|---|
| NF-PR-080 | MUST use PHYLIP output (`--phylipout`); FastME consumes PHYLIP. |
| NF-PR-081 | The query MUST be labelled `QUERY` in the alignment and tree. |
| NF-PR-082 | Original ids MUST be restored in the published alignment; ids are truncated at the first space in the process. |
| NF-PR-083 | Candidate ids that contain regex/`sed` metacharacters or that collide with `HIT<n>` after renaming are **not** handled; the sed substitution uses `\<…\>` word boundaries. |

## 11. `FASTME`

- **Container:** biocontainer `fastme:2.1.6.3--h7b50bb2_1`. **Tag:** query folder.
- **Input:** `[query_folder, msa, id_mapping.tsv]`.
- **Output:** `[folder, candidates_phylogeny.nwk (ext.tree_nwk)]`, `*_stat.txt`, `*.matrix.phy`, `versions.yml`. Publishes the newick to `<outdir>/<query_folder>/`.
- **Command:** `fastme -i <msa> -d -O <msa>.matrix.phy -o temp.nwk -T ${task.cpus}` then rewrite tip labels `HIT<n>` → original ids using the id map (`sed` word-boundary substitution).

| ID | Requirement |
|---|---|
| NF-PR-090 | MUST use distance method mode `-d` with default model (no `-m`/`-s` options). |
| NF-PR-091 | Tip labels in the published tree MUST be the original candidate ids plus `QUERY`. |

## 12. `EVALUATE_SOURCE_DIVERSITY` (P4)

- **Label:** `daff_tax_assign`. **Tag:** folder. **Bind:** outdir, app-data, `params.temp_root_dir`.
- **Input:** `[query_folder, staged files 'sources_input/*']`, sequences, metadata.
- **Output:** `[folder, 4.flag]`, `[folder, independent_sources.json]`, optional `[folder, errors/*]`, log.
- **Command:** `python /app/scripts/p4_source_diversity.py <folder> --query-fasta … --metadata-csv … --output-dir ./ [--min-source-count N] [--temp-root <dir>] [--temp-dir-name <name>]`.

| ID | Requirement |
|---|---|
| NF-PR-100 | A successful run MUST produce `4.flag` and the sources JSON; missing either fails the task. |
| NF-PR-101 | `errors/*` is optional; when P4 records non-fatal errors they surface here and are routed to the report. |

## 13. `EVALUATE_DATABASE_COVERAGE` (P5)

- **Label:** `daff_tax_assign`. **Tag:** folder. **Bind:** taxdb, parent of loci file, outdir, app-data, temp root; **`--writable-tmpfs`**.
- **Input:** `[folder, staged 'db_coverage_input/*']`, sequences, metadata.
- **Output:** `[folder, db_coverage.json]`, `[folder, 5*flag]`, optional `[folder, map*png]`, optional `[folder, errors/*]`, log.
- **Command:** `python /app/scripts/p5_db_coverage.py <folder> --output-dir ./ --query-fasta … --metadata-csv … [--bold] [--db-coverage-toi-limit] [--db-coverage-max-candidates] [--gbif-limit-records] [--gbif-max-occurrence-records] [--gbif-accepted-status] [--db-cov-target-min-a←params.db_cov_min_a] [--db-cov-target-min-b←db_cov_min_b] [--db-cov-related-min-a] [--db-cov-related-min-b] [--db-cov-country-missing-a] [--temp-root] [--temp-dir-name]`.

| ID | Requirement |
|---|---|
| NF-PR-110 | Parameter names differ from CLI names for `db_cov_min_a/b` → `--db-cov-target-min-a/b`. |
| NF-PR-111 | A successful run MUST produce `db_coverage.json` and at least one file matching `5*flag`. |

## 14. `REPORT` (P6)

- **Label:** `daff_tax_assign`. **Tag:** folder. **Bind:** parent of loci file, outdir, app-data.
- **Input:** tuple `[query_folder, hits_files, candidates_files, db_coverage_files, db_coverage_errors, tree.nwk, independent_sources_files, independent_sources_errors, versions_file, params_file, timestamp_file]`, plus `taxonomy_file`, `metadata_file`, `sequences_file`.
- **Output:** `<query_folder>/*.html` (`html_report`, published), log.
- **Behaviour:** exports `INPUT_FASTA_FILEPATH` and `INPUT_METADATA_CSV_FILEPATH` as absolute paths; moves the tree to `<folder>/candidates_phylogeny.nwk`; moves every staged group into `<folder>/`; puts both error groups into `<folder>/errors/`; runs `python /app/scripts/p6_report.py <folder> --query-fasta … --metadata-csv … --output-dir ./ --versions_yml … --params_json … [--bold] [--report-debug] [--database-name '<name>'] [--facility-name '<name>'] [--analyst-name '<name>']`.

| ID | Requirement |
|---|---|
| NF-PR-120 | `--report-debug` MUST be passed only when `params.report_debug` is truthy (`1`). |
| NF-PR-121 | `--database-name/--facility-name/--analyst-name` values MUST be single-quoted in the command; a value containing a single quote breaks the command (**defect NF-D-006**, latent). |
| NF-PR-122 | Timestamp passed to the report is the file produced by NF-WF-010. |

## 15. `PREPARE_LOG`

- **Input/Output:** `combined_file`, republished unchanged as `<outdir>/<file>` (`publishDir mode copy`). Empty script; no container.

## 16. Defects raised in this document

| ID | Summary |
|---|---|
| NF-D-004 | `phylogeny_min_hit_identity` not forwarded to P3. |
| NF-D-005 | Report shows `blast_max_target_seqs_for_report` (default 2000) while BLAST is hard-coded to 500. |
| NF-D-006 | Single-quoted CLI args in `REPORT` break on embedded `'`. |
