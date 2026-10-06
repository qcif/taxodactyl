# Reference: BLAST mode vs BOLD mode, every difference in one place

`--db_type` selects the search backend for the **whole run**, not
per-sample ([params.md](../nextflow/params.md)). The two modes share
P3–P6; this file consolidates every point where they diverge, because
that divergence is otherwise scattered across six specs. Each row links
to the file with the full requirement.

> **Status.** BOLD mode cannot currently complete a run — see `NF-D-002`
> (workflow wiring), `P1B-D-001`–`P1B-D-003` (missing `hmmsearch`, wrong
> env var, an output that's never written). Everything below describes
> the code's intended contract, verified by reading, not by a successful
> run. [decisions.md `D-01`](../decisions.md) asks whether to repair or
> retire this branch.

## 1. Search and taxonomy (P1/P2)

| Aspect | BLAST | BOLD | Spec |
|---|---|---|---|
| Entrypoint | `BLAST_BLASTN` → `EXTRACT_HITS` (P1) → `BLAST_BLASTDBCMD` → `EXTRACT_TAXONOMY` (P2) — 4 Nextflow processes, whole-run | `BOLD_SEARCH` (P1-BOLD) — 1 process, whole-run, does search + taxonomy in one step | [p1-parse-blast.md](p1-parse-blast.md), [p1-bold-search.md](p1-bold-search.md) |
| External service | Local BLASTN against operator-provisioned Core Nt | Remote BOLD v4 ID Engine API (HTTP, no local DB) | same |
| Per-hit fields | `identity`, `alignment_length`, `query_coverage`, `bitscore`, `e_value`, full HSP list, `accession` (version-stripped), computed `taxonomy`/`species`/`taxid` via `taxonomy.csv` join | `similarity` (copied into `identity` at source), `taxonomic_identification`, `accession` (may be empty — no GenBank record), `taxonomy` dict already attached, no alignment statistics | same |
| Hit sequence content | Last HSP's aligned subject fragment, **including gap characters** (`P1-D-001`) | Full nucleotide sequence, gaps stripped | [p1-parse-blast.md §3](p1-parse-blast.md), [p1-bold-search.md §4](p1-bold-search.md) |
| Orientation handling | N/A | Historical HMM-based orientation step runs **unconditionally** unless env `SKIP_ORIENTATION` is set (not `BOLD_SKIP_ORIENTATION`, which Nextflow actually exports — `P1B-D-002`); needs `hmmsearch`, absent from the image (`P1B-D-001`) | [p1-bold-search.md §3.1](p1-bold-search.md) |
| Taxonomy source | `blastdbcmd` + `taxonkit lineage`, one shared `taxonomy.csv` for the whole run | Per-hit, from BOLD's "Full data retrieval" endpoint + a GBIF kingdom lookup; no `taxonomy.csv` | [p2-extract-taxonomy.md](p2-extract-taxonomy.md), [p1-bold-search.md §3.3](p1-bold-search.md) |

## 2. Candidate selection (P3)

| Aspect | BLAST | BOLD | Spec |
|---|---|---|---|
| Filtering | Two-stage: length/coverage filter, then identity threshold (`P3-001`) | Single stage: identity threshold only, no length/coverage filter (`P3-010`) | [p3-assign-taxonomy.md §3](p3-assign-taxonomy.md) |
| Taxonomy join | Looked up from `taxonomy.csv` per hit; a miss leaves `species=None` (`P3-002`, `P3-003`) | Already attached at P1-BOLD; not re-looked-up (`P3-011`) | same |
| `candidates.csv` header | `species,taxid,accession,hit_subject,identity,query_coverage,alignment_length,e_value,bitscore` | `species,hit_id,accession,sequence_description,similarity,bin_uri,url` (`P3-041`) | same |
| FASTA join key | `accession` | `hit_id` (`P3-012`, `P3-042`) | same |
| Known crash | — | `similarity = None` (unmatched BOLD field) raises `TypeError` in threshold comparisons (`P3-D-005`) | same |

## 3. Evidence evaluation (P4/P5)

| Aspect | BLAST | BOLD | Spec |
|---|---|---|---|
| P4 source diversity | GenBank publication metadata via Entrez `efetch` | BOLD hits without a GenBank accession fall back to a `BOLDCollectorsSource` keyed on the `collectors` field | [p4-source-diversity.md §5](p4-source-diversity.md) |
| P5 target/related counts | NCBI Entrez `esearch`, locus-scoped query from `loci.json` | `fetch_bold_records_count` against the BOLD stats API, restricted to ranks species/genus/family/order (`P1B-030`) | [p5-db-coverage.md §4.3–4.4](p5-db-coverage.md) |
| `--bold` flag threading | N/A | Passed explicitly to P0, P3, P5, P6 (not P1/P2, which don't exist in this branch) | [p5-db-coverage.md §2](p5-db-coverage.md) |

## 4. Report (P6)

| Aspect | BLAST | BOLD | Spec |
|---|---|---|---|
| Report filename | `report_<sample_id>_<timestamp>.html` | `report_BOLD_<sample_id>_<timestamp>.html` (CFG-030) | [p6-report.md §1](p6-report.md) |
| Title | `config.report.title` | `BOLD - ` + title | same |
| Rendered terminology | "identity" | Every whole word `identity`/`Identity` in the **fully rendered HTML** (including inlined vendored JS/CSS) is regex-replaced with `similarity`/`Similarity` (`P6-003`); can rename identifiers inside vendored libraries (`P6-D-004`) | same |
| Taxonomy source for report | `config.read_taxonomy_file()` (`taxonomy.csv`) | Hit's own `taxonomy` dict (`_load_taxonomies_bold`) | [p6-report.md §3](p6-report.md) |

## 5. Validation (P0) and input constraints

| Aspect | BLAST | BOLD | Spec |
|---|---|---|---|
| `locus` requirement | Must resolve against `loci.json` or be `NA` | Blank locus is *intended* to be accepted (per `--bold`'s help text) but P0's required-field check rejects a blank value before the BOLD exemption is reached (`P0-D-006`) — in practice BOLD rows need `locus=NA` too | [p0-validation.md §4.3](p0-validation.md) |
| `taxdb` | Required | Also required — P0 always validates it, regardless of `db_type` (`NF-D-010`) | same |

## 6. Nextflow wiring

| Aspect | BLAST | BOLD | Spec |
|---|---|---|---|
| Branch selection | `params.db_type != 'bold'` | `params.db_type == 'bold'` (`NF-WF-030`) | [workflow.md §4.2](../nextflow/workflow.md) |
| Can the branch currently complete? | Yes | **No** — `EXTRACT_HITS.out.extract_hits_log` is referenced unconditionally even though `EXTRACT_HITS` never runs in this branch, and `BOLD_SEARCH.out.hits` isn't regrouped into the `[query_folder, files]` shape `EXTRACT_CANDIDATES` expects (`NF-D-002`) | same |
| Default test profile | — | `conf/test.config` (`-profile test`) defaults to `db_type='bold'`, so the out-of-the-box test profile cannot succeed (`NF-D-009`) | [params.md §9](../nextflow/params.md) |

---

## Provenance

**Initially derived from:** cross-reference compilation of
[p0-validation.md](p0-validation.md), [p1-parse-blast.md](p1-parse-blast.md),
[p1-bold-search.md](p1-bold-search.md), [p3-assign-taxonomy.md](p3-assign-taxonomy.md),
[p4-source-diversity.md](p4-source-diversity.md), [p5-db-coverage.md](p5-db-coverage.md),
[p6-report.md](p6-report.md) and [nextflow/workflow.md](../nextflow/workflow.md) —
each already derived from source, v1.5.0. This file adds no new facts;
it is a navigational aid. If it drifts from the files it summarises,
those files are authoritative.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
