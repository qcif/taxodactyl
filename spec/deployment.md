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

| Image | Built from | Contents | Tag |
|---|---|---|---|
| `neoformit/taxodactyl` | `scripts/Dockerfile` | `python:3.12` + taxonkit + `scripts/` **source and requirements** at `/app/scripts` | `v<VERSION>` and `latest` |
| `ncbi/blast` | upstream | BLAST+ | `2.16.0` |
| MAFFT mulled image, `fastme` biocontainer | upstream | — | pinned in `conf/process.config` |

| ID | Requirement |
|---|---|
| DEP-010 | The analysis image MUST contain every executable the Python layer invokes: `taxonkit` (present), `hmmsearch` (**absent**, P1B-D-001). |
| DEP-011 | The pipeline MUST reference the analysis image by an explicit version tag in `conf/process.config` and `conf/azure.config`; it MUST NOT use `latest`. (Satisfied: both say `v1.5.0`.) |
| DEP-012 | `scripts/Dockerfile.update` builds `FROM neoformit/taxodactyl:latest` and copies the current `scripts/` over it (`docker_build.sh -u`): a code-only rebuild that inherits whatever `latest` currently is. It MUST NOT be used for releases (DEP-D-002). |
| DEP-013 | `scripts/docker_build.sh` builds `<image>:<tag>`, tags it `latest`, and with `-p` pushes both. |

## 3. Release

| ID | Requirement |
|---|---|
| DEP-020 | A release MUST update the version in **five** places: `conf/manifest.config` (`version`), `scripts/VERSION`, `scripts/pyproject.toml` (`version`), the `daff_tax_assign` image tag in `conf/process.config` and in `conf/azure.config`. (`scripts/README.md` lists four, including a `cloudgene.yml` that does not exist in the repository; it omits the two image tags.) |
| DEP-021 | Publishing a GitHub release triggers `.github/workflows/build.yml`: it MUST fail unless `v$(cat scripts/VERSION)` equals the release tag, then run `docker_build.sh -p -t <tag>` (pushing `<tag>` and `latest` to Docker Hub with repository secrets). |
| DEP-022 | The build workflow does not verify that `manifest.version`, `pyproject.toml` or the config image tags match the release tag (DEP-D-001). |
| DEP-023 | Before release, surfaces 2–4 of [tests.md](tests.md) SHOULD be run and the reference-data versions recorded. |

## 4. Reference data

The pipeline never builds or checks reference data; operators provision it
and pass paths (`--blastdb`, `--taxdb`). See NF-PA rows in
[nextflow/params.md](nextflow/params.md).

| ID | Requirement |
|---|---|
| DEP-030 | BLAST Core Nt MUST be a multi-volume database whose path ends in `core_nt` (start-up check NF-WF-013 only tests that `blastdb` is set). |
| DEP-031 | The taxdump directory MUST contain the nine `*.dmp/gc.prt` files (P0-031) and be from April 2025 or later for virus support. |
| DEP-032 | On Azure, reference data (≈250 GB) MUST be staged once per node by the pool start task to `/mnt/nvme/refdata` and mounted read-only into tasks; the run script defaults are `/mnt/nvme/refdata/core_nt/core_nt` and `/mnt/nvme/refdata/taxdump/taxdump`. |

## 5. Azure Batch deployment (as implemented)

| Item | Value (hard-coded in repo) |
|---|---|
| Pool | `taxodactyl`, autoscale 0–1 node, node retained 15 min after tasks, VM `Standard_L8as_v3` (8 vCPU, 64 GB, NVMe), Ubuntu 20.04 (per `pool-setup.json.template` and `docs/azure/`; see DEP-D-008) |
| Storage | **two accounts**: `daffstandard` (`STORAGE_ACCOUNT_STD`) holds `workdata` (Nextflow work dir, deleted after 14 days), `scripts`, `cache` (entries deleted after 7 days) — lifecycle rules in `deployment/azure/storage-policy.json`, applied to `daffstandard` only; `daffpremium` (`STORAGE_ACCOUNT_PREM`) holds `refdata` only, staged directly to node-local NVMe by the pool start task via `azcopy` (outside Nextflow, no lifecycle rule) |
| Batch account | `daffbatch`, `australiaeast` |
| Secrets | Key Vault via pool managed identity (`AZURE_KEY_VAULT_URL`); Batch and storage keys via `.env.azure` (not committed; `.env.sample` documents it) |
| Redis | dedicated VM (`redis-vm-setup.sh`) or on-demand |
| Entry script | `deployment/azure/run-taxodactyl.sh`: sources `.env.azure`, asks for confirmation, runs `nextflow run main.nf -profile azure …` |
| Docs | `docs/azure/01…07*.md` (setup, pool management, reference data, start tasks, troubleshooting, maintenance, Key Vault, Redis) |

| ID | Requirement |
|---|---|
| DEP-040 | Azure credentials MUST be supplied via environment (`AZURE_BATCH_ACCESS_KEY`, `AZURE_STORAGE_ACCOUNT_KEY`) and never committed (`.gitignore` excludes `.env.*` except `*sample`). |
| DEP-041 | All processes run on the single node; `maxForks` limits (config-profiles.md NF-CF-022) are the only concurrency control. |

## 6. Defects

| ID | Severity | Defect |
|---|---|---|
| DEP-D-001 | Medium | Release consistency is checked only for `scripts/VERSION` vs the tag; the other four version locations can drift silently (e.g. image tag ≠ code). |
| DEP-D-002 | Medium | `docker_build.sh` always pushes `latest`, and `Dockerfile.update` derives from `latest`, so a code-only update can be layered on a different base than the versioned tag intended. |
| DEP-D-003 | Medium | `Dockerfile` is not reproducible: floating `python:3.12` base and taxonkit from `releases/latest` (IMG-D-001); `apt install nano less` in production. |
| DEP-D-005 | Low | `run-taxodactyl.sh` uses `set -e` before `exit_code=$?`, so a failed run exits before the failure message. |
| DEP-D-006 | Low | Azure account names, pool, region and `/mnt/nvme/refdata` are hard-coded in `conf/azure.config`; a second tenant needs a fork or edit. |
| DEP-D-007 | Low | `scripts/README.md`'s release section is out of date (`cloudgene.yml`, four locations); `scripts/dev/render_docs.py` is referenced for docs but docs rendering is not part of release automation. |
| DEP-D-008 | Medium | `.env.sample` sets `NODE_AGENT_SKU="batch.node.ubuntu 24.04"` / `IMAGE_TAG=canonical:ubuntu-24_04-lts:server`, but the committed `deployment/azure/pool-setup.json.template` and every `docs/azure/*.md` walkthrough (01, 02, 04) consistently use Ubuntu **20.04** (`batch.node.ubuntu 20.04`, `ubuntu-server-container:20-04-lts`, container image `ubuntu:20.04`), with 02 explicitly stating "We use Ubuntu 20.04 for Docker container compatibility". An operator who copies `.env.sample` to `.env.azure` as instructed and runs `az batch pool create --image $IMAGE_TAG --node-agent-sku-id "$NODE_AGENT_SKU"` creates a pool on a different OS than the one every doc and template assumes, risking the exact container-compatibility problem the docs say 20.04 was chosen to avoid. Either `.env.sample` is stale relative to the template/docs, or the template/docs were never updated after a 24.04 migration — *to confirm which*. |

---

## Provenance

**Initially derived from:** `scripts/Dockerfile`, `scripts/Dockerfile.update`, `scripts/docker_build.sh`, `.github/workflows/build.yml`, `conf/process.config`, `conf/azure.config`, `conf/manifest.config`, `deployment/azure/**`, `.env.sample`. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
