# Taxodactyl specification

Specification of `qcif/taxodactyl` **as implemented in v1.5.0**, derived
from the source code. Documentation (`README.md`, `docs/`) was used only
as a cross-check; where they differ, the code is described and the
difference is logged as a defect.

Start with **[../CONSTITUTION.md](../CONSTITUTION.md)** — the
non-negotiable principles this spec and every future change are held to.

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
