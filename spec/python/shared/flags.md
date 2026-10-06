# Spec: Flags (`src/utils/flags.py`, `config/flags.csv`)

## 1. Purpose

Flags are the discrete, reportable outcomes of the analysis. Each is an
identifier (`1`, `2`, `4`, `5.1`…), a value (`A`–`E`, `NA`, `ERR`), and
optionally a target taxon and target type. Their meaning, wording and
severity live in `flags.csv`, not in code.

## 2. Flag catalogue (`flags.csv`)

| Id | Name | Values (level) | Written by |
|---|---|---|---|
| 1 | Candidate selection | A(1) B(2) C(3) D(2) E(3) | P3 |
| 2 | Taxa of interest | A(1) B(3) NA(0) | P3 |
| 4 | Supporting publications | A(1) B(2) — per candidate species | P4 |
| 5 | Database coverage (summary) | NA(0) B(2) — per target | computed at read (§4) |
| 5.1 | Target taxon coverage | A(1) B(2) C(3) NA(0) ERR(0) | P5 |
| 5.2 | Related species coverage | A(1) B(2) C(3) NA(0) ERR(0) | P5 |
| 5.3 | Related species in country | A(1) B(2) C(0) NA(0) ERR(0) | P5 |
| 6 | Phylogenetic assessment | A(1) B(2) C(3) | **never written** (P3-D-003) |
| 7 | Preliminary ID confirmation | A(1) B(3) NA(0) | P3 |

Level → Bootstrap class: 0 secondary, 1 success, 2 warning, ≥3 danger.

## 3. Writing (`Flag.write(query_dir, flag_id, value, target=None, target_type=None)`)

| ID | Requirement |
|---|---|
| FLG-001 | File `<query_dir>/<flag_id>.flag` holds a JSON list of `{flag_id, value, target, target_type}`. |
| FLG-002 | Writing replaces the entry with the same `(flag_id, target, target_type)` or appends a new one (upsert). An unreadable file is treated as empty and overwritten. |
| FLG-003 | Writes are not locked; concurrent writers to the same file (threads) could lose updates. Current writers are single-threaded per file. |

## 4. Reading (`Flag.read(query, as_json=False)`)

| ID | Requirement |
|---|---|
| FLG-010 | Merge all `*.flag` files in the query dir into `{flag_id: Flag}` (no target) or `{flag_id: {target_type: {target: Flag}}}` (target with type) or `{flag_id: {target: Flag}}` (target, no type). Malformed files are skipped with a warning. |
| FLG-011 | Every `5.x` entry MUST have all three target types present (empty dicts added). |
| FLG-012 | If no Flag 4 was written, `flags['4'] = None` ("P4 not run"). |
| FLG-013 | Summary Flag 5 per `(target_type, target)`: among 5.1/5.2/5.3 take the highest level, or the lowest if any is level 0; if the chosen level is < 2 and the query has no locus, use `5B` instead. A `5NA` "null" fallback is always present per target type. |
| FLG-014 | `explanation`/`outcome` text comes from `flags.csv`; if the query has no locus, the phrases " given locus for this", " at the given locus", " for this locus" are removed. |

## 5. Defects

| ID | Severity | Defect |
|---|---|---|
| FLG-D-001 | Medium | `flags.csv` explanations hard-code thresholds ("≥ 98.5%", ">5 entries", ">90%") that do not follow parameter changes (see P3-D-004, P5-D-001). |
| FLG-D-002 | Medium | FLG-013 takes the **minimum** level whenever any sub-flag is level 0 — e.g. 5.1C (danger) with 5.3C (level 0) summarises as level 0 "secondary", hiding the danger in the summary badge. *Confirm intent.* |

---

## Provenance

**Initially derived from:** `flags.py` (360), `config/flags.csv`, callers in P3–P6. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
