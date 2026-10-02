# Spec: P6 report (`scripts/p6_report.py`, `src/report/`)

**Derived from:** `p6_report.py` (93), `src/report/report.py` (476),
`src/report/outcomes.py`, `src/report/filters/css_hash.py`,
`src/utils/flags.py` (`Flag.read`), `src/report/templates/**` (1,552 lines
of Jinja2), `src/report/static/**`. v1.5.0.
**Called by:** Nextflow `REPORT`, once per query that survives the report
join (NF-WF-060/061).
**Depends on:** outputs of P1/P2 (or BOLD), P3, P4 (optional), P5,
MAFFT/FastME tree, `software_versions.yml`, `params_<ts>.json`,
`timestamp.txt`; [shared/config.md](shared/config.md), `shared/errors.md`.

This spec covers the **data contract and decision rules** of the report.
Visual layout is defined by the templates and verified by the Selenium
suite (`test/selenium`); it is not restated here.

## 1. Interface

| Arg | Required | Notes |
|---|---|---|
| `query_dir` (positional) | yes | |
| `--query-fasta`, `--metadata-csv` | yes | (Nextflow also exports `INPUT_FASTA_FILEPATH`, `INPUT_METADATA_CSV_FILEPATH`) |
| `--output-dir` | no | |
| `--bold` | no | BOLD wording and taxonomy source |
| `--params_json` | no | path; rendered as "Workflow parameters" |
| `--versions_yml` | no | path; rendered as "Software versions" |
| `--report-debug` | no | filename timestamp → `DEBUG` |
| `--database-name`, `--facility-name`, `--analyst-name` | no | header fields (facility also vault-resolved, CFG-036) |
| `--flag-details-csv` | no | override `config/flags.csv` |

**Reads** (in `query_dir` unless stated): `query_title.txt`,
`all_hits.json`, `candidates.json`, `candidates.fasta`,
`candidates_phylogeny.fasta`, `candidates_phylogeny.nwk` (**required**),
`assigned_taxonomy.csv` (required iff Flag 1A), `taxa_of_concern_detected.csv`
(optional), `aggregated_sources.json` (optional), `db_coverage.json`
(optional), `map_*.png` (optional), `candidates_identity_boxplot.png`
(optional), `*.flag`, `errors/*`; `<output_dir>/taxonomy.csv` (BLAST mode),
`<output_dir>/timestamp.txt`.

**Writes:** `<query_dir>/report_[BOLD_]<sample_id>_<timestamp>.html`
(CFG-030); `<output_dir>/report_context.json` (full render context,
debugging aid; not published by Nextflow).

## 2. Output requirements

| ID | Requirement |
|---|---|
| P6-001 | The report MUST be a single self-contained HTML file: every file in `static/css` and `static/js` is inlined (sorted by name), every image in `static/img` and every map/boxplot is embedded as a base64 data URI. No network access is needed to view it. |
| P6-002 | A missing image MUST be replaced by `placeholder.png` (logged). |
| P6-003 | In BOLD mode, every whole word `identity`/`Identity` in the **rendered HTML** (including inlined JS/CSS) MUST be replaced by `similarity`/`Similarity`, and the title prefixed `BOLD - `. |
| P6-004 | The page MUST include a JavaScript "save report" function (`save-report.js`) that lets the analyst record answers to the subjective prompts and save a locked copy. |

## 3. Render context (data contract)

| Key | Source / rule |
|---|---|
| `title`, `html_title` | `report.title` (`BOLD - ` prefix in BOLD mode) |
| `facility`, `analyst_name` | `inputs.facility_name`, `inputs.analyst_name` (default `Not provided`) |
| `start_time` | `timestamp.txt` as `YYYY-MM-DD HH:MM:SS`, or `Unknown` |
| `end_time`, `wall_time` | time of rendering; wall time = now − start (per query, so it differs between reports of one run) |
| `metadata` | `sample_id` + every metadata column except `sequence` (CFG-026) |
| `locus_provided` | CFG-027 (`NA` ⇒ false; BOLD ⇒ true) |
| `input_fasta` | the query record as FASTA |
| `hits` | all hits from `all_hits.json` (up to 500 with printable alignments) |
| `hits_taxonomy` | BLAST: `taxonomy.csv` row per hit accession (or `None`); BOLD: hit `taxonomy` fields |
| `candidates` | `candidates.json` + `fasta` (`{id: FASTA}` from `candidates.fasta`) + `strict` (= Flag 1 not `D`/`E`) |
| `candidates_boxplot_src` | data URI or `None` |
| `toi_rows`, `tois_detected` | rows of the TOI CSV; `{toi: detected?}` |
| `aggregated_sources` | P4 JSON or `{}` |
| `db_coverage` | `{full, summary, ncbi_urls}`: P5 JSON with `map_exists`/`map_src_base64` added per target; `summary` = per target `{target count, related fraction, country fraction}` where fraction = share of species with count > 0, 2 dp, `None` if not a dict, `0.0` if empty |
| `tree_nwk_str` | contents of `candidates_phylogeny.nwk` (**read unconditionally**) |
| `tree_accessions` | ids in `candidates_phylogeny.fasta`, ordered as in `hits`, mapped to species (`Unknown` if no taxonomy) |
| `flag_definitions` | `flags.csv` (CFG-032) |
| `conclusions` | §4 |
| `error_log` | all error files in `<query_dir>/errors` (`ErrorLog`) |
| `workflow_params` | the params JSON **unfiltered** (P6-D-001) |
| `workflow_versions` | versions YAML flattened to `{tool: version}` (duplicate tool names: last wins) |
| `config` | the whole `Config` object (templates read `config.criteria.*`, `config.database_name`, `config.blast_max_target_seqs`, `config.gbif_max_occurrence_records`) |

## 4. Conclusion rules

Flags are read with `Flag.read` (merging all `*.flag` files; summary Flag 5
per target computed as in [p5-db-coverage.md §5.4](p5-db-coverage.md);
Flag 4 set to `None` if no `4.flag` exists).

### 4.1 Taxonomic result

| ID | Requirement |
|---|---|
| P6-010 | Flag 1 = `A`: result `confirmed = true`, `species` = first row of `assigned_taxonomy.csv`; `sources_verified` = every Flag 4 entry has level 1 (`4A`); colour `success`/level 1 if verified, else `warning`/level 2. **A single-species match with weak publication support is therefore never shown as a clean positive.** |
| P6-011 | Flag 1 ≠ `A`: `confirmed = false`, colour and level of Flag 1. |

### 4.2 Preliminary ID

| ID | Requirement |
|---|---|
| P6-020 | Flag 1 ≠ `A` ⇒ "Inconclusive taxonomic identity (Flag 1<X>)", grey, not confirmed. |
| P6-021 | Flag 1 = `A` ⇒ `7A` confirmed (green) or not confirmed (red), with the `flags.csv` explanation. |

### 4.3 Taxa of interest

| ID | Requirement |
|---|---|
| P6-030 | No TOI CSV ⇒ no TOI result. Otherwise `detected` = rows with a non-empty `Match rank`; `ruled_out` = Flag 2 is `B`; colour green if any detected, else red. |

### 4.4 Other

| ID | Requirement |
|---|---|
| P6-040 | `conclusions.hits.lowest_identity` = minimum hit identity, or `None` without hits. |
| P6-041 | Flag texts shown for a query without a locus MUST have locus phrases (" given locus for this", " at the given locus", " for this locus") removed. |
| P6-042 | Error files MUST be rendered at their report location, filtered by location code and `context.target` (see `shared/errors.md`). |

## 5. Failure behaviour

Uncaught exceptions fail `REPORT` for the query (no HTML). Known causes:
missing tree file, missing `assigned_taxonomy.csv` with Flag 1A, missing
`1.flag`/`7.flag`, malformed JSON inputs.

## 6. Defects

| ID | Severity | Defect |
|---|---|---|
| P6-D-001 | High (security) | **The NCBI API key is written into every report.** The "Workflow parameters" modal renders the whole params JSON unfiltered, and the README instructs users to pass `--ncbi_api_key` (and `--ncbi_user_email`) on the command line. The same data is in `pipeline_info/params_*.json`. |
| P6-D-002 | Medium (security) | Jinja2 `Environment` is created without autoescaping and templates do not escape values: metadata cells (arbitrary user columns), GenBank titles and error messages (`| safe`) are injected as raw HTML/JS into a file meant to be shared. |
| P6-D-003 | Medium (security) | `report_context.json` serialises the full `Config`, including `ncbi_api_key`, `redis_password` and `cache_azure_connection_string`, into the task work directory (on Azure: blob storage). |
| P6-D-004 | Medium | BOLD mode rewrites `identity` → `similarity` across all inlined JS/CSS, which can rename identifiers in vendored libraries (e.g. Plotly). |
| P6-D-005 | Low | Wall time is computed per query at render time; reports from the same run show different end/wall times. |
| P6-D-006 | Low | `print()` used alongside logging for the context path. |

## 7. Test mapping

No Python unit tests for `src/report`. `test/selenium/test_reports.py`
checks rendered reports in a browser (manual; see `../testing.md`).
nf-test asserts the number of HTML files produced.

## 8. Open questions

1. Which params may appear in the report? (Proposal: an allow-list, never
   anything matching `*key*`, `*password*`, `*secret*`, `*email*`.)
2. Should the report show an explicit "analysis incomplete" state instead
   of failing when the tree or coverage is missing (see NF-D-003, P3-D-001)?
