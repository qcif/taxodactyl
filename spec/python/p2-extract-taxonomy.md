# Spec: P2 taxonomy extraction (`scripts/p2_extract_taxonomy.py`) and `src/taxonomy/extract.py`

**Called by:** Nextflow `EXTRACT_TAXONOMY` (BLAST mode, once per run).
`extract.taxids()` is also used by P5 (database coverage).
**External tool:** `taxonkit` on `PATH` + taxdump in `config.taxdb_dir`
(`TAXONKIT_DATA`).

## 1. Purpose

Map every BLAST hit accession to a taxid (done upstream by `blastdbcmd`)
and then to a fixed set of ranks, producing `taxonomy.csv`, the lineage
table P3 and P6 join hits against.

## 2. P2 entrypoint

| Arg | Required |
|---|---|
| `taxids_csv` (positional) | yes — lines `accession,taxid`, no header (`blastdbcmd -outfmt "%a,%T"`) |
| `--query-fasta`, `--metadata-csv` | yes (config only) |
| `--output-dir` | no; must exist |

Output: `<out>/taxonomy.csv` with header
`accession,taxid,domain,superkingdom,kingdom,phylum,class,order,family,genus,species`.

| ID | Requirement |
|---|---|
| P2-001 | Read `taxids_csv` into `accession → taxid`; a repeated accession keeps the last taxid. |
| P2-002 | Query taxonkit once with the sorted distinct taxids (§3.1). |
| P2-003 | Write one row per input accession **whose taxid is a key of the taxonkit result**; others are omitted without warning (see P2-D-001). |
| P2-004 | `accession` in the output MUST be the input accession truncated at the first `.` (drops the version so it joins with P1's version-less accessions). |
| P2-005 | Rank columns MUST contain the lineage name at that rank, or empty if the lineage has no such rank. Only the 9 ranks listed are kept. |
| P2-006 | A taxonkit non-zero exit MUST raise (run fails — P2-D-002). Non-empty taxonkit stderr is logged as a warning. |

## 3. Library: `src/taxonomy/extract.py`

### 3.1 `taxonomies(taxids) -> {taxid: {rank: name}}`

| ID | Requirement |
|---|---|
| P2-010 | Write taxids to a temp file, run `taxonkit lineage -R -c <file> --data-dir <taxdb_dir>`, delete the temp file. |
| P2-011 | Parse each output line split on tab: with 4 fields drop the first (input taxid); with 3 fields use `(taxid, lineage, ranks)`; any other shape is skipped and a single warning with the full stdout is logged. |
| P2-012 | Lineage names and ranks are paired positionally (`;`-separated); the result is keyed by the **second** column of taxonkit output. |

### 3.2 `taxids(names, classification=None) -> {name: taxid | None}` (used by P5)

| ID | Requirement |
|---|---|
| P2-020 | Run `taxonkit name2taxid <file> --data-dir <taxdb_dir>`; each non-blank line is `name[\ttaxid]`. Names with no taxid are returned with `None`. |
| P2-021 | If `classification` is given (a `HIGHER_CLASSIFICATIONS` entry, CFG-029), run one `taxonkit lineage -R` over all returned taxids and keep only results whose lineage contains the pair (rank == `ncbi.rank`, name == `ncbi.taxon`, case-insensitive). Names without a taxid are always kept. |
| P2-022 | If the classification matches none of the taxids, all taxid-bearing results are dropped and a warning lists the ranks observed. |
| P2-023 | If the classification lineage call fails, results MUST be returned unfiltered (logged as an error, not raised). |
| P2-024 | If one name maps to several taxids after filtering, the **first** is used, and an HTML error message with links to each taxid MUST be written to `errors` location `DB_COVERAGE_TAXONKIT_ERROR` for the current query dir with context `{'target': name}`. |
| P2-025 | All taxonkit invocations in a process MUST be serialised (module-level semaphore of 1). |

## 4. Defects

| ID | Severity | Defect |
|---|---|---|
| P2-D-001 | High | Result keyed by taxonkit's second column; for a merged taxid that is the new id (status column of `-c`), so P2-003's lookup by the original taxid misses and the accession disappears from `taxonomy.csv`. Deleted taxids behave likewise. *To confirm* with a merged-id fixture. Downstream effect on P3 of a hit with no taxonomy row: see p3 spec. |
| P2-D-002 | Medium | A taxonkit failure aborts P2 and therefore all queries. |
| — | Low | Log messages in `taxonomies()` say "name2taxid" for a `lineage` call. |

## 5. Test mapping (`tests/test_taxonkit.py`)

`test_it_can_extract_taxonomic_data_for_accessions` (P2-010..012 with the
fixture), `test_taxids_with_classification_filter` (P2-021),
`test_main` (P2-001..005). **Not covered:** merged/deleted taxids,
P2-022..025, malformed stdout.

---

## Provenance

**Initially derived from:** `p2_extract_taxonomy.py` (88), `src/taxonomy/extract.py` (352), `tests/test_taxonkit.py`, `tests/test-data/taxonkit.stdout`. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
