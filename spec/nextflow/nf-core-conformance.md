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

## 0. One thing this pipeline does follow: reusing `nf-core/modules`

`modules.json` shows `blast/blastdbcmd`, `blast/blastn`, `fastme` and
`mafft/align` were installed from the shared `nf-core/modules` registry at
pinned commits (`installed_by: ["modules"]`), rather than hand-written —
exactly what the [Design Proposal](../../../Design%20proposal%20-%20WF2%20Taxonomic%20Assignment%20-%20FINAL.pdf)
suggested ("Nf-core has an existing BLAST module that can be utilized for
running BLAST locally," §2.1). This is correct nf-core practice, not a
finding.

## 1. Declared opt-outs (not defects)

| Skipped feature | What it would have added |
|---|---|
| `multiqc`, `fastqc` | Sequencing-QC tooling; not applicable — this pipeline doesn't process raw reads. |
| `igenomes` | nf-core's shared reference-genome config; not applicable — reference data here is BLAST Core Nt / BOLD / taxdump, provisioned per `deployment.md §4`. |
| `github` | nf-core's GitHub community templates (issue/PR templates, `CONTRIBUTING.md`, `.dockstore.yml`) and, per `.nf-core.yml`'s `files_exist` lint exemptions, the nf-core CI workflows `awstest.yml`/`awsfulltest.yml`. This is additional, direct evidence for the already-known CI-coverage gap (`decisions.md D-41`): the nf-core-standard linting/AWS-test CI jobs were never just forgotten — they were declared out of scope at template generation, alongside `linting.yml`/`branch.yml`. |
| `is_nfcore` | The badges/links/metadata that mark a pipeline as an official nf-core release (it isn't one). |
| `codespaces`, `vscode` | GitHub Codespaces / VS Code devcontainer config. |
| `adaptivecard`, `slackreport` | Automated run-completion notifications to Teams/Slack. |

Source for what each `skip_features` entry disables:
[nf-core pipeline file structure](https://nf-co.re/docs/developing/pipelines/template-files).

## 2. Undeclared divergences (real findings)

### 2.1 Error handling: blanket `ignore`, no retry

nf-core's own template `conf/base.config` — generated into every
nf-core-derived pipeline, including this one, before any manual edits —
ships this default:

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

(Source: [`nf-core/tools` pipeline template, `conf/base.config`](https://github.com/nf-core/tools/blob/master/nf_core/pipeline-template/conf/base.config).)

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
because of the inner-join report structure — silently drops that query's
report (`NF-D-003`). nf-core's canonical pattern exists specifically to
absorb this class of failure before giving up. This is not a style
preference: it is the direct mechanism by which `NF-D-003` manifests more
often than it would need to.

(The Nextflow reference docs confirm `ignore`'s own documented risk: "The
failure is logged... By default, the run exits with status `0`." —
[`errorStrategy` reference](https://docs.seqera.io/nextflow/reference/process/directives/error-strategy).
This pipeline does set `workflow.failOnIgnore = true`, so the exit-status
half of that risk is already mitigated — `NF-ER-002` — but the report
instead just goes missing, not immediately or especially the process exit code.)

| ID | Severity | Defect |
|---|---|---|
| NF-D-013 | Medium **(vs nf-core/Nextflow best practice)** | `errorStrategy` is a blanket `'ignore'`, applied globally with no `retry` tier and no `task.attempt` resource scaling, diverging from the nf-core template's default pattern (retry on transient-failure exit codes, `ignore` only as an explicit per-process opt-in label). [decisions.md `D-02`](../decisions.md) (closing `NF-D-003`) should consider adopting the retry pattern, not only a better join. |

### 2.2 No resource-label system; `NF-D-011`'s placeholder default has no safety net

nf-core's template also defines tiered labels (`process_low`: 2 cpu/12 GB/4 h;
`process_medium`: 6 cpu/36 GB/8 h; `process_high`: 12 cpu/72 GB/16 h;
`process_long`: time only, 20 h — all scaled by `task.attempt`) plus a
`check_max()` helper that caps any requested resource at the executor's
configured maximum, so a retry can't request more than the cluster
actually has. (Same source as §2.1.)

`conf/process.config` has neither labels nor a cap function — every
process gets a static, hand-picked `cpus`/`memory`/`time`, and the
un-overridden default is `1MB` memory (`NF-D-011`, already registered).
§2.1 and this are the same root cause: the pipeline never adopted the
template's resource-and-retry model at all, it only kept the config file
names. No new defect ID — this is additional grounding for `NF-D-011`,
not a separate finding.

### 2.3 `CHANGELOG.md` is template-standard but absent

The nf-core template generates a `CHANGELOG.md` ("changes for each
release") alongside `CITATIONS.md` and `LICENSE`; `.nf-core.yml` doesn't
list it under `skip_features` or any lint exemption, and `CITATIONS.md`
(filled in) and `LICENSE` (present) show the sibling template files were
kept. `CHANGELOG.md` itself does not exist in the repo. There is
consequently nowhere that records what changed between the 5
version-numbered release points (`deployment.md DEP-020`) — someone
auditing "what's different since `v1.5.0`" has only `git log`.
(Source: [nf-core pipeline file structure](https://nf-co.re/docs/developing/pipelines/template-files).)

| ID | Severity | Defect |
|---|---|---|
| DEP-D-009 | Low **(vs nf-core best practice)** | `CHANGELOG.md`, a standard nf-core template file not listed under any `skip_features`/lint exemption, is absent from the repo; no human-readable release history exists alongside the five version locations in `DEP-020`. |

### 2.4 No per-module `meta.yml` — including the four modules installed *from* `nf-core/modules`

nf-core's module specification states a module "MUST have a `meta.yaml`
[`meta.yml`] in the same directory as the module `main.nf`," documenting
its tools, inputs, outputs and meta-map contents.
(Source: [nf-core module documentation spec](https://nf-co.re/docs/specifications/components/modules/documentation).)

This is not a question of whether that rule binds a local, hand-written
module (where it would be only a recommendation): `blast/blastdbcmd`,
`blast/blastn`, `fastme` and `mafft/align` (§0) were installed from the
nf-core/modules registry itself, where every module ships with a
`meta.yml` (and usually `environment.yml`, `tests/`) alongside `main.nf`.
Each of those four directories here contains **only** `main.nf` — no
`meta.yml`, `environment.yml` or `tests/`. Either they were stripped after
installation or copied in a way that dropped them; either way, the
metadata that `nf-core modules install` would have brought in is gone,
and `nf-core modules update` would have nothing to diff against. The
pipeline's own local-only modules (`extract/*`, `evaluate/*`, `validate/*`,
`report`, `bold/search`) never had `meta.yml` to begin with, which *is*
only a recommendation for those.

| ID | Severity | Defect |
|---|---|---|
| NF-D-014 | Low **(vs nf-core best practice)** | None of the four modules installed from the `nf-core/modules` registry (`blast/blastdbcmd`, `blast/blastn`, `fastme`, `mafft/align`, per `modules.json`) retain their `meta.yml` (or `environment.yml`/`tests/`); only `main.nf` is present. This pipeline's local-only modules never had one, which is a lesser, recommendation-level gap by comparison. |

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
`CHANGELOG.md` (absence), `modules/**/main.nf` (absence of `meta.yml`),
cross-checked against the nf-core/Nextflow documentation cited inline
above (fetched during derivation, not from memory). See
[README.md § Version](../README.md#version) for the exact commit.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
