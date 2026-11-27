# Spec: Deployment, images and release

## 1. Execution environments

| ID | Requirement |
|---|---|
| DEP-001 | The workflow MUST run under Singularity (`-profile singularity`) on a local machine or HPC, and under Azure Batch (`-profile azure`). Other engines are unsupported (NF-PR-005). |
| DEP-002 | Environments differ only in configuration (cache, throttle and vault backends; resources; container references); analysis code MUST NOT branch on the environment. |

| Environment | Cache | Throttle | Vault | Notes |
|---|---|---|---|---|
| Local | SQLite in `temp_root_dir` | SQLite | local file (`SECRET_KEY`) | |
| HPC | SQLite in a **shared** `temp_root_dir` | SQLite (Redis recommended) | local | `temp_root_dir` on a shared filesystem with `fcntl` locking is a hard prerequisite (THR-001) |
| Azure Batch | Azure Blob (`CACHE_BACKEND=azure_blob`, the coded default under `-profile azure`) | SQLite unless `THROTTLE_BACKEND=redis` is set — **not** automatic (`conf/azure.config` falls back to `sqlite`); Redis is only recommended, not defaulted | Azure Key Vault | Ephemeral nodes, no shared filesystem |

## 2. Container images

See [containers.md](containers.md) for the detailed companion — Dockerfile
contents, exact build/push commands, and the full container-pinning table
for the `nf-core/modules`-sourced tools.

| Image | Built from | Contents | Tag |
|---|---|---|---|
| `neoformit/taxodactyl` | `scripts/Dockerfile` | `python:3.12` + taxonkit + `scripts/` **source and requirements** at `/app/scripts` | `v<VERSION>` and `latest` (release, DEP-021); `main` (DEP-024); `<branch>` while a PR is open (DEP-025) |
| `ncbi/blast` | upstream | BLAST+ | `2.16.0` |
| MAFFT mulled image, `fastme` biocontainer | upstream | — | pinned in `conf/process.config` |

| ID | Requirement |
|---|---|
| DEP-010 | The analysis image MUST contain every executable the Python layer invokes: `taxonkit` (present), `hmmsearch` (**absent**, P1B-D-001). |
| DEP-011 | A release MUST reference the analysis image by its version tag, `v<VERSION>`, in `conf/process.config` and `conf/azure.config`; it MUST NOT use `latest`. Between releases both configs reference `neoformit/taxodactyl:main` (since `48dc4e8`), and the release checklist (`.github/release_template.md`) re-pins them; a run from `main` is therefore not reproducible from the commit (`DEP-D-014`). Either can be overridden per run with `TAXODACTYL_IMAGE` (DEP-026). |
| DEP-012 | `scripts/Dockerfile.update` builds `FROM neoformit/taxodactyl:latest` and copies the current `scripts/` over it (`docker_build.sh -u`): a code-only rebuild that inherits whatever `latest` currently is. It MUST NOT be used for releases (DEP-D-002). |
| DEP-013 | `scripts/docker_build.sh` builds `<image>:<tag>`, tags it `latest`, and with `-p` pushes both. |

## 3. Release

| ID | Requirement |
|---|---|
| DEP-020 | A release MUST update the version in **five** places: `conf/manifest.config` (`version`), `scripts/VERSION`, `scripts/pyproject.toml` (`version`), the `daff_tax_assign` image tag in `conf/process.config` and in `conf/azure.config`. (`cloudgene.yml` is no longer in this repository — removed in `3339050`; the Cloudgene workflow file lives in the `daff-cloudgene` repo.) Between releases the two image tags read `main` (DEP-011). |
| DEP-021 | Publishing a GitHub release triggers `.github/workflows/build.yml`: it MUST fail unless `v$(cat scripts/VERSION)` equals the release tag, then run `docker_build.sh -p -t <tag>` (pushing `<tag>` and `latest` to Docker Hub with repository secrets). |
| DEP-022 | The build workflow does not verify that `manifest.version`, `pyproject.toml` or the config image tags match the release tag (DEP-D-001). |
| DEP-023 | Before release, surfaces 2–4 of [tests.md](tests.md) SHOULD be run and the reference-data versions recorded. |
| DEP-024 | A push to `main` that changes `scripts/**.py`, `scripts/Dockerfile`, `scripts/requirements.txt` or `scripts/config/**` (or a manual dispatch) triggers `.github/workflows/build-main.yml`, which builds `scripts/Dockerfile` and pushes `neoformit/taxodactyl:main`. It does not use `docker_build.sh`, so `latest` is not moved. |
| DEP-025 | A pull request to `main` triggers `.github/workflows/build-pr.yml`. If the PR changes the same paths as DEP-024 (diffed against the base branch), it builds and pushes `neoformit/taxodactyl:<branch>` (branch name with characters outside `[A-Za-z0-9_.-]` replaced by `-`, at most 128 characters) and checks the tag exists remotely; otherwise the tag is `main`. It then calls `nf-test.yml` with that image ([tests.md](tests.md) TST-024). When the PR is closed, it deletes the branch tag from Docker Hub, refusing to delete `main`, `latest` or any `v…` tag. |
| DEP-026 | The `daff_tax_assign` container MUST be `$TAXODACTYL_IMAGE` when that variable is set in the environment that launches Nextflow (a leading `docker://` is stripped; NF-CF-011, NF-CF-021), so a run can test any image without editing config. `deployment/azure/run-taxodactyl*.sh` pass it through. |

## 4. Reference data

See [reference-data.md](reference-data.md) for the detailed companion —
every external data source (not only the locally-provisioned ones below),
split into what's provisioned vs. what's a live remote service.

The pipeline never builds or checks reference data; operators provision it
and pass paths (`--blastdb`, `--taxdb`). See NF-PA rows in
[nextflow/params.md](nextflow/params.md).

| ID | Requirement |
|---|---|
| DEP-030 | BLAST Core Nt MUST be a multi-volume database whose path ends in `core_nt` (start-up check NF-WF-013 only tests that `blastdb` is set). |
| DEP-031 | The taxdump directory MUST contain the nine `*.dmp/gc.prt` files (P0-031) and be from April 2025 or later for virus support. |
| DEP-032 | On Azure, reference data (≈250 GB) MUST be staged once per node by the pool start task to `/mnt/nvme/refdata` and mounted read-only into tasks; the run script defaults are `/mnt/nvme/refdata/core_nt/core_nt` and `/mnt/nvme/refdata/taxdump/taxdump`. |

## 5. Azure Batch deployment — DAFF's current tenancy

Everything in this section, except `DEP-040`/`DEP-041`, is **operator
config, not a general requirement**: it documents what DAFF's specific
Azure subscription is set up to do today, not something another deployer
running this pipeline on their own tenancy would need to replicate
exactly. See [config-profiles.md §4](nextflow/config-profiles.md) for the
same general-vs-operator split applied to `conf/azure.config` itself, and
`DEP-D-006`/[decisions.md `D-44`](decisions.md) for the open question of
moving these values out of the repo.

| Item | Value (hard-coded in repo, DAFF tenancy) |
|---|---|
| Pool | `taxodactyl`, autoscale 0–1 node, node retained 15 min after tasks, VM `Standard_L8as_v3` (8 vCPU, 64 GB, NVMe), Ubuntu 20.04 (per `pool-setup.json.template` and `docs/azure/`; see DEP-D-008) |
| Storage | `daffstandard` (`STORAGE_ACCOUNT_STD`) holds everything the pipeline uses: `workdata` (Nextflow work dir, blobs deleted after 14 days), `cache` (entries deleted after 7 days), `scripts` (pool start-task script) and `refdata-wf2` (Core Nt + taxdump, **public container-level read**, no SAS token), staged to node-local NVMe by the pool start task via `azcopy` outside Nextflow. Lifecycle rules (`deployment/azure/storage-policy.json`) match only `workdata/` and `cache/`. The same account also serves public CI test data (`test-data/`, used by `.github/workflows/nf-test.yml`). `daffpremium` (`STORAGE_ACCOUNT_PREM`) held `refdata` until `edaacae`; nothing in the repository, including `.env.sample` and `docs/azure/`, uses it now. |
| Batch account | `daffbatch`, `australiaeast` |
| Secrets | Key Vault via pool managed identity (`AZURE_KEY_VAULT_URL`); Batch and storage keys via `.env.azure` (not committed; `.env.sample` documents it) |
| Redis | dedicated VM (`redis-vm-setup.sh`) or on-demand |
| Entry scripts | `deployment/azure/run-taxodactyl.sh`: sources `.env.azure`, asks for confirmation, runs `nextflow run main.nf -profile azure …`. `run-taxodactyl-coverage.sh` does the same in database coverage mode (`--coverage-taxa <csv>` instead of `--metadata`/`--sequences`/`--blastdb`). |
| Docs | `docs/azure/01…07*.md` (setup, pool management, reference data, start tasks, troubleshooting, maintenance, Key Vault, Redis) |

The two items below *are* general requirements — they'd apply to any
Azure Batch deployment of this pipeline, not just DAFF's:

| ID | Requirement |
|---|---|
| DEP-040 | Azure credentials MUST be supplied via environment (`AZURE_BATCH_ACCESS_KEY`, `AZURE_STORAGE_ACCOUNT_KEY`) and never committed (`.gitignore` excludes `.env.*` except `*sample`). |
| DEP-041 | All processes run on the single node; `maxForks` limits (config-profiles.md NF-CF-022) are the only concurrency control. |

## 6. Defects

| ID | Severity | Defect |
|---|---|---|
| DEP-D-001 | Medium | Release consistency is checked only for `scripts/VERSION` vs the tag; the other four version locations can drift silently (e.g. image tag ≠ code). Re-pinning the image tags from `main` is a manual checklist item; if it's missed, the release runs whatever `:main` is (`DEP-D-014`). |
| DEP-D-002 | Medium | `docker_build.sh` always re-tags `latest` locally and, with `-p` (every CI release), pushes it to Docker Hub, and `Dockerfile.update` derives from `latest`, so a code-only update can be layered on a different base than the versioned tag intended. |
| DEP-D-003 | Medium | `Dockerfile` is not reproducible: floating `python:3.12` base and taxonkit from `releases/latest` (IMG-D-001); `apt install nano less` in production. |
| DEP-D-005 | Low | `run-taxodactyl.sh` uses `set -e` before `exit_code=$?`, so a failed run exits before the failure message. |
| DEP-D-006 | Low | Azure account names, pool, region and `/mnt/nvme/refdata` are hard-coded in `conf/azure.config`; a second tenant needs a fork or edit. |
| DEP-D-007 | Low | `scripts/dev/render_docs.py` is referenced for docs but docs rendering is not part of release automation. |
| DEP-D-008 | Medium | `.env.sample` sets `NODE_AGENT_SKU="batch.node.ubuntu 24.04"` / `IMAGE_TAG=canonical:ubuntu-24_04-lts:server`, but the committed `deployment/azure/pool-setup.json.template` and every `docs/azure/*.md` walkthrough (01, 02, 04) consistently use Ubuntu **20.04** (`batch.node.ubuntu 20.04`, `ubuntu-server-container:20-04-lts`, container image `ubuntu:20.04`), with 02 explicitly stating "We use Ubuntu 20.04 for Docker container compatibility". An operator who copies `.env.sample` to `.env.azure` as instructed and runs `az batch pool create --image $IMAGE_TAG --node-agent-sku-id "$NODE_AGENT_SKU"` creates a pool on a different OS than the one every doc and template assumes, risking the exact container-compatibility problem the docs say 20.04 was chosen to avoid. Either `.env.sample` is stale relative to the template/docs, or the template/docs were never updated after a 24.04 migration — *to confirm which*. |
| DEP-D-014 | Medium | Between releases, `conf/process.config` and `conf/azure.config` reference the moving `neoformit/taxodactyl:main` tag (since `48dc4e8`), rebuilt by `build-main.yml` (DEP-024) whenever the Python scripts change on `main`. A run from `main` uses whatever image `:main` was when Singularity or Azure pulled it (or a cached older copy), not one the commit determines, while the report's versions table names `manifest.version`. CONSTITUTION rule 11 forbids only `latest`, but `main` moves the same way. Mitigated for CI, which clears the Singularity cache and can pass an explicit image (TST-024). |

---

## Provenance

**Initially derived from:** `scripts/Dockerfile`, `scripts/Dockerfile.update`, `scripts/docker_build.sh`, `.github/workflows/build.yml`, `conf/process.config`, `conf/azure.config`, `conf/manifest.config`, `deployment/azure/**`, `.env.sample`. The `cloudgene.yml` removal added from `3339050`. DEP-011, DEP-024..026 and DEP-D-014 updated from `48dc4e8`, `9da958a`, `91fe43e` and `fe65a14` (image `main` tag, `build-main.yml`, `build-pr.yml`, `TAXODACTYL_IMAGE`); `run-taxodactyl-coverage.sh` from `ef96c8f`. See [README.md Version](README.md#version) for the exact commit.

This spec describes the intended behaviour. If the agent identifies a
suspected error, ambiguity, or inconsistency in the spec, including a conflict
with existing code, it must explain the concern to the user and agree on a
resolution before changing the affected code or spec.
