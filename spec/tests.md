# Spec: Testing

There are four test surfaces. Only the first runs automatically.

| # | Surface | Location | Runs | Automatic | Hermetic |
|---|---|---|---|---|---|
| 1 | Python unit tests | `scripts/tests/test_*.py` | `python -m unittest discover -s scripts/tests -p 'test*.py'` | **CI on push/PR to `main`** (Python 3.12) | mostly (some need `hmmsearch`/`taxonkit`/network) |
| 2 | Python integration | `scripts/tests/integration/` | `run_tests.sh [--bold] [--keep] [--continue] [--test_case X]` | no | no — live NCBI/GBIF/BOLD |
| 3 | Nextflow end-to-end (`nf-test`) | `test/{scenario_01..04,core}` | `nf-test test <file>` (scenario chosen in `nf-test.config`) | no | no — needs BLAST/taxdump; P4/P5 use live APIs |
| 4 | Report UI (Selenium) | `test/selenium/` | `pytest test_reports.py --dir <reports>` | no | needs generated reports |

## 1. Requirements

| ID | Requirement |
|---|---|
| TST-001 | Every requirement ID in this spec SHOULD be traceable to at least one test. Modules with no unit tests today are listed in §4. |
| TST-002 | A change to any threshold, filename, flag rule or report rule MUST be accompanied by a change to the test that pins it (or by a new test). |
| TST-003 | CI MUST run surface 1 on every push and pull request to `main`. It MUST NOT depend on secrets other than `USER_EMAIL`. |
| TST-004 | Surfaces 2–4 SHOULD be run before every release; the release checklist (`deployment.md` §3) records the versions of the reference data used. |
| TST-005 | Fixtures that embed reference-data-derived values (snapshots, flags, `db_coverage.json`, HTML) MUST record the reference-data versions they were generated with (as `test/core/README.md` does: BLAST DB, taxdump date). |

## 2. Surface details

### 2.1 Unit tests

14 modules: `test_blast_parser`, `test_cache`, `test_cache_azure`,
`test_coalesce`, `test_config`, `test_coverage_assert`, `test_gbif`,
`test_genbank`, `test_orient`, `test_phylogeny_sampling`, `test_secrets`,
`test_taxonkit`, `test_utils`, `test_validation`. Fixtures in
`scripts/tests/test-data/`. `test_coverage_assert` tests the integration
comparison logic, not production code. `test_orient` needs `hmmsearch`,
which CI does not install (§4).

### 2.2 Integration tests

| ID | Requirement |
|---|---|
| TST-010 | Each case directory under `tests/test-data/integration/{blast,bold}/<case>/` MUST contain `blast_result.xml`, `candidates.nwk`, `metadata.csv`, `query.fasta`, `taxids.csv`, `taxonomy.csv` (BLAST cases). The runner executes P0, P1, P2, P3, P4, P5, P6 in-process per case. |
| TST-011 | Env `USER_EMAIL`, `NCBI_API_KEY`, `TAXONKIT_DATA` MUST be set, else setup fails. |
| TST-012 | Default assertion: no exception. Optional `expected/db_coverage.json` fixtures are compared by `coverage_assert` with tiered rules: exact key sets at the target layer, type-only leaves, non-null propagation (truthy expected ⇒ truthy actual); sub-keys below the target layer tolerated. |
| TST-013 | `testkit.py harvest/promote/seed` manage fixtures (scaffold from a Nextflow run, update after semantic-diff review, first-time write). It is deliberately not part of `run_tests.sh`. |

21 BLAST case directories and 1 BOLD case directory exist; the BOLD case
cannot pass (P1B-D-001..003).

### 2.3 `nf-test`

| ID | Requirement |
|---|---|
| TST-020 | `nf-test.config` selects one scenario (`testsDir`, `configFile`, `profile singularity`, `workDir`); scenarios 01/03 use FASTA+CSV, 02/04 sequences in CSV (02 = viral, locus `NA`, classification `viruses`); scenarios 01–04 set `mock_blast=true` with a stored `blast_result.xml`; `core` runs real BLAST against a subset DB (`mock_blast=false`). |
| TST-021 | Assertions (scenario_01): snapshot of `ch_hits_for_report`, `ch_candidates_for_report`, `ch_source_diversity_for_report`, `ch_homology_trees`; 6 HTML reports; 1 versions file; 1 params JSON; 1 timestamp; 6 db-coverage map groups (11 map files); 6 coverage JSON; 6 flag groups each with 3 files (18). |
| TST-022 | Flag regression check (post-run): `bin/collect_flags.sh` gathers `*.flag` from the run, `bin/test_flags.py` compares them with `test/<scenario>/flags` using normalised JSON (sorted keys; lists sorted by `(flag_id, target, target_type)`) and prints per-path differences. Not integrated into `nf-test`. |
| TST-023 | Placeholders `CUSTOMISE` in each scenario's `nextflow.config` (`blastdb`, `taxdb`, `temp_root_dir`) and in `nf-test.config` (`workDir`) MUST be edited by the tester; the tests do not run out of the box. |

### 2.4 Selenium

| ID | Requirement |
|---|---|
| TST-030 | Fixtures `test/selenium/expected/*.yaml` (20) describe, per sample id, the values a browser must find in the report (overview, candidates, TOIs, database coverage, sample metadata; collectors in `lib/`). Reports are matched to fixtures by `sample_id`. |
| TST-031 | `test/selenium/testkit.py render` builds a review page of differences; `promote` accepts drift into fixtures. |
| TST-032 | `--dir` is required so a run states whether it validates new output or the checked-in reference reports (`expected/reports`). |

## 3. Which requirements are exercised

| Area | Unit | Integration | nf-test | Selenium |
|---|---|---|---|---|
| Nextflow wiring, joins, gating | – | – | yes (channel snapshot + counts) | – |
| P0 validation | yes | – | – | – |
| P1 parsing | yes (stats) | yes | yes | – |
| P2 taxonomy | yes | yes | yes | – |
| P3 flags/candidates | phylogeny sampling only | yes (no asserts) | yes (flags baseline) | yes (overview) |
| P4 | partial (`fetch_sources`) | yes (no asserts) | yes | partial |
| P5 | GBIF only | yes + `db_coverage.json` fixture | yes | yes |
| P6 | – | yes (no asserts) | report count | yes |
| Shared throttle/cache/secrets/config | yes (cache, coalesce, secrets, config) | – | – | – |

## 4. Gaps (tests the spec implies but that do not exist)

| ID | Gap |
|---|---|
| TST-G-001 | No test of a `1E` (no candidate) query, the case most exposed to NF-D-003 / P3-D-001. |
| TST-G-002 | No test of Flag 5.1 thresholds (P5-D-001) or of taxid-less targets (P5-D-002). |
| TST-G-003 | P3 filtering, Flags 1/2/7 and output files have no unit tests. |
| TST-G-004 | P6 decision rules (§4 of `p6-report.md`) have no unit tests; only Selenium against generated HTML. |
| TST-G-005 | Nextflow: no `stub:` blocks, so no fast wiring test; `nf-test` needs real reference data and live APIs. |
| TST-G-006 | CI does not install `hmmsearch` or `taxonkit`, so `test_orient` / taxonkit-dependent tests behave differently in CI and locally (*to confirm which are skipped or mocked*). |
| TST-G-007 | No test that `default.yml` filenames match `conf/filenames.config` usage, or that `default.yml` equals what `dev/generate_default_config.py` would emit (CFG-D-001). |
| TST-G-008 | No test for the input-validation web service (`services/`). |
| TST-G-009 | nf-test snapshots contain file hashes of live-API-derived content, so they drift when GBIF/NCBI data change; there is no automated way to distinguish drift from regression (flag comparison is manual). |
| TST-G-010 | `bin/test_flags.py` is documented (`docs/nf-tests.md`) as living in `test/`; it is in `bin/`, and is therefore auto-added to every Nextflow task's `PATH`. |

## 5. Test data provenance

### 5.1 nf-test scenarios

| Scenario | Samples | Character |
|---|---|---|
| `scenario_01` | 6 | FASTA + metadata; `Scenario_01`–`Scenario_05`-style animal COI samples with `preliminary_id`/`taxa_of_interest` populated. |
| `scenario_02` | dozens | Metadata-only (`sequence` column, no separate FASTA); `locus=NA`, `classification=viruses` — the viral/bacterial barcode case family (sample ids like `barcode_57_1916-01_Grapevine_virus_E_cluster_0_RC2300`). |
| `scenario_03` | 14 | FASTA + metadata; mixed animal/insect COI samples (e.g. `SME25-218`, `SME25-221` lineage). |
| `scenario_04` | dozens | Metadata-only, mixed virus/bacteria/animal; `classification` sometimes blank. |
| `core` | 20 | Real BLAST (`mock_blast=false`) against a **subset** Core Nt DB; the authoritative, most diverse fixture — spans animal COI, a fungal β-tubulin sample (`FungusB_Btub`), a plant `matK` sample (`MP23-0432_matK`), and the same viral/bacterial barcode family as `scenario_02`/`04`. Reference-data versions are recorded in `test/core/README.md` (BLAST DB build date, taxonkit/taxdump date) per TST-005. |

### 5.2 Selenium fixtures

20 fixtures in `test/selenium/expected/*.yaml`, numbered `1`–`20`,
covering the same sample families as the `core` scenario (animal COI,
`FungusB_Btub`, `MP23-0432_matK`, `MG220521_3`, `VE24-1351_COI`,
`512503_1_Andrew`, and 9 virus/bacteria barcode samples) plus
`Scenario_01`–`05`, `SME25-218`, `SME25-221`. Matched to observed reports
by `sample_id`, not by file order (TST-030).

### 5.3 Fixtures are correctness tests, not benchmarks

**Do not tune a threshold against these fixtures.** They pin *current*
behaviour, including current bugs — `test/<scenario>/flags` baselines
were captured under today's defaults, which include the Flag 5.1
off-by-one (`P5-D-001`) and the other threshold defects in
[defects.md](defects.md). Fixing one of those defects is expected to
**change** the flag baseline for every sample it touches; that is the
correct outcome, not a regression, and the baseline must be regenerated
deliberately (`testkit.py promote`, TST-013) rather than treated as
ground truth to preserve. Conversely, a change that leaves these
baselines untouched is not proof a threshold fix was unnecessary — the
20–100-sample fixtures were not constructed to exercise every flag value
at every boundary.

---

## Provenance

**Initially derived from:** `.github/workflows/*.yml`, `scripts/tests/**`, `test/**`, `nf-test.config`, `bin/test_flags.py`, `bin/collect_flags.sh`, `testkit.py` (root), `scripts/tests/integration/testkit.py`. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
