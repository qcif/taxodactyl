# Phase 3: Publications database

## Background

Run this **in parallel with Phase 2 Step 3**. Both phases read the same bulk
GenBank flat files, and those files are large and slow to download. Parse both
kinds of metadata in a single pass rather than streaming the whole release twice.

This phase builds a separate, standalone database. It has nothing to do with loci
or taxonomy — it answers a different question: **which papers describe this
sequence record?**

Every GenBank record carries a `REFERENCE` block listing the publications its
submitters attached to it: journal articles, and usually also a
"Direct Submission" entry naming the submitting lab. A record can have several
references, and — this is the point of the phase — one publication is typically
attached to thousands of records. A single barcoding paper might be cited by
every sequence it produced.

Because the relationship runs both ways — one record has many publications, one
publication has many records — this is a **many-to-many** relationship, and it
needs three tables: `records` (built in Phase 1), `publications`, and a junction
table between them holding one row per link.

---

## Identifying a publication

A GenBank reference looks like this:

```
REFERENCE   1  (bases 1 to 658)
  AUTHORS   Hebert,P.D.N. and Ratnasingham,S.
  TITLE     Barcoding animal life
  JOURNAL   Proc. R. Soc. Lond., B, Biol. Sci. 270 (2003)
   PUBMED   12952648
```

There is no identifier in that block we can rely on. The `PUBMED` line — the
PubMed identifier — is the obvious candidate, but it is **optional**, and a large
minority of real, published references do not have one. A PMID means "indexed in
PubMed", which is a narrower thing than "published". References with no PMID
include:

- papers in journals PubMed does not index — much of taxonomy and systematics is
  published in small journals that fall outside it
- work that was genuinely unpublished when the sequence was submitted, and never
  back-filled (`JOURNAL   Unpublished`)
- theses, books, and reports
- recent papers not yet indexed at the time of the GenBank release

So `publications` gets a **surrogate primary key**: an integer `publication_id`
that we generate ourselves, meaningful only inside this database. The junction
table carries it as a foreign key. Every reference that is not a Direct
Submission gets a row, regardless of whether PubMed knows about it.

The PMID is still worth keeping, just not as the key. Store it as a nullable
column, because:

- **it is the best dedup signal you have.** Where two references carry the same
  PMID they are the same paper, full stop. Everything else is inference from text
  — see Step 2.
- it lets a downstream consumer link straight out to the PubMed record.

---

## Target schema

### `accession_publication` — the junction table

One row per (accession, publication) link. A record with three references
produces three rows; a publication cited by 10,000 records appears in 10,000
rows.

| column | notes |
|---|---|
| `accession` | FK to `records.accession` from Phase 1 |
| `publication_id` | FK to `publications.publication_id` |
| `reference_number` | the `REFERENCE n` ordinal, 1-based |

Primary key `(accession, publication_id)`. Index both columns separately — you
will traverse this table in both directions.

Keep `reference_number` because reference 1 is conventionally the primary
description of the record and later ones are supporting entries — a consumer may
want to weight them differently.

### `publications`

One row per distinct publication.

| column | notes |
|---|---|
| `publication_id` | PK, surrogate integer |
| `pmid` | integer, **nullable** — kept for dedup and link-out, never as the key |
| `authors` | the full author list |
| `title` | article title |
| `journal` | the `JOURNAL` line, verbatim |
| `match_key` | unique — the dedup key from Step 2 |
| `n_accessions` | denormalised count, filled at the end |

Store `authors` however you stored list-valued columns in Phase 2 — be
consistent across the two databases. Preserve author order; it is meaningful.

Keep `journal` as the raw line. It is a single unstructured string that packs
together journal name, volume, pages and year, and its format is not consistent
enough to split reliably. Anyone who needs the year can regex it out of this
column; storing it as its own field would mean committing to a parse that fails
on a long tail of theses, books and `Unpublished` entries.

---

## Step 1 — Parse references during the Phase 2 pass

Add reference extraction to the flat-file parser from Phase 2 Step 3. Each
`REFERENCE` block ends where the next `REFERENCE`, `COMMENT` or `FEATURES` line
begins.

Two parsing details will bite you:

- **Continuation lines.** `AUTHORS` and `TITLE` values wrap across multiple lines,
  indented. Join them before parsing. Author lists in particular are nearly always
  multi-line.
- **Direct Submission entries.** These have `TITLE   Direct Submission`. They are
  submission records naming the depositing lab, not papers. Skip them — and note
  that they would otherwise all collapse onto one match key.

As in Phase 2, skip past `ORIGIN` to `//` — the references all appear before the
feature table, so you never need to touch the sequence.

Write the same way you wrote Phase 1: streaming, batched, re-runnable, reporting
progress.

---

## Step 2 — Deduplicate

This is the step that decides whether the database is any good.

Compute a **match key** for every reference — the value you look up to decide
"have I seen this publication before?". It is two-tier:

| | match key |
|---|---|
| **PMID present** | `pmid:<the PMID>`. Exact, reliable, no inference. |
| **PMID absent** | `hash:<hash of normalised title + authors>`. Inferred. |

Normalise before hashing — lowercase, collapse whitespace, strip punctuation —
because the same paper is formatted inconsistently across submissions. Store the
match key in its own column so the dedup is reproducible and inspectable after
the fact.

Insert into `publications` on first sight of a match key, then only into
`accession_publication` thereafter. The same publication will appear with
slightly different formatting across records — **first one wins** is fine, but
count how often you see a conflicting title for an already-known PMID. If that
number is large, something is wrong with your parser.

The hash tier is the weak one, and its normalisation is a dial with two bad ends:

| too strict | too loose |
|---|---|
| one paper splits into many near-duplicate rows | distinct papers collapse into one row |
| `n_accessions` is mostly 1 | a few rows have implausible `n_accessions` |

Title alone is too loose — generic titles recur. Title plus authors is a
reasonable starting point. Tune it against the distributions in Step 3 rather
than by intuition, and write down what you chose.

Fill `n_accessions` once at the end, from `accession_publication`.

---

## Step 3 — Measure the dedup quality

The PMID tier needs no validation. The hash tier does, and you have no ground
truth for it — so you validate against shape and samples.

**The trick is to use the PMID tier as your control.** Split every distribution
by whether `pmid IS NULL` and compare the two groups. The PMID group is what
correct dedup looks like on this data; the hash group should resemble it. Where
it does not, the hash rules are wrong.

1. **The `n_accessions` distribution, split by tier.** Both should be extremely
   skewed: most publications linked to a handful of records, a few barcoding
   papers linked to hundreds of thousands. If the hash group is almost all 1s
   while the PMID group is skewed, normalisation is too strict and one paper is
   splitting into many rows.
2. **Inspect the top 20 by `n_accessions` by hand.** Each should be a real,
   plausibly high-throughput paper. A generic or truncated title at the top of
   this list means distinct papers have been merged — normalisation too loose.
3. **Inspect a sample of 30 hash-tier singletons.** If you can eyeball two of
   them as obviously the same paper, you have a splitting problem.
4. **Cross-check the two tiers.** Run your hash rule over the PMID group as if
   the PMIDs were missing. Anywhere one PMID yields several hashes is a split
   your rule would have caused; anywhere one hash covers several PMIDs is a merge
   it would have caused. **This gives you a measured error rate for the hash tier,
   and it is the single most useful number in this step.**

Report what fraction of references carried a PMID, the distributions, the
normalisation rules you settled on, and the Step 3.4 error rate.

---

## Step 4 — Sanity checks

- Every `accession` in `accession_publication` exists in `records`. Report any
  that do not — it means the two databases were built from different GenBank
  snapshots.
- `SUM(n_accessions)` equals `COUNT(*)` from `accession_publication`.
- Every `publication_id` in the junction table exists in `publications`, and no
  `publications` row has zero links.
- `match_key` is unique across `publications`. If it is not, your insert path has
  a race or a batching bug.
- `pmid` is unique where it is not null.
- Spot-check 20 PMIDs against the live PubMed record: authors, title and journal
  should agree.

---

## Step 5 — Queries that must work

**1. Publications for one record**

```sql
SELECT p.title, p.authors, p.journal, p.pmid
FROM accession_publication ap
JOIN publications p ON p.publication_id = ap.publication_id
WHERE ap.accession = 'NC_012920'
ORDER BY ap.reference_number;
```

**2. Records attributed to one publication**

```sql
SELECT COUNT(*)
FROM accession_publication
WHERE publication_id = 12345;
```

**3. Most-cited publications**

```sql
SELECT publication_id, title, n_accessions
FROM publications
ORDER BY n_accessions DESC
LIMIT 20;
```

**4. How much of the database rests on the weaker dedup tier**

```sql
SELECT pmid IS NULL AS hash_tier, COUNT(*), SUM(n_accessions)
FROM publications
GROUP BY hash_tier;
```

**5. Publication coverage**

```sql
SELECT COUNT(DISTINCT accession) FROM accession_publication;
```

Compare that against `COUNT(*)` from `records` and report it as a percentage.

---

## Deliverables

1. Reference parsing folded into the Phase 2 flat-file pass — **one read of the
   bulk files, two databases out**.
2. A populated two-table publications database, joined to Phase 1's `records` by
   accession.
3. **The Step 3 dedup assessment** — PMID coverage, the `n_accessions`
   distributions split by tier, the normalisation rules you settled on, and the
   measured hash-tier error rate from Step 3.4. This is the output that
   determines whether the database is usable.
4. Coverage: what fraction of records have at least one publication.
