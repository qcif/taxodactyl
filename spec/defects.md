# Defect register

All bugs and inconsistencies found while deriving the spec from the
`v1.5.0` source. This file is the **single triage list**; each module spec
also lists its own defects locally, with more context, under the same IDs.

Found by reading code, not by running it, unless marked **confirmed by
test/run**. Items marked *to confirm* depend on external tool behaviour.

**Severity**
- **High** — wrong or missing scientific result, a feature that cannot
  work, or a silent loss of output.
- **Medium** — misleading report/config, a validation gap that lets bad
  input through, or a latent crash.
- **Low** — cosmetic, documentation drift, dead code.

**Status:** `open` unless stated. When fixed, change status to
`fixed in <version/commit>` and keep the row.

---

## Summary

| Severity | Count |
|---|---|
| High | 17 |
| Medium | 53 |
| Low | 25 (some rows group several items) |

## High

| ID | Area | Defect | Spec |
|---|---|---|---|
| NF-D-002 | Nextflow | **BOLD mode cannot run**: `EXTRACT_HITS.out` is referenced when `EXTRACT_HITS` was never invoked, and `BOLD_SEARCH.out.hits` is not regrouped into `[query_folder, files]` for `EXTRACT_CANDIDATES`. | [nextflow/workflow.md §4.2](nextflow/workflow.md) |
| NF-D-009 | Nextflow | Default `-profile test` uses `db_type='bold'`, so it cannot succeed. | [nextflow/params.md §9](nextflow/params.md) |
| NF-D-003 | Nextflow | Any ignored failure in `EXTRACT_CANDIDATES`, `MAFFT_ALIGN`, `FASTME`, `EVALUATE_SOURCE_DIVERSITY` or `EVALUATE_DATABASE_COVERAGE` **silently removes that query's report** (inner joins); the only trace is `<outdir>/errors/`. | [nextflow/workflow.md §4.5](nextflow/workflow.md), [nextflow/error-handling.md](nextflow/error-handling.md) |
| NF-D-004 | Nextflow→P3 | `phylogeny_min_hit_identity` is never passed to P3; the parameter has no effect. | [nextflow/processes.md §9](nextflow/processes.md) |
| P0-D-001 | P0 / config | Loci **`atpB`, `trnL`, `AChE` can never validate** — mixed-case synonyms compared against lower-cased input. `Locus.__contains__` has the same flaw downstream. | [python/p0-validation.md](python/p0-validation.md) |
| P0-D-002 | P0 | Sequences given in the metadata `sequence` column **bypass length and count limits**; a blank cell writes an empty FASTA record. | [python/p0-validation.md](python/p0-validation.md) |
| P1-D-001 | P1 | `all_hits.fasta` holds only the **last HSP's aligned subject fragment, including `-` gap characters**, not the subject sequence. This feeds candidate FASTA, phylogeny sampling and MAFFT. | [python/p1-parse-blast.md](python/p1-parse-blast.md) |
| P2-D-001 | P2 | Taxonomy is keyed by the taxid taxonkit reports; for a **merged taxid** that is the new id, so the lookup by the original taxid fails and the accession is **silently dropped** from `taxonomy.csv`. *To confirm* against taxonkit `lineage -c` output for a merged id. | [python/p2-extract-taxonomy.md](python/p2-extract-taxonomy.md) |
| P3-D-001 | P3 | A query with no hit above `phylogeny_min_hit_identity` (every Flag `1E` "no match") gets an empty phylogeny FASTA; if FastME then fails the query is dropped and **no report is produced for a no-match result**. No test covers `1E`. *To confirm by run.* | [python/p3-assign-taxonomy.md](python/p3-assign-taxonomy.md) |
| P3-D-002 | P3 | Hits with no taxonomy row cannot form candidates; if all strict hits lack taxonomy the result silently degrades to `1D`/`1E` (log warning only). Compounds P2-D-001. | [python/p3-assign-taxonomy.md](python/p3-assign-taxonomy.md) |
| P1B-D-001 | P1 BOLD / image | `hmmsearch` is not installed in the analysis image (HMMER block commented out in `scripts/Dockerfile`), while orientation runs by default ⇒ BOLD search crashes. | [python/p1-bold-search.md](python/p1-bold-search.md) |
| P1B-D-002 | P1 BOLD / Nextflow | Code reads env `SKIP_ORIENTATION`; Nextflow exports `BOLD_SKIP_ORIENTATION` ⇒ `--bold_skip_orientation` has no effect. | [python/p1-bold-search.md](python/p1-bold-search.md) |
| P1B-D-003 | P1 BOLD / Nextflow | `bold_taxonomy.json` is never written (call commented out) but is a required `BOLD_SEARCH` output ⇒ process always fails. | [python/p1-bold-search.md](python/p1-bold-search.md) |
| P5-D-001 | P5 | **Flag 5.1 off-by-one**: `count > db_cov_target_min_b` (default 1) grades a taxon with exactly **one** reference record as `5.1C` "not present (0 entries)". | [python/p5-db-coverage.md](python/p5-db-coverage.md) |
| P5-D-002 | P5 | Targets without an NCBI taxid are queried as `txidNone[Organism]`; if Entrez drops the unknown term the count is every record at the locus ⇒ false `5.1A`. *To confirm with a live esearch.* | [python/p5-db-coverage.md](python/p5-db-coverage.md) |
| P6-D-001 | P6 / security | **NCBI API key leaks into every HTML report** (and `params_*.json`): the report renders all Nextflow params unfiltered, and the README tells users to pass `--ncbi_api_key` on the command line. | [python/p6-report.md](python/p6-report.md) |
| SVC-D-001 | validation service | `remove_sequence_from_csv` writes CSV with unquoted `",".join(...)`; any comma/quote in a metadata value corrupts the returned CSV (shifts columns). | [services/input-validation.md](services/input-validation.md) |

## Medium

| ID | Area | Defect | Spec |
|---|---|---|---|
| NF-D-005 | Nextflow / report | Report shows `blast_max_target_seqs_for_report` (2000) while BLAST is hard-coded to `-max_target_seqs 500`. | [nextflow/processes.md §3](nextflow/processes.md) |
| NF-D-006 | Nextflow | `REPORT` single-quotes `--facility-name` etc.; a value containing `'` breaks the command. | [nextflow/processes.md §14](nextflow/processes.md) |
| NF-D-011 | Nextflow config | Default process memory is `1MB`; any memory-enforcing scheduler would kill tasks without overrides. | [nextflow/config-profiles.md §2](nextflow/config-profiles.md) |
| NF-D-010 | Nextflow | `taxdb` is needed in BOLD mode too (P0 always checks it); not documented. | [nextflow/params.md §9](nextflow/params.md) |
| P0-D-003 | P0 | An empty FASTA passes validation with any metadata. | [python/p0-validation.md](python/p0-validation.md) |
| P0-D-004 | P0 | Duplicate `sample_id` rows are not rejected; CSV sequences then produce duplicate FASTA ids, and metadata keeps only the last row. | [python/p0-validation.md](python/p0-validation.md) |
| P0-D-006 | P0 | `--bold` claims to accept a blank locus, but blanks are rejected earlier. | [python/p0-validation.md](python/p0-validation.md) |
| P0-D-007 | P0 | `sample_id` is validated stripped but matched to FASTA unstripped. | [python/p0-validation.md](python/p0-validation.md) |
| P0-D-008 | P0 | `classification` accepts 12 values in P0 but only 7 in `assets/schema_input.json`, nf-schema's secondary schema for `--metadata` (validated before any process runs). If that layer validates CSV content as documented, the 5 extra values P0 accepts (`animal`, `animals`, `plant`, `plants`, `virus`) never reach P0 through the Nextflow-launched pipeline — only via the validation web service or a direct script call. *To confirm by running `classification=animal`.* | [python/p0-validation.md](python/p0-validation.md), [contracts/inputs.md §1](contracts/inputs.md) |
| CFG-D-001 | config | `default.yml` and `schema.py` disagree (5 filenames, `taxdb_dir`, `database_name`); regenerating `default.yml` from the schema, as documented, would break Nextflow file globs. | [python/shared/config.md](python/shared/config.md) |
| CFG-D-002 | config | Any `-c` config file **replaces** `default.yml` instead of layering on it. | [python/shared/config.md](python/shared/config.md) |
| CFG-D-003 | config | `get_locus_for_query` returns a `str` (not `Locus`) for values ending in ` gene`, and calls `.endswith` before its `None` check. | [python/shared/config.md](python/shared/config.md) |
| CFG-D-004 | config | `default.yml` hard-codes `taxdb_dir: /home/cameron/.taxonkit`. | [python/shared/config.md](python/shared/config.md) |
| CFG-D-005 | config | `LOGGING_DEBUG="0"` is non-empty, so **every pipeline run logs at DEBUG**; `--logging_debug` has no effect. | [python/shared/config.md](python/shared/config.md) |
| P1-D-002 | P1 | Query folders are assigned by BLAST XML record order = FASTA record order, with no check; a mismatched XML (e.g. a mock) silently mislabels results. | [python/p1-parse-blast.md](python/p1-parse-blast.md) |
| P1-D-003 | P1 | With zero hits across all queries, `accessions.txt` is a single blank line. | [python/p1-parse-blast.md](python/p1-parse-blast.md) |
| P2-D-002 | P2 | A taxonkit failure aborts P2 and therefore the whole run (no per-query isolation). | [python/p2-extract-taxonomy.md](python/p2-extract-taxonomy.md) |
| P3-D-003 | P3 | Flag 6 (phylogenetic assessment) is defined in `flags.csv` but never computed or written. | [python/p3-assign-taxonomy.md](python/p3-assign-taxonomy.md) |
| P3-D-004 | P3 | Flag 1 B/C boundary hard-coded at 4 species; `flags.csv` text hard-codes 98.5%/93.5%. Changing `max_candidates_for_analysis` or identity thresholds desynchronises flags, report text and gating. | [python/p3-assign-taxonomy.md](python/p3-assign-taxonomy.md) |
| P3-D-005 | P3 | BOLD `similarity = None` raises `TypeError` in threshold comparisons. | [python/p3-assign-taxonomy.md](python/p3-assign-taxonomy.md) |
| P1B-D-004 | P1 BOLD | Uses BOLD **v4** API over plain http; may be retired (*to confirm*). | [python/p1-bold-search.md](python/p1-bold-search.md) |
| P1B-D-005 | P1 BOLD | XML parsing crashes if any expected element (coords, url) is missing. | [python/p1-bold-search.md](python/p1-bold-search.md) |
| P1B-D-007 | P1 BOLD | For un-oriented queries the kept strand depends on thread completion order; `query_strand` always `+`. | [python/p1-bold-search.md](python/p1-bold-search.md) |
| P1B-D-008 | P1 BOLD / MAFFT | Alignment uses the original query, not the orientation actually submitted to BOLD; reverse-complemented queries misalign. | [python/p1-bold-search.md](python/p1-bold-search.md) |
| IMG-D-001 | image | `scripts/Dockerfile` installs taxonkit from the **`latest`** release and uses floating base `python:3.12`: the `neoformit/taxodactyl` image is not reproducible from source. | [deployment.md §2](deployment.md) |
| P4-D-001 | P4 | Source grouping not transitive (a bridging source is added to several groups, groups never merged) ⇒ independent sources over-counted, order-dependent; can turn Flag 4 B→A. | [python/p4-source-diversity.md](python/p4-source-diversity.md) |
| P4-D-002 | P4 | "Same source" requires an identical author list; automated and publication-less records pooled together. | [python/p4-source-diversity.md](python/p4-source-diversity.md) |
| P4-D-003 | P4 | One Entrez failure after retries aborts P4 ⇒ query loses its report. | [python/p4-source-diversity.md](python/p4-source-diversity.md) |
| P4-D-004 | P4/P5 | Entrez term has an unbalanced `)` (`txid…[Organism]) AND (…)`). *To confirm.* | [python/p4-source-diversity.md](python/p4-source-diversity.md) |
| P5-D-003 | P5 | `db_cov_country_missing_a` is never used; 5.3 is B as soon as one in-country species lacks records. | [python/p5-db-coverage.md](python/p5-db-coverage.md) |
| P5-D-004 | P5 | In-country GBIF paging uses occurrence offset not facet offset ⇒ endless loop for genera with ≥500 species in one country (until timeout ⇒ no report). | [python/p5-db-coverage.md](python/p5-db-coverage.md) |
| P5-D-005 | P5 | Failed per-species record counts become 0, lowering 5.2/5.3 instead of `ERR`. | [python/p5-db-coverage.md](python/p5-db-coverage.md) |
| P5-D-006 | P5 | Locus ending in ` gene` (accepted by P0) ⇒ every 5.x flag `ERR` (via CFG-D-003). | [python/p5-db-coverage.md](python/p5-db-coverage.md) |
| P5-D-007 | P5 | GBIF `name_lookup` without `datasetKey` may include non-backbone names, inflating 5.2 denominator. *To confirm.* | [python/p5-db-coverage.md](python/p5-db-coverage.md) |
| P6-D-002 | P6 / security | No HTML autoescaping: metadata cells, GenBank titles and error messages are injected raw into a shareable report (HTML/JS injection). | [python/p6-report.md](python/p6-report.md) |
| P6-D-003 | P6 / security | `report_context.json` stores the full config incl. API key, Redis password and Azure connection string in the work dir. | [python/p6-report.md](python/p6-report.md) |
| P6-D-004 | P6 | BOLD mode rewrites `identity`→`similarity` across inlined vendored JS/CSS. | [python/p6-report.md](python/p6-report.md) |
| ERR-D-001 | P4 / errors | P4 non-fatal errors are written without `query_dir` ⇒ outside the collected folder ⇒ **never shown in the report**. | [python/shared/errors.md](python/shared/errors.md) |
| THR-D-002 | throttle | Any exception whose text contains `429` is treated as rate limiting; for Entrez/BOLD this sleeps 10 min and resets retries **indefinitely** ⇒ task hangs to timeout ⇒ report lost. | [python/shared/throttle.md](python/shared/throttle.md) |
| THR-D-001 | throttle | SQLite per-minute limit checked over 12 s (not 60/90 s) ⇒ up to 5× the configured per-minute rate (BOLD). | [python/shared/throttle.md](python/shared/throttle.md) |
| SEC-D-001 | secrets / security | Vault keyed by unauthenticated `USER_EMAIL`; on Azure any pipeline user can retrieve another user's NCBI API key. | [python/shared/secrets.md](python/shared/secrets.md) |
| FLG-D-001 | flags | `flags.csv` text hard-codes thresholds that do not follow parameters. | [python/shared/flags.md](python/shared/flags.md) |
| FLG-D-002 | flags | Summary Flag 5 takes the *minimum* level whenever any sub-flag is level 0, so e.g. 5.1C (danger) + 5.3C (level 0) shows as a grey summary badge. *Confirm intent.* | [python/shared/flags.md](python/shared/flags.md) |
| SVC-D-002 | validation service | Error classification is by exact P0 message text; P0 wording changes silently degrade to `unknown`; several P0 errors have no classifier. | [services/input-validation.md](services/input-validation.md) |
| SVC-D-003 | validation service | Imports P0 (singleton `Config`, creates `output/`+`run.log` in cwd); blocking work inside `async def`. | [services/input-validation.md](services/input-validation.md) |
| SVC-D-004 | validation service / security | No auth or rate limit; CORS `*` with credentials. | [services/input-validation.md](services/input-validation.md) |
| SVC-D-005 | validation service | "Validated" input can still fail in the pipeline (taxdb, limits in force). | [services/input-validation.md](services/input-validation.md) |
| OUT-D-001 | outputs | No machine-readable per-query result is published (flags, coverage, sources, errors stay in work dir). | [contracts/outputs.md](contracts/outputs.md) |
| DEP-D-001 | release | Only `scripts/VERSION` is checked against the release tag; 4 other version locations can drift. | [deployment.md](deployment.md) |
| DEP-D-002 | release | `docker_build.sh` always pushes `latest`; `Dockerfile.update` builds on `latest`. | [deployment.md](deployment.md) |
| DEP-D-008 | deployment | `.env.sample` specifies Ubuntu 24.04 for Azure Batch nodes; the committed pool-setup template and every `docs/azure/*.md` walkthrough consistently specify Ubuntu 20.04 (chosen there for "Docker container compatibility"). Following `.env.sample` as instructed provisions a pool on the OS none of the docs or templates were written for. *To confirm which side is stale.* | [deployment.md §6](deployment.md) |
| DEP-D-003 | image | Image not reproducible (floating base + taxonkit `latest`). Same as IMG-D-001. | [deployment.md](deployment.md) |
| TST-G-001..010 | testing | Test gaps (no `1E` test, no Flag 5.1 threshold test, P3/P6 rules untested, no stub tests, CI lacks hmmsearch/taxonkit, etc.). | [tests.md](tests.md) |

## Low

| ID | Area | Defect | Spec |
|---|---|---|---|
| NF-D-001 | Nextflow | `assets/NO_FILE_PLACEHOLDER` does not exist; the "no loci file" branch is unreachable. | [nextflow/workflow.md §4.1](nextflow/workflow.md) |
| NF-D-007 | Nextflow | Schema error messages state wrong defaults (`phylogeny_min_hit_identity` 0.95, `phylogeny_max_seqs` 10). | [nextflow/params.md §9](nextflow/params.md) |
| NF-D-008 | Nextflow | `analyst_name`, `facility_name`, `blast_xml` are not declared in `params.config`. | [nextflow/params.md §9](nextflow/params.md) |
| — | Nextflow | `publish_dir_mode` is declared but ignored (all `publishDir` hard-code `copy`); `samplesheetToList` imported but unused; dead first definition of `ch_candidates_for_report`. | [nextflow/params.md §8](nextflow/params.md), [nextflow/workflow.md §4.7](nextflow/workflow.md) |
| P0-D-005 | P0 | Regex `A-z` admits `[ \ ] ^ _` and backtick. | [python/p0-validation.md](python/p0-validation.md) |
| P0-D-009 | P0 | Malformed `logger.debug("…:", x)` calls in auto-fix. | [python/p0-validation.md](python/p0-validation.md) |
| CFG-D-006 | config | Case-sensitive synonym matching (root cause of P0-D-001). | [python/shared/config.md](python/shared/config.md) |
| CFG-D-007 | config | Wrong `throttle_backend` description; inert `env_prefix`. | [python/shared/config.md](python/shared/config.md) |
| — | docs | Docs drift noted during derivation: `docs/detailed_tech.md` lists image `taxodactyl:v1.0.0` (actual `v1.5.0`); `scripts/README.md` links to non-existent `src/utils/config_schema.py`/`config.py`; README says `SKIP_ORIENTATION`, Nextflow exports `BOLD_SKIP_ORIENTATION`. | — |
| — | docs | `docs/src/understanding-the-analysis.md` states orientation "is no longer required for BOLD API v5, so this functionality is no longer used" — **false for the shipped code**: `id_engine.py` still calls `orientate(sequences)` unconditionally unless env `SKIP_ORIENTATION` is set. This doc claim is likely why nobody noticed P1B-D-001 (HMMER missing from the image) — the doc tells readers the HMM step is dead code. | [python/p1-bold-search.md](python/p1-bold-search.md) |
| — | docs | `docs/params.md`'s `taxdb` requirement list includes `taxonkit` (the binary) and `readme.txt`; the code's actual check (`TAXDB_EXPECT_FILES`, P0-031) is 9 `*.dmp`/`gc.prt` files only and never checks for a binary or readme. | [python/p0-validation.md](python/p0-validation.md) |
| — | docs | README states "Tested versions: 24.10.3, 24.10.6" for Nextflow, but `conf/manifest.config` sets `nextflowVersion = '!>=24.10.6'` — the `!` makes this a hard minimum, so 24.10.3 should refuse to launch at all. Either the tested-versions note is stale or the manifest constraint was tightened after that testing. | [nextflow/config-profiles.md §1](nextflow/config-profiles.md) |
| — | docs | `scripts/config/README.md` documents a cascading multi-file config workflow (`base.yml`, `high_confidence.yml`, `lab_environment.yml`, `test.yml`, `example_custom.yml`) with worked examples (`-c config/base.yml -c config/high_confidence.yml ...`). **None of these files exist** — git history shows them deleted in "Remove redundant example config.yml files"; only `default.yml` remains. Every example command in that README fails as written, and the doc no longer demonstrates the one real risk it should (CFG-D-002: a bare `-c custom.yml` drops `default.yml`'s filenames entirely). | [python/shared/config.md §2](python/shared/config.md) |
| P3-D-006..011 | P3 | Case-sensitive species de-dup vs case-insensitive counts; upper median for even counts; `preliminary_id_match.csv` missing newline; PMI/TOI compared against `accession`/`taxid` columns; unrounded `Match identity`; deprecated `boxplot(labels=)`. | [python/p3-assign-taxonomy.md](python/p3-assign-taxonomy.md) |
| P1B-D-006, -009, -010 | P1 BOLD | Invertebrate mt codon table never used in orientation; one HTTP failure aborts all queries; dead code (`taxon_*`, `_fetch_records`, `fetch_kingdom`). | [python/p1-bold-search.md](python/p1-bold-search.md) |
| P4-D-005..007 | P4 | Missing efetch accessions silently treated as "no publications"; wrong unused `hit_count`; `4B` for 0 sources vs "1–5" text. | [python/p4-source-diversity.md](python/p4-source-diversity.md) |
| P5-D-008..012 | P5 | TOI-truncation message lists nothing; sub-ranks (subspecies, tribe…) unsupported, "protozoa"→"protista"; fuzzy `name_suggest` may pick another taxon; 300-dpi maps bloat report; unreachable `None` return. | [python/p5-db-coverage.md](python/p5-db-coverage.md) |
| P6-D-005..006 | P6 | Per-query wall time; `print` alongside logging. | [python/p6-report.md](python/p6-report.md) |
| P6-D-007..008 | P6 | Heading link hard-coded to the project's old repo name (`daff-biosecurity-wf2`); tab-label/component-filename mismatch (cosmetic). | [python/p6-report.md](python/p6-report.md) |
| THR-D-003..005 | throttle | Backoff scope differs SQLite vs Redis; Entrez limit per user not per IP; Redis client per request. | [python/shared/throttle.md](python/shared/throttle.md) |
| CCH-D-001..004 | cache | Object args keyed by class only; unpickling from shared storage; transient empties cached 7 days; `fcntl` Linux-only. | [python/shared/cache.md](python/shared/cache.md) |
| ERR-D-002 | errors | Float location codes collide (1.1 == 1.10). | [python/shared/errors.md](python/shared/errors.md) |
| SEC-D-002..003 | secrets | Unsalted SHA-256 key derivation; Azure secret-name collisions. | [python/shared/secrets.md](python/shared/secrets.md) |
| SVC-D-006..007 | validation service | Unpinned deps, hard-coded paths; CSV/FASTA split not obvious to users. | [services/input-validation.md](services/input-validation.md) |
| DEP-D-005..007 | deployment | `set -e` hides failure message; hard-coded Azure names; stale release docs (`cloudgene.yml`). | [deployment.md](deployment.md) |
| OUT-D-002..003 | outputs | No run status file; `mode: copy` hard-coded. | [contracts/outputs.md](contracts/outputs.md) |

## Coverage

Every component listed in [README.md](README.md) is now specified. Defects
found by *running* the pipeline (rather than reading it) are not yet
included; items marked *to confirm* are the first candidates.
