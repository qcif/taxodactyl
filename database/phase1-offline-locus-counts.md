# Phase 1: Offline locus counts from sequence titles

## Background

Our bioinformatics workflow repeatedly needs to answer one question:

> *How many DNA sequence records exist for organism **X** at locus **Y**?*

Today we answer it by making live API calls to NCBI Entrez over the internet.
That is slow, rate-limited, needs network access from every compute node, and is
not reproducible — the same query run six months apart returns different numbers
and we cannot reconstruct why.

**Your goal is to replace those API calls with a local database file.**

Phase 1 builds a complete, working version of that database using only the
metadata we can extract cheaply. Phase 2 improves its accuracy using richer
metadata that is expensive to fetch. You should finish Phase 1 with something
that already answers the question end to end, even if some of the answers are
wrong. Getting the whole shape working first is the point.

### The two terms you need

You need no biology background for this. Two terms, and then it is a data
engineering problem:

- **Record** — one DNA sequence plus its metadata. It has an **accession** (a
  unique ID like `MT012345.1`), a **taxid** (an integer identifying which
  organism it came from), a **length** in bases, and a **title**: a free-text
  description written by whoever submitted it.

- **Locus** — a named region of DNA that biologists commonly sequence, e.g.
  `COI`, `16S`, `rbcL`. There are 31 we care about and the list is fixed. A
  record "covers" a locus if the sequence includes that region. Our job is to
  decide, per record, which of the 31 loci it covers.

The source of records is a sequence database called `core_nt`. We have a copy on
a VM. It is large — hundreds of gigabytes — so all heavy extraction happens
there.

### Two things about taxids

**Taxonomy is a tree.** Taxids are nodes in a hierarchy: domain → kingdom →
phylum → class → order → family → genus → species, and often further down into
subspecies and strains. A record's taxid can sit at *any* level of that tree.

**Queries count whole subtrees.** Asking for *Fusarium oxysporum* must also count
every subspecies, strain and variant filed underneath it. We handle this by
storing each taxid's full lineage as columns, so a subtree query becomes a
`GROUP BY` on a lineage column rather than a tree traversal.

---

## The target schema

Three tables. Build them in this order; each is derived from the one before.

### Table 1 — `records`

One row per sequence in `core_nt`.

| column | type | notes |
|---|---|---|
| `accession` | text | primary key, e.g. `MT012345.1` |
| `taxid` | integer | which organism |
| `length` | integer | sequence length in bases |
| `title` | text | free-text description |

This is the **source of truth**. Nothing in it is derived, and it is rebuilt only
when `core_nt` is refreshed. In Phase 2 it gains extra source columns parsed from
GenBank metadata.

### Table 2 — `record_locus`

One row per record-locus assessment.

| column | type | notes |
|---|---|---|
| `accession` | text | FK to `records` |
| `locus_id` | integer | FK to `loci` |
| `status` | text | `present`, `absent` or `unknown` |
| `evidence_source` | text | `title` for everything in Phase 1 |

**Derived and revisable.** It is rebuilt from `records` whenever the synonym
lists or the matching rules change. Never hand-edit it.

The three-way `status` matters. If you only recorded present/absent, a zero would
conflate *"we checked and it isn't there"* with *"we had no way to check"*. Those
are different, and Phase 2 needs to tell them apart to know what is worth
enriching.

| status | meaning |
|---|---|
| `present` | we found evidence the record covers this locus |
| `absent` | we looked at the evidence we had and found nothing |
| `unknown` | the evidence we had cannot settle it either way |

### Table 3 — `taxid_locus`

One row per distinct taxid appearing in `core_nt`.

| column | type | notes |
|---|---|---|
| `taxid` | integer | primary key |
| `rank_domain` … `rank_species` | text | 8 lineage columns, from `taxonkit` |
| `n_records` | integer | total records for this taxid |
| `locus_1` … `locus_31` | integer | count of `present` records per locus |

The lineage columns are `rank_domain`, `rank_kingdom`, `rank_phylum`,
`rank_class`, `rank_order`, `rank_family`, `rank_genus`, `rank_species`.

Counts are for **this taxid exactly**, not its subtree. Subtree counts are
produced at query time by summing over the relevant lineage column — see
[Step 8](#step-8--queries-that-must-work).

### Table 0 — `loci`

The column names `locus_1` … `locus_31` are opaque, so you also need a small
registry table mapping them back to names. Put the vocabulary in the **database**,
not in constants in your code — someone reading this file in a year needs to know
what `locus_8` meant without finding the right git commit.

| column | type | notes |
|---|---|---|
| `locus_id` | integer | 1–31, **stable forever** |
| `name` | text | e.g. `coi` |
| `synonym` | text | one row per synonym |
| `ambiguity_class` | text | `ambiguous` or `non_ambiguous` |

(Split this into two tables if you prefer — one for loci, one for synonyms.)

`locus_id` is permanent and append-only. It is baked into the column names of
table 3, so if you ever renumber, every previously built database silently starts
lying. If a locus is retired, tombstone it and leave the ID unused.

---

## Step 1 — Get onto the VM and look at `core_nt`

```bash
ssh <username>@<vm-hostname>

echo $BLASTDB                      # directory holding core_nt
blastdbcmd -db core_nt -info       # sequence count and total bases
df -h .                            # check free space before you start
```

Write down the sequence count from `-info`. You will use it to sanity-check your
final row count.

---

## Step 2 — Test the extraction on a handful of records

`blastdbcmd` reads the BLAST database and can print per-sequence metadata in a
format you choose. Try it on a few records before running it over everything:

```bash
blastdbcmd -db core_nt -entry all -outfmt "%a	%T	%l	%t" | head -n 20
```

| specifier | meaning |
|---|---|
| `%a` | accession |
| `%T` | taxid |
| `%l` | length |
| `%t` | title |

The separator above is a literal tab.

**Read the output carefully before continuing:**

- Does every line split into exactly four fields on tab?
- Do any titles contain tabs themselves, which would break the parse?
- Are there taxids of `0`, or missing?
- Are there duplicate accessions?

Change the delimiter if tabs are unsafe, and note anything odd — you handle it in
Step 4.

---

## Step 3 — Run the full extraction

This takes hours and produces a very large file. So:

1. Run it in `tmux` so it survives your SSH session dropping.
2. Compress as you write.

```bash
tmux new -s extract

blastdbcmd -db core_nt -entry all -outfmt "%a	%T	%l	%t" \
  | gzip -c > core_nt_metadata.tsv.gz
```

Detach with `Ctrl-b d`, reattach with `tmux attach -t extract`.

When it finishes:

```bash
ls -lh core_nt_metadata.tsv.gz

# Compare this count against -info:
zcat core_nt_metadata.tsv.gz | wc -l

# Confirm it did not truncate:
zcat core_nt_metadata.tsv.gz | tail -n 5
```

**Record the date you ran this and the `-info` output.** Everything you build is
a snapshot as of that date and we need to be able to say so.

---

## Step 4 — Make a sample and work locally

The full file is too big to iterate against while you are still writing code.

```bash
zcat core_nt_metadata.tsv.gz | head -n 2000000 | gzip -c > core_nt_sample.tsv.gz
```

A head-of-file sample is fine for development but is **not random** — records are
not in random order, so draw no conclusions from it about the data as a whole.
For a representative sample to test your parser against unusual records, use
`shuf -n` instead (slower; reads the whole file).

```bash
scp <username>@<vm-hostname>:core_nt_sample.tsv.gz .
```

**From here you work locally in Python**, against the sample. The final build
runs back on the VM with the same code pointed at the full file.

---

## Step 5 — Load table 1 (`records`)

Pick SQLite or DuckDB and be ready to justify the choice. DuckDB is generally the
better fit here — columnar, fast aggregation, handles the table 3 rollup well —
but SQLite is fine and simpler to ship.

Requirements for the loader:

- **Stream it.** Read and insert in batches. Never load the whole file into
  memory; it is bigger than your RAM.
- **Make it re-runnable.** If it dies halfway you must be able to start again
  cleanly, not end up with a half-populated table.
- **Report progress.** A silent process that runs for two hours is
  indistinguishable from a hung one.
- **Log what you reject.** Malformed lines, missing taxids, duplicate
  accessions — count them and write them somewhere. Do not silently drop rows.

Sanity checks before moving on:

```sql
SELECT COUNT(*) FROM records;                      -- vs blastdbcmd -info
SELECT COUNT(DISTINCT accession) FROM records;     -- should equal the above
SELECT COUNT(DISTINCT taxid) FROM records;
SELECT MIN(length), MAX(length) FROM records;
```

---

## Step 6 — Load the locus registry and build table 2

### 6a. Load the registry

The 31 loci and their synonyms are supplied in
[scripts/config/loci.json](../scripts/config/loci.json). Load them into the
`loci` table; do not invent or edit them. Assign `locus_id` in a fixed order
(alphabetical by name is fine) and **write the mapping down** — it is permanent.

Each locus has two classes of synonym:

- **`non_ambiguous_synonyms`** — distinctive strings like
  `cytochrome oxidase subunit 1`. Finding one anywhere is safe evidence.
- **`ambiguous_synonyms`** — short strings like `coi`, `act`, `cox` that collide
  with unrelated text. The live API only trusts these inside two structured
  fields: the record **Title** and the record's **GENE** field.

We have the title. We do not have the GENE field until Phase 2. So in Phase 1:

> **Match both classes against the title.** For non-ambiguous synonyms this is a
> subset of what the live API does. For ambiguous synonyms it is exactly the
> `[Title]` half of what the live API does. The missing `[GENE]` half is what
> Phase 2 adds.

### 6b. Detect records you cannot assess

Some titles describe a **complete genome** rather than a specific region — a
whole mitochondrial genome, a chloroplast genome, a bacterial chromosome. These
almost never name individual loci, but they contain many of them. Calling them
`absent` for all 31 loci would be wrong.

Write a conservative title pattern to identify these, and mark them `unknown`
for every locus, with `evidence_source = 'title'`. Phase 2 resolves them.

Report how many records this catches and eyeball a sample of the titles by hand.

### 6c. Run the matching pass

For every record, for every locus:

| condition | status |
|---|---|
| the title looks like a complete genome | `unknown` |
| a synonym of this locus appears in the title | `present` |
| otherwise | `absent` |

Practical notes:

- Match **case-insensitively**, and tolerate the ways submitters separate
  words — `cytochrome c oxidase`, `cytochrome-c-oxidase` and
  `cytochrome  c  oxidase` should all match.
- **Watch your word boundaries.** Naive substring matching finds `act` inside
  `bacterial` and `its` inside `units`, and you will spend a long time tracking
  the false positives down.
- **Compile your patterns once**, outside the loop. This runs over the whole
  database.

### 6d. Decide how to store it

A full cross product is (number of records) × 31 rows. Work out what that
actually is for `core_nt` before you write any of it to disk — it will be in the
billions, and that is not a table you want in SQLite.

The fix is to store it **sparsely**: write rows only for `present` and `unknown`,
and treat any (accession, locus) pair with no row as `absent`. Document the
convention clearly — a reader must not mistake a missing row for missing data.

Implement it this way unless you find a better option, and justify whichever you
pick. Either way, index `(accession)` and `(locus_id, status)`.

---

## Step 7 — Build table 3 (`taxid_locus`)

### 7a. Get the lineages

`records` gives you a taxid per record but not the tree it sits in, and no
readable names. Those come from NCBI's taxonomy dump, read with a tool called
`taxonkit`. Both are already used elsewhere in this project — the project
[README](../README.md) covers downloading `taxdump.tar.gz` and the `taxonkit`
binary.

Extract your distinct taxids, then resolve each to a full lineage:

```bash
# one taxid per line
taxonkit lineage --data-dir $TAXONKIT_DB taxids.txt \
  | taxonkit reformat --data-dir $TAXONKIT_DB -i 2 -F -r "" \
      -f "{d}\t{k}\t{p}\t{c}\t{o}\t{f}\t{g}\t{s}" \
  | cut -f1,3-
```

The `-f` placeholders are domain, kingdom, phylum, class, order, family, genus,
species. **Check them against `taxonkit reformat --help` for your version** —
the placeholder set has changed between releases. `-F` fills in missing ranks
rather than dropping them; `-r ""` leaves unfillable ranks empty.

Note that you will have millions of taxids to extract. It might be necessary to
chunk this into batches of 100K or so - feel free to test this and solve as you
see fit.

Things that will happen and that you must handle:

1. Taxids in `core_nt` that do not appear in the taxonomy dump at all.
2. Taxids that have been **merged** into another taxid (see `merged.dmp`).
3. Taxids with no value at some ranks — plenty of organisms have no assigned
   phylum or genus.

For 1 & 2, count each case and report it. Let 3 pass silently - it should not
create issues.

### 7b. Aggregate the counts

One row per distinct taxid. `n_records` is the record count for that taxid;
`locus_N` is the count of its records with `status = 'present'` for locus N.

Remember that each row is **the taxid alone**. Usually that points to a species,
but sometimes it may be a subspecies, genus or family. Taxonkit will fill out
the rank columns, and some may be blank, but we can work with that.

Index the lineage columns you expect to filter on — at minimum `rank_species`
and `rank_genus`.

### 7c. Record provenance

Add a `build_info` table with one row: extraction date, `core_nt` version from
`-info`, taxdump version, row counts per table, and the number of records in each
status category. **Do not skip this.** A database nobody can date is a database
nobody can trust.

---

## Step 8 — Queries that must work

These are the acceptance criteria. Written for SQLite; adapt as needed.

**1. Records for one taxid exactly**

```sql
SELECT n_records FROM taxid_locus WHERE taxid = 7227;
```

**2. Records for a species including everything beneath it**

```sql
SELECT SUM(n_records)
FROM taxid_locus
WHERE rank_species = 'Drosophila melanogaster';
```

**3. Records for a species at one locus**

```sql
SELECT SUM(locus_8)
FROM taxid_locus
WHERE rank_species = 'Drosophila melanogaster';
```

**4. The same at any rank**

```sql
SELECT SUM(locus_8) FROM taxid_locus WHERE rank_genus  = 'Drosophila';
SELECT SUM(locus_8) FROM taxid_locus WHERE rank_family = 'Drosophilidae';
```

**5. Many taxa at once**

```sql
SELECT rank_species, SUM(locus_8) AS n
FROM taxid_locus
WHERE rank_species IN ('Fusarium oxysporum', 'Bactrocera dorsalis')
GROUP BY rank_species;
```

**6. Breakdown of a genus by species**

```sql
SELECT rank_species, SUM(n_records) AS n
FROM taxid_locus
WHERE rank_genus = 'Drosophila'
GROUP BY rank_species
ORDER BY n DESC;
```

**7. Present / absent / unknown for a taxid at one locus**

```sql
SELECT rl.status, COUNT(*)
FROM records r
JOIN record_locus rl ON r.accession = rl.accession
WHERE r.taxid = 7227 AND rl.locus_id = 8
GROUP BY rl.status;
```

(Adjust for your sparse-storage convention — `absent` will need deriving.)

**8. Decoding a locus column without reading the source**

```sql
SELECT DISTINCT name FROM loci WHERE locus_id = 8;
```

**9. Provenance**

```sql
SELECT * FROM build_info;
```

---

## Step 9 — Verify

Convince yourself the numbers are right before anyone relies on them.

- Does `COUNT(*) FROM records` match `blastdbcmd -info`?
- Does `SUM(n_records) FROM taxid_locus` equal `COUNT(*) FROM records`?
- Pick a genus. Does the sum over its species, plus records attached directly to
  the genus node itself, equal the genus total? *(That last part catches a common
  bug — records do not only attach to species-level taxids.)*
- Take 20 species at random and compare `n_records` against the live Entrez API.
  They will **not** match exactly; some Entrez records are not in `core_nt`. What
  matters is that the differences have an explanation, not that they are zero.
- Take 20 (species, locus) pairs and do the same. Expect worse agreement here —
  quantifying and explaining that gap is the whole job of Phase 2, so a clear
  statement of where you stand at the end of Phase 1 is exactly what is wanted.
- Hand-check 30 title matches, 10 per class: obvious positives, obvious
  negatives, and cases the matcher called `present` on a short ambiguous synonym.
  Count how many it got wrong.
- Time a batch of queries against your database and against the live API, and
  report the speedup.

---

## Deliverables

1. Python code that builds all four tables from `core_nt` and the taxonomy dump,
   in a git repo, runnable end to end with a single command.
2. A built database from the full `core_nt` extraction.
3. A README covering: how to rebuild, the schema, your storage choice for table 2
   and why, and timing results.
4. A short note on what did not fit your assumptions — malformed lines, missing
   or merged taxids, duplicate accessions, records you could not classify. There
   will be some. We want to know what you did with them.
5. Your Step 9 verification numbers, including the hand-checked accuracy of the
   title matcher.

## Out of scope

Anything requiring the full GenBank record for a sequence. Phase 1 uses only what
`blastdbcmd` and the taxonomy dump give you. Do not start downloading records
from NCBI.
