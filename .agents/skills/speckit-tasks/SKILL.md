---
name: "speckit-tasks"
description: "Generate an actionable task brief using the repository's numbered tasks/ convention, based on available design artifacts."
metadata:
  author: "github-spec-kit"
  source: "templates/commands/tasks.md"
---


## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Planning scope and implementation authorization

Invoking this skill creates or revises a task brief; it does **not** authorize
implementation. Limit changes to planning artifacts and lifecycle indexes.
Inspect code/tests read-only as needed. Do not edit application code, test
code, workflow channels, fixtures or baselines, or start implementation via
another skill, agent or extension hook unless the user explicitly requests
implementation. A request to add something **to the task**, an active task
status, an existing implementation branch, or approval of a testing strategy
is not permission to implement it.

Record `Implementation authorization: pending explicit user instruction` for
new scope unless the user has explicitly authorized that scope in the current
conversation. Keep authorization scoped: an earlier request to implement an
older task revision does not authorize newly discussed changes. An explicit
request such as “implement task 04” or invocation of `speckit-implement`
authorizes that implementation, subject to any stated limits. Do not ask
again for authorization already supplied for the same scope.

Task-planning hooks obey this boundary too: if a hook would implement code or
change test expectations, leave that action pending and explain why rather
than running it as an automatic consequence of planning.

## Required testing decision

For every task creation or revision, assess the relevant tests, then ask the
user what they want done about testing **before settling the testing plan**.
Do not silently choose automatic tests, manual drift review, or both. If the
user has already explicitly supplied the testing choice for this scope, use
and record it without asking the same question again. A materially changed
test scope needs a new decision; routine clarification does not revoke a
choice already given.

Briefly name the affected suites and likely changes, then ask a concise
question that distinguishes these responsibilities:

- Writing or modifying automated tests and running existing checks.
- Reviewing output drift and changing snapshots, flags or Selenium fixtures.

Offer a mixed approach (agent implements agreed automated tests; user reviews
drift), user-owned testing/review, or a per-suite allocation. The user may
choose any combination; test creation and manual drift review are not mutually
exclusive. Do not imply that allowing automated tests permits baseline updates.

Record the answer in `## Testing decision`: affected suites, who implements
new assertions, who runs checks, who reviews drift, who may update expected
results, and the scope/date of the decision. Until answered, mark the decision
**pending user input**. Continue independent planning, but do not finalize
that choice or implement dependent tests/fixtures. No reply is not consent.
The testing decision is separate from implementation authorization.

## Repository Customization (local): Task Brief Convention

This repository keeps task briefs directly under the top-level `tasks/`
directory, following the convention used by `qcif/daff-mito-assembly`:

- Active task briefs are numbered files named `tasks/<NN>_<short_name>.md`.
- `tasks/active.md` lists the active task brief basenames, one per line.
- Completed briefs move to `tasks/completed/`; shelved briefs move to
  `tasks/shelved/`.
- Do not create generated task files inside a feature directory under
  `spec/`, `specs/`, or `.specify/`.
- If `tasks/`, `tasks/active.md`, `tasks/completed/`, or `tasks/shelved/`
  is missing, create the needed directory or file. Empty lifecycle directories
  may use `.gitkeep`.
- Preserve existing task numbering. Choose the next unused numeric prefix by
  inspecting active, completed, and shelved task filenames.
- When creating a task, use its lifecycle status to place it correctly:
  `active` tasks belong in `tasks/active.md`; `planned` or backlog tasks belong
  in `tasks/todo.md`; completed and shelved tasks belong in their respective
  directories. Do not alter unrelated entries.

The generated artifact is a task brief, not a Spec Kit `tasks.md` checklist.
The repository convention takes precedence over the generic Spec Kit template
when both are present.

## Pre-Execution Checks

**Check for extension hooks (before tasks generation)**:
- Check if `.specify/extensions.yml` exists in the project root.
- If it exists, read it and look for entries under the `hooks.before_tasks` key
- If the YAML cannot be parsed or is invalid, do not skip silently: tell the user that `.specify/extensions.yml` could not be read (include the parser error) and that no hooks were checked, including any mandatory (`optional: false`) hooks registered there, then continue normally
- Filter out hooks where `enabled` is explicitly `false`. Treat hooks without an `enabled` field as enabled by default.
- For each remaining hook, do **not** attempt to interpret or evaluate hook `condition` expressions:
  - If the hook has no `condition` field, or it is null/empty, treat the hook as executable
  - If the hook defines a non-empty `condition`, skip the hook and leave condition evaluation to the HookExecutor implementation
- When constructing command invocations from hook command names, replace dots (`.`) with hyphens (`-`). For example, `speckit.git.commit` → `$speckit-git-commit`.
- For each executable hook, output the following based on its `optional` flag:
  - **Optional hook** (`optional: true`):
    ```
    ## Extension Hooks

    **Optional Pre-Hook**: {extension}
    Command: `/{command}`
    Description: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```
  - **Mandatory hook** (`optional: false`):
    ```
    ## Extension Hooks

    **Automatic Pre-Hook**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}

    Wait for the result of the hook command before proceeding to the Outline.
    ```
    After emitting the block above you MUST actually invoke the hook and wait for it to finish before continuing. Run it the same way you would run the command yourself in this agent/session (the invocation may differ from the literal `{command}` id shown above, e.g. a skills-mode agent runs it as `/skill:speckit-...` or `$speckit-...`). Emitting the block alone does not run the hook.
- If no hooks are registered or `.specify/extensions.yml` does not exist, skip silently

## Outline

1. **Setup**: Inspect the top-level `tasks/` directory and determine the next unused numeric task prefix. Check `.specify/extensions.yml` before generation. If an active Spec Kit feature directory is configured, run `.specify/scripts/bash/setup-tasks.sh --json` and use its documents. If setup fails because no feature directory exists, continue using the repository's existing `spec/` documents and state that fallback in the task brief; do not create a synthetic `feature.json`, `spec.md`, or `plan.md` merely to satisfy the script.

2. **Load design documents**: Read from FEATURE_DIR when available:
   - **Required**: plan.md (tech stack, libraries, structure), spec.md (user stories with priorities)
   - **Optional**: data-model.md (entities), contracts/ (interface contracts), research.md (decisions), quickstart.md (test scenarios)
   - **IF EXISTS**: Load `.specify/memory/constitution.md` for project principles and governance constraints
   - Note: Not all projects have all documents. Generate tasks based on what's available. When using the fallback, inspect the relevant `spec/` files, existing source files, and tests directly.

3. **Execute task generation workflow**:
   - Load plan.md and extract tech stack, libraries, project structure
   - Load spec.md and extract user stories with their priorities (P1, P2, P3, etc.)
   - If data-model.md exists: Extract entities and map to user stories
   - If contracts/ exists: Map interface contracts to user stories
   - If research.md exists: Extract decisions for setup tasks
   - Generate tasks organized by user story (see Task Generation Rules below)
   - Generate dependency graph showing user story completion order
   - Create parallel execution examples per user story
   - Assess affected tests and expected-result changes using the test-impact guidance below
   - Obtain and record the required testing decision (or the explicit choice already supplied for this scope)
   - Validate task completeness (each user story has all needed tasks, independently testable)

4. **Generate the task brief** at the next numbered path under `tasks/`. Use this structure:
   - `# Task NN — <short title>`
   - `**Status:** active`
   - `**Priority:**` when known
   - `**Scope:**` and source-material references
   - `## Preconditions`
   - `## Objective`
   - `## Implementation`
   - `## Documentation and configuration` when relevant
   - `## Testing decision`
   - `## Validation`
   - `## Test impact and manual review`
   - `## Completion criteria`
   - `## Open decision` or `## Risks` when relevant
   Use exact repository file paths throughout. Then update the lifecycle index
   matching the task status: `tasks/active.md` for active work or
   `tasks/todo.md` for planned/backlog work.

## Mandatory Post-Execution Hooks

**You MUST complete this section before reporting completion to the user.**

Check if `.specify/extensions.yml` exists in the project root.
- If it does not exist, or no hooks are registered under `hooks.after_tasks`, skip to the Completion Report.
- If it exists, read it and look for entries under the `hooks.after_tasks` key.
- If the YAML cannot be parsed or is invalid, do not skip silently: tell the user that `.specify/extensions.yml` could not be read (include the parser error) and that no hooks were checked, including any mandatory (`optional: false`) hooks registered there, then continue to the Completion Report.
- Filter out hooks where `enabled` is explicitly `false`. Treat hooks without an `enabled` field as enabled by default.
- For each remaining hook, do **not** attempt to interpret or evaluate hook `condition` expressions:
  - If the hook has no `condition` field, or it is null/empty, treat the hook as executable
  - If the hook defines a non-empty `condition`, skip the hook and leave condition evaluation to the HookExecutor implementation
- When constructing command invocations from hook command names, replace dots (`.`) with hyphens (`-`). For example, `speckit.git.commit` → `$speckit-git-commit`.
- For each executable hook, output the following based on its `optional` flag:
  - **Mandatory hook** (`optional: false`) — **You MUST emit `EXECUTE_COMMAND:` for each mandatory hook**:
    ```
    ## Extension Hooks

    **Automatic Hook**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}
    ```
    After emitting the block above you MUST actually invoke the hook and wait for it to finish before continuing. Run it the same way you would run the command yourself in this agent/session (the invocation may differ from the literal `{command}` id shown above, e.g. a skills-mode agent runs it as `/skill:speckit-...` or `$speckit-...`). Emitting the block alone does not run the hook.
  - **Optional hook** (`optional: true`):
    ```
    ## Extension Hooks

    **Optional Hook**: {extension}
    Command: `/{command}`
    Description: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```

## Completion Report

Output path to generated task brief and summary:
- Task brief path and numeric task ID
- Active-index update path
- Scope and implementation summary
- Recorded testing decision (or pending question), implementation authorization,
  validation criteria, affected expected-output paths, and pending manual checks
- Parallel opportunities, if any
- MVP scope, if applicable
- Confirmation that the task follows the repository task-brief structure and uses exact file paths

Context for task generation: $ARGUMENTS

The task brief should be immediately executable: each implementation and validation item must be specific enough that an LLM can complete it without additional context.

## Task Brief Generation Rules

**CRITICAL**: The task brief MUST be organized around a concrete objective, implementation scope, validation evidence, and completion criteria. If the source specification contains user stories, preserve their priorities and independent test criteria in the brief, but do not force the output into a checklist template.

**New tests follow the explicit testing decision.** Feature requirements inform
the proposed plan, but do not replace asking the user how test implementation
and drift review should be handled. Assessing existing test impact is required;
it does not authorize creating tests or replacing expected results.

### Preserve bug detection; avoid test-hacking

Carry these requirements into each brief's testing/validation instructions
when automated test changes are in scope:

- Derive expected results from the agreed behavior and independently understood
  inputs. Do not calculate expectations with the production logic being tested
  or copy actual output into expected values merely to obtain a passing run.
- Preserve meaningful assertions about content, membership, ordering, boundaries
  and error behavior where relevant. Do not weaken or remove assertions, skip
  failing cases, broaden tolerances, or mock away the behavior under test just
  to make checks pass.
- Change an existing expectation only when the agreed contract changes or
  evidence establishes that the test was wrong. Explain that reason and retain
  coverage for the intended behavior. For a filename-only change, update path
  expectations while preserving content and scientific-result assertions.
- Treat failures as evidence to investigate. Distinguish implementation bugs,
  incorrect tests and environment/data issues; plan fixes within authorized
  scope and report unresolved failures instead of hiding them. Record checks
  actually run and their outcomes, including failures and skipped/unavailable
  checks. Passing checks do not replace pending manual review.

These constraints do not authorize test implementation or expected-result
updates. Preserve the explicit testing allocation and manual baseline-review
requirements below.

### Test impact and manual review

Inspect the checked-in CI workflows (including the requested runner), actual
suite commands and assertions before proposing test changes. Prefer extending
existing suites; do not scaffold a new nf-test scenario, flag case or Selenium
case merely because outputs change. Keep precise count/ID/sequence assertions
in scoped Python integration tests when they exercise the Python behavior;
workflow/browser tests cover their existing integration and presentation roles.
Do not assume the runner's label or which scenarios it executes.

For each task brief, inspect the relevant existing tests and include a concise
`## Test impact and manual review` section. If none are affected, state that
with a brief reason. Otherwise identify:

- Exact test, snapshot, expected-output and fixture paths; the behavior or
  fields likely to change; and why. Distinguish expected changes from possible
  changes that need evidence. Do not invent new expected values.
- Preparation the implementer should perform so results can be inspected:
  for example, required named process/workflow output channels, stable query
  keys, fixtures, comparison artifacts or report fields. Separate emitting a
  channel from publishing its files or routing them into scientific analysis.
- Automated checks the implementer can run, and tests/expected-result review
  owned by the user. In this repository, explicitly flag affected nf-tests
  and snapshots, flag baselines, and Selenium assertions/expected reports for
  **manual user review**. Record the agreed owner for running validation and changing baselines;
  proposing a manual review does not settle ownership without the testing decision.
- A concrete handoff: commands, input/reference-data versions, output locations,
  and what differences the user must inspect. Separate intended behavior
  changes from reference-data drift and suspected regressions.

Do not plan automatic snapshot acceptance, flag-baseline replacement or
Selenium fixture promotion merely to make tests pass. Plan observability
preparation and automated verification within the agreed testing scope. This
skill remains planning-only unless implementation is explicitly requested.
Manual review stays an explicit handoff requirement.
Record implementation status separately from manual validation status. Never
mark a manual check passed without user evidence, and retain pending checks
in outcomes/completion reporting. When manual acceptance is required for task
completion, keep it explicit rather than treating automated checks as a
substitute.

### Task Brief Format (REQUIRED)

Every generated brief MUST:

1. Use a numbered filename under `tasks/`.
2. State status and priority when known.
3. Name exact implementation, documentation, configuration, and test paths.
4. Separate implementation from validation evidence.
5. State completion criteria and any unresolved product decision.
6. Be detailed enough to execute without recovering context from the chat.
7. Identify test impact, required preparation, and ownership of manual review.
8. Record the explicit testing decision or pending user question, separately
   from authorization to implement.

### Task Organization

1. **From User Stories (spec.md)** - PRIMARY ORGANIZATION:
   - Each user story (P1, P2, P3...) gets its own phase
   - Map all related components to their story:
     - Models needed for that story
     - Services needed for that story
     - Interfaces/UI needed for that story
     - If tests requested: Tests specific to that story
   - Mark story dependencies (most stories should be independent)

2. **From Contracts**:
   - Map each interface contract → to the user story it serves
   - If tests requested: Each interface contract → contract test task [P] before implementation in that story's phase

3. **From Data Model**:
   - Map each entity to the user story(ies) that need it
   - If entity serves multiple stories: Put in earliest story or Setup phase
   - Relationships → service layer tasks in appropriate story phase
   - For each field with constraints in data-model.md (max length, nullable/required, enum values, validation rules), quote the constraint verbatim in the task description so it is not left to implementation-time discretion

4. **From Setup/Infrastructure**:
   - Shared infrastructure → Setup phase (Phase 1)
   - Foundational/blocking tasks → Foundational phase (Phase 2)
   - Story-specific setup → within that story's phase

### Phase Structure

- **Phase 1**: Setup (project initialization)
- **Phase 2**: Foundational (blocking prerequisites - MUST complete before user stories)
- **Phase 3+**: User Stories in priority order (P1, P2, P3...)
  - Within each story: Tests (if requested) → Models → Services → Endpoints → Integration
  - Each phase should be a complete, independently testable increment
- **Final Phase**: Polish & Cross-Cutting Concerns

## Done When

- [ ] Testing decision is recorded, or the brief clearly remains draft pending
      the user’s answer; do not claim the testing plan is finalized while pending
- [ ] Implementation authorization is recorded separately; planning has not
      triggered unrequested implementation

- [ ] Numbered task brief generated under `tasks/`
- [ ] The appropriate lifecycle index is updated (`tasks/active.md` for active
      work or `tasks/todo.md` for planned/backlog work)
- [ ] Extension hooks dispatched or skipped according to the rules in Mandatory Post-Execution Hooks above
- [ ] Completion reported with the task path, scope, validation criteria, and lifecycle status
