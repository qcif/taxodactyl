# Reference: every external data source this pipeline depends on

Not a replacement for [deployment.md §4](deployment.md) — that keeps the
normative `DEP-030`..`032` requirements. This file answers a broader
question: **everything** Taxodactyl's scientific output depends on that
it doesn't itself produce, not only the two sources an operator has to
provision. They split into two genuinely different categories, and
conflating them is why `deployment.md`'s "Reference data" section looks
short — it was only ever scoped to the first one:

| | Provisioned locally | Live remote service |
|---|---|---|
| **What** | Core Nt, taxdump | NCBI Entrez/GenBank, GBIF, BOLD |
| **Operator action** | Download, store, point `--blastdb`/`--taxdb` at it | None — just network access |
| **Availability risk** | Stale if never refreshed | Outage, rate limit, API deprecation |
| **Spec'd in** | §1 below | §2 below |

## 1. Locally-provisioned

### 1.1 BLAST Core Nt

- **What:** NCBI's full nucleotide BLAST database (`core_nt`), used by
  `BLAST_BLASTN`/`BLAST_BLASTDBCMD` in BLAST mode (the default;
  `--db_type blast_core_nt`).
- **Requirement:** a multi-volume BLAST DB whose path ends in `core_nt`
  (`DEP-030`). The only start-up check (`NF-WF-013`) is that `--blastdb`
  is *set* — it does not check the DB is valid, complete, or actually
  named `core_nt`.
- **Two different failure modes, two different outcomes:** a **missing or
  corrupt** DB is caught, just not by this pipeline — `blastn`/`blastdbcmd`
  themselves refuse to run against one (their own index-loading error),
  which takes out the *entire* run since `BLAST_BLASTN` is a run-wide
  process (`NF-ER-005`). A **structurally valid but wrong** DB — a
  different organism-specific database, a stale or outdated Core Nt
  build, anything merely *renamed* to end in `core_nt` — is caught by
  **nothing**: not Nextflow's start-up check, not BLAST+ itself, since any
  well-formed nucleotide DB is equally "valid" to search as far as BLAST
  is concerned. `decisions.md D-33` is open on whether to validate DB
  identity before a run, not only record it afterward.
- **Size:** ≈220 GB on disk (per `deployment.md §5`'s Azure pool sizing,
  `Standard_L8as_v3` with NVMe local storage).
- **Versioning in practice, not in the pipeline:** NCBI doesn't version
  Core Nt releases with a stable identifier; operators track this
  themselves. `docs/subset_blastdb.md` (a guide for building a small test
  subset) shows the real convention in use: a date-stamped directory,
  e.g. `/home/ubuntu/blastdbs/2026-05-12`. The pipeline itself records
  **no** database build date, version, or checksum anywhere in its output
  — `decisions.md D-33` is open on adding this.
- **Azure:** staged once per pool node to `/mnt/nvme/refdata` by the pool
  start task via `azcopy`, from the **`daffpremium`** storage account's
  `refdata` container — a separate account from `daffstandard` (which
  holds the Nextflow work dir), with no lifecycle/deletion policy, since
  this data is meant to persist (`DEP-032`, `deployment.md §5`). This
  staging happens entirely outside Nextflow.

### 1.2 Taxdump

- **What:** NCBI's taxonomy dump, used by `taxonkit lineage`/`name2taxid`
  (invoked by P2's `EXTRACT_TAXONOMY` and P5's GenBank-mode taxid lookup)
  to resolve accessions/taxids to full lineages.
- **Requirement:** the 9 `*.dmp`/`gc.prt` files `TAXDB_EXPECT_FILES`
  checks for (`P0-031`), from **April 2025 or later** — needed for virus
  taxonomy support (`DEP-031`). Older taxdumps pass the file-presence
  check but silently lack virus lineages.
- **Consumed by a floating-latest binary:** `taxonkit` itself is
  installed in the image from `releases/latest` at build time
  ([containers.md §1](containers.md)) — so even with a perfectly
  version-pinned taxdump, the *tool* reading it isn't pinned.
- **Azure:** staged alongside Core Nt to `/mnt/nvme/refdata`, same
  mechanism.

## 2. Live remote services

None of these are provisioned, downloaded, or staged — they're external
HTTP APIs called at runtime, every run, subject to the shared throttle
layer ([shared/throttle.md](python/shared/throttle.md)). If one of them
is unreachable, slow, or changes its API, that's an availability risk no
amount of local storage planning mitigates.

### 2.1 NCBI Entrez (GenBank)

- **Used for:** P4's source-diversity publication metadata (`efetch`,
  one call per accession) and P5's BLAST-mode record counts (`esearch`,
  one call per target taxid).
- **Access:** via Biopython's `Entrez` module (`Entrez.email`,
  `Entrez.api_key` set from `USER_EMAIL`/`NCBI_API_KEY`), not raw HTTP —
  no literal base URL appears in this codebase.
- **Rate:** 5 req/s with `NCBI_API_KEY` set, else 2 req/s; scope is **per
  user** (`USER_EMAIL`, or `ANONYMOUS` if unset) — enforced by this
  pipeline's own throttle, not by NCBI rejecting requests
  ([throttle.md §2](python/shared/throttle.md)). `THR-D-004`: several
  users sharing one host can still exceed NCBI's *actual* per-IP/key
  limit together, since the throttle only tracks per-`USER_EMAIL`.
- **Auth leak risk:** the same `NCBI_API_KEY` this throttle relies on is
  the credential `P6-D-001` writes unfiltered into every HTML report.

### 2.2 GBIF

- **Used for:** P5's database-coverage-within-genus/country assessment
  (species lookup, occurrence search) and P1-BOLD's kingdom lookup for
  BOLD hits without a GenBank accession.
- **Access:** via the `pygbif` client library (`import pygbif`), which
  targets GBIF's public REST API — again no literal URL in this codebase,
  since the library owns that detail. Endpoints actually called:
  `species/suggest` (fuzzy name lookup, `P5-010`) and `species/search`
  (`name_lookup`, paged, `P5-040`).
- **Rate:** two separate endpoint buckets — `GBIF_SLOW` (1 req/s) and
  `GBIF_FAST` (5 req/s) — both **global**, i.e. shared across every
  concurrent query and every node in a run, not per-user like Entrez/BOLD
  ([throttle.md §2](python/shared/throttle.md)). A 429 halves the
  effective rate (floor 0.1 req/s), recovering over 2 hours.
  `THR-D-003`: this backoff state is tracked per SQLite *endpoint* but
  per Redis *service* — a GBIF 429 only slows both GBIF endpoints
  together when Redis is the throttle backend.
- **Known gaps:** `P5-D-007` (`name_lookup` without `datasetKey` searches
  all GBIF checklists, not just the taxonomic backbone, inflating result
  counts); `P5-D-010` (`name_suggest` is fuzzy — the first match may be
  the wrong taxon, surfaced only as an informational error).

### 2.3 BOLD

- **Used for:** the entire BOLD search branch (alternative to
  BLAST+taxonomy, `--db_type bold`) and, separately, P5's BOLD-mode
  record counts.
- **Access:** raw HTTP, three literal endpoints, all under BOLD's **v4**
  API:
  - `http://v4.boldsystems.org/index.php/Ids_xml` — the ID Engine (the
    actual sequence search)
  - `…/API_Public/combined` — record metadata (TSV)
  - `…/API_Public/stats` — record counts for P5 (https)

  All three go through `Throttle(ENDPOINTS.BOLD)`
  ([p1-bold-search.md §2](python/p1-bold-search.md)).
- **Rate:** 5 req/s *and* 50 req/min, per user — the only endpoint with
  two simultaneous limits (`throttle.md §2`).
- **Status: not currently reachable end-to-end.** `P1B-D-004` (*to
  confirm*): BOLD v4 may already be retired in favour of v5 — the ID
  Engine call is still plain `http://`, not `https://`, which is itself a
  signal of an old integration. Compounding this, the branch can't
  complete a run today regardless (`NF-D-002`, `P1B-D-001`, `P1B-D-002`,
  `P1B-D-003`) — see
  [python/blast-vs-bold.md](python/blast-vs-bold.md) for the full list.
  Database version/vintage is not something BOLD exposes to a consumer
  the way a downloadable DB would — there's no equivalent of Core Nt's
  "which build" question for a live API like this.

## 3. Summary

| Source | Category | Rate limit | Status |
|---|---|---|---|
| Core Nt | Provisioned | — (local) | Operational; no version/provenance captured (`D-33`) |
| Taxdump | Provisioned | — (local) | Operational; reader (`taxonkit`) is floating-latest |
| NCBI Entrez | Live | 5 or 2 req/s, per user | Operational |
| GBIF | Live | 1–5 req/s, global | Operational, with known accuracy gaps |
| BOLD | Live | 5 req/s + 50/min, per user | **Not operational end-to-end** |

---

## Provenance

**Initially derived from:** `docs/subset_blastdb.md`,
`scripts/src/gbif/taxonomy.py` (`pygbif` import), cross-reference
compilation of [p1-bold-search.md](python/p1-bold-search.md),
[p4-source-diversity.md](python/p4-source-diversity.md),
[p5-db-coverage.md](python/p5-db-coverage.md),
[shared/throttle.md](python/shared/throttle.md),
[deployment.md](deployment.md) — each already derived from source. See
[README.md § Version](README.md#version) for the exact commit.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
