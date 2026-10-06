# Spec: Input validation web service (`services/input_validation/`)

**Depends on:** [../python/p0-validation.md](../python/p0-validation.md)
(`p0_validation.validate_inputs`, imported from `scripts/`).

Not part of the Nextflow pipeline. It lets a submitter check and fix
`metadata.csv` and FASTA in a browser **before** running Taxodactyl.

## 1. Components

| Component | Tech | Role |
|---|---|---|
| API | FastAPI/uvicorn, one endpoint `POST /validate` | runs P0 on uploaded/edited input, maps failures to structured errors and offending rows |
| Client | React (Vite) SPA, `VITE_API_URL` (default `http://127.0.0.1:8000`), `VITE_BASE_PATH` | upload, table editor for the CSV, re-validate, download corrected files |
| Deployment | systemd unit (uvicorn on 127.0.0.1:8000, user `www-data`, repo at `/mnt/data/taxodactyl_repo`) + nginx (`/validation/api/` → 8000, `/validation/` → `client/dist`, 50 MB body limit) | |

## 2. API contract: `POST /validate` (multipart form)

| Field | Notes |
|---|---|
| `metadata_csv` | uploaded file, **or** |
| `metadata_text` | edited CSV text (takes precedence) |
| `query_fasta` | optional if the CSV has a `sequence` column (header compared lower-cased/stripped) |

| ID | Requirement |
|---|---|
| SVC-001 | No metadata ⇒ HTTP 400 `{ok:false, error:"No metadata CSV provided"}`. No FASTA and no `sequence` column ⇒ 400 with an explanatory error. |
| SVC-002 | With a `sequence` column and no FASTA, the API MUST synthesise a temporary FASTA from `sample_id`/`sequence` (80-column lines; rows lacking either are skipped). |
| SVC-003 | The API MUST call `validate_inputs(metadata_csv, query_fasta, ignore_seq_count=True)`. Consequences: P0's auto-fixes (space→`_` in ids, duplicate FASTA ids dropped) are applied to the temporary copies; the max-sequence-count rule is not enforced; the taxdb directory is not checked. |
| SVC-004 | Success ⇒ 200 `{ok:true, message, metadata_csv, query_fasta}` where `metadata_csv` is the (possibly auto-fixed) CSV text with the `sequence` column removed if present, and `query_fasta` the (possibly auto-fixed) FASTA text. |
| SVC-005 | Failure ⇒ 400 `{ok:false, error:{type,message,sample_id,value}, metadata_csv, [rows], [invalid_columns], [fix_location]}`. `rows` = 0-based data-row indexes of the offending rows. |
| SVC-006 | The exception text from P0 MUST be classified by regex into: `metadata_missing_sample`, `invalid_taxa_of_interest`, `invalid_pmi`, `invalid_country` (with hints for Turkey/Türkiye/Hawaii), `invalid_required_columns`, `invalid_locus`, `invalid_classification`, `invalid_fasta` (min length, max length, illegal residue; `fix_location: local_fasta_file`), else `unknown` with the raw message. |
| SVC-007 | Temporary files MUST be deleted after each request. |

## 3. Client behaviour

| ID | Requirement |
|---|---|
| SVC-010 | The client lets the user upload a CSV (+ optional FASTA), shows the CSV in an editable table, highlights the rows/columns reported by the API, and re-submits edited text. |
| SVC-011 | After success the client MUST offer download of the validated CSV and FASTA as a **zip**, split into files of at most 150 sequences each (the P0 limit), with a warning when splitting occurs. |

## 4. Defects

| ID | Severity | Defect |
|---|---|---|
| SVC-D-001 | High | `remove_sequence_from_csv` rebuilds the CSV with `",".join(...)` and **no quoting**: any metadata value containing a comma (e.g. host `Cut flower, Rosa`) or quote corrupts the returned CSV, shifting columns. Downstream, the user submits a shifted CSV that may still pass validation. |
| SVC-D-002 | Medium | Error classification depends on exact P0 message wording. A P0 wording change (P0-D-* fixes) silently degrades to `unknown`; several P0 failures (duplicate/invalid sample id, illegal sequence in CSV, too many sequences) have no classifier. |
| SVC-D-003 | Medium | The API imports `p0_validation`, which instantiates the process-wide `Config` singleton and mutates it on every request (`update_from_args`); `validate()` is an `async def` running blocking code, so requests serialise on the event loop (safe but blocks all clients while validating large inputs). Import also creates `output/` and `run.log` in the working directory. |
| SVC-D-004 | Medium (security) | No authentication or rate limit; CORS `allow_origins=["*"]` with `allow_credentials=True`; unbounded parsing of a 50 MB body per request. |
| SVC-D-005 | Medium | The validator does not check the taxdb, locus file version or the pipeline's parameter limits actually in force (`fasta_min/max_length` overrides), so "validated" input can still fail in the pipeline. |
| SVC-D-006 | Low | `requirements.txt` is unpinned and duplicates `scripts/requirements.txt` partially; the systemd unit hard-codes `/mnt/data/taxodactyl_repo`. |
| SVC-D-007 | Low | API returns cleaned CSV without the `sequence` column while the user's own file keeps it; users may not realise two artefacts (CSV + FASTA) must now be submitted together. |

## 5. Test mapping

None. No unit, integration or UI tests exist for this service
(TST-G-008).

---

## Provenance

**Initially derived from:** `api/main.py` (~330), `api/utils.py` (~480), `client/src/App.jsx` (439), `client/src/components/CsvEditor.jsx` (129), `deployment/validation.{service,nginx.conf}`, `README.md`. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
