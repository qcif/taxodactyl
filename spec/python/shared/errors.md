# Spec: Non-fatal error reporting (`src/utils/errors.py`)

## 1. Purpose

Record failures that must not stop the analysis (typically one external
lookup for one target) and show them in the report next to the result
they affect, so a missing value is never silently presented as a
negative.

## 2. Requirements

| ID | Requirement |
|---|---|
| ERR-001 | `write(location, msg, exc=None, query_dir=None, context=None)` MUST write `{location, message, exception: str(exc)|null, context}` as JSON to `<query_dir or output_dir>/errors/<md5(content)[:8]>.json`. Identical errors therefore collapse to one file. |
| ERR-002 | Callers inside a per-query step MUST pass `query_dir`; Nextflow only collects `<query_folder>/errors/*` (NF-PR-101, NF-PR-111). |
| ERR-003 | `ErrorLog(query_dir)` MUST load every `errors/*.json` under `query_dir` (or `output_dir`), removing exact duplicates. |
| ERR-004 | `ErrorLog.filter(...)` supports `location`, `location_not`, `location_gt/gte/lt/lte`, `location_in` (string prefix of the location number), and `context` (an error is excluded only if it **has** a context key with a different value; errors without that key are kept). |
| ERR-005 | Custom exceptions: `FASTAFormatError` ("FASTA format error: …"), `MetadataFormatError` ("Metadata CSV format error: …"), `APIError`. |

## 3. Locations

| Name | Value | Written by |
|---|---|---|
| `BLAST` | 1.0 | — (unused) |
| `BOLD` | 1.1 | — |
| `BOLD_ID_ENGINE` | 1.10 | — |
| `BOLD_TAXA` | 1.11 | P1-BOLD (dead code) |
| `SOURCE_DIVERSITY_ACCESSION_ERROR` | 4.01 | P4 |
| `DB_COVERAGE` | 5 | P5 |
| `DB_COVERAGE_NO_GBIF_RECORD` | 5.01 | P5 |
| `DB_COVERAGE_TAXONKIT_ERROR` | 5.02 | P5, `taxonomy.extract.taxids` |
| `DB_COVERAGE_TARGET` | 5.1 | — |
| `DB_COVERAGE_RELATED` | 5.2 | P5 |
| `DB_COVERAGE_RELATED_COUNTRY` | 5.3 | P5 |

## 4. Defects

| ID | Severity | Defect |
|---|---|---|
| ERR-D-001 | Medium | P4 writes `SOURCE_DIVERSITY_ACCESSION_ERROR` **without `query_dir`** (`src/sources/collect.py`), so the file lands in `<task>/errors/`, which Nextflow does not collect: P4 non-fatal errors never reach the report. |
| ERR-D-002 | Low | Locations are floats: `BOLD` (1.1) and `BOLD_ID_ENGINE` (1.10) are the same value; `location_in` string prefixes also conflate e.g. 1.1 and 1.11. |

---

## Provenance

**Initially derived from:** `errors.py` (194) and its callers. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
