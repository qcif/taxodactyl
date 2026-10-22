# Contract: user inputs

**Producer:** the submitter, or the validation web service
([services/input-validation.md](../services/input-validation.md)),
which returns a cleaned copy. **Consumers:** [P0](../python/p0-validation.md)
(validation, see the per-column table below); every `p0`–`p6` script
downstream, which reads values via
[`Config.metadata`](../python/shared/config.md).

## 1. `metadata.csv`

One row per query sequence. Header names are configurable
(`inputs.metadata_csv_header`); defaults below.

**One content-validation layer: P0.** `p0_validation.py`
([../python/p0-validation.md](../python/p0-validation.md)), inside the
`VALIDATE_INPUT` process, is the only code that checks what is *in* the
file — required columns, locus-panel membership, country lookup,
cross-check against the FASTA, etc. The validation web service runs the
same checks by calling `validate_inputs()` directly
([../services/input-validation.md](../services/input-validation.md)).

nf-schema (`validateParameters()`, `UTILS_NFSCHEMA_PLUGIN`, on by default
via `validate_params`) checks only the `--metadata` *parameter*: the path
must match `^\S+\.csv$` (no spaces, `.csv` extension), exist, and be a
file. Until `3339050` the parameter also carried
`"schema": "assets/schema_input.json"`, which made nf-schema parse and
validate every CSV row as UTF-8 before any process started. That crashed
the run on cp1252 files exported from Excel (#326), so it was removed;
`assets/schema_input.json` is now unused (`P0-D-015`).

| Column | Req. | Enforced by | Rule | Consumed as |
|---|---|---|---|---|
| `sample_id` | yes | P0-020 | `[A-Za-z0-9_.-]+` (P0-020 is looser than it looks: also `[ \ ] ^ _` `` ` ``); unique (not enforced, P0-D-004); equals a FASTA id. `ß` is rewritten to `beta` first (P0-046) | folder/report name; join key |
| `locus` | yes | P0-021 | a synonym in `loci.json` (case-insensitive, optional trailing ` gene`) or `NA`. `ß` is rewritten to `β` first (P0-045) | Flag 5 queries; report; `NA` disables locus filter |
| `preliminary_id` | yes | P0-022 | letters and spaces only | Flag 7; P5 target |
| `taxa_of_interest` | no | P0-023 | `\|`-separated names, letters/spaces | Flag 2; P5 targets (first 10) |
| `country` | no | P0-024 | pycountry name/alpha-2/alpha-3 | Flag 5.3 (converted to alpha-2) |
| `classification` | no | P0-027 | one of 12 keys of `HIGHER_CLASSIFICATIONS`: `animalia, plantae, fungi, chromista, bacteria, archaea, viruses` plus `animal, animals, plant, plants, virus` | taxonomy filters (P2, P5) |
| `host` | no | — (no enforcement) | free text | report only |
| `sequence` | cond. | P0-026 | IUPAC DNA; required per row if no FASTA | split into `sequences.fasta`, then dropped from metadata |
| *any other* | no | — (no enforcement) | free text | report "Sample metadata" (values injected unescaped, P6-D-002) |

**Encoding:** any encoding is accepted and converted to UTF-8 before
validation (P0-043, P0-044): UTF-8 with or without BOM, UTF-16 with BOM,
cp1252 (the Windows Excel default) and latin-1. A legacy encoding other
than cp1252 is converted with the wrong characters and no error
(`P0-D-013`). An Excel workbook (`.xlsx`) renamed to `.csv` is rejected
with a message telling the user to re-export as "CSV UTF-8". All later
readers (`Config.metadata`, P0 itself) open the file explicitly as UTF-8.

## 2. Query FASTA

| Rule | Value |
|---|---|
| ids | first header token; unique; each matches a `sample_id` and vice versa |
| alphabet | IUPAC ambiguous DNA after removing whitespace and `-`; lower case accepted |
| length | 20 ≤ n ≤ 3000 (raw length, before sanitising) |
| count | ≤ 150 |
| output | `sequences.fasta`: sanitised, upper case, header = id only, in input order; wrapped at 60 columns when written from a FASTA input (Biopython), single-line when written from the CSV `sequence` column |

## 3. Run parameters

See [../nextflow/params.md](../nextflow/params.md).

---

## Provenance

**Initially derived from:** `assets/schema_input.json`, `nextflow_schema.json`, [p0-validation.md](../python/p0-validation.md) §4, [services/input-validation.md](../services/input-validation.md) — each already derived from source. §1 rewritten for `3339050` (nf-schema no longer reads the CSV; encoding repair). See [README.md Version](../README.md#version) for the exact commit.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
