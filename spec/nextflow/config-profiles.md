# Spec: Nextflow configuration, profiles and resources

**Sources:** `nextflow.config`, `conf/*.config`. Derived from code.

## 1. Composition

| ID | Requirement |
|---|---|
| NF-CF-001 | `nextflow.config` MUST include, in this order: `params`, `process`, `filenames`, `manifest`, `validation`, `profiles`, `misc`, `env`. |
| NF-CF-002 | `manifest.nextflowVersion` is `!>=24.10.6`: the pipeline MUST refuse to run on older Nextflow. `manifest.version` (`1.5.0`) is the single source of the pipeline version used by `--version`. |
| NF-CF-003 | `conf/filenames.config` MUST parse `scripts/config/default.yml` with `YamlSlurper` and expose filenames as `process.ext.*`. `blast_xml_filename`, `candidates_msa` and `versions_yml` are defined in Nextflow itself (`blast_result.xml`, `candidates_phylogeny.msa`, `versions.yml`); all others originate from the Python config. |
| NF-CF-004 | Plugins: `nf-schema@2.1.1` and `nf-azure` (latest) MUST be declared in `misc.config`. |

`ext` keys exposed (the Nextflow↔Python filename contract):
`accessions_filename`, `blast_xml_filename`, `hits_fasta`, `hits_json`,
`boxplot_img`, `candidates_csv`, `candidates_fasta`,
`candidates_phylogeny_fasta`, `candidates_json`, `candidates_sources_json`,
`independent_sources_json`, `bold_taxonomy_json`, `taxonomy_file`,
`candidates_msa`, `tree_nwk`, `query_title_file`, `candidates_count_file`,
`taxonomy_id_csv`, `pmi_match_csv`, `toi_detected_csv`, `log_filename`,
`versions_yml`. Values are fixed in `scripts/config/default.yml`; see
[../contracts/filenames.md](../contracts/filenames.md).

## 2. Process defaults and resources (`conf/process.config`, local/HPC)

| ID | Requirement |
|---|---|
| NF-CF-010 | Default for every process: `errorStrategy 'ignore'`, `cpus 1`, `memory '1MB'`, `time '10m'`, and `beforeScript` = `mkdir -p "<temp_root_dir>"`. |
| NF-CF-011 | Containers: label `daff_tax_assign` → `docker://neoformit/taxodactyl:v1.5.0`; label `blast` → `docker://ncbi/blast:2.16.0`; `MAFFT_ALIGN` → the pinned mulled-v2 image; `FASTME` → `quay.io/biocontainers/fastme:2.1.6.3--h7b50bb2_1`. No `latest` tags. |
| NF-CF-012 | The image tag of `daff_tax_assign` MUST equal `manifest.version` and `scripts/VERSION` at release (see [../deployment.md](../deployment.md)). |

Per-process overrides:

| Process | cpus | memory | time | other |
|---|---|---|---|---|
| `BLAST_BLASTN` | 4 | 7 GB | 4 h | |
| `BOLD_SEARCH` | 2 | 2 GB | 1 h | |
| `EXTRACT_TAXONOMY` | 2 | 1 GB | 10 m (default) | |
| `EVALUATE_DATABASE_COVERAGE` | 0.5 | 2 GB | 1 h | `maxForks 10` |
| `EVALUATE_SOURCE_DIVERSITY` | 0.5 | **1 MB (default)** | 1 h | `maxForks 10` |
| `MAFFT_ALIGN` | 2 | 1 MB (default) | 10 m (default) | |
| `FASTME` | 1 | 20 MB | 2 h | |
| `/.*PREPARE.*/` | 0.5 | 1 MB | 10 m | |
| all others (`VALIDATE_INPUT`, `EXTRACT_HITS`, `EXTRACT_CANDIDATES`, `REPORT`, `BLAST_BLASTDBCMD`, `MOCK_BLASTN`) | 1 | 1 MB | 10 m | |

**Observation (NF-D-011).** The `1MB` default memory is not a real
requirement — it is only harmless on the local executor, which does not
enforce memory. Under a scheduler that enforces `memory` (SLURM, LSF, etc.)
every process without an override would be killed. Real memory needs are
undocumented (Azure config uses 2 GB for the light processes).

## 3. Profiles (`conf/profiles.config`)

| Profile | Effect |
|---|---|
| `singularity` | singularity on, `autoMounts` true; all other engines off. **The only tested engine.** |
| `apptainer`, `docker`, `podman`, `shifter`, `charliecloud`, `conda`, `mamba` | nf-core boilerplate, mutually exclusive engine flags. Not supported (NF-PR-005). |
| `arm` | adds `--platform=linux/amd64` to docker runOptions. |
| `azure` | `includeConfig 'azure.config'` (see §4). |
| `test` | `includeConfig 'test.config'`: `metadata=test/metadata.csv`, `sequences=test/query.fasta`, `db_type='bold'`, analyst/facility placeholders. |
| `debug` | `dumpHashes`, keep work dir (`cleanup=false`), echo hostname. |
| `wave`, `gitpod` | nf-core boilerplate. |

- `custom_config_base` (nf-core institutional configs) is fetched from the network unless `NXF_OFFLINE` is set.
- Registry for all engines defaults to `quay.io` (irrelevant for fully qualified images).

## 4. Azure Batch profile (`conf/azure.config`)

| ID | Requirement |
|---|---|
| NF-CF-020 | Under `-profile azure`, `workDir` MUST be `az://workdata/work` and every process MUST use executor `azurebatch`, queue `taxodactyl`, `errorStrategy 'ignore'`, default memory 2 GB, default container `docker.io/library/ubuntu:22.04`. |
| NF-CF-021 | Container refs MUST use `docker.io/...` (Azure Batch rejects `docker://`): `neoformit/taxodactyl:v1.5.0`, `ncbi/blast:2.16.0`. |
| NF-CF-022 | Resource classes (single-node design, pool 0–1 nodes): **heavy** `BLAST_BLASTN|BLAST_BLASTDBCMD|EXTRACT_TAXONOMY` 8 cpu / 64 GB / `maxForks 1` / 1 h; **medium** `MAFFT_ALIGN|FASTME` 4 / 32 GB / `maxForks 2` / 1 h; **light** `VALIDATE_INPUT|EXTRACT_HITS|EXTRACT_CANDIDATES|REPORT` 1 / 2 GB / `maxForks 16` / 30 m; **API** `EVALUATE_SOURCE_DIVERSITY|EVALUATE_DATABASE_COVERAGE` 0.5 / 2 GB / `maxForks 16` / 1 h. |
| NF-CF-023 | Reference data MUST be pre-staged on the node at `/mnt/nvme/refdata` and mounted read-only (`-v /mnt/nvme/refdata:/mnt/nvme/refdata:ro`); `REPORT` additionally sets `-e TZ=Australia/Brisbane`. |
| NF-CF-024 | Azure env MUST forward: `THROTTLE_BACKEND` (default `sqlite`), `REDIS_HOST/PORT/PASSWORD`, `AZURE_KEY_VAULT_URL`, `CACHE_BACKEND` (default `azure_blob`), `CACHE_AZURE_ACCOUNT_URL`, `CACHE_AZURE_CONNECTION_STRING`, `CACHE_AZURE_CONTAINER`, `CACHE_AZURE_BLOB_PREFIX`. |
| NF-CF-025 | Storage account `daffstandard` (key from `AZURE_STORAGE_ACCOUNT_KEY`); batch account `daffbatch`, `australiaeast`, `autoPoolMode false`, `allowPoolCreation false`, `copyToolInstallMode 'task'`, jobs/tasks not deleted on completion. |
| NF-CF-026 | Under Azure, `containerOptions` are overridden to `-v` syntax, so the `--bind` options in modules are not used for the listed processes. `PREPARE_INPUTS/PREPARE_LOG/BOLD_SEARCH/MOCK_BLASTN` have no override. |

Note: Azure account names, region and node paths are **hard-coded**
(`daffbatch`, `daffstandard`, `taxodactyl` pool, `/mnt/nvme/refdata`);
another deployment needs a config edit. Tenancy-specific values belong in
a private overlay, not in this repo (open question).

## 5. Environment (`conf/env.config`)

The following environment variables MUST be exported into every task:
`LOGGING_DEBUG`, `BOLD_SKIP_ORIENTATION`, `NCBI_API_KEY`, `USER_EMAIL`,
`TAXONKIT_DATA` (= `params.taxdb` or `''`), `SECRET_KEY` (launcher env or
`''`). Python behaviour keyed on these is specified in
[../python/shared/config.md](../python/shared/config.md).

## 6. Run reporting (`conf/misc.config`)

| ID | Requirement |
|---|---|
| NF-CF-030 | `timeline`, `report`, `trace`, `dag` MUST be enabled and written to `<outdir>/pipeline_info/` with the run suffix; the trace MUST include field `workdir` (required by NF-WF-004). |
| NF-CF-031 | `workflow.failOnIgnore = true`: a run in which any task error was ignored MUST finish with a non-zero exit status. |
| NF-CF-032 | `cleanup = false`: the work directory is never auto-deleted. |
| NF-CF-033 | `validation.defaultIgnoreParams = ["genomes"]`; help enabled with `--help_full` / `--show_hidden`. |
