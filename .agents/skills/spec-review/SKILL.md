---
name: spec-review
description: Review this repository's spec/ against code changes since a saved Git commit or a user-specified point in time. Write an evidence-based differences report and review checkpoint, leaving spec-correction-versus-bug decisions to the user.
---

# Incremental specification review

Review the repository's `spec/`, implementation, tests and configuration together.
This is repository-specific; it does not require feature-local `spec.md`, `plan.md`
or `tasks.md`, and does not invoke the standard speckit-analyze prerequisite script.

Invocation examples (natural-language arguments, not a separate executable CLI):

- `$spec-review` — continue from the saved checkpoint through checked-out HEAD.
- `$spec-review from 3339050 through main` — review an explicit commit range.
- `$spec-review since 2026-11-13 through main` — resolve the date to a commit.
- `$spec-review since PR #329` — use that PR's merge/squash commit as the base.

## Outputs and authority

- State: `spec/reviews/state.json`.
- Report: `spec/reviews/YYYY-MM-DD-<target-sha12>.md`; add a numeric suffix if that
  path already exists. Use the user's timezone for report dates.
- Use [assets/report-template.md](assets/report-template.md) for reports.
- Only write review reports and state during a review. Do not correct specs,
  code, tests, baselines, the constitution, or task lifecycle files. Do not create
  tasks or implement fixes unless the user separately requests those actions.
- Describe disagreements without assuming current code is correct. The user
  decides `spec correction`, `implementation bug`, `both`, or `no change`.
  A proposed interpretation is separate from the user's recorded decision.
- A completed review means the change range has been examined, not that the spec
  matches the code or that outstanding findings are approved/resolved.

## Establish the comparison

1. Follow repository `AGENTS.md`; first check branch and working-tree status.
   Read `spec/reviews/state.json`, its last report, and every pending report.
   Read `spec/README.md` for declared provenance and `CONSTITUTION.md` for project
   rules. Do not treat `.specify/memory/constitution.md` scaffold text as adopted
   principles. Follow constitution conflicts through to findings; do not silently
   change the principles to fit implementation.
2. Resolve a fixed target commit: user-specified target, otherwise checked-out
   `HEAD`. Record its full SHA, branch and whether remote freshness was verified.
   If the user requests current remote main, verify the remote ref first. Do not
   silently use an old local ref, switch branches, or reset the user's checkout.
3. Choose the base in this order:
   - User's explicit commit/tag/merged PR reference/date.
   - `last_reviewed_commit` from state.
   - `bootstrap_base_commit` from state.
   - The exact commit declared in `spec/README.md` (record its source).
   If none is available, ask for the starting point. A missing checkpoint is not
   permission to claim that today's HEAD has already been reviewed.
4. Resolve commit references to full SHAs. For a date, establish the user's time
   and timezone (a date alone means end of that local day), resolve the last
   first-parent commit of the target history at/before that instant, and report
   the exact selected commit. For a merged PR, identify the actual merge/squash
   commit from Git or available PR metadata, not a guess from the PR number.
5. Check that base and saved checkpoint objects exist and are ancestors of the
   target using `git merge-base --is-ancestor`. If objects are unavailable, obtain
   the missing history when permitted or report the limitation. If histories
   diverge, do not silently substitute a merge-base or advance the checkpoint:
   ask whether to use an explicit new baseline or review the full target history.
6. The base is exclusive and target inclusive: `base..target`. Inspect full-range
   history, not only first-parent commits, so merged branches are included. Record
   net file changes with rename/deletion detection and examine individual commits
   where intermediate changes/reverts explain intent. Compare code and specs from
   the same target revision, using `git show`/`git diff` if it differs from checkout.
   The checkpoint tracks the target commit, not the later commit saving this report.

Uncommitted implementation/spec/config/test changes cannot be represented by a
Git checkpoint. Exclude them explicitly and read committed target content, or
review them as a separately labelled working-tree supplement with no checkpoint
advancement. Do not overwrite user edits to existing review files/state. If HEAD
moves during the review, keep the recorded target fixed; never claim the new HEAD
was examined without reviewing the added range.

## Review the range

Build a change inventory covering all changed paths/commits. Group generated
fixtures, vendored content, documentation-only changes and related files when
helpful, but record each group's paths and disposition. An unchanged relevant
spec file must still be read when changed behavior falls within its scope.
Changes only to `spec/reviews/` are review bookkeeping: account for them as such,
not as production behavior changes or a reason to repeat the previous audit.

For each behavior area:

- Compare implementation, CLI/schema/config defaults, observable outputs, error
  handling and tests with the relevant requirement IDs and related spec pages.
- Follow cross-cutting changes into consumers and shared rules: workflow branches,
  input validation, report contracts, flags, container selection, CI invocation,
  reference data and test inventories. Check spec-to-spec contradictions too.
- Identify both missing new behavior and stale claims that behavior/tests are
  absent. Distinguish a missing test from a test merely omitted by the spec.
- Read task/PR rationale as supporting evidence, not proof that behavior is
  approved. Planned tasks describe future work, not currently shipped behavior.
- Preserve disagreements already recorded as known open defects; do not report
  them as new regressions without evidence. Link to the existing ID and record
  whether the changed code affects it. Recognize already-updated specs as aligned.
- Separate observed facts from hypotheses. A successful test or existing fixture
  does not establish intended correctness. Do not run expensive/live integration
  tests solely for this review; use read-only evidence unless execution was
  requested or a small relevant check is needed and permitted. Record checks
  actually run, unavailable evidence and limits on verification.

Report every material discrepancy found. Group related manifestations, but do not
hide findings behind a fixed maximum. An exhaustive claim means every changed
area has a disposition, not that every line of the whole repository was proved
correct. An explicit partial review must list unexamined paths and cannot advance
the global checkpoint.

## Write findings for user review

Use plain language: explain what the spec promises, what the code does, and why
that difference matters. Include concrete examples where useful. Keep requirement
IDs and exact file paths/line numbers as evidence, with the full target SHA so
locations can be recovered after files change. Capture the relevant old behavior
at the base when it establishes when a discrepancy appeared.

Give new findings stable IDs `SR-<target-sha12>-NNN`. Each finding records:

- Severity/impact and affected function/artifacts.
- Spec claim, implemented behavior, supporting evidence and introducing commit
  when established. Use `unknown` rather than inventing an origin.
- Suggested options: correct the spec if implementation is intended; fix code if
  the spec is intended; or resolve a conflict in both. Explain the tradeoff.
- `User decision: pending`, `Decision evidence: none`, and `Resolution: open`.
  Do not preselect a classification or treat merged code as approval to change
  normative requirements. Explicit constitution conflicts are critical and need
  owner resolution, not automatic weakening of the constitution.

Carry forward every unresolved finding from pending reports, with its original
ID and link. Recheck relevant findings when their area changes. If code/spec now
appears aligned, record `appears addressed; verification/user decision pending`
unless existing user instructions authorize a resolution and evidence supports it.
A decision of “implementation bug” does not mean the bug has been fixed.

The report must contain a change-coverage inventory with `aligned`, `finding`,
`no spec impact`, or `not examined` for each changed area, including rationale
for omissions. For `base == target`, say no new commits and still list pending
findings; do not manufacture a fresh full review of unchanged behavior.

## Save the checkpoint without losing pending work

Write the report first, verify evidence paths/IDs and inventory, then update
state atomically (write a sibling temporary JSON file and rename it). Preserve
unrelated state fields and user decisions.

Advance `last_reviewed_commit` only if:

- All relevant changes in the range were examined; there are no unexamined groups
  or missing evidence that prevents review completion.
- The report covers committed target content, not a working-tree supplement.
- It continues the saved checkpoint (or starts earlier), with no gap. A user-
  specified later base can produce a report but must not silently skip the
  interval between the saved checkpoint/bootstrap and that base.
- The target does not move the checkpoint backwards or into divergent history.

For a complete contiguous review, set `last_reviewed_commit`,
`last_completed_report`, and `last_completed_at` to the target/report/date.
For a partial or gapped review leave those fields unchanged. In either case,
record `last_attempt_report` and add any report with open findings to
`pending_reports`. Pending user classification does not block recording that a
range was reviewed: it blocks resolving those findings. Keep pending reports
until every finding has a recorded user disposition and any required fix has
verification evidence. No automatic assumption that absence from the next diff
means an old finding is resolved.

If state does not exist, create schema version 1 using the fields in this
repository's initial state file, with a provenance-backed bootstrap base and
null completed-review fields. If state is invalid or has an unknown schema
version, report the problem and preserve it rather than resetting history.

Finish with report/state links, base and target, whether the checkpoint advanced,
counts of new/carried findings and any unexamined work. Ask the user to classify
the findings; do not ask permission merely to write the requested review report.
Creating a remediation task or applying fixes is a separate action.
