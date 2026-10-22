# Reference: container images

Not a replacement for [deployment.md §2–3](deployment.md) — those keep
the normative `DEP-0xx` requirements (`DEP-010`..`023`). This is the
detailed companion: what's actually in each image, how it's built, and
the exact commands, so a reader doesn't have to reconstruct them from the
Dockerfile and shell scripts themselves.

**Single source of truth for what's wired in:** `conf/process.config`
(local/HPC) and `conf/azure.config` (Azure) — specifically the
`withLabel`/`withName` blocks. Nothing elsewhere in the repo overrides
them.

## 1. Custom-logic image: `neoformit/taxodactyl`

Built from `scripts/Dockerfile`:

```dockerfile
FROM python:3.12

RUN apt update && apt install -y nano less

# Install taxonkit
RUN wget https://github.com/shenwei356/taxonkit/releases/latest/download/taxonkit_linux_amd64.tar.gz \
    && tar -zxvf taxonkit_linux_amd64.tar.gz \
    && mv taxonkit /usr/local/bin/ \
    && rm taxonkit_linux_amd64.tar.gz

# Install HMMSearch
# RUN wget http://eddylab.org/software/hmmer/hmmer-3.4.tar.gz \
#     ... (10 more commented-out lines, full build-from-source recipe) ...

COPY . /app/scripts
RUN pip install -r /app/scripts/requirements.txt
RUN mkdir -p /var/lib/taxodactyl/
```

- **Base:** `python:3.12` — a floating tag, not a digest. Reproducing a
  past build exactly requires knowing when it was built (`IMG-D-001`).
- **`taxonkit`:** fetched from `releases/latest` on every build — same
  floating-tag problem, specific to this one binary (`IMG-D-001`). There
  is no version pin anywhere in the Dockerfile for it.
- **`hmmsearch` (HMMER):** the entire install block exists in the
  Dockerfile but is **commented out** (shown above, abbreviated — the
  real file has the full build-from-source recipe, `configure`/`make`/
  `make install`/`strip`). This is the literal, direct cause of
  `P1B-D-001`: BOLD-mode orientation calls `hmmsearch` unconditionally
  unless skipped, and it simply isn't on the `PATH` in this image.
  Someone evidently started wiring it in and stopped.
- **`nano`/`less`:** interactive editing/paging tools installed into a
  production image — harmless, but dead weight (part of `DEP-D-003`).
- **Everything else:** the whole `scripts/` tree (all P0–P6 entrypoints
  and the `src/` package) is copied in at `/app/scripts` and invoked
  in-container as `python /app/scripts/<pN_*.py>` (`NF-PR-003`) — there is
  no separate "deploy the code" step; the image *is* the code.

**Build and push** (`scripts/docker_build.sh`):

```bash
docker build -t $IMAGE:$TAG -f $DOCKERFILE .
docker tag $IMAGE:$TAG $IMAGE:latest     # always, unconditionally
if [ "$PUSH" = true ]; then
  docker push $IMAGE:$TAG
  docker push $IMAGE:latest              # both tags pushed together
fi
```

Run manually as `./docker_build.sh -t <tag> -p`. If `-t` is omitted, it
reads `scripts/VERSION`, prompts "Have you updated the VERSION file?",
and uses `v$(cat VERSION)` as the tag. Every build — manual or CI — tags
and pushes `:latest` alongside the versioned tag, unconditionally; this
is `DEP-D-002`'s root cause, not a separate bug.

**CI** (`.github/workflows/build.yml`, triggered on a published GitHub
release):

```yaml
- name: Check that VERSION file is up-to-date
  run: |
    if [ "v$(cat scripts/VERSION)" != "${{ env.VERSION_TAG }}" ]; then
      echo "VERSION file does not match the release tag..."; exit 1
    fi
- name: Build and push Docker image
  run: cd scripts && ./docker_build.sh -p -t "$VERSION_TAG"
```

This is the *entire* release-consistency check (`DEP-021`): it verifies
`scripts/VERSION` against the git release tag and nothing else — not
`manifest.version`, not `pyproject.toml`, not either config's image tag
(`DEP-D-001`, the other four of the five version locations in `DEP-020`).

**Code-only rebuild** (`scripts/Dockerfile.update`, `docker_build.sh -u`):
builds `FROM neoformit/taxodactyl:latest` and copies the current
`scripts/` over it — a layer on top of whatever `:latest` currently is,
not a from-scratch build. `DEP-012` says this MUST NOT be used for a
release; nothing technical stops someone from doing it anyway.

**Currently pinned** (both `conf/process.config` and `conf/azure.config`,
label `daff_tax_assign`): `v1.5.0` — matching `DEP-011`'s "no `latest`
tags" requirement at the point of use, even though the image's own
*contents* aren't reproducible from that tag alone (`IMG-D-001`).

## 2. Off-the-shelf tools

`BLAST_BLASTN`, `BLAST_BLASTDBCMD`, `MAFFT_ALIGN` and `FASTME` started
as `nf-core/modules` installs, which each declared their own
biocontainers image (e.g. `blast:2.15.0`). They were replaced by local
rewrites in May 2025 (`e393a9c`/`7b6d96a`; see
[nextflow/nf-core-conformance.md §0](nextflow/nf-core-conformance.md)).
`modules.json` still lists them as nf-core installs (`NF-D-019`). None of
the current `main.nf` files declares a `container` directive — checked
directly: `BLAST_BLASTN`/`BLAST_BLASTDBCMD` only carry `label 'blast'`,
`MAFFT_ALIGN`/`FASTME` carry no label or container line at all. Every one
of them is pinned entirely by `conf/process.config`/`conf/azure.config`'s
`withLabel`/`withName` blocks:

| Tool | Container | How it's selected |
|---|---|---|
| BLAST+ (`blastn`, `blastdbcmd`) | `ncbi/blast:2.16.0` | `withLabel: 'blast'` |
| MAFFT | `quay.io/biocontainers/mulled-v2-12eba4a074f913c639117640936668f5a6a01da6:425707898cf4f85051b77848be253b88f1d2298a-0` | `withName: MAFFT_ALIGN` |
| FastME | `quay.io/biocontainers/fastme:2.1.6.3--h7b50bb2_1` | `withName: FASTME` |

The MAFFT image is a `mulled-v2` bundle (a Biocontainers convention for
packaging more than one bioconda tool into a single image when a process
needs several tools together) — its hash-based tag is opaque by design;
the real pin is the full digest string above, not a human-readable
version.

**Azure quirk** (`NF-CF-021`): Azure Batch rejects the `docker://` scheme
these `withLabel`/`withName` blocks imply for local/HPC; `conf/azure.config`
re-expresses the same two custom-logic/BLAST images with a `docker.io/...`
prefix instead. The MAFFT/FastME biocontainer images, already fully
qualified (`quay.io/...`), don't need this treatment.

## 3. Checking what's actually pinned right now

`conf/process.config`'s `process { ... }` block (local/HPC) or
`conf/azure.config`'s equivalent (Azure) — not this file, not
`deployment.md`, not `modules.json`. Those config files are the only
place that's guaranteed current; everything above is a snapshot at this
spec's derivation commit ([README.md § Version](README.md#version)).

## 4. Known gaps

All already registered in [defects.md](defects.md) — not repeated here
with new IDs, just the pointer: `IMG-D-001` (floating base + taxonkit),
`DEP-D-001` (only one of five version locations checked), `DEP-D-002`
(unconditional `:latest`), `DEP-D-003` (dev tools in prod image),
`NF-D-014` (no module has `meta.yml`/`environment.yml`/`tests/`),
`NF-D-019` (`modules.json` still lists the four removed nf-core modules).

---

## Provenance

**Initially derived from:** `scripts/Dockerfile`, `scripts/Dockerfile.update`,
`scripts/docker_build.sh`, `.github/workflows/build.yml`,
`conf/process.config`, `conf/azure.config`, `modules/blast/blastn/main.nf`,
`modules/blast/blastdbcmd/main.nf`, `modules/mafft/align/main.nf`,
`modules/fastme/main.nf`. See [README.md § Version](README.md#version)
for the exact commit.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
