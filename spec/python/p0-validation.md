# Spec: P0 input validation (`scripts/p0_validation.py`)

**Called by:** Nextflow `VALIDATE_INPUT` ([../nextflow/processes.md §2](../nextflow/processes.md));
`services/input_validation/api` (programmatic `validate_inputs()`).
**Depends on:** [shared/config.md](shared/config.md).

---

## 1. Purpose

Reject malformed user input before any search runs, with a message a
submitter can act on, and emit a normalised `sequences.fasta` for the rest
of the pipeline. P0 is the only content validation of the sample sheet
and FASTA in the whole pipeline (Nextflow does none — NF-WF-014 note;
since `3339050` nf-schema no longer reads the CSV either,
[../contracts/inputs.md §1](../contracts/inputs.md)).

**Non-goals:** it does not check taxonomic names exist, does not check the
BLAST database, and does not check the taxonkit binary or taxdump version.
It does not *normalise* `metadata.csv` (stripped ids, canonical locus
names — `D-23`); it rewrites the file only for the encoding and `ß`
repairs in §5.1.

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
- after the encoding and `ß` repairs that both paths run (§5.1), runs two
  further **auto-fixes that mutate the input files in place** (§5.2);
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

P0 writes no new `metadata.csv`; the Nextflow process relies on the
staged input file having that name already (NF-PR-021). But P0 may
**rewrite that staged file in place** (§5.1): `VALIDATE_INPUT` stages
inputs with `stageInMode 'copy'` and emits the same `metadata.csv`, so the
repaired copy is what every later step reads, and the user's original
file is never touched. The same applies to the staged FASTA when `ß` is
replaced in its headers.

## 3. Order of checks (`main()`)

1. Parse args; `config.update_from_args(args)` (sets paths/limits, writes `BOLD` marker).
2. `_validate_taxdbs(taxdb_dir)`.
3. `_autofix_metadata_encoding(metadata_csv, query_fasta)` (§5.1).
4. `_validate_fasta(query_fasta)` → list of sequence ids, or `None` if no FASTA.
5. `_validate_metadata(metadata_csv, ids, bold)` — reads the CSV explicitly as UTF-8.

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
| P0-023 | `taxa_of_interest` | If present: after strip, MUST match `^[A-z\| ]*$`. `\|` separates taxa. |
| P0-024 | `country` | If non-blank: MUST resolve with `pycountry.countries.lookup` (name, official name, alpha-2 or alpha-3; case-insensitive). `NA` resolves to Namibia (`P0-D-011`). |
| P0-025 | `host` | No validation. |
| P0-026 | `sequence` | If non-blank: sanitised value MUST be IUPAC DNA (P0-004). **Length and count limits are not applied** (P0-D-002). |
| P0-027 | `classification` | If non-blank: lowercased value MUST be a key of `Config.HIGHER_CLASSIFICATIONS`: `animalia, animal, animals, plantae, plant, plants, fungi, chromista, bacteria, archaea, viruses, virus`. |

### 4.4 Taxdb (`_validate_taxdbs`)

| ID | Requirement |
|---|---|
| P0-030 | `taxdb_dir` MUST be a directory, else `FileNotFoundError`. |
| P0-031 | It MUST contain `citations.dmp, delnodes.dmp, division.dmp, gc.prt, gencode.dmp, images.dmp, merged.dmp, names.dmp, nodes.dmp`, else `FileNotFoundError` listing the missing files. No version or `taxonkit` binary check. |

## 5. Auto-fixes

### 5.1 Encoding and `ß` repair (both paths)

Added in `3339050` (#326). Runs first in `main()` (after the taxdb check)
and in `validate_inputs()`, before any validation
(`_autofix_metadata_encoding`, helpers in `src/utils/encoding.py`). Why:
Excel on Windows saves CSVs as cp1252, and users type German `ß` for
Greek `β` (e.g. `ß-tub`), which `loci.json` spells `β-tub` (LOC-005).

| ID | Requirement |
|---|---|
| P0-043 | `normalise_csv_encoding` MUST read the metadata CSV as bytes and decide its encoding in this order: (1) starts with the ZIP signature `PK\x03\x04` → raise `MetadataFormatError` saying the file looks like an Excel workbook (`.xlsx`) renamed to `.csv` and must be re-exported as "CSV UTF-8 (Comma delimited)"; (2) UTF-16 BOM (LE or BE) → UTF-16; (3) UTF-8 BOM → UTF-8 with BOM; (4) otherwise the first of `utf-8`, `cp1252`, `latin-1` that decodes without error. It never rejects a file on encoding grounds alone (`latin-1` decodes any bytes — `P0-D-013`). |
| P0-044 | A file that decodes as plain UTF-8 (no BOM) MUST be left byte-for-byte untouched, line endings included. Any other file MUST be rewritten in place as UTF-8 without BOM, with `\r\n` and `\r` line endings converted to `\n`, logging a warning that names the source encoding. |
| P0-045 | Every `ß` in the `locus` column MUST be replaced with `β` (e.g. `ß-tub` → `β-tub`). |
| P0-046 | Every `ß` in the `sample_id` column MUST be replaced with the ASCII text `beta`, because sample ids must be ASCII (P0-020). If that changed any row and a FASTA was given, every FASTA header line containing `ß` MUST get the same replacement (whole header line, description included), so ids still match (P0-012, P0-015); the FASTA is then rewritten as UTF-8. If no sample id changed, the FASTA is not touched. |
| P0-047 | The `ß` repairs MUST rewrite the CSV with `csv.DictWriter` and the original header, only when something changed, logging a warning. Neither repair is reported to the submitter other than as a warning in `run.log` (`P0-D-014`). |

Example: a cp1252 file with header `sample_id,locus,preliminary_id` and the
row `VEß1,ß-tub,Fusarium oxysporum`, plus FASTA header `>VEß1`, comes out
as UTF-8 with `VEbeta1,β-tub,Fusarium oxysporum` and `>VEbeta1`; the
report for that query is named `VEbeta1`.

### 5.2 Space and duplicate-id fixes (programmatic path only)

| ID | Requirement |
|---|---|
| P0-040 | `_autofix_sample_id_spaces`: replace spaces with `_` in every `sample_id` in the CSV (rewriting the file with the same columns); for FASTA records whose full description with spaces→`_` equals a CSV sample id and differs from the record id, rename the record to it; rewrite the FASTA if changed. |
| P0-041 | `_autofix_duplicate_fasta_ids`: drop all but the first record for each repeated id and rewrite the FASTA, logging a warning per duplicated id. |
| P0-042 | P0-040 and P0-041 MUST NOT run in the Nextflow path (`main()`), where the same inputs are rejected instead (P0-003, P0-020). The §5.1 repairs are the exception: they run in both paths. |

## 6. Errors and exit

All failures are Python exceptions (`FASTAFormatError`,
`MetadataFormatError`, `FileNotFoundError`) with an uncaught traceback;
the process exits non-zero, `VALIDATE_INPUT` fails and the run stops
(NF-ER-005). The message is intended for the submitter; it appears in the
task's `.command.err` (collected to `<outdir>/errors/VALIDATE_INPUT/`).

## 7. Defects

| ID | Defect |
|---|---|
| P0-D-001 | **Loci `atpB`, `trnL`, `AChE` can never validate.** Why: P0 lowercases the user's *input* before comparing, but never lowercases the *synonym list* it compares against, and none of the three loci's synonyms are already lower-case (`atpB`, `ATP synthase subunit B`, `trnL`, `tRNA leu`, `AChE`, `Acetylcholinesterase`). Example: a user enters `atpB` → P0 lowercases it to `atpb` → checks `atpb` against `[atpB, ATP synthase subunit B]` → no match (case-sensitive) → rejected. Entering `atpb` instead doesn't help either, since `atpb` isn't literally in that list. `Locus.__contains__` has the same asymmetry. |
| P0-D-002 | Sequences supplied via the metadata `sequence` column bypass `fasta_min_length`, `fasta_max_length` and `fasta_max_sequences`. A blank `sequence` cell passes and writes an empty FASTA record. |
| P0-D-003 | An empty FASTA passes validation with any metadata (P0-012 is skipped when the id list is empty and P0-015 compares against an empty set). |
| P0-D-004 | Duplicate `sample_id` rows in metadata are not rejected; with CSV sequences they produce duplicate FASTA ids, and `config.metadata` keeps only the last row. |
| P0-D-005 | Regex range `A-z` also admits `[ \ ] ^ _` and backtick in `sample_id`, `preliminary_id`, `taxa_of_interest`. |
| P0-D-006 | `--bold` help says it "accept[s] blank locus field", but P0-013 rejects blank locus before the BOLD exemption is reached. |
| P0-D-007 | P0-012 compares the **unstripped** `sample_id` to FASTA ids, while P0-020 validates the stripped value; a trailing space yields a confusing "not present in FASTA" error. |
| P0-D-008 — **fixed in `3339050`** | `classification` accepts 12 values here but `assets/schema_input.json` enumerated only 7, and until `3339050` that schema was applied by nf-schema to every CSV row before P0 ran. `Config.HIGHER_CLASSIFICATIONS` has 12 keys: the 7 formal names (`animalia, plantae, fungi, chromista, bacteria, archaea, viruses`) plus 5 colloquial synonyms (`animal`, `animals`, `plant`, `plants`, `virus`). So through the Nextflow-launched pipeline those 5 values were rejected before P0 saw them. `3339050` removed the `"schema"` key from the `metadata` parameter, so nf-schema no longer reads the CSV and all 12 values now reach P0 and pass. The obsolete schema artifact and its misleading documentation were subsequently removed by task 03_remove_obsolete_metadata_schema (`P0-D-015`); no JSON metadata schema constrains current CSV contents. |
| P0-D-009 | `_autofix_sample_id_spaces` logs with `logger.debug("…:", repr(x))` (print-style args) — malformed log calls. |
| P0-D-010 **(vs Design Proposal)** | The Design Proposal (§2.3 Workflow inputs) states BOLD mode is COI-only: "The BOLD database can only be used for query sequences at the COI locus. The locus is therefore not required for the BOLD workflow version." Nothing in P0 enforces a COI-specific check — `--bold` only relaxes the generic locus check (see P0-021, and the blank-locus bug P0-D-006); any locus value (not just COI) that resolves against `loci.json`, or in principle no restriction at all once P0-D-006 is fixed, is accepted in BOLD mode. [decisions.md `D-06`](../decisions.md) is open on whether to add the COI restriction or keep the current relaxed behaviour. |
| P0-D-012 | `docs/params.md`'s `taxdb` requirement list includes `taxonkit` (the binary) and `readme.txt`; the actual check (`TAXDB_EXPECT_FILES`, `P0-031`) is 9 `*.dmp`/`gc.prt` files only — it never checks for a binary or a readme. |
| P0-D-011 | A `country` cell containing the literal text `NA` is resolved to the real country **Namibia** by `pycountry.countries.lookup` (`P0-024`), not treated as missing (use a blank cell). `csv.DictReader` preserves `NA` as text. `README.md` documents this pitfall, but P0 accepts it without a warning, so a mistaken value feeds Flag 5.3. The removed JSON schema historically documented the same warning but never enforced it. [decisions.md `D-24`](../decisions.md) remains open on whether to special-case bare `NA`/`N/A` as missing. |
| P0-D-013 | **The encoding repair never rejects a file, so a wrong guess goes unnoticed.** Anything that is not valid UTF-8 is decoded as cp1252, and if that fails as latin-1, which accepts every byte (`P0-043`). A CSV saved in another legacy encoding is converted with the wrong characters and no error. Example: a Polish Excel saves `Białowieża` in Windows-1250, where `ł` is byte `0xB3` and `ż` is `0xBF`; read as cp1252 these become `³` and `¿`, so the report shows host `Bia³owie¿a`. A UTF-16 file *without* a BOM is valid UTF-8 byte-wise (ASCII plus `NUL` bytes) and is left untouched, then fails later with a confusing missing-column error. |
| P0-D-014 | **The `ß` → `beta` rename in sample ids can collide with an existing id, and the submitter is not told about it.** P0-046 renames silently: the only record is a warning in `run.log`, and the report is named after the new id. If the sheet already has the id the rename produces, two rows end up with the same id. Example: rows `VEß1` and `VEbeta1` both become `VEbeta1`. With a FASTA, P0-003 then rejects "Duplicate sequence ID VEbeta1", naming an id the submitter never typed. With sequences in the CSV, the duplicate goes through unchecked (`P0-D-004`). |
| P0-D-015 — **fixed by task 03_remove_obsolete_metadata_schema** | Historically, `assets/schema_input.json` remained in the repository and was presented as the metadata schema after `3339050` removed nf-schema CSV validation. Its seven-value classification list disagreed with P0's 12 accepted values. Task 03_remove_obsolete_metadata_schema removed the unused artifact and updated `README.md`, `docs/detailed_tech.md`, `docs/params.md`, and the input contract to identify P0 and this specification as the metadata-validation authority. Runtime validation is unchanged. |

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
| `test_it_converts_latin1_metadata_to_utf8` | P0-043, P0-044 (cp1252 source, `\r` removed) |
| `test_it_strips_utf8_bom_from_metadata` | P0-043, P0-044 |
| `test_it_converts_utf16_metadata_to_utf8` | P0-043, P0-044 |
| `test_it_leaves_utf8_metadata_untouched` | P0-044 |
| `test_it_rejects_excel_workbook_with_csv_extension` | P0-043 (ZIP signature) |
| `test_it_autofixes_eszett_locus_and_validates` | P0-045, then P0-021 accepts `β-tub` |
| `test_it_replaces_eszett_in_sample_ids_and_fasta_headers` | P0-046 |

**Not covered:** P0-027 (classification), P0-007 output content, auto-fixes
(P0-040/041), `main()` end-to-end (so the §5.1 repairs are only tested
through `_autofix_metadata_encoding` directly), every defect above. The unused fixture
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

**Initially derived from:** `p0_validation.py` (561 lines), `src/utils/config/*`, `src/utils/locus.py`, `src/utils/countries.py`, `src/utils/utils.py`, `tests/test_validation.py`. §5.1, P0-D-013..015 and the P0-D-008 fix added from `3339050` (`src/utils/encoding.py`, 120 lines). See [README.md Version](../README.md#version) for the exact commit.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
