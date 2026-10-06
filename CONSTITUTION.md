# CONSTITUTION

**Project:** `qcif/taxodactyl` — High-confidence, evidence-based
taxonomic assignment of DNA sequences
**Status:** v1 · **Companion:** [spec/](spec/)

This file distils the non-negotiable principles that govern every design
decision in this project. It is deliberately short. When `spec/` and this
file disagree, this file wins; `spec/` is updated to reconcile.

Unlike a green-field constitution, every principle below is grounded in
the **shipped `v1.5.0` codebase**, derived the same way as the rest of
`spec/` — by reading the code, not by aspiration. Where the codebase
itself falls short of a principle stated here, that is a **defect**
(tracked in [spec/defects.md](spec/defects.md)), not a reason to weaken
the principle.

Principles fall into three tiers:

- **Hard constraints** — the shape of the problem this tool solves. Not
  open to revision without a scope change.
- **Design principles** — the shape of the solution. Revised only with
  explicit reconciliation of every downstream spec file.
- **Engineering rules** — how the system is built and shipped. Revised
  with a pull request + evidence that the change is safe.

---

## Hard constraints

### 1. Scope is evidence-based taxonomic assignment, not sequence generation.

Taxodactyl takes already-sequenced query DNA (a FASTA file, or a
`sequence` column in the metadata CSV) and assigns taxonomic identity by
search against a reference database plus corroborating evidence. It does
not assemble genomes, call variants, or generate sequences — upstream
pipelines are responsible for that
([spec/overview.md §3](spec/overview.md)).

### 2. The pipeline never outputs an unqualified final identification.

It surfaces the strongest supportable claim plus every piece of
corroborating and contradicting evidence (flags, phylogeny, database
coverage, publication diversity), and explicitly prompts the analyst for
a subjective genus/species-level call whenever more than
`max_candidates_for_analysis` species match
([spec/python/p3-assign-taxonomy.md §5](spec/python/p3-assign-taxonomy.md),
[spec/python/p6-report.md §2a.2](spec/python/p6-report.md) tab 5's analyst
checklist). A report that reads as an unqualified identification, or that
lets the analyst conclude without seeing the corroborating evidence, is a
defect against this constraint — not a style choice.

### 3. Reference database choice is whole-run; locus is per-sample.

`--db_type` (`blast_core_nt` or `bold`) is one parameter for the entire
invocation — every query in a run searches the same reference database.
`locus` is declared per metadata row and constrained to the panel in
`scripts/config/loci.json`
([spec/nextflow/params.md](spec/nextflow/params.md),
[spec/contracts/loci.md](spec/contracts/loci.md)). Mixing BLAST and BOLD
queries requires two invocations, by design.

### 4. Every query is independent.

Every sequence in the input is analysed and reported on its own, fanned
out to its own `query_NNN_<sample_id>` folder, with no dependency on any
other query's outcome, from candidate selection onward
([spec/architecture.md §3](spec/architecture.md)). The initial validation
and search stage is a deliberate exception — see rule 6.

---

## Design principles

### 5. Flags are the atomic reportable unit.

Every analytical claim rendered in the report traces to a **flag**: a
`{flag_id, value, target, target_type}` record whose explanation text and
severity level come from the versioned `scripts/config/flags.csv`, never
from a hardcoded string
([spec/python/shared/flags.md](spec/python/shared/flags.md)). A flag
value of `NA` or `ERR` is itself a reportable outcome; "not assessed" must
never be rendered the same way as "assessed and negative". `flags.csv`
text that hard-codes a threshold instead of reading it from config
(`FLG-D-001`) is a defect against this rule, not an exception to it.

### 6. Search is batched; evaluation is per-query.

Input validation (P0), the reference-database search (P1), and taxonomy
lookup (P2, BLAST mode) run **once for the whole batch** — one BLASTN
call over every query sequence, one taxonomy lookup over every accession.
Only from candidate selection (P3) onward does each query become fully
independent (rule 4). This split exists because the batched stages are
inherently one request against one external resource (one BLAST DB
search, one taxonkit call); forcing them per-query would multiply
external calls for no analytical benefit
([spec/overview.md §2](spec/overview.md),
[spec/nextflow/workflow.md §4.2–4.3](spec/nextflow/workflow.md)).

### 7. Non-fatal failures are captured and shown, never silently swallowed.

A single external-API failure (one candidate's database-coverage lookup,
one publication fetch) must not fail the whole query's analysis. It is
written via the `errors` module, keyed to a report location, and rendered
inline at the section it affects
([spec/python/shared/errors.md](spec/python/shared/errors.md)). A
non-fatal error that never reaches the report (`ERR-D-001`) is a defect
against this rule.

### 8. One query's failure must not silently remove its report.

A query whose evaluation fails should be visibly flagged as failed, not
simply absent from the output. **This principle is currently violated**
(`NF-D-003`): the report join is an inner join, so a missing tree or
missing coverage result drops the query with no trace beyond
`<outdir>/errors/`. [decisions.md `D-02`](spec/decisions.md) is open on
how to close this; until it is, treat any taxodactyl output as
potentially missing queries that produced no visible failure.

### 9. Locus panel and flag semantics are versioned config, not hardcoded.

`scripts/config/loci.json` (permitted loci + synonyms) and
`scripts/config/flags.csv` (flag values + explanation text) are the
single source of truth for two of the most report-visible behaviours in
the system. Editing report text for a flag is a config change, never a
template or code change.

### 10. Reference data is operator-provisioned, not pipeline-built.

Unlike a pipeline that assembles its own versioned, checksummed reference
bundle, Taxodactyl consumes BLAST Core Nt, taxdump, and BOLD's reference
database as external paths the operator supplies
([spec/deployment.md §4](spec/deployment.md)). This is a deliberate scope
boundary (these are large, centrally-maintained resources unsuitable for
per-pipeline bundling), but it is a weaker provenance guarantee than a
versioned bundle would give — [decisions.md `D-33`](spec/decisions.md) is
open on whether to tighten it.

---

## Engineering rules

### 11. Every process runs in a container; every tag is pinned.

Every process/label in `conf/process.config` and `conf/azure.config`
declares a container with an explicit tag or digest — never `latest`
([spec/deployment.md §2](spec/deployment.md)). The image's own
reproducibility (floating base, taxonkit from `latest`,
`IMG-D-001`/`DEP-D-003`) is tracked as a defect against this rule, not an
exception to it.

### 12. Custom logic ships as one versioned Python package, in its own image.

The P0–P6 entrypoints and the `scripts/src/` package they call into are
released as a single unit (`scripts/VERSION`), baked into one bespoke
image (`neoformit/taxodactyl`), separate from every off-the-shelf tool
image (BLAST, MAFFT, FastME)
([spec/deployment.md §2–3](spec/deployment.md)). A release that updates
the code without updating all five version locations
(`DEP-D-001`/`DEP-020`) is incomplete.

### 13. Unit tests are the CI floor; the other three surfaces are the target.

`scripts/tests/*.py` MUST pass in CI on every push and PR to `main`
([spec/tests.md §1](spec/tests.md)). Integration tests, `nf-test`, and
Selenium exist and must keep passing when run, but are not yet
CI-enforced — that gap is tracked, not accepted as permanent
([decisions.md `D-41`](spec/decisions.md)).

### 14. Every external API call goes through the shared throttle and cache.

No code may call NCBI Entrez, GBIF, or BOLD directly; every call goes
through `Throttle(...).with_retry(...)`, optionally with caching
([spec/python/shared/throttle.md](spec/python/shared/throttle.md)). This
is not a style preference — bypassing it risks a rate-limit ban on a
shared resource for every concurrent query in the run.

### 15. Secrets never land in an output artifact.

No report, log, or published file may contain an NCBI API key, a Redis
password, or an Azure connection string. **This rule is currently
violated** (`P6-D-001`, `P6-D-003`): the report renders unfiltered
pipeline parameters, and `report_context.json` serialises the full
config. Until [decisions.md `D-30`](spec/decisions.md) is resolved, any
report or `params_*.json` from this pipeline must be treated as
potentially containing secrets, and handled accordingly before sharing.

### 16. Provenance is captured per run.

Tool versions, fully-resolved parameters, and a workflow timestamp are
captured and rendered into every report
([spec/python/p6-report.md §3](spec/python/p6-report.md)). Rule 15 takes
precedence where the two are in tension: provenance must not come at the
cost of leaking a secret — fix the filtering, not the capturing.

### 17. Reproducibility across laptop, HPC, and Azure Batch is a backend
### abstraction, never an assumption of a shared filesystem.

The same code runs on all three by selecting a cache backend (SQLite /
Azure Blob), a throttle backend (SQLite / Redis), and a vault backend
(local file / Azure Key Vault) per environment
([spec/deployment.md §1](spec/deployment.md)). A change that only works
because a filesystem happens to be shared is a defect, not a feature.

### 18. When in doubt, favour conservative, auditable reporting.

A confident-looking result built on thin evidence is worse than a
correctly-qualified uncertain one. Prefer an explicit `NA`/`ERR` flag over
a suppressed section; prefer surfacing a single-source-publication caveat
over a clean-looking report; prefer a versioned config value over a
hardcoded threshold. Every tie-break in this codebase resolves in favour
of the analyst being able to see *why* a claim is or isn't supported.

---

## Governing meta-rule: spec before code

From this point on, **`spec/` is the source of truth**. When the code and
the spec disagree, the correct fix is almost always to change the code to
match the spec — not the reverse. A pull request that changes observable
behaviour without updating the matching `spec/` file is incomplete,
exactly as if it shipped without a test. The only exception is fixing a
spec file that is itself wrong (a transcription error, not a behaviour
decision) — that is a spec-only change and needs no code change.

## Amendment procedure

- **Hard constraints (1–4):** change requires explicit sign-off from the
  project owner. Update this file first, then every affected `spec/`
  file. No orphaned references.
- **Design principles (5–10):** change requires a pull request that
  updates this file, the affected `spec/` sections, and
  [decisions.md](spec/decisions.md) if it closes an open question. No
  orphaned references.
- **Engineering rules (11–18):** change requires a pull request with
  evidence (a passing test, a CI run, or a documented manual check) that
  the new rule is upheld and the old failure mode is closed.

This constitution describes `v1.5.0` as shipped, including where it falls
short of itself. Where a later version changes that, update this file in
the same change that introduces the difference — it must never go stale
silently.
