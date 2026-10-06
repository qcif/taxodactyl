# Spec: P0 input validation (`scripts/p0_validation.py`)

**Called by:** Nextflow `VALIDATE_INPUT` ([../nextflow/processes.md §2](../nextflow/processes.md));
`services/input_validation/api` (programmatic `validate_inputs()`).
**Depends on:** [shared/config.md](shared/config.md).

---

## 1. Purpose

Reject malformed user input before any search runs, with a message a
submitter can act on, and emit a normalised `sequences.fasta` for the rest
of the pipeline. P0 is the only content validation of the sample sheet
and FASTA in the whole pipeline (Nextflow does none — NF-WF-014 note).

**Non-goals:** it does not check taxonomic names exist, does not check the
BLAST database, does not check the taxonkit binary or taxdump version, and
does not rewrite `metadata.csv`.

## 2. Interface

### 2.1 CLI (`main()`)

| Arg | Type | Required | Effect |
|---|---|---|---|
| `--output-dir` | existing path | no (default `config.output_dir`) | where `sequences.fasta` and the log are written |
| `--metadata-csv` | existing path | **yes** | sample sheet |
| `--query-fasta` | existing path | no | if absent, sequences are taken from the metadata `sequence` column |
| `--taxdb-dir` | existing path | **yes** | NCBI taxdump dir |
| `--bold` | flag | no | writes the BOLD marker file (`<output_dir>/BOLD`) and relaxes locus validation (§4.3) |
| `--allowed-loci-file` | existing path | no | overrides the loci panel |
| `--fasta-max-sequences`, `--fasta-min-length`, `--fasta-max-length` | int | no | override limits |
| `-c/--config` (repeatable) | path | no | config cascade (shared/config.md) |

A path argument that does not exist fails argument parsing
(`FileNotFoundError`) before validation starts.

### 2.2 Programmatic (`validate_inputs(metadata_csv, query_fasta, bold=False, ignore_seq_count=False)`)

Used by the input-validation web service. Differs from `main()`:
- runs two **auto-fixes that mutate the input files in place** first (§5);
- does **not** validate the taxdb directory;
- can skip the max-sequence-count check (`ignore_seq_count`);
- requires `query_fasta` (auto-fixes read it unconditionally).

### 2.3 Outputs

| Output | When | Content |
|---|---|---|
| `<output_dir>/sequences.fasta` | always on success | sanitised sequences (§4.1, §4.4) |
| `<output_dir>/BOLD` | `--bold` | contains `1`; marker read by `config.is_bold` |
| `<output_dir>/run.log` | always | log |
| exit status | — | 0 on success; non-zero with an exception message on any validation failure |

`metadata.csv` is **not written** by P0; the Nextflow process relies on
the staged input file having that name already (NF-PR-021).

## 3. Order of checks (`main()`)

1. Parse args; `config.update_from_args(args)` (sets paths/limits, writes `BOLD` marker).
2. `_validate_taxdbs(taxdb_dir)`.
3. `_validate_fasta(query_fasta)` → list of sequence ids, or `None` if no FASTA.
4. `_validate_metadata(metadata_csv, ids, bold)`.

The first failure raises and stops; only one error is reported per run.

## 4. Requirements

### 4.1 FASTA (`_validate_fasta`)

| ID | Requirement |
|---|---|
| P0-001 | If no FASTA path is given, MUST return `None` (sequences expected in metadata). |
| P0-002 | Records are parsed with Biopython; the **id** is the header text up to the first whitespace. |
| P0-003 | A repeated id MUST raise `FASTAFormatError("Duplicate sequence ID …")`. |
| P0-004 | Each sequence is sanitised (remove all whitespace and `-`, uppercase) and MUST then contain only IUPAC ambiguous DNA letters `GATCRYWSMKHBVDN`; otherwise raise naming the first illegal residue and its position in the sanitised sequence. |
| P0-005 | When the running count exceeds `inputs.fasta_max_sequences` (default 150) and `ignore_seq_count` is false, MUST raise. |
| P0-006 | Raw (unsanitised) length MUST be `>= fasta_min_length` (default 20) and `<= fasta_max_length` (default 3000); otherwise raise with the length and limit. |
| P0-007 | On success MUST write all sanitised records (id only, no description) to `<output_dir>/sequences.fasta`, in input order. |
| P0-008 | An empty FASTA (0 records) MUST pass and yields an empty id list (see P0-D-003). |

Note: lengths are checked **before** sanitising (P0-006), so gaps and
whitespace count toward the length limit.

### 4.2 Metadata structure (`_validate_metadata`)

Column names come from `config.inputs.metadata_csv_header` (defaults:
`sample_id, locus, preliminary_id, taxa_of_interest, country, host,
classification, sequence`). Required fields:
`inputs.metadata_csv_required_fields` = `sample_id, locus, preliminary_id`.

| ID | Requirement |
|---|---|
| P0-010 | Every required column MUST be present in the header, else `MetadataFormatError("missing required column(s): …")`. (Checked per row; with no data rows, not checked.) |
| P0-011 | If no FASTA was given, the `sequence` column MUST be present, else raise "Sequence column is expected but no sequence provided …". |
| P0-012 | If a FASTA was given, every row's `sample_id` (unstripped) MUST be one of the FASTA ids. |
| P0-013 | Every required field MUST be non-blank after stripping; for `locus` the message adds "please enter "NA"". This applies in BOLD mode too. |
| P0-014 | Each row's field validators (§4.3) MUST run; any failure is re-raised as `MetadataFormatError("Error in row N (sample ID: X): …")`. Rows are 1-based excluding the header. |
| P0-015 | If a FASTA was given, every FASTA id MUST appear as a `sample_id` in the sheet, else raise listing the missing ids. |
| P0-016 | If no FASTA was given, MUST write `<output_dir>/sequences.fasta` with one record per metadata row (`>sample_id` + sanitised `sequence`), in row order. |
| P0-017 | Extra columns are allowed and ignored by P0 (they flow to the report via `config.metadata`). |

### 4.3 Field validators

| ID | Field | Rule |
|---|---|---|
| P0-020 | `sample_id` | After strip, MUST match `^[A-z0-9_\-\.]*$` (see P0-D-005 on `A-z`). |
| P0-021 | `locus` | If `config.allowed_loci` is empty, accept anything. If `--bold` and value is empty, accept (unreachable — P0-013 rejects blanks first). Otherwise lowercase, strip, remove a trailing `" gene"`, and the result MUST be `na` or equal to one of the synonyms of some locus in the loci file; else raise listing all loci. |
| P0-022 | `preliminary_id` | After strip, MUST match `^[A-z ]*$` — letters and spaces only (no digits, `.`, `-`, `×`). |
| P0-023 | `taxa_of_interest` | If present: after strip, MUST match `^[A-z| ]*$`. `|` separates taxa. |
| P0-024 | `country` | If non-blank: MUST resolve with `pycountry.countries.lookup` (name, official name, alpha-2 or alpha-3; case-insensitive). `NA` resolves to Namibia. |
| P0-025 | `host` | No validation. |
| P0-026 | `sequence` | If non-blank: sanitised value MUST be IUPAC DNA (P0-004). **Length and count limits are not applied** (P0-D-002). |
| P0-027 | `classification` | If non-blank: lowercased value MUST be a key of `Config.HIGHER_CLASSIFICATIONS`: `animalia, animal, animals, plantae, plant, plants, fungi, chromista, bacteria, archaea, viruses, virus`. |

### 4.4 Taxdb (`_validate_taxdbs`)

| ID | Requirement |
|---|---|
| P0-030 | `taxdb_dir` MUST be a directory, else `FileNotFoundError`. |
| P0-031 | It MUST contain `citations.dmp, delnodes.dmp, division.dmp, gc.prt, gencode.dmp, images.dmp, merged.dmp, names.dmp, nodes.dmp`, else `FileNotFoundError` listing the missing files. No version or `taxonkit` binary check. |

## 5. Auto-fixes (programmatic path only)

| ID | Requirement |
|---|---|
| P0-040 | `_autofix_sample_id_spaces`: replace spaces with `_` in every `sample_id` in the CSV (rewriting the file with the same columns); for FASTA records whose full description with spaces→`_` equals a CSV sample id and differs from the record id, rename the record to it; rewrite the FASTA if changed. |
| P0-041 | `_autofix_duplicate_fasta_ids`: drop all but the first record for each repeated id and rewrite the FASTA, logging a warning per duplicated id. |
| P0-042 | These MUST NOT run in the Nextflow path (`main()`), where the same inputs are rejected instead (P0-003, P0-020). |

## 6. Errors and exit

All failures are Python exceptions (`FASTAFormatError`,
`MetadataFormatError`, `FileNotFoundError`) with an uncaught traceback;
the process exits non-zero, `VALIDATE_INPUT` fails and the run stops
(NF-ER-005). The message is intended for the submitter; it appears in the
task's `.command.err` (collected to `<outdir>/errors/VALIDATE_INPUT/`).

## 7. Defects

| ID | Defect |
|---|---|
| P0-D-001 | **Loci `atpB`, `trnL`, `AChE` can never validate.** Their synonyms contain upper-case letters (`atpB`, `ATP synthase subunit B`, `trnL`, `tRNA leu`, `AChE`, `Acetylcholinesterase`) and none of the three keys appear in their own synonym list in lower case; P0 lowercases the input and compares case-sensitively. `Locus.__contains__` has the same asymmetry. |
| P0-D-002 | Sequences supplied via the metadata `sequence` column bypass `fasta_min_length`, `fasta_max_length` and `fasta_max_sequences`. A blank `sequence` cell passes and writes an empty FASTA record. |
| P0-D-003 | An empty FASTA passes validation with any metadata (P0-012 is skipped when the id list is empty and P0-015 compares against an empty set). |
| P0-D-004 | Duplicate `sample_id` rows in metadata are not rejected; with CSV sequences they produce duplicate FASTA ids, and `config.metadata` keeps only the last row. |
| P0-D-005 | Regex range `A-z` also admits `[ \ ] ^ _` and backtick in `sample_id`, `preliminary_id`, `taxa_of_interest`. |
| P0-D-006 | `--bold` help says it "accept[s] blank locus field", but P0-013 rejects blank locus before the BOLD exemption is reached. |
| P0-D-007 | P0-012 compares the **unstripped** `sample_id` to FASTA ids, while P0-020 validates the stripped value; a trailing space yields a confusing "not present in FASTA" error. |
| P0-D-008 | `classification` accepts 12 values here but `assets/schema_input.json` (nf-schema's secondary schema for `--metadata`, validated by `validateParameters()` before any process runs) enumerates only 7. If that nf-schema layer validates CSV row content as documented (see [../contracts/inputs.md §1](../contracts/inputs.md)), the 5 extra values P0 accepts (`animal`, `animals`, `plant`, `plants`, `virus`) are rejected by nf-schema **before P0 ever sees the row**, through the Nextflow-launched pipeline — those P0 branches are reachable only via the validation web service or a direct script call, which bypass nf-schema. *To confirm nf-schema's file-content validation actually fires here, by running a metadata.csv with `classification=animal`.* |
| P0-D-009 | `_autofix_sample_id_spaces` logs with `logger.debug("…:", repr(x))` (print-style args) — malformed log calls. |

## 8. Test mapping (`tests/test_validation.py`)

| Test | Covers |
|---|---|
| `test_it_can_validate_fasta_input` | P0-003..006 |
| `test_it_can_validate_metadata_csv` | P0-010, P0-012, P0-015, P0-021 |
| `test_it_creates_fasta_from_csv_sequences` | P0-016 |
| `test_it_sanitizes_sequences_when_creating_fasta` | P0-016, P0-004 sanitisation |
| `test_it_raises_error_when_no_fasta_and_no_sequence_column` | P0-011 |
| `test_it_allows_no_sequence_column_when_fasta_provided` | P0-011 |
| `test_it_can_validate_metadata_{sample_id,locus,preliminary_id,taxa_of_interest,country,host}` | P0-020..025 |
| `test_it_can_validate_taxdbs_path` | P0-030/031 |

**Not covered:** P0-027 (classification), P0-007 output content, auto-fixes
(P0-040/041), `main()` end-to-end, every defect above. The unused fixture
`metadata_sequences_max_length.csv` suggests P0-D-002 was intended to be
tested.

## 9. Open questions

1. Should `preliminary_id` / `taxa_of_interest` allow `sp.`, digits and
   hyphens (common in real IDs, e.g. `Aphis sp.`)?
2. Should P0 write a normalised `metadata.csv` (stripped ids, canonical
   locus names) so downstream steps don't re-interpret raw values?
3. Should P0 check the taxdump age (known virus incompatibility with
   pre-April-2025 taxdumps)?

---

## Provenance

**Initially derived from:** `p0_validation.py` (561 lines), `src/utils/config/*`, `src/utils/locus.py`, `src/utils/countries.py`, `src/utils/utils.py`, `tests/test_validation.py`. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
