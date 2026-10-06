# Overview

Specification of **`qcif/taxodactyl` v1.5.0**, derived from the source code.
See [README.md](README.md) for conventions and status,
[defects.md](defects.md) for every bug found.

## 1. Purpose

Given one or more query DNA sequences with a locus and a preliminary
morphological identification, decide — conservatively and with evidence —
which species the sequence most likely belongs to, and present that
decision with everything an analyst needs to accept or overrule it. It is
used by biosecurity analysts (DAFF context) on intercepted or unknown
specimens.

## 2. What the system does

Two phases. The first runs **once for the whole batch** (every query
sequence together, in one FASTA/metadata input); the second runs **per
query sequence, independently**.

**Once per run (batch phase):**

1. Validate the inputs (P0) — the whole metadata CSV and FASTA together,
   before any search starts.
2. Search a reference database: one local BLAST call against NCBI Core Nt
   over the entire input FASTA, producing one XML with one record per
   query (BOLD ID Engine is implemented but not operational); the XML is
   then split into one hit set per query.
3. Attach taxonomy to every hit (blastdbcmd + taxonkit, P2) — all
   accessions from all queries are looked up together into one
   `taxonomy.csv`.

**Per query sequence, independently, from here on:**

4. Select **candidate species** by identity/coverage thresholds and set
   Flags 1 (identification), 2 (taxa of interest), 7 (preliminary ID) (P3).
5. Build a distance tree of the query among a stratified sample of hits
   (MAFFT + FastME).
6. Assess **publication diversity** of the candidates' reference sequences
   (P4 → Flag 4).
7. Assess **reference-database coverage** of the candidate, preliminary-ID
   and taxa-of-interest taxa and their relatives, optionally within the
   sample's country, and draw occurrence maps (P5 → Flags 5.1–5.3).
8. Render one self-contained HTML report (P6).

A failure in step 1–3 affects the whole run (every query); a failure in
step 4–8 affects only that one query's report
([architecture.md §3](architecture.md),
[nextflow/error-handling.md](nextflow/error-handling.md)).

## 3. Scope

**In scope:** the eight steps above; deployment on local, HPC (shared
filesystem) and Azure Batch; an optional web validator for input files.

**Out of scope:** sequence generation/assembly; automatic final
identification (the analyst decides, and the report says so when more
than three species match); metabarcoding; databases other than Core Nt
and BOLD `COX1_SPECIES_PUBLIC`; cross-sample summaries.

## 4. Actors

| Actor | Interaction |
|---|---|
| Submitter | prepares `metadata.csv` + FASTA; may use the validation web service |
| Analyst | runs the workflow, reads reports, records subjective conclusions in the report ("save report") |
| Operator | provisions BLAST DB, taxdump, containers, Azure pool, Redis, Key Vault |
| Developer | changes code, `scripts/config/*.{yml,json,csv}`, templates; runs the four test surfaces |
| External services | NCBI Entrez, GBIF, BOLD (rate-limited; throttled and cached) |

## 5. Glossary

| Term | Meaning |
|---|---|
| Query | one input sequence and its metadata row |
| Hit | a database match to a query |
| Filtered hit | hit passing the length/coverage filter (P3) |
| Candidate hit / species | filtered hit at or above the moderate identity threshold / species with one |
| Strong / moderate match | candidate at ≥ `min_identity_strict` / ≥ `min_identity` identity — both configurable, defaulting to 98.5% / 93.5% |
| Selected species | strict candidates if any, else moderate candidates |
| PMI | preliminary morphological identification (`preliminary_id`) |
| TOI | taxon of interest |
| Target (P5) | a taxon whose database coverage is assessed: candidate, PMI or TOI |
| Flag | discrete outcome `{id, value, target}` with text/level in `flags.csv` |
| Locus | genetic region of the query (e.g. COI); `NA` = none/unspecified |
| Query folder | `query_<NNN>_<sample_id>`, the per-query working and output directory |

## 6. Document map

| Area | Files |
|---|---|
| Governing principles | [../CONSTITUTION.md](../CONSTITUTION.md) — non-negotiable rules this spec is held to |
| Architecture | [architecture.md](architecture.md) |
| Nextflow layer | [nextflow/](nextflow/) — workflow, processes, params, config-profiles, error-handling |
| Python layer | [python/](python/) — P0–P6, [blast-vs-bold.md](python/blast-vs-bold.md) (every BLAST/BOLD difference, one place), `shared/` (config, throttle, cache, errors, secrets, flags) |
| Data contracts | [contracts/](contracts/) — inputs, query-folder, filenames, hits, candidates, coverage-and-sources, loci, outputs |
| Services | [services/input-validation.md](services/input-validation.md) |
| Quality and delivery | [tests.md](tests.md), [deployment.md](deployment.md) |
| Backlog and decisions | [defects.md](defects.md), [decisions.md](decisions.md) |
