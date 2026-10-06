# Spec: Runtime configuration (`scripts/src/utils/config/`)

**Used by:** every `p*.py` entrypoint and most `src/` modules.

---

## 1. Purpose

Provide one process-wide `Config` object holding validated settings,
input paths, per-query helpers (metadata lookup, query dir naming, report
path) and lazily created services (vault). It is also the definition of
most filenames that cross the Nextflow/Python boundary.

## 2. Precedence

For every setting, the effective value is the **last** of:

1. Pydantic defaults in `schema.py`;
2. YAML files: `config/default.yml`, or instead every `-c/--config FILE`
   given on the command line, deep-merged in order;
3. environment variables listed in `mappings.PARAMS[*].env_name`;
4. CLI arguments passed to `config.update_from_args(args)` (only those
   whose value is not `None` and whose name maps to a known key).

| ID | Requirement |
|---|---|
| CFG-001 | `Config()` MUST be a singleton: the first instantiation loads config; later calls return the same object without reloading. |
| CFG-002 | `-c` files are read from `sys.argv` at first instantiation (`parse_known_args`). If none are given, `scripts/config/default.yml` MUST be loaded. Supplying any `-c` **replaces** `default.yml` rather than layering on it. Missing `-c` files are warned and skipped. |
| CFG-003 | Merged YAML MUST validate against `ConfigSchema`; failure MUST log and `sys.exit(1)`. |
| CFG-004 | After YAML, every mapped env var that is **set** (even to the empty string) MUST override the YAML value, cast by its mapping type. Cast failures are warned and ignored. |
| CFG-005 | `update_from_args` MUST ignore `None` values and unknown arg names; cast failures are warned and ignored. |
| CFG-006 | Values set via env/CLI are **not** re-validated by Pydantic (e.g. an out-of-range threshold is accepted). |

### 2.1 Casting rules (`mappings.py`)

| Type | Rule |
|---|---|
| String | `str(v)` |
| Int / Float | `int(v)` / `float(v)` |
| Bool | false iff `str(v).lower()` in `none, 0, false, ""`; everything else true |
| Path | `Path(v)`; `output_dir` is created (`mkdir -p`). `""` becomes `Path('.')` |
| UppercaseList (`gbif_accepted_status`) | upper-case, remove spaces, split on `,` |

## 3. Settings and their external names

Only settings with an effect outside config itself are listed. Full list:
`mappings.PARAMS`. Defaults are from `default.yml` (the file actually
loaded), with schema defaults noted where they differ.

### 3.1 Paths and inputs

| Key | Env | CLI | Default |
|---|---|---|---|
| `output_dir` | `OUTPUT_DIR` | `--output-dir` | `output` |
| `query_dir` | `QUERY_DIR` | positional/`query_dir` | none |
| `inputs.query_fasta` | `INPUT_FASTA_FILEPATH` | `--query-fasta` | none |
| `inputs.metadata_csv` | `INPUT_METADATA_CSV_FILEPATH` | `--metadata-csv` | none |
| `taxdb_dir` | `TAXONKIT_DATA` | `--taxdb-dir` | `/home/cameron/.taxonkit` (**developer path**; schema default `~/.taxonkit`) |
| `allowed_loci_file` | `ALLOWED_LOCI_FILE` | `--allowed-loci-file` | `config/loci.json` (resolved relative to `scripts/`) |
| `flag_details_csv_path` | `FLAG_DETAILS_CSV_PATH` | `--flag-details-csv` | `config/flags.csv` |
| `temp_root` | `TEMP_ROOT` | `--temp-root` | none ⇒ OS temp dir |
| `temp_dir_name` | `TEMP_DIR_NAME` | `--temp-dir-name` | `biosecurity` |

### 3.2 Thresholds (namespace `criteria`)

| Key | Env | CLI | Default |
|---|---|---|---|
| `alignment_min_nt` | `MIN_NT` | `--min-alignment-length` | 300 |
| `alignment_min_q_coverage` | `MIN_Q_COVERAGE` | `--min-query-coverage` | 0.85 |
| `alignment_min_identity` | `MIN_IDENTITY` | `--min-identity` | 0.935 |
| `alignment_min_identity_strict` | `MIN_IDENTITY_STRICT` | `--min-identity-strict` | 0.985 |
| `median_identity_warning_factor` | `MEDIAN_IDENTITY_WARNING_FACTOR` | same | 0.95 |
| `max_candidates_for_analysis` | `MAX_CANDIDATES_FOR_ANALYSIS` | `--max-candidates-analysis` | 3 |
| `sources_min_count` | `MIN_SOURCE_COUNT` | `--min-source-count` | 5 |
| `db_cov_target_min_a` / `_b` | `DB_COV_MIN_A` / `_B` | `--db-cov-target-min-a/b` | 5 / 1 |
| `db_cov_related_min_a` / `_b` | `DB_COV_RELATED_MIN_A` / `_B` | same | 90 / 10 |
| `db_cov_country_missing_a` | `DB_COV_COUNTRY_MISSING_A` | same | 1 |
| `phylogeny_min_hit_identity` | `PHYLOGENY_MIN_HIT_IDENTITY` | same | 0.935 |
| `phylogeny_min_seqs` / `max_seqs` | `PHYLOGENY_MIN_SEQS` / `MAX_SEQS` | same | 20 / 50 |
| `phylogeny_species_max_seqs` / `candidate_max_seqs` | `…` | same | 3 / 5 |

### 3.3 Inputs limits and labels (namespace `inputs`)

`fasta_max_sequences` (150), `fasta_min_length` (20), `fasta_max_length`
(3000), `facility_name` / `analyst_name` (`"Not provided"`; env
`FACILITY_NAME`/`ANALYST_NAME`; CLI `--facility-name/--analyst-name`),
`metadata_csv_header` (logical→CSV column map), `metadata_csv_required_fields`.

### 3.4 Services

| Key | Env | Default |
|---|---|---|
| `user_email` | `USER_EMAIL` | `''` |
| `ncbi_api_key` | `NCBI_API_KEY` | `''` |
| `azure_key_vault_url` | `AZURE_KEY_VAULT_URL` | none |
| `cache_backend` | `CACHE_BACKEND` | `sqlite` |
| `cache_disabled` | `CACHE_DISABLED` | false |
| `cache_timeout_hours` | `CACHE_TIMEOUT_HOURS` | 168 |
| `cache_azure_*` | `CACHE_AZURE_ACCOUNT_URL`, `_CONNECTION_STRING`, `_CONTAINER` (default `biosecurity-cache`), `_BLOB_PREFIX` | |
| `throttle_backend` | `THROTTLE_BACKEND` / `--throttle-backend` | `sqlite` (`sqlite`\|`redis`) |
| `redis_host/port/password` | `REDIS_*` | `localhost`/6379/none; `redis_ssl` is true iff port 6380 |
| `max_api_retries` | `MAX_API_RETRIES` | 3 |
| `gbif_limit_records`, `gbif_max_occurrence_records`, `gbif_accepted_status` | `GBIF_*` + CLI | 500, 5000, `[ACCEPTED, DOUBTFUL]` |
| `db_coverage_toi_limit`, `db_coverage_max_candidates` | env + CLI | 10, 3 |
| `bold_database` | `BOLD_DATABASE` / `--bold-database` | `COX1_SPECIES_PUBLIC` |
| `hmmsearch_min_evalue` | `HMMSEARCH_MIN_EVALUE` | 1e-5 |
| `report.debug` | `REPORT_DEBUG` / `--report-debug` | false |
| `report.database_name` | `BLAST_DATABASE_NAME` / `--database-name` | `NCBI Core Nt` |
| `report.title` | `REPORT_TITLE` | `Taxonomic identification report` |
| `blast_max_target_seqs` | `BLAST_MAX_TARGET_SEQS` / `--blast-max-target-seqs` | 2000 |

Not in mappings but read directly from the environment elsewhere:
`LOGGING_DEBUG` (log level, §6), `SECRET_KEY` (vault), and module-specific
variables specified in their own specs.

### 3.5 Filenames (the cross-boundary contract)

Values from `default.yml`. **Several differ from the schema defaults**
(right column) — `default.yml` wins at runtime, and `conf/filenames.config`
reads `default.yml`, so Nextflow and Python agree.

| Key | Value | Schema default |
|---|---|---|
| `hits_json` | `all_hits.json` | `hits.json` |
| `hits_fasta` | `all_hits.fasta` | `hits.fasta` |
| `phylogeny_fasta` | `candidates_phylogeny.fasta` | `phylogeny.fasta` |
| `boxplot_img_filename` | `candidates_identity_boxplot.png` | `identity-boxplot.png` |
| `tree_nwk_filename` | `candidates_phylogeny.nwk` | `candidates.nwk` |
| `accessions_filename` | `accessions.txt` | same |
| `taxonomy_file` | `taxonomy.csv` | same |
| `query_title_file` | `query_title.txt` | same |
| `taxonomy_id_csv` | `assigned_taxonomy.csv` | same |
| `candidates_fasta/csv/json` | `candidates.fasta/.csv/.json` | same |
| `candidates_count_file` | `candidates_count.txt` | same |
| `candidates_sources_json` | `candidates_sources.json` | same |
| `independent_sources_json` | `aggregated_sources.json` | same |
| `toi_detected_csv` | `taxa_of_concern_detected.csv` | same |
| `pmi_match_csv` | `preliminary_id_match.csv` | same |
| `db_coverage_json` | `db_coverage.json` | same |
| `bold_taxonomy_json` / `bold_taxon_count_json` / `bold_taxon_collectors_json` | `bold_taxonomy.json` / `bold_taxon_counts.json` / `bold_taxon_collectors.json` | same |
| `timestamp_filename` | `timestamp.txt` | same |
| `log_filename` | `run.log` | same |
| `errors_dir` | `errors` | same |
| `flag_file_template` | `{identifier}.flag` | same |
| `bold_flag` | `BOLD` (marker file name) | same |
| `sqlite_file` | `db.sqlite` | same |
| `entrez_cache_dirname` | `entrez_cache` | same |

| ID | Requirement |
|---|---|
| CFG-010 | Filenames used by Nextflow `task.ext.*` MUST come from `default.yml`. Changing a filename is a change to both layers. |
| CFG-011 | Running a script with any `-c` file that omits a filename key silently reverts that filename to the schema default, breaking Nextflow globs (CFG-D-002). |

## 4. Derived values and helpers

| ID | Requirement |
|---|---|
| CFG-020 | `output_dir`: `OUTPUT_DIR` env if set, else `--output-dir` from argv, else YAML, else `output`; created on init. Resolved at first `Config()` — i.e. at import time of every entrypoint. |
| CFG-021 | Logging MUST be configured on init to console + `<output_dir>/<log_filename>` (append), level DEBUG if `LOGGING_DEBUG` env is set to **any non-empty value** (including `"0"`), else INFO; messages containing `.lock` are filtered out. |
| CFG-022 | `is_bold` is true iff file `<output_dir>/BOLD` exists. `update_from_args` writes it when `args.bold` is true. BOLD mode therefore depends on the working dir, not on a setting. |
| CFG-023 | `database_name` is `'BOLD'` in BOLD mode, else `report.database_name`. |
| CFG-024 | Query directory for 0-based index `i` MUST be `<output_dir>/query_<i+1 zero-padded to 3>_<sample_id>`, where `sample_id` is the id of FASTA record `i` of `inputs.query_fasta`; created on access. Passing a string containing `query_` or a `Path` returns it unchanged. |
| CFG-025 | `get_query_ix(dir)` MUST parse the index as `int(name.split('_')[1]) - 1`. More than 999 queries would give a 4-digit prefix; still parsable. |
| CFG-026 | `metadata` (cached): dict `sample_id → {logical_key: value}` over **all** CSV columns except `sample_id` and `sequence`; values stripped; missing columns → `None`; any key containing `interest` is split on `|` into a list (empty → `[]`). Duplicate sample ids: last row wins. |
| CFG-027 | `get_locus_for_query(q)`: BOLD mode ⇒ `'COI'`; value ending `' gene'` ⇒ returns the **string** with the suffix removed (not a `Locus`; CFG-D-003); `na` (any case) ⇒ `Locus('NA', {})` (falsy); otherwise the first loci-file entry containing the value as a synonym, renamed to the user's spelling; else `ValueError`. |
| CFG-028 | `get_country_for_query(q, code=True)` returns the pycountry alpha-2 code or `None`. |
| CFG-029 | `get_classification_for_query(q)` returns the `HIGHER_CLASSIFICATIONS` entry (`{'gbif': kingdomKey, 'ncbi': {'rank', 'taxon'}}`) or `None`. Mapping: animalia→1/metazoa, plantae→6/viridiplantae, fungi→5/fungi, chromista→4/clade sar, bacteria→3/domain bacteria, archaea→2/domain archaea, viruses→8/`acellular root` viruses (+ singular/plural aliases). |
| CFG-030 | `get_report_path(q, bold)`: `<query_dir>/report_[BOLD_]<sample_id with . → _>_<timestamp>.html`, then every char outside `[\w\d\-_.]` replaced by `_`. `<timestamp>` is `DEBUG` if `report.debug`, else `YYYY-MM-DD HH:MM:SS` from `timestamp.txt` (so spaces/colons become `_`), or `Unknown` if the file is absent/invalid. |
| CFG-031 | `start_time` parses `<output_dir>/timestamp.txt` with format `%Y%m%d %H%M%S` (written by NF-WF-010). |
| CFG-032 | `read_flag_details_csv()` groups `flags.csv` rows by `id` → `{name, explanation[value], outcome[value], level[value]:int}`; a non-integer `level` MUST raise `ValueError`. |
| CFG-033 | Temp dirs: `tempdir = (temp_root or OS temp)/temp_dir_name`; `user_tempdir = tempdir/(user_email or 'ANONYMOUS')`; both created on access. `throttle_sqlite_path = user_tempdir/throttle_db.sqlite`, `throttle_sqlite_global_path = tempdir/throttle_db.sqlite`, `cache_sqlite_path = tempdir/cache_db.sqlite`. |
| CFG-034 | `user_secrets_dir`: first writable of `/var/lib/taxodactyl/<email or ANONYMOUS>`, `~/.local/share/taxodactyl/<…>`; else `OSError`. |
| CFG-035 | `cleanup()` removes `<output_dir>/entrez_cache` and any sub-dir of `tempdir` whose newest mtime is older than `temp_clean_after_days` (7). |
| CFG-036 | On init, `_resolve_ncbi_api_key()`: if `user_email` unset, warn and skip. If an API key is set, store it in the vault; else read it from the vault. `update_from_args` ends with `_resolve_facility_name()`: same pattern for `inputs.facility_name` (the default `"Not provided"` counts as unset). See [secrets.md](secrets.md). |

## 5. Loci (`src/utils/locus.py`)

| ID | Requirement |
|---|---|
| CFG-040 | `allowed_loci` MUST re-read the loci JSON on every access and return one `Locus(name, data)` per key. |
| CFG-041 | `Locus.name` is lower-cased/stripped; `bool(locus)` is false iff name is `na`; `x in locus` iff `x.lower().strip()` is in the (case-sensitive) synonym list; `locus == x` compares lower-cased names. |
| CFG-042 | `genbank_query_str` MUST be `(s[Title]) OR (s[GENE])` for each ambiguous synonym, followed by ` OR (s)` for each non-ambiguous synonym. A locus with no ambiguous synonyms yields a string starting with ` OR `. |

Loci file schema: see `../../contracts/loci.md`.

## 6. Defects

| ID | Defect |
|---|---|
| CFG-D-001 | `default.yml` is out of sync with `schema.py` (filenames in §3.5, `taxdb_dir`, `report.database_name`); the documented regeneration step would **change runtime filenames** and break Nextflow. `default.yml` is the de-facto spec; the schema defaults should be aligned to it. |
| CFG-D-002 | `-c` replaces rather than extends `default.yml` (CFG-002, CFG-011). |
| CFG-D-003 | `get_locus_for_query` returns `str` for values ending in ` gene`, and calls `.endswith` before its `None` check. |
| CFG-D-004 | `default.yml` hard-codes `taxdb_dir: /home/cameron/.taxonkit`. |
| CFG-D-005 | `conf/env.config` always exports `LOGGING_DEBUG="${params.logging_debug}"`, i.e. `"0"` by default; `os.getenv` returns the non-empty string `"0"`, so **every pipeline run logs at DEBUG**. `--logging_debug` has no effect. |
| CFG-D-006 | Case-sensitive synonym matching (see P0-D-001). |
| CFG-D-007 | `schema.throttle_backend` description mentions `local`/`azure`; valid values are `sqlite`/`redis`. `model_config.env_prefix="BIOSEC_"` has no effect on a plain `BaseModel`. |

## 7. Test mapping

`tests/test_config.py`: singleton behaviour (CFG-001), cascade and
override order (CFG-002, CFG-004/005), invalid type in YAML (CFG-003),
`None` CLI values ignored (CFG-005). Not covered: CFG-020..036 helpers,
loci matching, filename contract.

---

## Provenance

**Initially derived from:** `config/config.py` (721), `config/schema.py` (361), `config/mappings.py` (539), `config/default.yml`, `src/utils/log.py`, `src/utils/locus.py`, `tests/test_config.py`. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
