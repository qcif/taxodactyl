# Spec: P1 BLAST parser (`scripts/p1_parse_blast.py`)

**Called by:** Nextflow `EXTRACT_HITS` (BLAST mode only; once per run).
**Depends on:** [shared/config.md](shared/config.md).

## 1. Purpose

Turn one BLAST XML file (all queries) into per-query hit files the rest of
the pipeline reads, compute hit-level statistics that BLAST does not give,
and list all hit accessions for taxid lookup. This is where the query
folders `query_NNN_<sample_id>` are **created**.

## 2. Interface

| Arg | Required | Notes |
|---|---|---|
| `blast_xml_path` (positional) | yes | must exist; BLAST `-outfmt 5` |
| `--query-fasta` | yes | defines query order and sample ids |
| `--metadata-csv` | yes | loaded into config; not otherwise used by P1 |
| `--output-dir` | no | default `config.output_dir` |
| `--blast-max-target-seqs` | no | stored in config for the report; **does not affect parsing** |

Outputs (names from [shared/config.md §3.5](shared/config.md)):

| File | Content |
|---|---|
| `<out>/accessions.txt` | unique hit accessions, one per line, unordered, trailing newline |
| `<out>/query_NNN_<id>/query_title.txt` | BLAST query definition line |
| `<out>/query_NNN_<id>/all_hits.json` | §3 schema |
| `<out>/query_NNN_<id>/all_hits.fasta` | one record per hit (only if the query has ≥1 hit) |

## 3. `all_hits.json` schema

```json
{
  "query_title": "<BLAST query def>",
  "query_length": <int>,
  "hits": [
    {
      "hit_id": "<BLAST hit id>",
      "hit_subject": "<hit def before first '>'>",
      "accession": "<accession without version>",
      "alignment_length": <int>,
      "subject_length": <int>,
      "query_coverage": <float 0..1, 3 dp>,
      "bitscore": <float>,
      "e_value": <float>,
      "identity": <float 0..1, 3 dp>,
      "hsps": [
        {"bitscore", "e_value", "identity", "identities", "strand_query",
         "strand_subject", "gaps", "query_start", "query_end",
         "subject_start", "subject_end", "alignment_length",
         "alignment": "<printable 80-col alignment>"}
      ]
    }
  ]
}
```

This is the contract P3 consumes; see `../contracts/hits.md` (to write).

## 4. Requirements

| ID | Requirement |
|---|---|
| P1-001 | The *i*-th BLAST iteration (0-based) MUST be written to the query folder of the *i*-th record of `--query-fasta` (CFG-024). No id check is made between the two (P1-D-002). |
| P1-002 | Every iteration MUST produce a query folder, `query_title.txt` and `all_hits.json`, even with zero hits (empty `hits`). |
| P1-003 | `all_hits.fasta` MUST be written only when the query has ≥1 hit. (Nextflow then creates an empty one — NF-PR-050.) |
| P1-004 | `hit_subject` MUST be the hit definition truncated at the first `>` (drops merged "redundant" definitions) and stripped. |
| P1-005 | Hit **bitscore** = Σ HSP bits. |
| P1-006 | Hit **e-value** = the HSP e-value if exactly one HSP, else `effective_search_space · 2^(−Σ bits)`. |
| P1-007 | Hit **identity** = round(Σ HSP identities / Σ HSP align_length, 3), capped at 1; 0 if total align length is 0. Align length includes gaps. |
| P1-008 | Hit **alignment_length** = number of query positions covered by the union of HSP query intervals (overlaps merged, both strands normalised to start ≤ end, inclusive). |
| P1-009 | Hit **query_coverage** = min(round(alignment_length / query_length, 3), 1); 0 if query length is 0. |
| P1-010 | HSP `identity` = round(identities / align_length, 3). |
| P1-011 | Hits MUST be sorted by `identity` descending (stable: ties keep BLAST order). HSPs keep BLAST order. |
| P1-012 | `all_hits.fasta` records: id = accession (no version), description = `hit_subject`, sequence = the **aligned subject string of the last HSP** of the hit (P1-D-001). Order = BLAST order, not identity order. |
| P1-013 | `accessions.txt` MUST contain each distinct hit accession across all queries once. |
| P1-014 | Printable alignment: 80-column blocks, 10-char groups, `Query`/`Sbjct` lines with start coordinates and the midline between. Display only. |

## 5. Failure behaviour

Unreadable/invalid XML raises and fails `EXTRACT_HITS`, which fails the run
(NF-ER-005). If the XML has more iterations than FASTA records,
`IndexError` is raised when resolving the sample id.

## 6. Defects

| ID | Severity | Defect |
|---|---|---|
| P1-D-001 | High | `all_hits.fasta` holds the last HSP's aligned subject fragment (with `-` gaps; other HSPs dropped), not the subject sequence. It is the source for candidate FASTA, phylogeny sampling and MAFFT input. |
| P1-D-002 | Medium | Iteration→query mapping is positional with no check against the query id in the XML. |
| P1-D-003 | Medium | Zero hits across all queries ⇒ `accessions.txt` is `"\n"`; `blastdbcmd` behaviour on a blank entry is untested. |

## 7. Test mapping (`tests/test_blast_parser.py`)

P1-005 (`test_calculate_hit_bitscore`), P1-006 (single and multiple
e-value), P1-007, P1-009, P1-008 (incl. overlap), `test_parse_blast_xml`
(P1-002/011 structure). **Not covered:** P1-001, P1-003, P1-012 (FASTA
content), P1-013, `main()`.

---

## Provenance

**Initially derived from:** `p1_parse_blast.py` (103), `src/blast/parse_xml.py` (195), `tests/test_blast_parser.py`. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
