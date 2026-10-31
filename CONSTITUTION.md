# CONSTITUTION

**Project:** `qcif/taxodactyl` — High-confidence, evidence-based
taxonomic assignment of DNA sequences
**Status:** v1 · **Spec version:** `v1.5.0` + 27 commits (`3339050`, version files `1.5.1`) — see
[spec/README.md § Version](spec/README.md#version) for the full
explanation · **Companion:** [spec/](spec/)

This file distils the non-negotiable principles that govern every design
decision in this project. It is deliberately short. When `spec/` and this
file disagree, this file wins; `spec/` is updated to reconcile.

Every principle below is grounded in the **shipped codebase**, at the
commit noted in **Spec version** above, derived the same way as the rest
of `spec/` — by reading the code, not by aspiration. Where the codebase
itself falls short of a principle stated here, that is a **defect**
(tracked in [spec/defects.md](spec/defects.md)), not a reason to weaken
the principle. Where the codebase falls short of the *original product
intent* instead — the Design Proposal for Development of a Taxonomic
Assignment Pipeline (QCIF, 2024-11-29) — that is noted explicitly wherever it applies, since
it is a gap against intent, not against this constitution's own
principles.

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

### 2. The pipeline never asserts a final identification on its own authority — the analyst always reviews the evidence.

Every report, regardless of outcome, surfaces the strongest supportable
claim (if any) alongside every piece of corroborating and contradicting
evidence (flags, phylogeny/BIN diversity, database coverage, source
diversity) and an editable field for the analyst's own conclusion — this
is a structural part of every report, not something shown only when the
result is ambiguous
([spec/python/p6-report.md §2a.2](spec/python/p6-report.md): the
subjective textareas on tabs 2–5 and tab 5's analyst checklist; design intent stated
explicitly in the Design Proposal §4.1, "the reader will be prompted to
contribute their subjective conclusions based on the information
provided"). A high-confidence, single-species match is still presented as
evidence for the analyst to weigh, never as a verdict the analyst may
skip reviewing. Separately, above `max_candidates_for_analysis` selected
species, the pipeline skips source-diversity evaluation and provides a
genus-grouped identity boxplot for the analyst's subjective assessment;
it still retains the species-level candidates
([spec/python/p3-assign-taxonomy.md §6.4](spec/python/p3-assign-taxonomy.md)).
Analyst judgement is required in either case. A report that reads as an unqualified
identification, or that lets the analyst conclude without seeing the
corroborating evidence, is a defect against this constraint — not a style
choice.

### 3. Reference database choice is whole-run; locus is per-sample.

`--db_type` (`blast_core_nt` or `bold`) is one parameter for the entire
invocation — every query in a run searches the same reference database.
`locus` is declared per metadata row and constrained to the panel in
`scripts/config/loci.json`
([spec/nextflow/params.md](spec/nextflow/params.md),
[spec/contracts/loci.md](spec/contracts/loci.md)). Mixing BLAST and BOLD
queries requires two invocations, by design. **Gap against original
intent** (`P0-D-010`): the Design Proposal states BOLD mode is COI-only
("The BOLD database can only be used for query sequences at the COI
locus... locus is therefore not required for the BOLD workflow version",
§2.3 Workflow inputs); the shipped code does not enforce this — `--bold`
only relaxes locus validation to accept (almost) any value, with no
COI-specific check. [decisions.md `D-06`](spec/decisions.md) is open on
whether to add the constraint or keep the relaxed behaviour.

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

### 8. One query's failure must never stop other queries — and a missing report must be discoverable, not just inferred.

A Nextflow task failure for one query MUST NOT abort or block any other
query's processing: `process.errorStrategy` is `ignore` on every executor
(`NF-ER-001`), and `workflow.failOnIgnore` is `true` so the run still
exits non-zero overall even though siblings complete
([spec/nextflow/error-handling.md §1](spec/nextflow/error-handling.md)).
This part of the principle holds today.

Suppressing the report itself for a query whose evaluation didn't
complete is **deliberate**, not a defect: a report built on an
incomplete evaluation (no tree, no coverage data) risks exactly the
false-confidence rule 2 exists to prevent, and an analyst is expected to
notice the absence and repeat the analysis. What's missing is the
mechanism that makes that absence noticeable: there is today no run-level
summary of per-query outcome, so "notice the absence" means counting
reports against submitted samples, then digging in `<outdir>/errors/` to
find out why — nothing published states *which* queries got no report or
why. [decisions.md `D-02`](spec/decisions.md) is open on closing that gap
(`OUT-D-002`); until it is, treat the absence of a report as something an
analyst must actively check for, not something the pipeline will surface
on its own.

### 9. Locus panel and flag semantics are versioned config, not hardcoded.

`scripts/config/loci.json` (permitted loci + synonyms) and
`scripts/config/flags.csv` (flag values + explanation text) are the
single source of truth for two of the most report-visible behaviours in
the system. Editing report text for a flag is a config change, never a
template or code change.

### 10. Reference data is operator-provisioned, not pipeline-built.

Unlike a pipeline that assembles its own versioned, checksummed reference
bundle, Taxodactyl consumes BLAST Core Nt and taxdump as external paths
the operator supplies ([spec/deployment.md §4](spec/deployment.md)). This
is a deliberate scope boundary (these are large, centrally-maintained
resources unsuitable for per-pipeline bundling), but it is a weaker
provenance guarantee than a versioned bundle would give —
[decisions.md `D-33`](spec/decisions.md) is open on whether to tighten it.
BOLD, GenBank/NCBI Entrez and GBIF are a different category entirely:
live remote APIs queried at runtime (through the shared throttle/cache
layer), never provisioned as a local path at all — not a weaker version
of this principle, just outside its scope.

---

## Engineering rules

### 11. Every process runs in a container; every tag is pinned.

Every container that `conf/process.config` and `conf/azure.config`
assign, by label, by process name or as Azure's default, has an explicit
tag or digest — never `latest`
([spec/deployment.md §2](spec/deployment.md),
[spec/containers.md](spec/containers.md)). Two housekeeping processes fall
short of the first half of this rule: `PREPARE_INPUTS` (copies the inputs)
and `PREPARE_LOG` (publishes `run.log`) have no label and no container,
and `conf/process.config` sets no default, so on local and HPC profiles
they run in the host shell. Only under `-profile azure` do they get a
container, the pinned default `docker.io/library/ubuntu:22.04`
(`NF-D-020`). That gap, and the image's own reproducibility (floating
base, taxonkit from `latest`, `IMG-D-001`/`DEP-D-003`), are tracked as
defects against this rule, not exceptions to it.

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
CI-enforced: `nf-test` and Selenium now have a GitHub Actions workflow
(`.github/workflows/nf-test.yml`), but it runs only when triggered by
hand, not on push or PR. That gap is tracked, not accepted as permanent
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

This constitution describes the codebase as shipped at the commit noted
in **Spec version** above, including where it falls short of itself.
Where a later version changes that, update this file in the same change
that introduces the difference — it must never go stale silently.
