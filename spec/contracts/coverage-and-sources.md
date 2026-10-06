# Contract: database coverage, sources and error files

**Producers:** [P5](../python/p5-db-coverage.md) (`db_coverage.json`,
`5.*.flag`, `map_*.png`), [P4](../python/p4-source-diversity.md)
(`aggregated_sources.json`, `4.flag`), both via
[shared/errors.md](../python/shared/errors.md) for `errors/*.json`.
**Consumer:** [P6](../python/p6-report.md).

## 1. `db_coverage.json`

```json
{ "coverage": { "candidate|toi|pmi": { "<target as supplied>": {
      "target":  <int | null>,
      "related": { "<species>": <int|null> } | {} | null,
      "country": { "<species>": <int> } | {} | "NA" | null,
      "genus":   "<string, only if a GBIF record was found>" } } },
  "ncbi_urls": { "<target>": {"blast": <url|null>, "taxonomy": <url|null>} } }
```

| ID | Guarantee |
|---|---|
| COV-001 | All three target-type keys are present (possibly empty). |
| COV-002 | A target with no GBIF record has `target/related/country = null`. Higher-rank targets have `related` and `country` `null` and `target` = a record count. |
| COV-003 | `country` is the literal string `"NA"` iff the query has no country. |
| COV-004 | `null` means "could not be determined", never "zero". Zero is `0`. (Exceptions: P5-D-005 records failed per-species counts as 0.) |

## 2. `aggregated_sources.json`

```json
{ "<species>": [ [ <source>, ... ], ... ] }   // list of independent-source groups
```
GenBank source: `{accession, is_automated, publications:[{authors:[…], title, journal}]}`;
BOLD collectors source: `{bold_id, bold_url, collectors, publications:[]}`.
Absent when P4 did not run (candidate count outside 1..max) — consumers
MUST tolerate absence (P6 does).

## 3. `errors/<hash8>.json`

`{ "location": <float>, "message": <str, may contain HTML>, "exception": <str|null>, "context": <object|null> }`.
Locations: [errors.md §3](../python/shared/errors.md). Only files inside
the query folder reach the report (ERR-D-001).

## 4. `*.flag`

See [../python/shared/flags.md](../python/shared/flags.md) §3.

---

## Provenance

**Initially derived from:** [p5-db-coverage.md](../python/p5-db-coverage.md) §6, [p4-source-diversity.md](../python/p4-source-diversity.md) §7, [shared/errors.md](../python/shared/errors.md) §3 — each already derived from source, v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
