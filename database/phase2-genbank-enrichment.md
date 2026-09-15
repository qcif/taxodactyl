# Phase 2: GenBank metadata enrichment

## Background

Phase 1 built a working database that answers *"how many records exist for
organism X at locus Y?"* using only the free-text `title` of each record.

The title is a summary. It is written by whoever submitted the sequence, with no
controlled vocabulary, and it frequently does not mention the loci the sequence
covers. The full record held at GenBank does much better: it has a **feature
table**, a structured listing of every gene the sequence covers, with dedicated
fields for gene names, synonyms and products.

**Phase 2's goal is to use that structured metadata to improve the accuracy of
tables 2 and 3, and — just as importantly — to measure how much it improved
them.**

This is a different kind of problem to Phase 1. Phase 1 was data engineering with
a right answer. Phase 2 is classification with no exact right answer, and most of
the work is deciding how wrong you are willing to be, and proving it.

### What the enrichment buys you

Recall the two synonym classes from `loci.json`:

- **`non_ambiguous_synonyms`** (`cytochrome oxidase subunit 1`) — distinctive.
  The live API searches these across all text.
- **`ambiguous_synonyms`** (`coi`, `cox`, `act`) — short and collide with
  unrelated words. The live API only trusts these inside two structured fields:
  **Title** and **GENE**.

In Phase 1 you matched both classes against the title. That covers the `[Title]`
half of the ambiguous-synonym query exactly, and part of the non-ambiguous query.
The feature table gives you the `[GENE]` half, plus product and note fields.

There are three sources of evidence, in increasing order of cost:

1. **The title.** Free. Already done in Phase 1.
2. **A rule for whole-genome records.** Cheap, and recovers a whole class of
   records that titles systematically miss.
3. **Full GenBank records, parsed for their feature tables.** Expensive, and
   covers only part of `core_nt`.

Your job is to add 2 and 3, combine them with 1, and characterise the result.

---

## Changes to the schema

### Table 1 — `records` gains source columns

The extra metadata you parse from GenBank goes into `records` as new columns,
alongside `title`. These are **source data**, so they belong in the source-of-
truth table. Suggested shape:

| column | notes |
|---|---|
| `gene_names` | the structured gene/locus_tag names from the feature table |
| `product_names` | the product field of each feature |
| `definition` | the record's DEFINITION line |
| `enriched` | boolean — did we manage to fetch this record? |

How you store a list in a column is your call (delimited text, JSON, a native
array type in DuckDB, or a separate child table). Pick one, justify it, and make
sure it is cheap to match against.

### Table 2 — `record_locus` gets rebuilt

Table 2 is derived and revisable — that is why it exists as its own table. You do
not patch it; you **rebuild it** from the enriched `records`. Same columns, but
now `evidence_source` takes three values:

| `evidence_source` | meaning |
|---|---|
| `title` | assessed from the title only (Phase 1 behaviour) |
| `genome_rule` | inferred from a whole-genome title plus length |
| `feature_table` | assessed from structured GenBank metadata |

Keep the source separate from the status. A user needs to be able to ask "how
much of this count came from the weakest evidence?" and get an answer.

### Table 3 — `taxid_locus` gets recomputed

No schema change. Re-aggregate it from the rebuilt table 2.

---

## Step 1 — The whole-genome rule

Do this first. It is cheap, it needs no downloads, and it resolves a large
fraction of the records Phase 1 marked `unknown`.

Titles describing a complete organellar genome — a mitochondrial genome, a
chloroplast/plastid genome — almost never name individual loci. But the gene
content of these genomes is highly conserved and well known. A complete insect
mitochondrial genome contains `COI` whether or not the title says so. The live
API catches these because it searches the feature table. You can catch most of
them with a rule.

1. Take the complete-genome candidates you identified in Phase 1 Step 6b.
2. **Sanity-check with `length`.** A complete mitochondrial genome falls in a
   fairly narrow size band, and a record claiming to be one that is 400 bases
   long is a fragment or mislabelled. Derive the bands from the actual length
   distribution in your data rather than guessing, and show your working.
3. For records passing both, set `status = 'present'` for the standard locus
   complement of that compartment, restricted to the loci in our registry. The
   complements will be supplied to you; do not invent them.
4. Set `evidence_source = 'genome_rule'`.

**Be conservative.** A rule that fires on partial genomes, or on records that
merely *reference* a mitochondrial genome, inflates counts in a way that is very
hard to detect downstream. When in doubt, leave the status as `unknown`.

Report how many records the rule fires on, per compartment, and hand-check a
sample of 30.

---

## Step 2 — Assess whether feature tables are worth it

**Do not start bulk-downloading GenBank records until you have done this step.**
The enrichment is expensive and may not be worth it for every locus.

Take a stratified sample of accessions — 20,000 to 50,000 — spread across the
taxa the workflow actually queries and across record types (short fragments,
whole genomes, everything in between). Fetch their full GenBank records through
the NCBI API. At that sample size this is a tractable number of calls; respect
the rate limits and use an API key.

Parse the feature tables and compute, **per locus**:

| metric | question it answers |
|---|---|
| title-pass false negatives | how often does the feature table find a locus the title missed? |
| title-pass false positives | how often does the title call a locus the feature table contradicts? |
| gap closed by the genome rule | how much of the false-negative gap did Step 1 already fix? |
| remaining `unknown` rate | how many records still cannot be assessed? |

**Present this as a table, one row per locus. That table is the deliverable of
this step**, and it determines whether Step 3 happens at all, and for which loci.

The likely result is that some loci are near-identical between methods and others
diverge badly, mostly on genome records. If a locus agrees to within a percent,
enriching it is wasted effort.

---

## Step 3 — Bulk enrichment (conditional)

Only if Step 2 justifies it.

The full GenBank record set is downloadable in bulk as flat files. Two things
make this much cheaper than it first appears:

- **You never need the sequence.** Each record is a header, then a feature table,
  then the raw sequence introduced by a line reading `ORIGIN`. Stream each file,
  and as soon as you hit `ORIGIN`, skip to the record separator (`//`). The
  sequence is the large majority of the bytes.
- **You never need to keep the raw text.** The output per record is an accession
  and a handful of short fields.

Populate the new `records` columns from what you parse, then rebuild table 2:

| synonym class | matched against |
|---|---|
| ambiguous | structured gene-name fields only |
| non-ambiguous | gene-name fields, plus product, note and the definition line |

For enriched records, a non-match is a genuine `absent` — you had the full
structured metadata and the locus was not in it. Only fall back to `unknown`
where the record itself is incomplete.

Where no enrichment exists, keep the Phase 1 title-derived row unchanged.

### Coverage caveat

The bulk GenBank release does not contain everything in `core_nt`. Whole-genome
shotgun and transcriptome assemblies are distributed separately, and RefSeq is a
separate download again. Expect enrichment to cover a substantial fraction but
not all of it.

**Quantify that fraction and record it in `build_info`**, broken down by
evidence source. A mixed-evidence database is fine. One that hides which records
got which treatment is not.

Also note the release cadence: the bulk files are a periodic snapshot with
incremental daily updates. Get the periodic snapshot working before you touch the
incrementals.

---

## Step 4 — Rebuild tables 2 and 3

Re-run the Phase 1 aggregation. This should be the *same code* — if rebuilding
table 3 requires changes, your Phase 1 pipeline was not properly separated.

Verify the rebuild:

- `SUM(n_records)` from table 3 still equals `COUNT(*)` from table 1.
- Every `locus_N` count is **greater than or equal to** its Phase 1 value for
  loci where enrichment only added evidence. Where a count went *down*,
  enrichment must have overturned title-based false positives — check a handful
  by hand and confirm that is what happened.
- The number of `unknown` assessments dropped, and you can say by how much.

---

## Step 5 — Validate against the live API

Your database will not exactly reproduce the current API results, and it is not
supposed to. The live search also indexes text you will never have offline —
publication titles, free-text notes, sample metadata.

The goal is **not parity**. It is a defensible characterisation of the
divergence.

- Sample at least a few thousand (species, locus) combinations, weighted toward
  the ones the workflow actually queries.
- Compare your count against the live API count for each.
- Report the **distribution** of the difference, per locus — medians and
  outliers, not just a mean.
- Investigate the worst outliers individually. Every large discrepancy should
  have a named cause.
- State clearly which loci you consider production-ready and which you do not.

The honest answer *"this locus is reliable, this one is within 5%, and this one I
would not trust"* is worth far more than a claim of perfect agreement.

---

## Step 6 — Queries that must work

Everything from Phase 1 Step 8, still, plus:

**1. How much of a count came from which evidence**

```sql
SELECT rl.evidence_source, COUNT(*)
FROM records r
JOIN record_locus rl ON r.accession = rl.accession
WHERE r.taxid = 7227
  AND rl.locus_id = 8
  AND rl.status = 'present'
GROUP BY rl.evidence_source;
```

**2. Present / absent / unknown for a species subtree**

```sql
SELECT rl.status, COUNT(*)
FROM taxid_locus tl
JOIN records r       ON r.taxid = tl.taxid
JOIN record_locus rl ON rl.accession = r.accession
WHERE tl.rank_species = 'Drosophila melanogaster'
  AND rl.locus_id = 8
GROUP BY rl.status;
```

**3. Records covering two loci at once**

```sql
SELECT COUNT(*) FROM (
  SELECT accession
  FROM record_locus
  WHERE locus_id IN (8, 1) AND status = 'present'
  GROUP BY accession
  HAVING COUNT(DISTINCT locus_id) = 2
);
```

**4. Records covering any of a set of loci**

```sql
SELECT COUNT(DISTINCT accession)
FROM record_locus
WHERE locus_id IN (8, 1, 16) AND status = 'present';
```

**5. Enrichment coverage**

```sql
SELECT enriched, COUNT(*) FROM records GROUP BY enriched;
```

Queries 3 and 4 cannot be served from table 3 and will be scans. Measure how slow
they are. If they are too slow to be practical, say so — that is a real finding,
and it may argue for a different storage engine.

---

## Deliverables

1. Code that adds the enrichment layer on top of Phase 1, in the same repo,
   runnable end to end.
2. **The Step 2 comparison table** — per-locus divergence between title-based and
   feature-table classification. This is the single most important output.
3. **The Step 5 validation report** — divergence from the live API per locus, with
   explanations for the outliers and a clear recommendation on which loci are
   production-ready.
4. A rebuilt database with enriched `records`, a rebuilt `record_locus` carrying
   real evidence sources, a recomputed `taxid_locus`, and coverage statistics in
   `build_info`.
5. A short design note: where you drew the genome-rule length bands and why,
   which loci you enriched and why, what you did with records you could not
   classify.

## What "done" looks like

Not *"the numbers match"*. Done is: **the numbers are explained.** For any query
this database answers, you should be able to say where the answer came from, what
evidence supported it, and how far it is likely to be from the truth.
