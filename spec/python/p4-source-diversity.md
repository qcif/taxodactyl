# Spec: P4 reference-source diversity (`scripts/p4_source_diversity.py`)

**Called by:** Nextflow `EVALUATE_SOURCE_DIVERSITY`, once per query whose
candidate count is 1..`max_candidates_for_analysis` (NF-WF-051).
**Depends on:** [shared/config.md](shared/config.md), `shared/throttle.md`,
`shared/cache.md`, `shared/errors.md`; input `candidates.json` from
[p3-assign-taxonomy.md](p3-assign-taxonomy.md).

## 1. Purpose

Estimate how many **independent** publication sources support the
reference sequences behind each candidate species, so a match resting on
one lab's submissions is visibly weaker than one corroborated by several
(Flag 4).

## 2. Interface

| Arg | Required | Maps to |
|---|---|---|
| `query_dir` (positional) | yes | |
| `--query-fasta`, `--metadata-csv` | yes | config |
| `--output-dir` | no | |
| `--min-source-count` | no | `criteria.sources_min_count` (5) |
| `--temp-root`, `--temp-dir-name` | no | cache/throttle location |

Env used via config: `USER_EMAIL` (→ `Entrez.email`), `NCBI_API_KEY`
(→ `Entrez.api_key`), cache/throttle settings.

**Reads:** `<query_dir>/candidates.json`.
**Writes:** `<query_dir>/4.flag`, `<query_dir>/aggregated_sources.json`,
`<query_dir>/errors/*` (non-fatal errors, §6).

## 3. Algorithm

| ID | Requirement |
|---|---|
| P4-001 | Input hits = `candidates.json.hits` with `is_candidate_hit == true` (the selected-stringency candidate hits of selected species only); species = `candidates.json.species`. |
| P4-002 | For every distinct non-empty `accession` among those hits, fetch the GenBank record (§4). |
| P4-003 | For each species, for each of its hits in `hits` order, determine a **source**: BOLD hit with empty accession and a `collectors` field ⇒ collectors source (§5.2); accession present in the fetch result ⇒ GenBank source (§5.1); otherwise no source, and a non-fatal error is written (P4-030). |
| P4-004 | Group sources into independent-source groups: compare the new source with every member of every existing group; append it to **each** group containing a matching member (P4-D-001); if none matched, start a new group. Groups are never merged. |
| P4-005 | `independent_sources(species)` = number of groups. |
| P4-006 | Flag 4 per species (upsert into `4.flag` with `target=<species>`, `target_type=null`): `A` if `independent_sources > sources_min_count`, else `B`. |
| P4-007 | `aggregated_sources.json` = `{species: [[source, …] per group]}` where a GenBank source serialises as `{accession, is_automated, publications:[{authors, title, journal}]}` and a collectors source as `{bold_id, bold_url, collectors, publications: []}`. |
| P4-008 | Finally run `config.cleanup()` (removes `<output_dir>/entrez_cache` and temp sub-dirs older than `temp_clean_after_days`). |

Flag 4 thresholds vs `flags.csv`: `4A` ">5 independent sources", `4B`
"1–5". With 0 groups the value is `B` although the text says 1–5.

## 4. GenBank fetch (`genbank.fetch_sources`)

| ID | Requirement |
|---|---|
| P4-010 | One `efetch(db=nuccore, id=<acc>, rettype=gb, retmode=xml)` per accession, 5 concurrent threads, each through `Throttle(ENDPOINTS.ENTREZ).with_retry(with_cache=True)` keyed by endpoint+db+args. (`EFETCH_BATCH_SIZE = 10` is unused.) |
| P4-011 | The response MUST be read only up to `<GBSeq_feature-table>` or `<GBSeq_sequence>`, then closed with `</GBSeq></GBSet>` (metadata only). |
| P4-012 | Records are keyed by `GBSeq_primary-accession`. Each `GBReference` contributes a publication `(authors[], title, journal)`. The record is **automated** iff the (truncated) XML contains `##Genome-Annotation-Data-START##`. |
| P4-013 | Accessions requested but not returned (e.g. keyed under a different primary accession) get an empty source (no publications), with a log warning only. |
| P4-014 | Any exception from a fetch (after retries) propagates and fails P4 for this query (P4-D-003). |

## 5. Matching rules

### 5.1 GenBank sources

Publication key ("repr"), first available of:
1. authors: each author with `.`, `,` and spaces removed, lower-cased,
   joined with `, ` (exact author list, order-sensitive);
2. title, lower-cased — skipped only if it contains "direct submission"
   **and** is ≤ 20 characters;
3. journal, lower-cased;
4. otherwise `None`.

| ID | Requirement |
|---|---|
| P4-020 | An automated record's key list is empty. |
| P4-021 | Two GenBank sources match iff their key lists are equal, or they share any non-`None` key. Consequence: all records with no publications **and** all automated records match each other (one "anonymous" group). |
| P4-022 | A GenBank source never matches a collectors source. |

### 5.2 BOLD collectors sources

| ID | Requirement |
|---|---|
| P4-025 | Key = `collectors` stripped and lower-cased; match iff keys are equal. |

## 6. Errors

| ID | Requirement |
|---|---|
| P4-030 | A hit with an empty accession and no `collectors` MUST produce `errors.write(SOURCE_DIVERSITY_ACCESSION_ERROR, …, context={index, hit_id, species, accession})` and contribute no source; P4 continues. These files surface in the report (NF-PR-101). |

## 7. Library function used by P5: `genbank.fetch_gb_records(locus, taxid, count)`

| ID | Requirement |
|---|---|
| P4-040 | Build the Entrez term `txid<taxid>[Organism])` (note stray `)`, P4-D-004), append ` AND (<locus.genbank_query_str>)` if the locus is truthy (not `NA`). |
| P4-041 | `esearch(db=nuccore, term, retmax = 1 if count else 100)` via the same throttle/cache path; return `int(Count)` or the id list. |

## 8. Defects

| ID | Severity | Defect |
|---|---|---|
| P4-D-001 | Medium | Grouping is not transitive: a source matching two groups is added to both and the groups are not merged, so the number of independent sources can be **over-counted** and is order-dependent; this can raise Flag 4 from `B` to `A`. |
| P4-D-002 | Medium | "Same source" requires an identical author list; two papers from the same lab with different co-authors count as independent. Automated records and records without publications are pooled with each other (P4-021), contradicting the class docstring ("automated only matches automated"). |
| P4-D-003 | Medium | One Entrez failure after retries aborts P4 for the query, which removes its report (NF-D-003), instead of recording an error and continuing. |
| P4-D-004 | Medium (*to confirm*) | Entrez term for P5 record counts has an unbalanced `)` (`txid9606[Organism]) AND (...)`); correctness depends on NCBI tolerating it. |
| P4-D-005 | Low | Accessions missing from the efetch result are silently treated as "no publications" (TODO in code), not reported. |
| P4-D-006 | Low | `species[i]['hit_count']` is set to the last loop index over **all** hits (same wrong value for every species); unused, as is `hits[i]['source']`. |
| P4-D-007 | Low | `4B` is also emitted for 0 sources, while `flags.csv` says "1–5". |

## 9. Test mapping

`tests/test_genbank.py` covers parts of §4/§5 (fetch/parse). No unit test
for `sources_per_species`, Flag 4, or `p4_source_diversity.main`. The
nf-test baselines include `4.flag` files end-to-end.

## 10. Open questions

1. Should grouping be single-linkage (merge groups when a source bridges
   them), and should author overlap (e.g. shared first/last author) count
   as the same source?
2. Should automated-annotation records form their own group separate from
   publication-less records?

---

## Provenance

**Initially derived from:** `p4_source_diversity.py` (117), `src/sources/collect.py` (95), `src/entrez/genbank.py` (281), `src/utils/flags.py`. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
