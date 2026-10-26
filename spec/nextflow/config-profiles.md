# Spec: Nextflow configuration, profiles and resources

## 1. Composition

| ID | Requirement |
|---|---|
| NF-CF-001 | `nextflow.config` MUST include, in this order: `params`, `process`, `filenames`, `manifest`, `validation`, `profiles`, `misc`, `env`. |
| NF-CF-002 | `manifest.nextflowVersion` is `!>=24.10.6`: the pipeline MUST refuse to run on older Nextflow. `manifest.version` is the single source of the pipeline version used by `--version` — a fact about the code's own self-reporting, which changes at every release and is distinct from this spec's own provenance ([README.md § Version](../README.md#version)). It is one of **five** places a release must update in step — see `DEP-020` and the drift risk `DEP-D-001` in [../deployment.md](../deployment.md). The Nextflow *engine* version actually tested is a separate, weaker claim: the README's "Tested versions: 24.10.3, 24.10.6" note is itself inconsistent with the `!>=24.10.6` hard minimum (`NF-D-012`), and the nf-test CI workflow pins a third version, **25.04.6**, with a comment that later releases' stricter syntax parsing breaks this config (GitHub issue `#304`). There is no upper bound in `nextflowVersion`. |
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
| NF-CF-011 | Containers: label `daff_tax_assign` → `docker://neoformit/taxodactyl:v1.5.0`; label `blast` → `docker://ncbi/blast:2.16.0`; `MAFFT_ALIGN` → the pinned mulled-v2 image; `FASTME` → `quay.io/biocontainers/fastme:2.1.6.3--h7b50bb2_1`. No `latest` tags. There is no process-wide default container, so `PREPARE_INPUTS` and `PREPARE_LOG`, which match none of these, run in the host shell (`NF-D-020`). |
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

**Defect `NF-D-011` (Medium, [defects.md](../defects.md)).** The `1MB`
default memory is not a real requirement — it is only harmless on the
`local` executor, which does not enforce `memory` at all (it's advisory
there). Under a scheduler that *does* enforce `memory` (SLURM, LSF, etc.)
every process without an override above would be OOM-killed outright.
Several of those "without an override" cases aren't obvious from the
table alone: each `withName: <PROCESS>` block in `conf/process.config`
replaces *only the directives it mentions*, so a process can override
some resources and silently fall through to the `1MB`/`10m` global
default for the rest. `MAFFT_ALIGN`'s block, for example, sets `cpus`
(`2`) and `container` but says nothing about `memory`/`time` — so despite
doing real alignment work, it still runs under the same `1MB`/`10m`
defaults as a trivial housekeeping process like `PREPARE_LOG`. That's a
silent fallthrough, not a deliberate choice to under-resource it — which
is exactly why the table above shows "(default)" rather than an explicit
value in several cells. Real memory needs are undocumented (Azure config
uses 2 GB for the light processes, as a reference point).

## 3. Profiles (`conf/profiles.config`)

| Profile | Effect |
|---|---|
| `singularity` | singularity on, `autoMounts` true; all other engines off. **The only tested engine.** |
| `apptainer`, `docker`, `podman`, `shifter`, `charliecloud`, `conda`, `mamba` | nf-core boilerplate, mutually exclusive engine flags. Not supported (NF-PR-005). |
| `arm` | adds `--platform=linux/amd64` to docker runOptions. |
| `azure` | `includeConfig 'azure.config'` (see §4). |
| `test` | `includeConfig 'test.config'`: `metadata=test/metadata.csv`, `sequences=test/query.fasta`, `db_type='bold'`, analyst/facility placeholders. **The out-of-the-box test profile cannot succeed** — `db_type='bold'` selects the branch that cannot currently complete a run (`NF-D-009`, root cause `NF-D-002`; tracked under [decisions.md `D-01`](../decisions.md)). |
| `debug` | `dumpHashes`, keep work dir (`cleanup=false`), echo hostname. |
| `wave`, `gitpod` | nf-core boilerplate. |

- `custom_config_base` (nf-core institutional configs) is fetched from the network unless `NXF_OFFLINE` is set.
- Registry for all engines defaults to `quay.io` (irrelevant for fully qualified images).

## 4. Azure Batch profile (`conf/azure.config`)

This section mixes two different kinds of statement. **General
requirements** (`NF-CF-020`–`022`, `024`, `026`) describe how
`-profile azure` works architecturally — they'd hold for *any* operator
who points this pipeline at their own Azure Batch tenancy, not only DAFF.
**Operator-specific values** (`NF-CF-023`, `025`) are literal facts about
*DAFF's current tenancy* — account names, region, a node path — hard-coded
into `conf/azure.config` rather than parameterised. They are not a
requirement another deployer must satisfy; they're what the repo
currently assumes, and a second tenant needs to edit them. The split
isn't yet reflected in the code (`DEP-D-006`); [decisions.md
`D-44`](../decisions.md) is open on moving them to a private overlay.

**General requirements:**

| ID | Requirement |
|---|---|
| NF-CF-020 | Under `-profile azure`, every process MUST use executor `azurebatch`, `errorStrategy 'ignore'`, default memory 2 GB, default container `docker.io/library/ubuntu:22.04`. |
| NF-CF-021 | Container refs MUST use `docker.io/...` (Azure Batch rejects `docker://`): `neoformit/taxodactyl:v1.5.0`, `ncbi/blast:2.16.0`. |
| NF-CF-022 | Resource classes (single-node design, pool 0–1 nodes): **heavy** `BLAST_BLASTN|BLAST_BLASTDBCMD|EXTRACT_TAXONOMY` 8 cpu / 64 GB / `maxForks 1` / 1 h; **medium** `MAFFT_ALIGN|FASTME` 4 / 32 GB / `maxForks 2` / 1 h; **light** `VALIDATE_INPUT|EXTRACT_HITS|EXTRACT_CANDIDATES|REPORT` 1 / 2 GB / `maxForks 16` / 30 m; **API** `EVALUATE_SOURCE_DIVERSITY|EVALUATE_DATABASE_COVERAGE` 0.5 / 2 GB / `maxForks 16` / 1 h. |
| NF-CF-024 | Azure env MUST forward: `THROTTLE_BACKEND` (default `sqlite`), `REDIS_HOST/PORT/PASSWORD`, `AZURE_KEY_VAULT_URL`, `CACHE_BACKEND` (default `azure_blob`), `CACHE_AZURE_ACCOUNT_URL`, `CACHE_AZURE_CONNECTION_STRING`, `CACHE_AZURE_CONTAINER`, `CACHE_AZURE_BLOB_PREFIX`. |
| NF-CF-026 | Under Azure, `containerOptions` are overridden to `-v` syntax, so the `--bind` options in modules are not used for the listed processes. `PREPARE_INPUTS/PREPARE_LOG/BOLD_SEARCH/MOCK_BLASTN` have no override. |

**DAFF's current tenancy (operator-specific, not a general requirement):**

| ID | Current value |
|---|---|
| NF-CF-023 | `workDir` is `az://workdata/work`; reference data is pre-staged on the node at `/mnt/nvme/refdata` and mounted read-only (`-v /mnt/nvme/refdata:/mnt/nvme/refdata:ro`); `REPORT` additionally sets `-e TZ=Australia/Brisbane`; Batch queue is named `taxodactyl`. |
| NF-CF-025 | Storage account `daffstandard` (key from `AZURE_STORAGE_ACCOUNT_KEY`); batch account `daffbatch`, region `australiaeast`, `autoPoolMode false`, `allowPoolCreation false`, `copyToolInstallMode 'task'`, jobs/tasks not deleted on completion. |

## 5. Environment (`conf/env.config`)

The following environment variables MUST be exported into every task:
`LOGGING_DEBUG`, `BOLD_SKIP_ORIENTATION`, `HOME` (fixed to
`/tmp/taxodactyl/config`), `NCBI_API_KEY`, `USER_EMAIL`, `TAXONKIT_DATA`
(= `params.taxdb` or `''`), `SECRET_KEY` (launcher env or `''`). Python
behaviour keyed on these is specified in
[../python/shared/config.md](../python/shared/config.md).

**Defect `NF-D-018` (Low, *to confirm*, [defects.md](../defects.md)).**
`HOME` was added with the nf-test CI workflow (`a24581f`) but sits in
`conf/env.config`, so it applies to every profile, not just CI. Two code
paths read it through `Path.home()`/`expanduser`: the fallback local
secrets directory, `~/.local/share/taxodactyl/<user>` (used when
`/var/lib/taxodactyl` isn't writable — as in a read-only Singularity
image), and the default `taxdb_dir`, `~/.taxonkit` (used only if no
`--taxdb` is given). Both now resolve under `/tmp`, so per-user vault
data could land in a shared `/tmp` on HPC. Whether Singularity/Apptainer
actually honour a `HOME` passed this way is unconfirmed — they often
override it.

## 6. Run reporting (`conf/misc.config`)

| ID | Requirement |
|---|---|
| NF-CF-030 | `timeline`, `report`, `trace`, `dag` MUST be enabled and written to `<outdir>/pipeline_info/` with the run suffix; the trace MUST include field `workdir` (required by NF-WF-004). |
| NF-CF-031 | `workflow.failOnIgnore = true`: a run in which any task error was ignored MUST finish with a non-zero exit status. |
| NF-CF-032 | `cleanup = false`: the work directory is never auto-deleted. |
| NF-CF-033 | `validation.defaultIgnoreParams = ["genomes"]`; help enabled with `--help_full` / `--show_hidden`. |

---

## Provenance

**Initially derived from:** `nextflow.config`, `conf/*.config`. See [README.md Version](../README.md#version) for the exact commit.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
