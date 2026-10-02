# Spec: P3 candidate selection and taxonomic assignment (`scripts/p3_assign_taxonomy.py`)

**Derived from:** `p3_assign_taxonomy.py` (687), `src/utils/flags.py`
(`Flag.write`), `src/utils/ncbi.py`, `src/utils/utils.py` (`deduplicate`),
`tests/test_phylogeny_sampling.py`, `config/flags.csv`. v1.5.0.
**Called by:** Nextflow `EXTRACT_CANDIDATES`, once per query folder.
**Depends on:** [shared/config.md](shared/config.md), P1/P2 outputs
([p1-parse-blast.md](p1-parse-blast.md), [p2-extract-taxonomy.md](p2-extract-taxonomy.md)),
or BOLD equivalents.

This module makes the core scientific decisions of the pipeline: which
hits count, which species are candidates, whether a species-level
identification is made (Flag 1), whether the preliminary ID is supported
(Flag 7), whether taxa of interest are present (Flag 2), and which
sequences go into the tree.

---

## 1. Interface

| Arg | Required | Maps to |
|---|---|---|
| `query_dir` (positional) | yes; must exist | `config.query_dir` |
| `--query-fasta`, `--metadata-csv` | yes | config |
| `--output-dir` | no; must exist | config |
| `--bold` | no | BOLD mode (hit schema differs, §3.2) |
| `--min-alignment-length` | no | `criteria.alignment_min_nt` (300) |
| `--min-query-coverage` | no | `criteria.alignment_min_q_coverage` (0.85) |
| `--min-identity` | no | `criteria.alignment_min_identity` (0.935) |
| `--min-identity-strict` | no | `criteria.alignment_min_identity_strict` (0.985) |
| `--median-identity-warning-factor` | no | 0.95 |
| `--max-candidates-analysis` | no | `criteria.max_candidates_for_analysis` (3) |
| `--phylogeny-min-hit-identity` | no | 0.935 — **never passed by Nextflow** (NF-D-004) |
| `--phylogeny-min-seqs` / `-max-seqs` / `-species-max-seqs` / `-candidate-max-seqs` | no | 20 / 50 / 3 / 5 |

**Reads** (in `query_dir` unless noted): `all_hits.json`, `all_hits.fasta`,
`<output_dir>/taxonomy.csv` (BLAST mode), metadata via config.

**Writes** (all in `query_dir`):

| File | Always | Content |
|---|---|---|
| `1.flag` | yes | Flag 1 (§5) |
| `2.flag` | yes | Flag 2 (§8) |
| `7.flag` | yes | Flag 7 (§7) |
| `candidates.json` | yes | §6.1 |
| `candidates.csv` | yes | §6.2 |
| `candidates.fasta` | yes (may be empty) | §6.3 |
| `candidates_phylogeny.fasta` | yes (may be empty) | §9 |
| `candidates_count.txt` | yes | number of selected species (§4) |
| `taxa_of_concern_detected.csv` | iff TOIs given | §8 |
| `assigned_taxonomy.csv` | iff exactly 1 strict species | copy of `candidates.csv` |
| `preliminary_id_match.csv` | iff PMI matched | §7 |
| `candidates_identity_boxplot.png` | iff selected species > `max_candidates_for_analysis` | §6.4 |

## 2. Terms

| Term | Definition |
|---|---|
| **identity** | hit identity from P1 (BLAST) or BOLD `similarity` copied into `identity` |
| **filtered hit** | a hit kept by §3 |
| **moderate threshold** | `alignment_min_identity` (0.935) |
| **strict threshold** | `alignment_min_identity_strict` (0.985) |
| **candidate hit** | filtered hit with identity ≥ moderate threshold |
| **strict candidate hit** | candidate hit with identity ≥ strict threshold |
| **candidate species** | distinct non-empty `species` values among candidate hits; represented by the first (highest-identity) hit of that species |
| **selected species** | strict candidate species if any, else candidate species |
| **selected-species hits** | *all filtered hits* whose species is a selected species (not only candidate hits) |

## 3. Hit filtering

### 3.1 BLAST mode

| ID | Requirement |
|---|---|
| P3-001 | A hit is kept iff `alignment_length ≥ alignment_min_nt` **or** `query_coverage ≥ alignment_min_q_coverage` (i.e. excluded only when below both). |
| P3-002 | Each kept hit MUST be joined to `taxonomy.csv` by `accession` (version-less). On a match: `taxonomy` = the CSV row (including `accession`, `taxid` keys), `species` = row species, `taxid`, `ncbi_blast_url`. On no match: `taxonomy`, `species`, `taxid` = `None`, warning logged. |
| P3-003 | A hit without taxonomy MUST NOT form or join a candidate species (it is excluded by species de-duplication) but still counts in hit-level statistics (§6.1 `hit_counts`). |
| P3-004 | `ncbi_blast_url` = NCBI BLAST web URL restricting the search to `"<species> (taxid:<taxid>)"` with the full query sequence embedded in `QUERY=`; `None` if species or taxid missing. |

### 3.2 BOLD mode

| ID | Requirement |
|---|---|
| P3-010 | No length/coverage filter: all hits are filtered hits. Thresholds apply to `similarity`. |
| P3-011 | Hits already carry `species`, `taxonomy`, `accession`, `identity` (= similarity) from P1-BOLD; taxonomy.csv is not read. |
| P3-012 | Output CSV uses the BOLD header (§6.2); FASTA ids use `hit_id`, not accession. |

## 4. Candidate and selected species

| ID | Requirement |
|---|---|
| P3-020 | Candidate species and strict candidate species MUST be de-duplicated by exact (case-sensitive) `species` string, keeping the first hit in hit order (identity-descending from P1). |
| P3-021 | Each candidate species record MUST get `hit_count` = number of **filtered** hits with the same species. |
| P3-022 | Selected species = strict candidate species if non-empty, else candidate species. Moderate-only species are therefore **not** reported when any strict species exists. |
| P3-023 | Each selected-species hit MUST get `is_candidate_hit` = whether its `hit_id` is among the selected-stringency candidate hits. |
| P3-024 | For each selected species: `min_identity` = minimum identity over its selected-species hits; `median_identity` = element `n//2` of the ascending-sorted identities (upper median for even `n`); `median_bs_class` per §4.1. |
| P3-025 | `candidates_count.txt` MUST contain `len(selected species)` as a bare integer. Nextflow gates P4 on it (NF-WF-051). |

### 4.1 Median identity class

Threshold T = strict threshold if that species' top identity ≥ strict,
else moderate threshold.

| Condition | Class |
|---|---|
| median ≥ T | `success` |
| median ≥ T × `median_identity_warning_factor` | `warning` |
| otherwise | `danger` |

## 5. Flag 1 — candidate selection

Based on the number `s` of strict candidate species and `m` of candidate
species:

| Condition | Value | `flags.csv` level |
|---|---|---|
| `s == 1` | `1A` — positive species identification | 1 |
| `2 ≤ s ≤ 3` | `1B` | 2 |
| `s ≥ 4` | `1C` | 3 |
| `s == 0` and `m ≥ 1` | `1D` — moderate match only | 2 |
| `s == 0` and `m == 0` | `1E` — no candidate | 3 |

| ID | Requirement |
|---|---|
| P3-030 | Flag 1 MUST follow the table. The B/C boundary is the literal 4 (not `max_candidates_for_analysis`); see P3-D-004. |
| P3-031 | When `s == 1`, `assigned_taxonomy.csv` MUST be written as a byte copy of `candidates.csv` (which then lists all filtered hits of that one species). |

## 6. Candidate outputs

### 6.1 `candidates.json`

```json
{
  "hits":    [ <selected-species hits, P1 hit schema + taxonomy/species/taxid/ncbi_blast_url/is_candidate_hit> ],
  "species": [ <one hit per selected species + hit_count/min_identity/median_identity/median_bs_class> ],
  "hit_counts": {
    "strong":   {"hits": n, "species": n},   // strict candidate hits
    "moderate": {"hits": n, "species": n},   // candidate hits below strict
    "filtered": {"hits": n, "species": n}    // filtered hits below moderate ("NO MATCH")
  }
}
```

| ID | Requirement |
|---|---|
| P3-040 | `hit_counts.*.species` MUST count distinct species case-insensitively, ignoring hits without species. Note the key `filtered` means *no-match* filtered hits, not all filtered hits. |

### 6.2 `candidates.csv`

| ID | Requirement |
|---|---|
| P3-041 | One row per selected-species hit. BLAST header: `species,taxid,accession,hit_subject,identity,query_coverage,alignment_length,e_value,bitscore`. BOLD header: `species,hit_id,accession,sequence_description,similarity,bin_uri,url`. Missing keys → empty cell. Identity is a fraction (0–1). |

### 6.3 `candidates.fasta`

| ID | Requirement |
|---|---|
| P3-042 | Records of `all_hits.fasta` whose id is the accession (BLAST) / `hit_id` (BOLD) of any selected-species hit, in `all_hits.fasta` order. Sequence content inherits P1-D-001. |

### 6.4 Identity boxplot

| ID | Requirement |
|---|---|
| P3-043 | When `len(selected species) > max_candidates_for_analysis`, write a PNG (12×3 in, 150 dpi) of identity × 100 over selected-species hits, **grouped by genus** (first word of species; `No genus` if none), x-labels rotated when > 5 genera. |

## 7. Flag 7 — preliminary ID confirmation

| ID | Requirement |
|---|---|
| P3-050 | Only when Flag 1 is `A` (exactly one strict species): compare the PMI (case-insensitive, exact string) against every value in that species' taxonomy row. Any equality ⇒ `7A`; else `7B`. |
| P3-051 | Otherwise write `7NA`. |
| P3-052 | On `7A`, write `preliminary_id_match.csv` with the first matching `(rank, taxon)`. |

The PMI is never compared against moderate-only or multiple candidates.
Homonyms across kingdoms can produce false `7A` (documented limitation).

## 8. Flag 2 — taxa of interest

| ID | Requirement |
|---|---|
| P3-060 | If the query has no TOIs, write `2NA` and no CSV. |
| P3-061 | Otherwise write `taxa_of_concern_detected.csv` with header `Taxon of interest,Match rank,Match taxon,Match species,Match accession,Match identity` and one row per TOI, in metadata order. |
| P3-062 | A TOI is detected iff it equals (case-insensitive, exact) any value in the taxonomy row of any **selected** species; the first such (species order, then taxonomy column order) is reported. Unmatched TOIs get a row with empty match columns. |
| P3-063 | Flag 2 MUST be `2A` if at least one TOI is detected, else `2B`. (Implemented by re-writing `2.flag` per TOI until the first detection; `Flag.write` upserts.) |
| P3-064 | `Match identity` = `str(100 * identity) + '%'` (unrounded float, e.g. `98.69999999999999%`). |

## 9. Phylogeny sequence selection (`_get_accessions_for_phylogeny`)

Input: **all filtered hits** (not only selected species).

| ID | Requirement |
|---|---|
| P3-070 | Sort filtered hits by identity descending. If there are none, or the top identity < `phylogeny_min_hit_identity`, select nothing. |
| P3-071 | Candidate threshold for this step = strict if the top hit ≥ strict, else moderate. A species is a *candidate species* here iff its top hit ≥ that threshold. |
| P3-072 | Iterate species in order of their best hit (hits without species form one group keyed `None`). Before adding a species, stop if already `≥ phylogeny_max_seqs` selected, or if `> phylogeny_min_seqs` selected **and** this species' top identity < `phylogeny_min_hit_identity`. |
| P3-073 | Per species cap: `phylogeny_candidate_max_seqs` for candidate species, `phylogeny_species_max_seqs` otherwise. If the species has more hits than the cap, take a **systematic sample** of size cap from its identity-sorted hits: indices `round(i·(N−1)/(n−1))` for `i < n−1`, plus the last; `n == 1` picks the middle element. Otherwise take all. |
| P3-074 | Write `candidates_phylogeny.fasta` = records of `all_hits.fasta` whose id is selected, in `all_hits.fasta` order. The query sequence is **not** included (MAFFT_ALIGN adds it). |

Consequences: the max is soft (checked before adding a species; can be
exceeded by up to cap−1); species below `phylogeny_min_hit_identity` are
still added while ≤ `phylogeny_min_seqs` have been collected.

## 10. Failure behaviour

Uncaught exceptions fail `EXTRACT_CANDIDATES` for that query only, which
removes the query's report (NF-D-003). Missing `all_hits.json`, a malformed
taxonomy CSV, or BOLD `similarity = None` (§11) are such cases.

## 11. Defects

| ID | Severity | Defect |
|---|---|---|
| P3-D-001 | High (*to confirm by run*) | A query with no hit ≥ `phylogeny_min_hit_identity` (includes every Flag `1E` query) gets an empty `candidates_phylogeny.fasta`. MAFFT then aligns the query alone and FastME has < 3 taxa; if FastME fails, the inner join drops the query and **no report is produced for a "no match" result** — the case where the report matters most. P6 also reads the tree file unconditionally. No test scenario contains a `1E` query. |
| P3-D-002 | High | Hits lacking a taxonomy row (e.g. P2-D-001) cannot form candidate species. If all strict hits lack taxonomy the result silently degrades to `1D`/`1E`, with only a log warning — not surfaced in the report. |
| P3-D-003 | Medium | Flag 6 (phylogenetic assessment) is defined in `flags.csv` and `FLAGS.INTRASPECIES_DIVERSITY` but **never computed or written** by any module. |
| P3-D-004 | Medium | Flag 1 B/C boundary is hard-coded (`< 4`) while the boxplot, P4 gating and report prompts use `max_candidates_for_analysis`; changing that parameter desynchronises them. `flags.csv` text also hard-codes "98.5%" and "93.5%", which do not follow parameter changes. |
| P3-D-005 | Medium | BOLD: `similarity` can be `None` (P1-BOLD), which raises `TypeError` in threshold comparisons. |
| P3-D-006 | Low | Candidate species de-duplication is case-sensitive, species counts are case-insensitive. |
| P3-D-007 | Low | `median_identity` is the upper median for even counts. |
| P3-D-008 | Low | `preliminary_id_match.csv` is written without a newline between header and row (`rank,taxonspecies,X`); no consumer reads it (not used by P6). |
| P3-D-009 | Low | PMI and TOI comparisons include the `accession`/`taxid` columns of the taxonomy row as if they were ranks. |
| P3-D-010 | Low | `Match identity` is unrounded (`98.69999999999999%`). |
| P3-D-011 | Low | `plt.boxplot(labels=…)` is deprecated in Matplotlib ≥ 3.9 (`tick_labels`). |

## 12. Test mapping

`tests/test_phylogeny_sampling.py`: strict-candidate selection, moderate-
candidate selection, sampling above the per-species cap (P3-070..073).
**Not covered:** everything else — hit filtering (P3-001..004), Flag 1
branches, Flag 2/7, outputs §6, BOLD mode, empty-hit queries. The nf-test
flag baselines (`test/*/flags`) exercise P3 end-to-end but contain no `1E`
case.

## 13. Open questions

1. Should Flag 7 also be evaluated for genus-level agreement when Flag 1
   is B/C/D (all candidates share the PMI genus)?
2. Should TOI detection consider moderate candidates when strict ones
   exist (a TOI at 97% is currently invisible if another species is ≥98.5%)?
3. Should Flag 6 be implemented (automated clade assessment) or removed
   from `flags.csv`?
