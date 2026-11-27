# Taxodactyl specification

Specification of `qcif/taxodactyl`, derived from the source code — see
**Version** below for exactly which commit. Documentation (`README.md`,
`docs/`) and the original Design Proposal for Development of a
Taxonomic Assignment Pipeline (QCIF, 2024-11-29) were used only as a cross-check; where the code
differs from docs, the code is described and the difference is logged as
a defect. Where the code differs from the Design Proposal, that is a gap
against the project's *original intent* rather than an internal
contradiction, and is logged and labelled as such wherever it applies.

Start with **[../CONSTITUTION.md](../CONSTITUTION.md)** — the
non-negotiable principles this spec and every future change are held to.

## Version

This spec describes `main` at commit **`59d0e12`** (2026-11-26) — **not**
a clean checkout of the `v1.5.0` tag (`640df66`, 2026-07-10). Its version
files read `1.5.1`, but no `v1.5.1` git tag or `v1.5.1` container image
exists yet; between releases the pipeline runs the moving
`neoformit/taxodactyl:main` image (`DEP-011`, `DEP-D-014`).

```
git log --oneline v1.5.0..59d0e12
```

It was derived in steps. The bulk was derived from `edaacae`
(2026-09-01, `v1.5.0` + 20 commits) and brought forward to `3339050`
(2026-10-21) by reviewing the seven commits in between:

| Commit | Change | Spec updated |
|---|---|---|
| `cd6e10d` | Rank taxonkit `name2taxid` results (#316) | [p2-extract-taxonomy.md §3.2](python/p2-extract-taxonomy.md) |
| `a24581f` | nf-test CI workflow for GitHub runner (#315); `HOME` exported to every task | [tests.md](tests.md), [nextflow/config-profiles.md §5](nextflow/config-profiles.md) |
| `2decc0c` | GBIF queries moved to the Catalogue of Life backbone (#313); `cloudgene.yml` re-added as a symlink | [p5-db-coverage.md](python/p5-db-coverage.md), [reference-data.md §2.2](reference-data.md), [deployment.md](deployment.md) |
| `b0be80b` | Selenium `flex` tolerance (#320) | [tests.md §4](tests.md) |
| `0b63e39` | Report BLAST-hits modal shows every HSP | [p6-report.md §2a](python/p6-report.md) |
| `2e024f6` | `ß-tub` locus key corrected to `β-tub` | [contracts/loci.md](contracts/loci.md) |
| `3339050` | Metadata CSV encoding repair and `ß` auto-correction (#326, #327); nf-schema no longer reads the CSV; `cloudgene.yml` removed; version bumped to `1.5.1` | [python/p0-validation.md](python/p0-validation.md), [contracts/inputs.md](contracts/inputs.md), [services/input-validation.md](services/input-validation.md), [deployment.md](deployment.md), [nextflow/workflow.md](nextflow/workflow.md) |

The spec was committed at `7aedd0b` (2026-11-13). Since then, task PRs
have updated the spec in the same commit as the code (spec-driven
development). The commits below changed behaviour without updating the
spec at the time; the spec was brought forward to `59d0e12` for them in
one pass, by reviewing every non-task commit in `7aedd0b..59d0e12`:

| Commit | Change | Spec updated |
|---|---|---|
| `48dc4e8`, `954d470` | `build-main.yml` pushes `neoformit/taxodactyl:main`; configs reference `:main` between releases | [deployment.md](deployment.md) DEP-011, DEP-024, `DEP-D-014`; [containers.md](containers.md); `DEP-D-013` removed |
| `ef96c8f` | Database coverage mode, `--coverage_taxa` (#323); locus `' gene'` suffix resolved | [nextflow/workflow.md §6](nextflow/workflow.md), [nextflow/processes.md §2a, §13, §14a](nextflow/processes.md), [nextflow/params.md](nextflow/params.md), [nextflow/config-profiles.md](nextflow/config-profiles.md), [python/p0-validation.md §5a](python/p0-validation.md), [python/p5-db-coverage.md §2.1](python/p5-db-coverage.md), [python/p6-report.md §1a](python/p6-report.md), [python/modules/config.md](python/modules/config.md), [python/modules/flags.md](python/modules/flags.md), [contracts/inputs.md §4](contracts/inputs.md), [contracts/outputs.md](contracts/outputs.md), [contracts/query-folder.md](contracts/query-folder.md), [overview.md](overview.md), [architecture.md](architecture.md), [tests.md](tests.md); `P5-D-006`, `CFG-D-003` removed; `NF-D-021` added |
| `39777ff` … `f778535` | nf-test CI moved to the self-hosted runner, called by `build-pr.yml` for every PR (with a PR-built image), weekly; run files kept on the runner | [tests.md](tests.md) TST-024, `TST-D-001` rewritten, `TST-D-002` added; [deployment.md](deployment.md) DEP-025; [decisions.md](decisions.md) D-41 |
| `9da958a` | `TAXODACTYL_IMAGE` overrides the analysis image | already in [nextflow/config-profiles.md](nextflow/config-profiles.md); [deployment.md](deployment.md) DEP-026 |
| `fa8ad21` | Root `testkit.py` symlink removed | [tests.md](tests.md) |

Where it says "the spec version" or quotes footer provenance, it means
**this commit**, not the `v1.5.0` tag. `main` will advance further;
re-verify against current `main` before trusting this spec on anything
newer commits may have touched.

Use this spec for spec-driven development: change the spec first, then
the code; cite requirement IDs (e.g. `NF-WF-061`) in tasks, commits and
tests.

## Conventions

- **Requirement IDs** — `<AREA>-<SECTION>-<nnn>`; never reused. MUST /
  SHOULD / MAY per RFC 2119.
- **Defects** — `*-D-nnn`: places where the code contradicts what its own
  structure or interfaces imply. A defect is a backlog item; it does not
  redefine the requirement.
- **Open questions** — end of each file.

## Layout

```
spec/
├── README.md              this file
├── overview.md            purpose, scope, actors, glossary
├── architecture.md        layers, interface, per-query model, design properties
├── nextflow/              workflow, processes, params, config-profiles, error-handling
├── python/                p0-validation … p6-report (+ p1-bold-search,
│                          blast-vs-bold)
│   └── modules/           config, throttle, cache, errors, secrets, flags
├── contracts/             query-folder, filenames, inputs, hits, candidates,
│                          coverage-and-sources, loci, outputs
├── services/              input-validation
├── tests.md
├── deployment.md
├── containers.md           detailed companion to deployment.md §2–3
├── reference-data.md       detailed companion to deployment.md §4
├── defects.md             every bug found, by severity
└── decisions.md           open questions needing an owner
```

## Status

All areas drafted from code. Not yet done: verifying by execution the
items marked *to confirm* in [defects.md](defects.md), and reviewing each
spec with the code owner.

## Defects

All bugs found are collected in **[defects.md](defects.md)** (severity-ranked,
with status). Module specs keep a local table under the same IDs.
