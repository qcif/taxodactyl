# Spec: P5 database coverage (`scripts/p5_db_coverage.py`, `src/coverage/`, `src/gbif/`)

**Called by:** Nextflow `EVALUATE_DATABASE_COVERAGE`, once per query
(always; not gated by candidate count at Nextflow level).
**Depends on:** [shared/config.md](shared/config.md), `shared/throttle.md`,
`shared/cache.md`, `shared/errors.md`, [p2-extract-taxonomy.md §3.2](p2-extract-taxonomy.md),
[p4-source-diversity.md §7](p4-source-diversity.md), [p1-bold-search.md §5](p1-bold-search.md).

## 1. Purpose

For each **target taxon** relevant to a query, estimate how well the
reference database covers it and its close relatives at the query's
locus, so the analyst can judge whether a match (or a non-match) could be
an artefact of missing reference data. Produces Flags 5.1–5.3 and one
occurrence map per target.

## 2. Interface

| Arg | Maps to (default) |
|---|---|
| `query_dir` (positional, required) | |
| `--query-fasta`, `--metadata-csv` (required) | config |
| `--output-dir`, `--temp-root`, `--temp-dir-name` | config |
| `--bold` | use BOLD record counts instead of GenBank |
| `--db-coverage-toi-limit` | `db_coverage_toi_limit` (10) |
| `--db-coverage-max-candidates` | `db_coverage_max_candidates` (3) |
| `--gbif-limit-records` | `gbif_limit_records` (500) |
| `--gbif-max-occurrence-records` | `gbif_max_occurrence_records` (5000) |
| `--gbif-accepted-status` | `gbif_accepted_status` (`ACCEPTED,DOUBTFUL`) |
| `--db-cov-target-min-a` / `-b` | `criteria.db_cov_target_min_a/b` (5 / 1) |
| `--db-cov-related-min-a` / `-b` | `criteria.db_cov_related_min_a/b` (90 / 10) |
| `--db-cov-country-missing-a` | `criteria.db_cov_country_missing_a` (1) — **unused** (P5-D-003) |

**Reads:** `<query_dir>/candidates.json`; metadata (PMI, TOIs, country,
classification, locus) via config.
**Writes** (in `query_dir`): `db_coverage.json` (§6), `5.1.flag`,
`5.2.flag`, `5.3.flag` (§5), `map_<target>.png` per target (§4.6),
`errors/*` (§7).
**External services:** GBIF species + occurrence APIs (`pygbif`), NCBI
Entrez esearch, BOLD stats API (BOLD mode), `taxonkit name2taxid`.
**Exit:** 0 even when some targets failed; a summary line is written to
stderr when any lower-rank target has a missing result.

## 3. Targets

| ID | Requirement |
|---|---|
| P5-001 | Candidates = `candidates.json.species[*].species`; if more than `db_coverage_max_candidates`, **no** candidate is assessed. |
| P5-002 | PMI = metadata `preliminary_id`; always a target. |
| P5-003 | TOIs = metadata `taxa_of_interest`; only the first `db_coverage_toi_limit` are assessed, and a `DB_COVERAGE` error message is written (P5-D-008: it lists no excluded names). |
| P5-004 | A taxon appearing in more than one role (e.g. PMI equals a candidate) is assessed once and reported under each role. |

## 4. Algorithm

### 4.1 GBIF record per target (`RelatedTaxaGBIF`)

| ID | Requirement |
|---|---|
| P5-010 | Query `species/suggest` (`name_suggest`, `q=<target>`, limit 20). If the lower-cased target is in `KINGDOM_TAXA` (e.g. `animals`, `metazoa`, `fungus`, `viral`), replace `q` with the canonical kingdom name and add `rank=Kingdom`. |
| P5-011 | Take the **first** suggestion that: matches the query's classification (`kingdomKey == HIGHER_CLASSIFICATIONS[c].gbif`, or no classification given, or record has no kingdomKey); has status in `gbif_accepted_status`; is not extinct; and has a rank in {species, genus, family, order, class, phylum, kingdom, domain}. A `SYNONYM` suggestion is replaced by its accepted record (`name_usage` on the first of `speciesKey…kingdomKey`) and `from_synonym` is set. |
| P5-012 | No qualifying suggestion ⇒ `GBIFRecordNotFound`; error `DB_COVERAGE_NO_GBIF_RECORD`; the target gets `{target, related, country} = null` and all three flags `ERR`. |
| P5-013 | Informational errors (location `DB_COVERAGE`) MUST be written when the target is a synonym, or when the accepted canonical name differs from the input (case-insensitive) — the analysis proceeds on the GBIF name. |
| P5-014 | Rank species or genus ⇒ **lower** target (all three analyses). Family or above ⇒ **higher** target: only the record count is fetched and all three flags are `NA`. |

### 4.2 Taxids

| ID | Requirement |
|---|---|
| P5-020 | Resolve canonical names of all targets with `taxonkit name2taxid`, filtered by the query's classification (P2-021..024). |
| P5-021 | A name returned without taxid MUST produce error `DB_COVERAGE_TAXONKIT_ERROR` ("coverage … assumed to be zero"). The target is still processed with `taxid = None` (P5-D-002). |

### 4.3 Target record count (Flag 5.1 input)

| ID | Requirement |
|---|---|
| P5-030 | GenBank mode: `esearch nuccore` term `txid<taxid>[Organism])` + ` AND (<locus query>)` when the locus is not `NA`; value = `Count`. Locus query per CFG-042. |
| P5-031 | BOLD mode: `fetch_bold_records_count(canonical_name, rank)` (P1B-030..032). |
| P5-032 | Locus `NA` ⇒ no locus restriction: the count is **all** nucleotide records for the taxon. The summary flag compensates (§5.4). |

### 4.4 Related-species coverage (Flag 5.2 input), lower targets only

| ID | Requirement |
|---|---|
| P5-040 | Relatives = GBIF `species/search` (`name_lookup`, `rank=species`, `higherTaxonKey=<genusKey>`), paged by `gbif_limit_records` until `endOfRecords`, keeping records that pass P5-011's acceptance rules and have a name. Early exit if, after 6 pages, a page starts with the same name as the previous page. |
| P5-041 | Species set = distinct canonical names of relatives. Empty ⇒ `{}` (Flag 5.2 `ERR`, error "No related species found"). |
| P5-042 | GenBank mode: taxids via `taxonkit name2taxid` **without** classification filter; one esearch count per taxid (5 threads); species without taxid ⇒ 0; a species whose count request fails ⇒ error `DB_COVERAGE_RELATED` and count **0** (P5-D-005). Result: `{species: count}`. |
| P5-043 | BOLD mode: `fetch_bold_records_count(species, rank=<target rank>)` per species; failures ⇒ `None`. |

### 4.5 In-country related coverage (Flag 5.3 input)

| ID | Requirement |
|---|---|
| P5-050 | If the query has no `country`, the value is the string `"NA"`. |
| P5-051 | Otherwise query GBIF occurrences (`genusKey`, `country=<alpha-2>`, `facet=speciesKey`, `facetLimit=gbif_limit_records`, `limit=1`), paging until the facet list is shorter than `gbif_limit_records` (P5-D-004). In-country species = relatives whose `speciesKey` is among the facet keys. |
| P5-052 | Value = `{species: count from §4.4 (0 if absent)}` for in-country species; `{}` if none. No extra database requests. |

### 4.6 Occurrence maps

| ID | Requirement |
|---|---|
| P5-060 | For every target with a GBIF key, write `map_<path_safe(original target)>.png`. |
| P5-061 | Lower targets: fetch GBIF occurrences (`taxonKey`) page by page until `endOfRecords` or `gbif_max_occurrence_records`; plot a log-scaled hexbin of coordinates on a Natural Earth 110m base map (bundled zip), 16×12 in at 300 dpi, with `n=<count> occurrences`, or a "No occurrence records" message. |
| P5-062 | Higher or unknown-rank targets: placeholder map with "Occurrence maps are only generated for taxa at rank genus or species". |
| P5-063 | Map errors MUST be written as `DB_COVERAGE` errors and not stop the analysis. |

### 4.7 Concurrency

Target/related tasks run in a 5-thread pool; every outbound call uses the
shared throttle and cache (`with_cache=True`). A task exception is written
as a `DB_COVERAGE` error and its result becomes `null`; an exception of
type `urllib.error.URLError` instead raises `APIError`, **failing P5 for
the query** (and removing its report, NF-D-003).

## 5. Flags

Written per `(target, target_type)` with `target_type ∈ {candidate, toi, pmi}`
and the **original** (user-supplied) target name.

### 5.1 Flag 5.1 — target coverage

| Condition | Value |
|---|---|
| higher target | `NA` |
| count `null` | `ERR` |
| count > `db_cov_target_min_a` (5) | `A` |
| count > `db_cov_target_min_b` (1) | `B` |
| otherwise | `C` |

`flags.csv`: A ">5 entries", B "≤5 entries", **C "not present (0 entries)"**.
With the defaults a count of exactly 1 is graded `C` (P5-D-001).

### 5.2 Flag 5.2 — related species

| Condition | Value |
|---|---|
| higher target | `NA` |
| `null` | `ERR` |
| `{}` (no relatives) | `ERR` + error |
| % of relatives with count > 0: > `db_cov_related_min_a` (90) | `A` |
| > `db_cov_related_min_b` (10) | `B` |
| otherwise | `C` |

### 5.3 Flag 5.3 — related species in country

| Condition | Value |
|---|---|
| higher target, or no country (`"NA"`) | `NA` |
| `null` | `ERR` |
| `{}` (no relatives observed in country) | `C` (level 0 in `flags.csv`: "unlikely to be another species in this genus") |
| every in-country species has count > 0 | `A` |
| otherwise | `B` |

| ID | Requirement |
|---|---|
| P5-070 | Any exception while setting flags MUST raise `RuntimeError` (P5 fails for this query). |

### 5.4 Summary Flag 5 (computed at read time, `Flag.read`)

Not written by P5. For each target, when a report reads the flags: take the
5.1/5.2/5.3 flag with the **highest** level, or the **lowest** if any has
level 0; if that level is < 2 and the query has no locus, replace it with
`5B` ("locus was not provided"). Targets with no flags fall back to `5NA`.

## 6. `db_coverage.json`

```json
{
  "coverage": {
    "candidate": { "<original name>": {"target": <int|null>,
                                       "related": {"<species>": <int|null>} | {} | null,
                                       "country": {"<species>": <int>} | {} | "NA" | null,
                                       "genus": "<GBIF genus>"} },
    "toi": { … },
    "pmi": { "<pmi>": { … } }
  },
  "ncbi_urls": { "<original name>": {"blast": "<url>|null", "taxonomy": "<url>|null"} }
}
```

`genus` is present only when a GBIF record was found. The integration
test kit compares this file semantically across runs
(`tests/integration/kit/coverage_assert.py`).

## 7. Errors written (location codes)

`DB_COVERAGE` (general, maps, TOI truncation, name substitutions, task
failures), `DB_COVERAGE_NO_GBIF_RECORD`, `DB_COVERAGE_TAXONKIT_ERROR`,
`DB_COVERAGE_RELATED`, `DB_COVERAGE_RELATED_COUNTRY`. All carry
`context.target`. See `shared/errors.md`.

## 8. Defects

| ID | Severity | Defect |
|---|---|---|
| P5-D-001 | High | Flag 5.1 uses `count > db_cov_target_min_b`; with the default `min_b = 1` a taxon with **one** reference record is graded `C` — "not present in reference database (0 entries)". The parameter is documented as the minimum *to receive* B. Same off-by-one for A (needs 6, documented as 5). |
| P5-D-002 | High (*to confirm*) | A target with no NCBI taxid is still queried as `txidNone[Organism]) AND (...)`. If Entrez drops the unknown term, the count becomes **all records at that locus** and the target is graded `5.1A`. All such targets also share one result slot (`results[None]`). |
| P5-D-003 | Medium | `db_cov_country_missing_a` is accepted everywhere (Nextflow, CLI, config) but never used: 5.3 becomes `B` as soon as one in-country species is unrepresented. |
| P5-D-004 | Medium | In-country paging advances the *occurrence* `offset` instead of the facet offset, so the facet list never shrinks; for a genus with ≥ `gbif_limit_records` (500) species in one country (e.g. *Eucalyptus* in AU) the loop never ends until the task times out. |
| P5-D-005 | Medium | A failed per-species count in 5.2 is recorded as 0 (unrepresented), lowering the 5.2/5.3 grade instead of yielding `ERR`. |
| P5-D-006 | Medium | A locus value ending in ` gene` (accepted by P0) makes `get_locus_for_query` return a `str` (CFG-D-003); `fetch_gb_records` then fails for every target ⇒ every 5.x flag is `ERR`. |
| P5-D-007 | Medium (*to confirm*) | `name_lookup` without `datasetKey` searches all GBIF checklists, not only the backbone; the relatives list can include non-backbone names/duplicates, inflating the 5.2 denominator. |
| P5-D-008 | Low | TOI truncation message computes excluded TOIs after truncating, so it always lists none. |
| P5-D-009 | Low | GBIF ranks such as subspecies, subgenus, tribe, subfamily are rejected (`RANK` has no entry), so such targets always hit P5-012. `KINGDOM_TAXA` maps protozoa to "protista" (GBIF kingdom is Protozoa). |
| P5-D-010 | Low | `name_suggest` is a prefix/fuzzy suggest; the first accepted suggestion may be a different taxon. This is reported as an informational error (P5-013) but the analysis proceeds. |
| P5-D-011 | Low | Occurrence maps are 300 dpi 16×12 in PNGs (~4800×3600 px), embedded in the HTML report, which inflates its size. |
| P5-D-012 | Low | `assess_coverage` returns `None` when there are no targets, which `main()` cannot unpack (unreachable because the PMI is always a target). |

## 9. Test mapping

- `tests/test_gbif.py`: relatives lookup, country request, classification filter (P5-011, P5-040, P5-051).
- `tests/test_genbank.py`: `fetch_gb_records` count/ids (P5-030).
- `tests/integration/` + `testkit.py`: live end-to-end comparison of `db_coverage.json` against reviewed fixtures (manual).
- **Not covered:** flag thresholds §5 (including P5-D-001), taxid-less targets, higher-rank targets, TOI limit, country paging, maps.

## 10. Open questions

1. Is 5.1B meant to start at 1 record (fix the comparison) or at 2 (fix
   `flags.csv` text and the parameter description)?
2. Should taxid-less targets be graded `5.1C` explicitly instead of
   querying Entrez?
3. Should `db_cov_country_missing_a` be implemented or removed?

---

## Provenance

**Initially derived from:** `p5_db_coverage.py` (153), `src/coverage/assess.py` (429), `targets.py` (215), `threads.py` (186), `fetch.py` (169), `src/gbif/relatives.py` (378), `src/gbif/maps.py` (139), `src/entrez/genbank.py` (`fetch_gb_records`), `src/bold/stats.py`, `src/taxonomy/extract.py` (`taxids`), `src/utils/flags.py`. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
