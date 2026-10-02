# Contract: loci panel (`scripts/config/loci.json`)

Used by P0 (validation, P0-021), config (`get_locus_for_query`, CFG-027,
CFG-040..042) and P5/P4 (GenBank queries).

```json
{ "<key>": { "ambiguous_synonyms": ["…"], "non_ambiguous_synonyms": ["…"] } }
```

| ID | Requirement |
|---|---|
| LOC-001 | Each key is a locus name; the union of its two synonym lists (`Locus.synonyms`) is what a user may enter. |
| LOC-002 | **Every synonym MUST be lower case with no surrounding space**, and the lower-cased key SHOULD be a synonym. P0 and `Locus.__contains__` lower-case the input and compare case-sensitively. Violated today by `atpB`, `trnL`, `AChE` (P0-D-001). |
| LOC-003 | A synonym MUST belong to only one locus (true today: no shared synonyms across the 31 loci). |
| LOC-004 | *Ambiguous* synonyms (short tokens such as `coi`, `its`) are searched only in GenBank `[Title]` and `[GENE]`; *non-ambiguous* synonyms in all fields (CFG-042). |
| LOC-005 | The file MUST be UTF-8; key `ß-tub` contains a non-ASCII character. |

Shipped panel (31 keys): 16s, 28s, act, alt-a1, ß-tub, cmda, co2, coi,
cytb, dnax, ef1a, fusa, gapa, gyrb, hsp60, its, its1, its2, leus, lsu,
matk, rbcl, recn, reca, rpob, rplb, rpod, rpb2, atpB, trnL, ache.
A key spelled `ache` has synonyms `AChE`/`Acetylcholinesterase`.

Override with `--allowed_loci_file`; the override replaces the panel (no
merge). The `NA` value is accepted separately and is not in the file.
