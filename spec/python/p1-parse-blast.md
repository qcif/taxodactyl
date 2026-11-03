# Spec: P1 BLAST parser (`scripts/p1_parse_blast.py`)

**Called by:** Nextflow `EXTRACT_HITS` (BLAST mode only; once per run).
**Depends on:** [shared/config.md](shared/config.md).

## 1. Purpose

Turn one BLAST XML file (all queries) into per-query hit files the rest of
the pipeline reads, compute hit-level statistics that BLAST does not give,
preserve every parsed hit in internal `all_xml_hits.json`, then select context
blocks and list only retained hit accessions for taxid lookup. This is where the query
folders `query_NNN_<sample_id>` are **created**.

## 2. Interface

| Arg | Required | Notes |
|---|---|---|
| `blast_xml_path` (positional) | yes | must exist; BLAST `-outfmt 5` |
| `--query-fasta` | yes | defines query order and sample ids |
| `--metadata-csv` | yes | loaded into config; not otherwise used by P1 |
| `--output-dir` | no | default `config.output_dir` |
| `--blast-max-target-seqs` | no | positive integer cap on retained hits per query (default 2000) |
| `--blast-context-min-identity` | no | finite fraction 0–1, default 0.935; independent of candidate eligibility |

Outputs (names from [shared/config.md §3.5](shared/config.md)):

| File | Content |
|---|---|
| `<out>/accessions.txt` | unique retained hit accessions, one per line, unordered, trailing newline |
| `<out>/query_NNN_<id>/query_title.txt` | BLAST query definition line |
| `<out>/query_NNN_<id>/all_xml_hits.json` | §3 schema, every XML hit; internal only |
| `<out>/query_NNN_<id>/all_hits.json` | §3 schema, only block-selected hits; published |
| `<out>/query_NNN_<id>/all_hits.fasta` | one record per selected hit; empty file for zero hits; published |

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

P3 and P6 consume only `all_hits.json`; see [hits contract](../contracts/hits.md).
`all_xml_hits.json` uses the same schema but includes every XML hit. It is
written before selection, never staged downstream or published, and has no
FASTA counterpart. Filenames are working names and remain open to discussion.

## 4. Requirements

| ID | Requirement |
|---|---|
| P1-001 | The *i*-th BLAST iteration (0-based) MUST be written to the query folder of the *i*-th record of `--query-fasta` (CFG-024). No id check is made between the two (P1-D-002). |
| P1-002 | Every iteration MUST produce a query folder, `query_title.txt`, `all_xml_hits.json` and `all_hits.json`, even with zero hits (empty `hits`). |
| P1-003 | `all_hits.fasta` MUST contain only selected sequences and MUST be empty for zero hits. No complete-extraction FASTA is written. Nextflow retains its empty-file fallback (NF-PR-050). |
| P1-004 | `hit_subject` MUST be the hit definition truncated at the first `>` (drops merged "redundant" definitions) and stripped. |
| P1-005 | Hit **bitscore** = Σ HSP bits. |
| P1-006 | Hit **e-value** = the HSP e-value if exactly one HSP, else `effective_search_space · 2^(−Σ bits)`. |
| P1-007 | Hit **identity** = round(Σ HSP identities / Σ HSP align_length, 3), capped at 1; 0 if total align length is 0. Align length includes gaps. |
| P1-008 | Hit **alignment_length** = number of query positions covered by the union of HSP query intervals (overlaps merged, both strands normalised to start ≤ end, inclusive). |
| P1-009 | Hit **query_coverage** = min(round(alignment_length / query_length, 3), 1); 0 if query length is 0. |
| P1-010 | HSP `identity` = round(identities / align_length, 3). |
| P1-011 | Hits MUST be sorted by `identity` descending (stable: ties keep BLAST order). HSPs keep BLAST order. |
| P1-012 | `all_hits.fasta` records: id = accession (no version), description = `hit_subject`, sequence = the **aligned subject string of the last HSP** of the hit (P1-D-001). Only retained hits, in relative BLAST order, not identity order; associate by original hit position, including repeated accessions. |
| P1-013 | `accessions.txt` MUST contain each distinct retained hit accession across all queries once. |
| P1-014 | Printable alignment: 80-column blocks, 10-char groups, `Query`/`Sbjct` lines with start coordinates and the midline between. Display only. |
| P1-015 | After stable aggregate-identity sorting, retain blocks of up to 500 until the last retained identity is ≤ `blast_context_min_identity` or available hits / `blast_max_target_seqs` are exhausted. Retain the entire stopping block, even below threshold. The first block is always retained if hits exist. |
| P1-016 | Cap the selected set from replay XML after sorting too, without truncating `all_xml_hits.json`; allow partial blocks and caps below 500. Preserve all retained HSP evidence and matching FASTA records. Log retrieved/retained counts, minimum retained identity and stopping reason per query. |
| P1-017 | Parse every XML hit independently of selection settings, write `all_xml_hits.json`, then select in a separate operation within P1 without modifying the complete records. The internal JSON must be invariant under cap/threshold changes on identical XML. No decision file or second accession list is produced. |

## 5. Failure behaviour

Unreadable/invalid XML raises and fails `EXTRACT_HITS`, which fails the run
(NF-ER-005). If the XML has more iterations than FASTA records,
`IndexError` is raised when resolving the sample id (a positional list
index into the parsed FASTA, `read_query_fasta`). If the XML has **fewer**
iterations than FASTA records, the opposite happens: the parsing loop
(`enumerate(blast_records)`) simply ends early, and every FASTA record
past that point is never visited by this function at all — no error, no
query folder, nothing (`P1-D-004`).

## 6. Defects

| ID | Severity | Defect |
|---|---|---|
| P1-D-001 | High | `all_hits.fasta` holds the last HSP's aligned subject fragment (with `-` gaps; other HSPs dropped), not the subject sequence. It is the source for candidate FASTA, phylogeny sampling and MAFFT input. |
| P1-D-002 | Medium | Iteration→query mapping is positional with no check against the query id in the XML. The fix is cheap: `create_query_dir` already receives the XML's `query_title` (the real `query-def` for that iteration) and writes it to `query_title.txt` — it just never compares it against `read_query_fasta(i).id`, the FASTA record actually selected by position. A mismatch (e.g. a stale/mock XML run against a different FASTA) produces no error, just silently mislabeled results. |
| P1-D-003 | Medium | Zero hits across all queries ⇒ `accessions.txt` is `"\n"`; `blastdbcmd` behaviour on a blank entry is untested. |
| P1-D-004 | Medium | If the BLAST XML has **fewer** iterations than the submitted FASTA has records (the reverse of P1-D-002's over-count `IndexError`), the parsing loop simply ends early: every FASTA record past that point gets no query folder, no `all_hits.json`, nothing — not even a log line, let alone a run failure. No count check exists between `len(blast_records)` and `len(query_fasta)` in either direction; only the over-count case happens to crash. |

Invalid caps (zero, negative, fractional) and non-finite/out-of-range context
thresholds fail configuration/CLI parsing rather than silently using defaults.

## 7. Test mapping (`tests/test_blast_parser.py`)

P1-005 (`test_calculate_hit_bitscore`), P1-006 (single and multiple
e-value), P1-007, P1-009, P1-008 (incl. overlap), `test_parse_blast_xml`
(P1-002/011 structure). `test_blast_context.py` covers P1-012/015/016,
rounding, ties, repeated accessions, multi-HSP aggregate stopping, empty queries
and invalid/non-default configuration. Its P1 entrypoint regression covers
P1-003/013/017: complete JSON is written before selection and remains invariant,
only selected FASTA/accessions are written, duplicate accessions preserve
sequence associations, and empty queries produce empty selected FASTA.
**Not covered:** P1-001 positional query-ID validation.

---

## Provenance

**Initially derived from:** `p1_parse_blast.py` (103), `src/blast/parse_xml.py` (195), `tests/test_blast_parser.py`. See [README.md Version](../README.md#version) for the exact commit.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
