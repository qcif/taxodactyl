# Spec: P1 BOLD search (`scripts/p1_bold_search.py`) and `src/bold/`

**Derived from:** `p1_bold_search.py` (100), `src/bold/id_engine.py` (434),
`src/bold/stats.py` (84), `src/utils/orient.py` (289),
`src/gbif/taxonomy.py`, `scripts/Dockerfile`, `tests/test_orient.py`.
v1.5.0.
**Called by:** Nextflow `BOLD_SEARCH` (BOLD mode, once per run).
`stats.fetch_bold_records_count` is used by P5 in BOLD mode.

> **Status: not operational.** Besides the Nextflow wiring faults
> (NF-D-002), this module cannot complete inside the shipped image
> (P1B-D-001, P1B-D-002). Requirements below describe the code's intended
> contract; none of it is exercised end-to-end today.

## 1. Purpose

Alternative to BLAST + P1 + blastdbcmd + P2: submit each query to the BOLD
v4 ID Engine, enrich hits with BOLD record metadata, and write per-query
hit files in a shape P3 can consume (BOLD branch of P3, §3.2 there).

## 2. Interface

| Arg | Required | Notes |
|---|---|---|
| `--query-fasta` | yes | |
| `--metadata-csv` | yes | config only |
| `--output-dir` | no | |
| `--bold-database` | no | default `COX1_SPECIES_PUBLIC` |

Environment: `SKIP_ORIENTATION` (any non-empty value skips HMM
orientation). **Not** `BOLD_SKIP_ORIENTATION`, which is what Nextflow
exports (P1B-D-002).

External services: `http://v4.boldsystems.org/index.php/Ids_xml` (ID
Engine), `…/API_Public/combined` (record metadata, TSV),
`…/API_Public/stats` (P5 record counts, https). All calls go through
`Throttle(ENDPOINTS.BOLD)` ([shared/throttle.md](shared/throttle.md)).
External tool: `hmmsearch` (HMMER) unless orientation is skipped.

Outputs per query (folder from `config.create_query_dir(query_index, query_title)`):

| File | Content |
|---|---|
| `query_title.txt` | FASTA description of the query |
| `all_hits.json` | §4 |
| `all_hits.fasta` | one record per hit: id `hit_id`, description `taxonomic_identification`, sequence = BOLD `nucleotides` with `-` removed (full barcode sequence, unlike BLAST P1-D-001) |

**Not written:** `bold_taxonomy.json` (the call is commented out:
"Not actually used downstream"), although `BOLD_SEARCH` declares it as a
required output (P1B-D-003).

## 3. Algorithm

### 3.1 Orientation (`src/utils/orient.py`), unless `SKIP_ORIENTATION` is set

| ID | Requirement |
|---|---|
| P1B-001 | Translate each query in 6 frames (sequence trimmed to a multiple of 3 before `-`/newline removal). Intended: try NCBI table 2 (vertebrate mt) then 5 (invertebrate mt); actually always table 2 (P1B-D-006). |
| P1B-002 | Run `hmmsearch --tblout` with each profile in `src/utils/ref_data/hmm/` (`pf00115`, `pf00116`, `pf02790` — COX1/COX2 domains) over all frames; a frame matches if full-sequence E-value < `hmmsearch_min_evalue` (1e-5). |
| P1B-003 | For each query, the first matching frame (hmmsearch output order, profile glob order) decides orientation: forward frame → submit as-is; reverse → submit reverse complement; annotate `oriented=True`, `frame`, `forward`. |
| P1B-004 | Queries with no match: submit **both** the original and its reverse complement (`oriented=False`). |
| P1B-005 | A failing `hmmsearch` (`CalledProcessError`) is logged and re-raised: the whole BOLD search fails. A missing binary raises `FileNotFoundError` (P1B-D-001). |

### 3.2 ID Engine search

| ID | Requirement |
|---|---|
| P1B-010 | Submit every (possibly doubled) sequence as `GET Ids_xml?sequence=<seq>&db=<db>`, up to 5 concurrent requests, each with throttle + retry; HTTP error ⇒ raise (run fails). |
| P1B-011 | Parse each `<match>` into: `hit_id`, `sequence_description`, `database`, `citation`, `taxonomic_identification`, `similarity` (float or `None`), `specimen`, `url`, `country`, `latitude`, `longitude`. A missing XML element raises `AttributeError` (P1B-D-005). |
| P1B-012 | Per query id keep one result: the first completed, replaced by a later one only if that one has hits. When both orientations return hits, the winner depends on completion order (P1B-D-007). |
| P1B-013 | Record per query: `query_index` (position in the input FASTA), `query_id`, `query_title`, `query_length`, `query_frame`, `query_strand` (`+`/`-` from HMM orientation; `+` for un-oriented winners even if the reverse complement won), `query_sequence` (the sequence actually submitted), `query_orientation` (`HMMSearch` or `BOLD ID Engine`). |

### 3.3 Metadata enrichment

| ID | Requirement |
|---|---|
| P1B-020 | Fetch `API_Public/combined?ids=<id1|…|id50>&format=tsv` in batches of 50 (5 concurrent), keyed by `processid`; merge all TSV columns into the matching hit. |
| P1B-021 | Then set `species` = `species_name` (or `''`), `taxonomy` = `{phylum, class, order, family, genus, species}` from `*_name` columns (no kingdom), `accession` = `genbank_accession` (or `''`), `identity` = `similarity`; remove the `*_name` columns. |
| P1B-022 | Hits with no metadata keep empty species/taxonomy and therefore cannot become P3 candidates. |

## 4. `all_hits.json` (BOLD)

```json
{
  "query_index": 0, "query_id": "...", "query_title": "...",
  "query_length": 658, "query_frame": 1 | null, "query_strand": "+|-",
  "query_sequence": "...", "query_orientation": "HMMSearch|BOLD ID Engine",
  "hits": [
    {"hit_id", "sequence_description", "database", "citation",
     "taxonomic_identification", "similarity", "identity", "specimen",
     "url", "country", "latitude", "longitude",
     "species", "taxonomy": {phylum..species}, "accession",
     "<all other BOLD combined-TSV columns, e.g. bin_uri, nucleotides, collectors>"}
  ]
}
```

No `alignment_length`, `query_coverage`, `bitscore`, `e_value`; hits are in
ID Engine order (not re-sorted).

## 5. `stats.fetch_bold_records_count(taxon, rank=None)` (used by P5)

| ID | Requirement |
|---|---|
| P1B-030 | Return `None` (with a warning) if `rank` is given and not one of species/genus/family/order. |
| P1B-031 | `GET API_Public/stats?taxon=<taxon>&format=json` via throttle. `records_with_species_name == 0` ⇒ 0. With `rank`: the `records` of the entity at that rank whose name equals `taxon` (case-insensitive), else 0. Without rank: `records_with_species_name`. |
| P1B-032 | `requests.RequestException` ⇒ log and return `None`. Other errors (e.g. malformed JSON, `KeyError`) propagate. |

## 6. Defects

| ID | Severity | Defect |
|---|---|---|
| P1B-D-001 | High | The analysis image does not contain `hmmsearch` (HMMER install is commented out in `scripts/Dockerfile`), and orientation runs by default ⇒ `FileNotFoundError`. |
| P1B-D-002 | High | Orientation is skipped only by env `SKIP_ORIENTATION`; Nextflow exports `BOLD_SKIP_ORIENTATION`, so `--bold_skip_orientation 1` has no effect. |
| P1B-D-003 | High | `bold_taxonomy.json` is never written, but `BOLD_SEARCH` declares it as a required output ⇒ the process always fails. The code that would build it (`taxon_taxonomy`) depends on `self.records`, which is commented out. |
| P1B-D-004 | Medium (*to confirm*) | Uses the BOLD **v4** API over plain `http`. The README states BOLD is not operational and the docs mention BOLD v5; the v4 endpoints may be retired. |
| P1B-D-005 | Medium | XML parsing assumes every element exists (`.find(...).text`); a match without coordinates or URL raises. `similarity=None` later breaks P3 (P3-D-005). |
| P1B-D-006 | Low | `translate()` breaks after the first table that yields any protein, so table 5 (invertebrate mt) is never used; most insect COI queries will fail HMM orientation and fall back to double submission (slower, not wrong). |
| P1B-D-007 | Medium | For un-oriented queries where both strands return hits, the kept strand depends on thread completion order (non-deterministic), and `query_strand` is always `+`. |
| P1B-D-008 | Medium | Downstream alignment uses the **original** query from `sequences.fasta`, not `query_sequence`; a reverse-complemented query is aligned against forward hits (MAFFT runs without `--adjustdirection`). |
| P1B-D-009 | Low | Any single HTTP failure aborts the search for all queries (no per-query isolation). |
| P1B-D-010 | Low | Dead code: `taxon_count`, `taxon_collectors`, `taxon_taxonomy`, `_fetch_records`, `_fetch_kingdoms`, `self.raw_hits`, `gbif.taxonomy.fetch_kingdom` (only caller is dead). |

## 7. Test mapping

`tests/test_orient.py::test_orientate` (P1B-001..004, requires hmmsearch
locally). `tests/integration/test_integration_bold.py` runs BOLD cases
against live APIs (manual). **Not covered:** P1B-010..022 parsing and
merging, `stats.py`, P1B-D-* failure modes.

## 8. Open questions

1. Is BOLD support to be repaired (v5 API, image with HMMER or orientation
   removed) or retired? The answer decides whether NF-D-002, NF-D-009 and
   every P1B defect are fixed or the BOLD branch is deleted.
