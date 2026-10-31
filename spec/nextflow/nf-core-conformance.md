# Reference: nf-core / Nextflow best-practice conformance

This pipeline was generated from the **nf-core pipeline template**
(`nf_core_version: 3.1.1`, per `.nf-core.yml`) but explicitly opted out of
being an official nf-core community pipeline:

```yaml
# .nf-core.yml
template:
  is_nfcore: false
  skip_features:
    - github
    - igenomes
    - is_nfcore
    - codespaces
    - multiqc
    - fastqc
    - adaptivecard
    - slackreport
    - vscode
```

That matters for how to read this file: a difference from the nf-core
template is not automatically a defect. Where the repo's own `.nf-core.yml`
*declares* a feature skipped, §1 below lists it as an intentional scope
decision, not a gap. Where the code diverges from nf-core/Nextflow norms
**without** a corresponding declaration, §2 treats it as a real finding —
each is grounded in a specific, fetched source, not general impression.

## 0. How the template was adopted, then diverged (from git history)

The template was generated on 2025-01-16 (`c3a2737`, "initial template
build from nf-core/tools, version 3.1.1"). Several nf-core pieces were
then **removed or replaced** over the following months. So most of §2 is
not "never adopted": those parts were in the repo, then dropped.

| What | Then | Now |
|---|---|---|
| `conf/base.config` (retry + `task.attempt` labels) | generated and included by default (`c3a2737`) | deleted 2025-06-23 (`be2ec57`); replaced by `conf/process.config` |
| `CHANGELOG.md` | generated (`c3a2737`) | deleted 2025-06-18 (`966b502`) |
| nf-core **modules** `blast/blastdbcmd`, `blast/blastn`, `fastme`, `mafft/align` | installed into `modules/nf-core/…` with `meta.yml` (`0626fb5`, 2025-03-14) — as the Design Proposal suggested ("Nf-core has an existing BLAST module that can be utilized", §2.1) | deleted 2025-05-20 (`e393a9c`); replaced next day by **local** rewrites at `modules/blast/…`, `modules/fastme`, `modules/mafft/align` (`7b6d96a`). These drop `meta`, the `process_*` labels and their own container directive, and BLASTN now emits XML with hard-coded megablast settings. `modules.json` still lists the removed modules (`NF-D-019`). |
| nf-core **subworkflows** `utils_nextflow_pipeline`, `utils_nfcore_pipeline`, `utils_nfschema_plugin` | installed | **still installed** under `subworkflows/nf-core/`, with `meta.yml`, and used — this is the one part still nf-core-managed |

## 1. Declared opt-outs (not defects)

| Skipped feature | What it would have added |
|---|---|
| `multiqc`, `fastqc` | Sequencing-QC tooling; not applicable — this pipeline doesn't process raw reads. |
| `igenomes` | nf-core's shared reference-genome config; not applicable — reference data here is BLAST Core Nt / BOLD / taxdump, provisioned per `deployment.md §4`. |
| `github` | nf-core's GitHub community templates (issue/PR templates, `CONTRIBUTING.md`, `.dockstore.yml`) and the nf-core CI workflows. `.nf-core.yml` exempts `awstest.yml`/`awsfulltest.yml` from the `files_exist` lint and `linting.yml`/`branch.yml`/`linting_comment.yml` from `files_unchanged`; none of those five exist. The repo's CI is instead its own: `unit-tests.yml` (push/PR), `build.yml` (release), and the manually-dispatched `nf-test.yml`/`mock-nf-test.yml` (`tests.md` TST-024). The nf-core linting job was declared out of scope, not forgotten. |
| `is_nfcore` | The badges/links/metadata that mark a pipeline as an official nf-core release (it isn't one). |
| `codespaces`, `vscode` | GitHub Codespaces / VS Code devcontainer config. |
| `adaptivecard`, `slackreport` | Automated run-completion notifications to Teams/Slack. |

Source for what each `skip_features` entry disables:
[nf-core pipeline file structure](https://nf-co.re/docs/developing/pipelines/template-files).

## 2. Undeclared divergences (real findings)

### 2.1 Error handling: blanket `ignore`, no retry

nf-core's own template `conf/base.config` — generated into every
nf-core-derived pipeline, including this one (`c3a2737`), and deleted
here in `be2ec57` (§0) — ships this default:

```groovy
process {
    cpus   = { 1    * task.attempt }
    memory = { 6.GB * task.attempt }
    time   = { 4.h  * task.attempt }
    errorStrategy = { task.exitStatus in ((130..145) + 104 + (175..177)) ? 'retry' : 'finish' }
    maxRetries = 1
    maxErrors  = '-1'
    // ...
    withLabel:error_ignore { errorStrategy = 'ignore' }
    withLabel:error_retry  { errorStrategy = 'retry'; maxRetries = 2 }
}
```

(Source: [`nf-core/tools` pipeline template, `conf/base.config`](https://github.com/nf-core/tools/blob/master/nf_core/pipeline-template/conf/base.config) on `master`. The 3.1.1 copy generated here, `git show c3a2737:conf/base.config`, differs only in retrying on `(130..145) + 104` and lacking the newer `process_low_memory`/`process_gpu` labels; it already had no `check_max()`.)

The template's default behaviour is: **retry** a task that failed with an
exit code typical of a transient resource problem (OOM-kill, timeout),
requesting more CPU/memory/time on each attempt (`task.attempt` scaling),
and only give up (`finish`) once `maxRetries` is exhausted. `ignore` is
available, but as an opt-in **label** (`error_ignore`) applied to specific
processes known to be safe to skip — not the global default.

`conf/process.config` instead sets, as the single global default applied
to every process on every executor:

```groovy
process {
    errorStrategy = 'ignore'
    cpus = 1
    memory = '1MB'
    time = '10m'
    // per-process cpus/memory/time overrides are static, not task.attempt-scaled
}
```

No process in this pipeline retries. A task that fails because it was
briefly throttled, hit a transient network error Python's own retry layer
didn't catch, or was killed for exceeding its (often placeholder, see
`NF-D-011`) memory limit gets exactly one attempt, is ignored, and —
because of the inner-join report structure — drops that query's report.
That suppression is itself deliberate
([CONSTITUTION.md](../../CONSTITUTION.md) rule 8), but nf-core's
canonical retry pattern exists specifically to avoid *needing* to make
that call in the first place for a purely transient failure — this is
not a style preference: adopting it would mean fewer queries ever reach
the point of losing their report over something that would have
succeeded on a second attempt.

It cannot be adopted verbatim, though. The template's fallback after
retries is `finish`, which stops the whole run, and "one query's failure
must never stop the others" is a DAFF-requested default (`NF-ER-001`,
CONSTITUTION rule 8). The compatible variant is to retry on the
transient exit codes with `task.attempt` scaling, then `ignore` instead
of `finish`.

(The Nextflow reference docs confirm `ignore`'s own documented risk: "The
failure is logged... By default, the run exits with status `0`." —
[`errorStrategy` reference](https://docs.seqera.io/nextflow/reference/process/directives/error-strategy).
This pipeline does set `workflow.failOnIgnore = true`, so the exit-status
half of that risk is already mitigated — `NF-ER-002` — but the report
still just goes missing, with nothing published naming which query it
was, `OUT-D-002`.)

| ID | Severity | Defect |
|---|---|---|
| NF-D-013 | Medium **(vs nf-core/Nextflow best practice)** | `errorStrategy` is a blanket `'ignore'`, applied globally with no `retry` tier and no `task.attempt` resource scaling. This diverges from the nf-core template's default pattern (retry on transient-failure exit codes, `ignore` only as an explicit per-process opt-in label), which this repo had until `be2ec57` deleted `conf/base.config`. [decisions.md `D-19`](../decisions.md) should consider retry-then-`ignore` (not the template's retry-then-`finish`, which would break the DAFF-requested isolation), independent of whether a run-level summary (`D-02`) is also added. |

### 2.2 No resource-label system; `NF-D-011`'s placeholder default has no safety net

nf-core's template also defines tiered labels (`process_low`: 2 cpu/12 GB/4 h;
`process_medium`: 6 cpu/36 GB/8 h; `process_high`: 12 cpu/72 GB/16 h;
`process_long`: time only, 20 h — all scaled by `task.attempt`), so a
process gets a realistic default just by carrying a label. (Same source
as §2.1.)

`conf/process.config` has no labels — every process gets a static,
hand-picked `cpus`/`memory`/`time`, and the un-overridden default is
`1MB` memory (`NF-D-011`, already registered). The labels were in the
generated `conf/base.config` and went with it in `be2ec57` (§0); the
local module rewrites (`7b6d96a`) also dropped the `process_*` labels the
nf-core modules carried. §2.1 and this are the same root cause. No new
defect ID — this is additional grounding for `NF-D-011`, not a separate
finding.

Capping resources is **not** a divergence. nf-core/tools 3.0 [replaced
the old `check_max()` helper with Nextflow's native
`process.resourceLimits`](https://nf-co.re/blog/2024/tools-3_0_0). The
current template sets `resourceLimits` only inside its example `gitpod`
profile, leaving real caps to user/institutional configs — exactly what
this repo's `conf/profiles.config` does too.

### 2.3 `CHANGELOG.md` is template-standard but absent

The nf-core template generates a `CHANGELOG.md` ("changes for each
release") alongside `CITATIONS.md` and `LICENSE`; `.nf-core.yml` doesn't
list it under `skip_features` or any lint exemption, and `CITATIONS.md`
(filled in) and `LICENSE` (present) show the sibling template files were
kept. `CHANGELOG.md` itself was generated (`c3a2737`) and then deleted
on 2025-06-18 (`966b502`), and has not been restored. There is
consequently nowhere that records what changed between the 5
version-numbered release points (`deployment.md DEP-020`) — someone
auditing "what's different since `v1.5.0`" has only `git log`.
(Source: [nf-core pipeline file structure](https://nf-co.re/docs/developing/pipelines/template-files).)

| ID | Severity | Defect |
|---|---|---|
| DEP-D-009 | Low **(vs nf-core best practice)** | `CHANGELOG.md`, a standard nf-core template file not listed under any `skip_features`/lint exemption, is absent from the repo; no human-readable release history exists alongside the five version locations in `DEP-020`. |

### 2.4 No module has a `meta.yml`, and `modules.json` lists modules that were removed

nf-core's module specification states a module "MUST have a `meta.yaml`
[`meta.yml`] in the same directory as the module `main.nf`," documenting
its tools, inputs, outputs and meta-map contents.
(Source: [nf-core module documentation spec](https://nf-co.re/docs/specifications/components/modules/documentation).)

That rule is written for modules published to `nf-core/modules`; for a
pipeline's own local modules it is a recommendation. Every module here
is now local. The four nf-core modules (`blast/blastdbcmd`,
`blast/blastn`, `fastme`, `mafft/align`) were installed with their
`meta.yml` under `modules/nf-core/` (`0626fb5`), then deleted
(`e393a9c`) and replaced by local rewrites (`7b6d96a`, §0), which have
only `main.nf`. The other local modules (`extract/*`, `evaluate/*`,
`validate/*`, `report`, `bold/search`, `mock/blastn`, `prepare/*`) never
had one. Only the three nf-core subworkflows keep their `meta.yml`.

`modules.json`, however, still records those four as installed from
`nf-core/modules` at pinned SHAs, under `modules/nf-core/…` paths that
no longer exist. nf-core tooling (`nf-core modules list/lint/update`)
reads `modules.json`, so it reports or acts on modules that aren't there,
and anyone reading `modules.json` would conclude BLAST/MAFFT/FastME are
stock nf-core modules — they aren't (they no longer take `meta`, carry
no `process_*` label or container directive, and `BLAST_BLASTN` emits XML
with hard-coded megablast settings).

| ID | Severity | Defect |
|---|---|---|
| NF-D-014 | Low **(vs nf-core best practice)** | No module under `modules/` has a `meta.yml` (or `environment.yml`/`tests/`). For local modules that is a recommendation-level gap; it includes the four local rewrites of what were nf-core modules, whose original `meta.yml` was deleted with them (`e393a9c`). |
| NF-D-019 | Low | `modules.json` is stale: it lists `blast/blastdbcmd`, `blast/blastn`, `fastme` and `mafft/align` as installed from `nf-core/modules` at pinned commits, but `modules/nf-core/` was deleted in `e393a9c` and the modules that run are local rewrites (`7b6d96a`). nf-core tooling and human readers are both misled about where these modules come from. |

### 2.5 Channel naming: good conformance, one real bug, one minor note

nf-core documents two channel-naming conventions:

- **Pipeline-level** ([Contributing to existing pipelines](https://nf-co.re/docs/contributing/contributing_to_pipelines)): an initial process output is `ch_output_from_<process>`; a channel handed to its next consumer is `ch_<previousprocess>_for_<nextprocess>` (their example: `ch_fastqc_for_multiqc`).
- **Component-level, for subworkflows specifically** ([naming-conventions](https://nf-co.re/docs/specifications/components/subworkflows/naming-conventions)): `snake_case`, lowercase; `val_` prefix for a single-value input, `ch_` prefix for a multi-element input; **output channels named after the main output file, without a `ch_` prefix** (their example: emit `bam`, not `ch_bam`).

`workflows/taxodactyl.nf`'s report-facing channels — `ch_hits_for_report`,
`ch_candidates_for_report`, `ch_source_diversity_for_report` — are a close
match for the pipeline-level `_for_<nextconsumer>` idiom, with "report"
standing in for the next process. This is good, deliberate conformance,
not a gap: it decouples the plain computation-phase name (`ch_hits_files`,
used earlier for candidate extraction, unrelated to reporting) from the
report hand-off name, so a later internal rename only touches one line.
`NF-D-016` ([defects.md](../defects.md), Nextflow area — `ch_candidates_for_report`
bound twice, the first value silently discarded) is a bug *within* this
pattern, not a reason to abandon it: the fix
([decisions.md `D-46`](../decisions.md)) is to stop that one name from
being bound twice, not to merge the two-phase naming into one name.

One minor, lower-confidence note: the `emit:` block keeps the `ch_`
prefix on every output (`ch_hits_for_report`, etc.), where the
*component-level* convention above would drop it. That rule is written
for shared subworkflows specifically; it's not established that it's
meant to bind a pipeline's own top-level workflow `emit:` the same way,
so this is flagged as a style note, not a defect.

## 3. Not evaluated

This comparison covers configuration/process conventions (errors,
resources, release files, module docs, channel naming) because they're
where the `.nf-core.yml` record makes "declared vs. undeclared" checkable
with confidence. It does not cover nf-core's module/subworkflow code-style
conventions in depth beyond naming (e.g. the `versions.yml` emission
pattern) — a worthwhile follow-up, not done here.

---

## Provenance

**Initially derived from:** `.nf-core.yml`, `conf/process.config`,
`conf/profiles.config`, `modules.json`, `modules/**/main.nf` (absence of
`meta.yml`), `subworkflows/nf-core/**`, `.github/workflows/*.yml`, and
git history (`c3a2737`, `0626fb5`, `e393a9c`, `7b6d96a`, `966b502`,
`be2ec57`), cross-checked against the nf-core/Nextflow documentation
cited inline above (fetched during derivation, not from memory). See
[README.md § Version](../README.md#version) for the exact commit.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
