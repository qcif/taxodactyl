# Spec: Testing

There are four test surfaces. Only the first runs automatically; 3 and 4
also have a GitHub Actions workflow, but it runs only when triggered by
hand.

| # | Surface | Location | Runs | Automatic | Hermetic |
|---|---|---|---|---|---|
| 1 | Python unit tests | `scripts/tests/test_*.py` | `python -m unittest discover -s scripts/tests -p 'test*.py'` | **CI on push/PR to `main`** (`unit-tests.yml`, Python 3.12) | mostly (some need `hmmsearch`/`taxonkit`/network) |
| 2 | Python integration | `scripts/tests/integration/` | `run_tests.sh [--bold] [--keep] [--continue] [--test_case X]` | no | no — live NCBI/GBIF/BOLD |
| 3 | Nextflow end-to-end (`nf-test`) | `test/{scenario_01..04,core}` | `nf-test test <file>` (scenario chosen in `nf-test.config`) | manual only: `nf-test.yml` (`workflow_dispatch`, `core` scenario; TST-024) | no — needs BLAST/taxdump; P4/P5 use live APIs |
| 4 | Report UI (Selenium) | `test/selenium/` | `pytest test_reports.py --dir <reports>` | manual only: run by `nf-test.yml` on the reports it just produced | needs generated reports |

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
| TST-022 | Database-coverage flag regression check (post-run): `bin/collect_flags.sh` gathers only the P5 flags `5.1.flag`, `5.2.flag` and `5.3.flag` from the run; `bin/test_flags.py` compares them with `test/<scenario>/flags` (which holds only those three per query) using normalised JSON (sorted keys; lists sorted by `(flag_id, target, target_type)`) and prints per-path differences. Not part of the nf-test assertions themselves; the CI workflow (TST-024) runs it after nf-test and fails the job on any difference. The P3 flags (`1.flag`, `2.flag`, `7.flag`) and P4's `4.flag` are **not** in this check: they are covered only as file hashes inside the channel snapshots of TST-021 (`test/<scenario>/taxodactyl.workflow.nf.test.snap`). |
| TST-023 | Placeholders `CUSTOMISE` in each scenario's `nextflow.config` (`blastdb`, `taxdb`, `temp_root_dir`) and in `nf-test.config` (`workDir`) MUST be edited by the tester; the tests do not run out of the box. (The CI workflow fills them in with `sed`.) |
| TST-024 | `.github/workflows/nf-test.yml` runs the `core` scenario on a GitHub-hosted runner, **only when dispatched by hand** — push and pull-request triggers are commented out. It pins Nextflow 25.04.6, nf-test 0.9.5 and Singularity 3.8.7. It downloads frozen reference data (taxdump `2026-05-08`, subset BLAST DB `2026-07-29`) from DAFF's public `daffstandard/test-data` blob container, takes `NCBI_API_KEY`/`USER_EMAIL` from repository secrets, and runs real BLAST (`MOCK_BLAST=false`). Then it runs TST-022's flag check, collects the work directories of failed or drifting tasks (`bin/collect_artifacts.py`) and uploads them as an artifact, runs Selenium (TST-030) on the produced reports, and uploads `review.html`. `mock-nf-test.yml` (also manual) re-runs only the post-processing steps on a downloaded, frozen work directory. |

### 2.4 Selenium

| ID | Requirement |
|---|---|
| TST-030 | Fixtures `test/selenium/expected/*.yaml` (20) describe, per sample id, the values a browser must find in the report (overview, candidates, TOIs, database coverage, sample metadata; collectors in `lib/`). Reports are matched to fixtures by `sample_id`. A further 3 fixtures live in `expected/test/`, each fixture directory keeping its reference HTMLs in a sibling `reports/`. |
| TST-031 | `test/selenium/testkit.py render` builds a review page of differences; `promote` accepts drift into fixtures, backing up the previous YAML in `expected/.backups/` (last 3 kept). |
| TST-032 | `--dir` is required so a run states whether it validates new output or the checked-in reference reports (`expected/reports`). |
| TST-033 | Fields that come from live GenBank counts (`record_count`, `species_count`, `species_total`, `first_bar_count` in database coverage) carry a `flex` tolerance of ±10% (`GENBANK_FLEX_FIELDS`, `lib/database_coverage.py`). `pytest` passes a value within tolerance. `promote` still offers every difference, including ones within tolerance, so fixtures never silently drift. `flex` is set in code and stamped onto fixtures on ingest/promote; it is not edited by hand. |

## 3. Which requirements are exercised

| Area | Unit | Integration | nf-test | Selenium |
|---|---|---|---|---|
| Nextflow wiring, joins, gating | – | – | yes (channel snapshot + counts) | – |
| P0 validation | yes | – | – | – |
| P1 parsing | yes (stats) | yes | yes | – |
| P2 taxonomy | yes | yes | yes | – |
| P3 flags/candidates | phylogeny sampling only | yes (no asserts) | yes (channel snapshot hashes of `1/2/7.flag` and candidate files) | yes (overview) |
| P4 | partial (`fetch_sources`) | yes (no asserts) | yes (channel snapshot hash of `4.flag`) | partial |
| P5 | GBIF only | yes + `db_coverage.json` fixture | yes (flag baseline, TST-022, plus counts) | yes |
| P6 | – | yes (no asserts) | report count | yes |
| Shared throttle/cache/secrets/config | yes (cache, coalesce, secrets, config) | – | – | – |

## 4. Gaps (tests the spec implies but that do not exist)

| ID | Gap |
|---|---|
| TST-G-001 | No test of a `1E` (no candidate) query, the case most exposed to report suppression (`OUT-D-002`) / `P3-D-001`. |
| TST-G-002 | No test of Flag 5.1 thresholds (P5-D-001) or of taxid-less targets (P5-D-002). |
| TST-G-003 | P3 filtering, Flags 1/2/7 and output files have no unit tests. |
| TST-G-004 | P6 decision rules (§4 of `p6-report.md`) have no unit tests; only Selenium against generated HTML. |
| TST-G-005 | Nextflow: no `stub:` blocks, so no fast wiring test; `nf-test` needs real reference data and live APIs. The CI workflow (TST-024) works around the data by downloading a frozen subset, but still needs live APIs and a manual trigger. |
| TST-G-006 | CI does not install `hmmsearch` or `taxonkit`, so `test_orient` / taxonkit-dependent tests behave differently in CI and locally (*to confirm which are skipped or mocked*). |
| TST-G-007 | No test that `default.yml` filenames match `conf/filenames.config` usage, or that `default.yml` equals what `dev/generate_default_config.py` would emit (CFG-D-001). |
| TST-G-008 | No test for the input-validation web service (`services/`). |
| TST-G-009 | nf-test snapshots contain file hashes of live-API-derived content, so they drift when GBIF/NCBI data change, and nothing distinguishes that drift from a regression. Selenium now tolerates ±10% on GenBank counts (TST-033), and the CI workflow runs the flag comparison automatically, but neither helps the snapshots. |
| TST-G-010 | `bin/test_flags.py` is documented (`docs/nf-tests.md`) as living in `test/`; it is in `bin/`, and is therefore auto-added to every Nextflow task's `PATH`. The same applies to the other CI-only helpers kept there: `collect_artifacts.py` (new with TST-024), `diff_json_snapshot_to_csv.py`, `collect_flags.sh`. |

## 4a. Defects

| ID | Severity | Defect |
|---|---|---|
| TST-D-001 | Medium (security, *to confirm*) | `nf-test.yml` (TST-024) injects the repository secret `NCBI_API_KEY` into `test/core/nextflow.config`. It then uploads the work directories of failed or drifting tasks as the `error_workdirs` artifact: `bin/collect_artifacts.py` copies each whole directory with `shutil.copytree`, hidden files included. Several files in those directories hold the key in plain text. Nextflow writes the task environment (from the `env` scope) into each task's wrapper files (`.command.run`/`.command.env`). A `REPORT` task directory also holds the rendered report and `report_context.json` (`P6-D-001`, `P6-D-003`). GitHub masks secrets in **logs**, but not inside artifacts, and the repository is public, so anyone signed in to GitHub can download an artifact while it is retained (no `retention-days` is set, so the repository default applies). The same applies to `USER_EMAIL`. Nothing is uploaded on a fully clean run. *To confirm* by inspecting a downloaded `error_workdirs` artifact for the key. |

## 5. Test data provenance

### 5.1 nf-test scenarios

| Scenario | Samples | Character |
|---|---|---|
| `scenario_01` | 6 | FASTA + metadata; `Scenario_01`–`Scenario_06`-style animal COI samples with `preliminary_id`/`taxa_of_interest` populated. |
| `scenario_02` | 77 | Metadata-only (`sequence` column, no separate FASTA); `locus=NA`, `classification=viruses` — the viral/bacterial barcode case family (sample ids like `barcode_57_1916-01_Grapevine_virus_E_cluster_0_RC2300`). |
| `scenario_03` | 14 | FASTA + metadata; mixed animal/insect COI samples (e.g. `SME25-218`, `SME25-221` lineage). |
| `scenario_04` | 48 | Metadata-only, mixed virus/bacteria/animal; `classification` sometimes blank. |
| `core` | 20 | Real BLAST (`mock_blast=false`) against a **subset** Core Nt DB; the authoritative, most diverse fixture — spans animal COI, a fungal β-tubulin sample (`FungusB_Btub`), a plant `matK` sample (`MP23-0432_matK`), and the same viral/bacterial barcode family as `scenario_02`/`04`. Reference-data versions are recorded in `test/core/README.md` (BLAST DB build date, taxonkit/taxdump date) per TST-005. |

### 5.2 Selenium fixtures

20 fixtures in `test/selenium/expected/*.yaml`, numbered `1`–`20`,
covering the same sample families as the `core` scenario (animal COI,
`FungusB_Btub`, `MP23-0432_matK`, `MG220521_3`, `VE24-1351_COI`,
`512503_1_Andrew`, and 9 virus/bacteria barcode samples) plus
`Scenario_01`–`05`, `SME25-218`, `SME25-221`. Matched to observed reports
by `sample_id`, not by file order (TST-030). A further 3 fixtures in
`expected/test/` (`SME25-218`, `SME25-221`, `VE24-1351_COI`) are a small
subset with their own reference reports. GenBank-count fields carry
`flex: 0.1` (TST-033).

### 5.3 Fixtures are correctness tests, not benchmarks

**Do not tune a threshold against these fixtures.** They pin *current*
behaviour, including current bugs — `test/<scenario>/flags` baselines
were captured under today's defaults, which include the Flag 5.1
off-by-one (`P5-D-001`) and the other threshold defects in
[defects.md](defects.md). Fixing one of those defects is expected to
**change** the flag baseline for every sample it touches; that is the
correct outcome, not a regression, and the baseline must be regenerated
deliberately — by re-running `bin/collect_flags.sh` over a reviewed run
into `test/<scenario>/flags/` — rather than treated as ground truth to
preserve. That baseline holds only the P5 flags (5.1–5.3, TST-022).
A fix that changes P3 or P4 flags (1, 2, 4, 7) shows up instead as a
changed hash in the channel snapshot (TST-021, TST-G-009), which is
regenerated with nf-test's `--update-snapshot` after review; re-running
`collect_flags.sh` does not touch it. (There is no `promote` command for flag baselines.
`testkit.py promote` covers only the integration `db_coverage.json`
fixtures, TST-013; the Selenium `testkit.py promote` covers only report
YAMLs, TST-031.) Conversely, a change that leaves these
baselines untouched is not proof a threshold fix was unnecessary — the
20–100-sample fixtures were not constructed to exercise every flag value
at every boundary.

In other words: `bin/test_flags.py` only answers "did this change
anything" — it diffs a fresh run against a saved snapshot of whatever the
code did last time, not against an independently-known correct answer.
A failing diff after a bug fix is not evidence the fix was wrong, and a
clean diff after one is not evidence the fix was unnecessary; a human
still has to look at *what* changed (or didn't) and judge whether that
is correct, the same way they would review any other diff. The fixture
itself cannot make that call in either direction — reviewing and, when
warranted, regenerating the baseline is a deliberate step for exactly
this reason, not a rubber stamp. The same holds for the integration
fixtures and Selenium YAMLs, whose `promote` commands show the diff
before accepting it.

---

## Provenance

**Initially derived from:** `.github/workflows/*.yml`, `scripts/tests/**`, `test/**`, `nf-test.config`, `bin/test_flags.py`, `bin/collect_flags.sh`, `testkit.py` (root — a git symlink to `scripts/tests/integration/testkit.py`). Brought forward to `2e024f6` from `a24581f` (`nf-test.yml`, `mock-nf-test.yml`, `bin/collect_artifacts.py`) and `b0be80b` (`test/selenium/lib/*`, fixtures). See [README.md Version](README.md#version) for the exact commit.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
