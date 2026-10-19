# Taxodactyl specification

Specification of `qcif/taxodactyl`, derived from the source code — see
**Version** below for exactly which commit. Documentation (`README.md`,
`docs/`) and the original [Design Proposal for Development of a
Taxonomic Assignment Pipeline](../../Design%20proposal%20-%20WF2%20Taxonomic%20Assignment%20-%20FINAL.pdf)
(QCIF, 2024-11-29) were used only as a cross-check; where the code
differs from docs, the code is described and the difference is logged as
a defect. Where the code differs from the Design Proposal, that is a gap
against the project's *original intent* rather than an internal
contradiction, and is logged and labelled as such wherever it applies.

Start with **[../CONSTITUTION.md](../CONSTITUTION.md)** — the
non-negotiable principles this spec and every future change are held to.

## Version

This spec was derived from `main` at commit `edaacae` (2026-09-01) — **not**
a clean checkout of the `v1.5.0` tag (`640df66`, 2026-07-10). That commit
is `v1.5.0` plus 20 further commits already merged to `main`, none of
them reverted or superseded as of the derivation date (2026-09-23):

```
git log --oneline v1.5.0..edaacae
```

Everywhere this spec says "v1.5.0" (container tags, version strings
quoted from `conf/manifest.config`, footer provenance lines) it means
**this commit**, not the tag. If you check out the `v1.5.0` tag itself to
verify a requirement against source, expect it to be missing at least
the 20 commits above — that is not a spec error. `main` has very likely
advanced further since 2026-09-01; re-derive (or re-verify) against
current `main` before trusting this spec on anything the newer commits
may have touched.

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
│   └── shared/            config, throttle, cache, errors, secrets, flags
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
