# Contract: user inputs

**Producer:** the submitter, or the validation web service
([services/input-validation.md](../services/input-validation.md)),
which returns a cleaned copy. **Consumers:** nf-schema and
[P0](../python/p0-validation.md) (validation, see the per-column table
below); every `p0`–`p6` script downstream, which reads values via
[`Config.metadata`](../python/shared/config.md).

## 1. `metadata.csv`

One row per query sequence. Header names are configurable
(`inputs.metadata_csv_header`); defaults below.

**Two independent enforcement layers**, run in this order:

1. **nf-schema** (`validateParameters()`, `UTILS_NFSCHEMA_PLUGIN`, runs
   whenever `validate_params` is true — the default). `nextflow_schema.json`'s
   `metadata` parameter carries `"schema": "assets/schema_input.json"`;
   nf-schema reads that secondary schema and validates every CSV row
   against it **before any process starts** — independent of
   `samplesheetToList`/`fromSamplesheet`, which this pipeline imports but
   never calls. *Behaviour of this file-content validation is inferred
   from documented nf-schema conventions, not confirmed by running it
   here.*
2. **P0** (`p0_validation.py`, [../python/p0-validation.md](../python/p0-validation.md)),
   inside the `VALIDATE_INPUT` process — the deeper, semantic checks
   (locus-panel membership, country lookup, cross-check against the
   FASTA, etc.). This is the **only** layer the validation web service
   exercises ([../services/input-validation.md](../services/input-validation.md)) — it calls
   `validate_inputs()` directly and never goes through nf-schema.

`assets/schema_input.json` constrains far less than P0 does: only
`sample_id` (no-whitespace pattern), `required` columns, and
`classification` (a 7-value enum) have any constraint at the nf-schema
layer; `locus`, `preliminary_id`, `taxa_of_interest`, `country`,
`sequence` are typed as `string` with no further constraint there, so for
those five columns P0 is the only enforcement that exists.

| Column | Req. | Enforced by | Rule | Consumed as |
|---|---|---|---|---|
| `sample_id` | yes | nf-schema (`^\S+$`, no spaces) **and** P0-020 (stricter) | `[A-Za-z0-9_.-]+` (P0-020 is looser than it looks: also `[ \ ] ^ _` `` ` ``); unique (not enforced, P0-D-004); equals a FASTA id | folder/report name; join key |
| `locus` | yes | P0-021 only (nf-schema: `string`, unconstrained) | a synonym in `loci.json` (case-insensitive, optional trailing ` gene`) or `NA` | Flag 5 queries; report; `NA` disables locus filter |
| `preliminary_id` | yes | P0-022 only (nf-schema: `string`, unconstrained) | letters and spaces only | Flag 7; P5 target |
| `taxa_of_interest` | no | P0-023 only (nf-schema: `string`, unconstrained) | `\|`-separated names, letters/spaces | Flag 2; P5 targets (first 10) |
| `country` | no | P0-024 only (nf-schema: `string`, unconstrained) | pycountry name/alpha-2/alpha-3 | Flag 5.3 (converted to alpha-2) |
| `classification` | no | **both, and they disagree** — nf-schema enum (7 values) runs first | nf-schema accepts `animalia, plantae, fungi, chromista, bacteria, archaea, viruses` only; P0 additionally accepts `animal, animals, plant, plants, virus` (12 total, `HIGHER_CLASSIFICATIONS`) | taxonomy filters (P2, P5) |
| `host` | no | — (no enforcement) | free text | report only |
| `sequence` | cond. | P0-026 only (nf-schema: `string`, unconstrained) | IUPAC DNA; required per row if no FASTA | split into `sequences.fasta`, then dropped from metadata |
| *any other* | no | — (no enforcement) | free text | report "Sample metadata" (values injected unescaped, P6-D-002) |

**Consequence (see P0-D-008):** if nf-schema's file-content validation
behaves as documented, the five extra `classification` values P0 accepts
(`animal`, `animals`, `plant`, `plants`, `virus`) can **never reach P0**
through the Nextflow-launched pipeline — nf-schema's enum rejects the row
first. Those P0 code paths are reachable only via the validation web
service or a direct `p0_validation.py` invocation, both of which bypass
nf-schema entirely.

Encoding: read with the platform default encoding by `csv.DictReader`
(UTF-8 assumed); a UTF-8 BOM would corrupt the first header name (untested).

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

**Initially derived from:** `assets/schema_input.json`, `nextflow_schema.json`, [p0-validation.md](../python/p0-validation.md) §4, [services/input-validation.md](../services/input-validation.md) — each already derived from source, v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
