# Task 03 — Remove the obsolete metadata schema documentation

**Status:** active

**Priority:** P1

**Issue:** [#334 — `assets/schema_input.json` is no longer used but README and docs still present it as the metadata schema](https://github.com/qcif/taxodactyl/issues/334)

**Scope:** Remove the unused and misleading JSON metadata schema and make the
documentation point to the actual P0 validation behavior. This is a
documentation/specification correction; it must not reintroduce nf-schema CSV
validation through `nextflow_schema.json`.

**Source material:** Issue #334, `scripts/p0_validation.py`,
`spec/python/p0-validation.md`, `README.md`, `docs/detailed_tech.md`, and
`docs/params.md`.

## Preconditions

- `nextflow_schema.json` must remain the schema for Nextflow parameters, not
  the metadata CSV contents.
- `scripts/p0_validation.py` remains the runtime authority for metadata and
  FASTA validation.
- The P0 specification in `spec/python/p0-validation.md` remains aligned with
  the validator implementation.

## Objective

Users must not be directed to `assets/schema_input.json` as the metadata
contract. The repository must have one clear authority for metadata validation:
the P0 validator and its corresponding specification. Documentation must
reflect the actual accepted values and rules, including all 12 accepted
classification values:

`animalia`, `animal`, `animals`, `plantae`, `plant`, `plants`, `fungi`,
`chromista`, `bacteria`, `archaea`, `viruses`, and `virus`.

## Implementation

1. Delete `assets/schema_input.json`, after confirming with repository-wide
   search that no runtime code or test requires it.
2. Update `README.md` to remove the link claiming that file is the metadata
   schema. Replace it with a link to the relevant metadata-validation
   documentation and/or `scripts/p0_validation.py`.
3. Update `docs/detailed_tech.md` to remove the obsolete
   `schema_input.json` section. Replace it with a description of P0 metadata
   validation that links to `scripts/p0_validation.py` and
   `spec/python/p0-validation.md`.
4. Update `README.md` and `docs/params.md` so their metadata rules do not
   present the old seven-value classification list as exhaustive; document
   the 12 values accepted by `Config.HIGHER_CLASSIFICATIONS`.
5. Update `spec/python/p0-validation.md` as needed so the issue resolution,
   obsolete-file removal, and documentation authority are recorded without
   claiming that a JSON metadata schema is applied.
6. Update `spec/contracts/inputs.md` so its validation-layer description and
   provenance no longer treat `assets/schema_input.json` as a current source;
   retain a concise historical note about the `3339050` change only if it is
   needed to explain why nf-schema no longer validates CSV rows.
7. Update the related historical entries in `spec/defects.md`, especially
   `P0-D-008`, `P0-D-011`, and `P0-D-015`, so they clearly distinguish the
   resolved historical schema mismatch from the current P0 authority and do
   not present the deleted file as live documentation.
8. Correct the classification-discrepancy wording in `P0-D-008` in both
   `spec/defects.md` and `spec/python/p0-validation.md`: preserve that the
   mismatch existed before `3339050`, but state that the nf-schema CSV schema
   was removed in `3339050` and the obsolete artifact is removed by this task.
   Do not leave wording that implies the seven-value schema still constrains
   Python validation or current Nextflow runs.

## Validation

- Run `rg -n "schema_input\\.json|metadata schema" README.md docs spec assets
  scripts nextflow_schema.json` and confirm no stale authoritative references
  remain. Any remaining references in `spec/contracts/inputs.md`,
  `spec/defects.md`, or `spec/python/p0-validation.md` must be explicitly
  historical and describe the resolved issue rather than direct users to the
  file.
- Confirm `assets/schema_input.json` no longer exists.
- Run the existing metadata validation tests in
  `scripts/tests/test_validation.py`.
- Confirm `nextflow_schema.json` still validates pipeline parameters and does
  not regain a `schema` property for the `metadata` parameter.
- Confirm the documented classification list matches
  `Config.HIGHER_CLASSIFICATIONS` in the implementation.

## Completion criteria

- The obsolete JSON file is removed.
- README and technical documentation identify P0 as the metadata-validation
  authority.
- Input contracts and defect/spec records distinguish historical
  `schema_input.json` usage from the current validation path.
- The classification discrepancy is recorded only as resolved history; no
  current specification implies that Python accepts one list while a live
  `schema_input.json` enforces another.
- User-facing metadata documentation reflects the actual accepted
  classification values and does not describe the removed JSON file as live.
- The P0 validation test suite passes.
- The task can then be moved to `tasks/completed/`.

## Risks and decisions

- Do not regenerate `assets/schema_input.json` unless a separate decision
  establishes that a documentation-only schema is required; the issue’s
  proposed resolution is to remove it and point readers to P0.
- Preserve the historical defect entry in
  `spec/python/p0-validation.md` if it is useful for provenance, but mark the
  obsolete-schema condition as resolved after the documentation change.
