# Refactoring GBIF API queries to the Catalogue of Life (COL) backbone

## Background

We currently use pygbif to search the GBIF API, which by default resolves
names against the legacy GBIF Backbone Taxonomy
(`d7dddbf4-2cf0-4f39-9b2a-bb099caae36c`). GBIF has migrated to the Catalogue
of Life eXtended Release as its taxonomic backbone:

```python
COL_CHECKLIST_KEY = '7ddf754f-d193-4cc9-b351-99906754a03b'
```

We need to update `src/gbif/relatives.py`, `src/gbif/taxonomy.py` and
`src/gbif/maps.py` so that every name lookup and occurrence query is resolved
against COL, and update the unit tests to match.


## Findings (verified against the live API, 2026-09-30)

### 1. The v1 endpoints keep the old flat schema

The original assumption was that we would need new parsing logic for the
nested `usage` / `classification` schema. **That schema only comes from
`/v2/species/match`**, which returns a single best match. There is no v2
suggest or search endpoint (`/v2/species/search` returns 404).

`/v1/species/suggest`, `/v1/species/search` and `/v1/species/{key}` accept
`datasetKey=<COL_CHECKLIST_KEY>` and return the **same flat schema we already
parse** (`key`, `rank`, `status`/`taxonomicStatus`, `genusKey`, `kingdomKey`,
`speciesKey`, `canonicalName`, ...). The "old backbone" example in the
original version of this plan was in fact already a COL record: its
`datasetKey` is the COL key.

So `GBIFRecord` mostly doesn't need new parsing. The work is in (a) sending
the dataset key, and (b) handling the changed key spaces, described below.

### 2. pygbif `name_suggest` silently can't filter by dataset

In pygbif 0.6.5, 0.6.6 and current `master`, `species.name_suggest`
documents a `datasetKey` argument but never adds it to the request params
(`pygbif/species/name_suggest.py:4,39-40`):

```python
def name_suggest(q=None, datasetKey=None, rank=None, limit=100, offset=None, **kwargs):
    ...
    args = {"q": q, "rank": rank, "offset": offset, "limit": limit}
    return gbif_GET(url, args, **kwargs)
```

`datasetKey` is dropped silently, and results come from all checklists. Any
other extra kwargs (such as `higherTaxonKey`) go to `requests.get()` through
`gbif_GET` (`pygbif/gbifutils.py:32-33`) and raise `TypeError`. Upstream
issue to be filed. Until then, we call `/v1/species/suggest` through our own
wrapper around `pygbif.gbifutils.gbif_GET`.

The other functions we use already forward the parameters we need:

| pygbif function        | Param needed                | Forwarded?          |
|------------------------|-----------------------------|---------------------|
| `species.name_suggest` | `datasetKey`                | **No**              |
| `species.name_lookup`  | `datasetKey`                | Yes (explicit arg)  |
| `species.name_usage`   | none (COL keys are unique)  | n/a                 |
| `occurrences.search`   | `checklistKey`              | Yes (via `**kwargs`) |

### 3. COL records have two different keys

| Key             | Example (genus *Drosophila*) | Used by                                    |
|-----------------|------------------------------|--------------------------------------------|
| v1 usage key    | `298353264` (int)            | `/v1/species/*` (`key`, `genusKey`, ...)   |
| COL taxon ID    | `BXWZ6` (str, the `taxonID` field) | `/v2/species/match`, occurrence API with `checklistKey` |
| legacy `nubKey` | `1522683`                    | Old backbone (being retired)               |

The occurrence API only accepts **COL taxon IDs**:

```
/v1/occurrence/search?genusKey=298353264&checklistKey=COL   -> 0 results
/v1/occurrence/search?taxonKey=298353264&checklistKey=COL   -> 0 results
/v1/occurrence/search?genusKey=BXWZ6&checklistKey=COL       -> 116,169 results
```

Occurrence facets also return COL taxon IDs (e.g.
`{'name': '6DM8M', 'count': 649}`), not ints.

**This breaks two places.**
- `RelatedTaxaGBIF.for_country()` passes `genusKey=self.genus_key` (an int
  v1 key), then does `int(species_key)` on facet names and compares them
  against `r.species_key`. Those facet names are now strings like `'6DM8M'`,
  so `int()` raises `ValueError`.
- `maps.draw_occurrence_map(gbif_target.key, ...)` passes the v1 key as
  `taxonKey`.

We don't get the genus's `taxonID` from a species record directly, only
`genusKey` (v1 int). Getting the genus COL ID needs one extra
`/v1/species/{genusKey}` call, which is cached. For species records,
`taxonID` is on the record itself.

### 4. Classification keys in `Config.HIGHER_CLASSIFICATIONS` are backbone-specific

`_matches_classification()` compares `record.kingdom_key` against
`HIGHER_CLASSIFICATIONS[...]['gbif']` (`src/utils/config/config.py:63`),
which holds legacy backbone kingdom keys (1, 6, 5, ...). Comparing against
`kingdomKey` no longer works under COL:

- Bacteria and Archaea are DOMAINs in COL. Their records have kingdoms such
  as `Pseudomonadati` (*E. coli*) or `Methanobacteriati`.
- Viruses is an UNRANKED root. Virus records have kingdoms such as
  `Orthornavirae`.

**Solution: filter on the server with `higherTaxonKey`.** Both
`/v1/species/suggest` and `/v1/species/search` accept `higherTaxonKey`, and
match on any ancestor rank, so this works for domains and unranked roots too.
It must be the **v1 integer key**. The COL string ID is rejected:

```
/v1/species/suggest?q=Prunella&datasetKey=COL&higherTaxonKey=N
  -> HTTP 400 "Invalid integer range: N"
/v1/species/suggest?q=Prunella&datasetKey=COL&higherTaxonKey=296374190
  -> [Prunella Vieillot (Animalia), ...]   # plant homonym excluded
/v1/species/suggest?q=Escherichia&datasetKey=COL&higherTaxonKey=293990344
  -> [Escherichia (Pseudomonadati), ...]   # animal homonym excluded
```

| Classification | Legacy key | COL taxonID (stable) | COL v1 key (unstable) | COL rank |
|----------------|-----------:|----------------------|----------------------:|----------|
| animalia       | 1          | `N`                  | 296374190             | KINGDOM  |
| plantae        | 6          | `P`                  | 293994071             | KINGDOM  |
| fungi          | 5          | `F`                  | 299629601             | KINGDOM  |
| chromista      | 4          | `C`                  | 299967116             | KINGDOM  |
| bacteria       | 3          | `CRRY6`              | 293990344             | DOMAIN   |
| archaea        | 2          | `CRLT8`              | 293990342             | DOMAIN   |
| viruses        | 8          | `92e52ff4-2dc6-4b35-9339-2e92035b8daf` | 337992105 | UNRANKED |
| (protozoa)     | -          | `Z`                  | 293992559             | KINGDOM  |

The v1 integer keys are internal GBIF IDs that may be reassigned when GBIF
reloads the COL checklist. The COL taxonIDs are stable. So we **store the COL
ID in `HIGHER_CLASSIFICATIONS`** and resolve it to the v1 key at runtime
(cached):

```
/v1/species?datasetKey=COL&sourceId=N  ->  results[0].key == 296374190
```

pygbif `species.name_usage(datasetKey=COL_CHECKLIST_KEY, sourceId='N')`
should do this. Confirm that `sourceId` is forwarded, or make the call with
`gbif_GET`.

### 5. Other things noticed

- `GBIFRecord.is_extinct` reads `isExtinct`, but v1 responses use `extinct`,
  so the extinct filter has never worked. Fix while we're here.
- v1 COL search results include `acceptedKey` for synonyms.
  `_get_synonym_key()` currently guesses the accepted key from
  `speciesKey`/`genusKey`/..., and could use `acceptedKey` first when it's
  present. Suggest results don't include `acceptedKey`, so keep the
  fallback.
- COL has extra ranks (`SUBGENUS`, `TRIBE`, `UNRANKED`, ...).
  `RANK.from_string()` already maps unknown ranks to `NONE`, so this is fine.
- Cached responses: `Throttle.with_retry(with_cache=True)` keys on
  `cache.keyhash(func, args, kwargs)`. Adding `datasetKey`/`checklistKey`
  changes the kwargs, so stale legacy-backbone responses won't be reused. If
  a new wrapper function is introduced, give it a stable `__name__`.
- `src/gbif/rate_limit_test.py` is an ad-hoc script. Update its
  `higherTaxonKey` or leave it alone.


## Tasks

### A. Shared constants / helpers (`src/gbif/__init__.py` or a new `src/gbif/api.py`)

1. Add `COL_CHECKLIST_KEY = '7ddf754f-d193-4cc9-b351-99906754a03b'` and
   `GBIF_SUGGEST_URL = 'https://api.gbif.org/v1/species/suggest'`.
2. Add `name_suggest(q, rank=None, limit=20, higher_taxon_key=None)`, a thin
   wrapper around `pygbif.gbifutils.gbif_GET(GBIF_SUGGEST_URL, {...,
   'datasetKey': COL_CHECKLIST_KEY, 'higherTaxonKey': ...})`. Callers pass it
   to `Throttle.with_retry` in place of `pygbif.species.name_suggest`. Add a
   comment linking the upstream pygbif issue.
3. Add `get_col_taxon_id(usage_key) -> str`, which calls cached
   `pygbif.species.name_usage(key=...)` and returns `taxonID`.
4. Add `get_usage_key(col_id) -> int`, which resolves a COL taxonID to its v1
   key through `/v1/species?datasetKey=COL&sourceId=<col_id>` (cached).

### B. `src/gbif/relatives.py`

1. `_get_taxon_record()`: use the new `name_suggest` wrapper. When
   `self.classification` is set, pass
   `higher_taxon_key=get_usage_key(self.classification)` so that GBIF does
   the filtering.
2. `GBIFRecord`:
   - add `self.taxon_id = data.get('taxonID')` (the COL ID)
   - fix `is_extinct` to read `extinct` (keep `isExtinct` as a fallback)
3. Remove `_matches_classification()` and its calls in
   `_get_taxon_record()` and `_is_accepted()`. The server filter replaces it.
   - Relatives are fetched by `higherTaxonKey=genus_key`, so they already
     fall inside the classification.
   - Synonym → accepted `name_usage` lookups can in theory cross
     classification. If we're worried about that, pass `higherTaxonKey` to
     the lookup too, or check the accepted record's
     `higherClassificationMap` for the classification key.
4. `_get_synonym_key()`: check `acceptedKey` first.
5. `relatives`: add `datasetKey=COL_CHECKLIST_KEY` to the `name_lookup`
   kwargs. `higherTaxonKey` stays as the v1 `genus_key`.
6. `for_country()`:
   - resolve `self.genus_taxon_id = get_col_taxon_id(self.genus_key)`
     (a cached property)
   - query with `genusKey=self.genus_taxon_id` and
     `checklistKey=COL_CHECKLIST_KEY`
   - treat facet `name`s as strings (drop `int()`) and filter relatives on
     `r.taxon_id in species_ids` instead of `r.species_key`

### C. `src/gbif/taxonomy.py`

1. `fetch_kingdom()`: use the new `name_suggest` wrapper. The response still
   has `kingdom`, so no parsing change is needed. Note that COL may return
   `Protozoa` where the legacy backbone returned something else. Check the
   caller in `src/bold/id_engine.py` to see how the kingdom string is used.

### D. `src/gbif/maps.py` and `src/coverage/assess.py`

1. `draw_occurrence_map()`: take a COL taxon ID and pass
   `checklistKey=COL_CHECKLIST_KEY` to `occurrences.search`.
2. `assess.py:268`: pass `gbif_target.record.taxon_id` instead of
   `gbif_target.key`. The target is the species or genus itself, so
   `taxonID` is on its record and no extra lookup is needed.

### E. `src/utils/config/config.py`

1. Replace the `'gbif'` legacy integer keys in `HIGHER_CLASSIFICATIONS` with
   COL taxonIDs, using the table in finding 4. Rename the key to `'gbif_col'`
   so that a stale legacy key fails loudly instead of silently mis-filtering.
   Update the reader in `RelatedTaxaGBIF.__init__`.
2. Check `tests/test_taxonkit.py:90`, which also uses a `'gbif'` value.
3. Add an integration test that resolves every `HIGHER_CLASSIFICATIONS` COL
   ID with `get_usage_key()` and asserts the result's `canonicalName`. This
   catches COL releases that retire an ID.

### F. Tests (`tests/test_gbif.py` + `tests/test-data/`)

1. Regenerate `gbif_related_species.json` from
   `/v1/species/search?rank=species&higherTaxonKey=<COL genus>&datasetKey=COL`
   and `gbif_related_country.json` from
   `/v1/occurrence/search?genusKey=<COL taxonID>&checklistKey=COL&country=AU&facet=speciesKey&limit=1`.
   The current test taxon is *Cheiloxena aitori*. Look up its COL genus key
   and taxonID and update the expected `genus_key` and counts.
2. Patch `name_suggest` at its new location (the wrapper, or
   `pygbif.gbifutils.gbif_GET`) instead of `pygbif.species.name_suggest`.
3. `test_request_country`: assert `name_lookup` is called with
   `datasetKey=COL_CHECKLIST_KEY`, and `occurrences.search` with
   `checklistKey` and a string `genusKey`.
4. `test_classification_filter`: filtering now happens on the server, so the
   test becomes a request-shape test:
   - mock `get_usage_key` to return `296374190`
   - set `classification={'gbif_col': 'N', ...}`
   - assert the suggest wrapper is called with `higher_taxon_key=296374190`
   - return only the Animalia Prunella fixture (`299375662`) and assert
     `key == 299375662`
5. New tests:
   - the extinct filter (`extinct: true` is excluded)
   - a synonym resolved via `acceptedKey`
   - `for_country` matching string facet IDs to `taxon_id`
6. Run the unit tests as described in `.vscode/launch.json` ("Unit tests"),
   then flake8.
7. Run the integration tests. Coverage counts will shift because COL
   circumscriptions differ from the legacy backbone. Review the diffs rather
   than blindly updating the expectations (see
   `tests/test_coverage_assert.py:134`).


## Open questions

1. ~~Bacteria / Archaea / Viruses~~: resolved. `higherTaxonKey` filtering
   works on the DOMAIN and UNRANKED roots (see finding 4).
2. **Alternative approach, `/v2/species/match` for target lookup:** it gives
   a single best match with built-in synonym resolution (`acceptedUsage`) and
   accepts `kingdom=` hints for homonyms. For example,
   `scientificName=Prunella&kingdom=Animalia` returns the bird genus. That
   could replace the suggest-then-filter-then-`name_usage` loop in
   `_get_taxon_record()`. It would mean parsing the new nested schema and
   only returns COL string IDs, so we'd still need v1 keys for
   `higherTaxonKey` in `relatives`. **Recommendation:** stay on v1 for this
   task (smaller change), and consider v2 match as a follow-up.
3. ~~Should `nubKey` (the legacy backbone key) be logged or kept anywhere for traceability during the transition?~~ Not needed.
