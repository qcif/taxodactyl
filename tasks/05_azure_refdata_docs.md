# Task 05 — Document reference-data staging from `daffstandard/refdata-wf2`

**Status:** active

**Priority:** Low (documentation drift; spec severity Low, defect `DEP-D-011`).

**Issue:** [#338 — Azure reference-data docs and .env.sample still describe the old daffpremium/refdata staging, not daffstandard/refdata-wf2](https://github.com/qcif/taxodactyl/issues/338)

**Scope:** Documentation, sample configuration and spec text only. Bring the
Azure operator docs, `.env.sample` and two display lines in
`deployment/azure/batch-helpers.sh` in line with the start task that already
runs in production. Since commit `edaacae`, that start task pulls Core Nt and
the taxdump anonymously from the public container `daffstandard/refdata-wf2`.
Do **not** change `deployment/azure/setup.sh.template`, `conf/azure.config`,
`deployment/azure/pool-setup.json.template` or any pipeline code. The
start-task *script* SAS token (`daffstandard/scripts/setup.sh?<SAS>`) is
still in use and must stay documented.

**Source material:** Issue #338 and the maintainer comment confirming the
design: all reference data is public, so it is served from a public blob
container. Also: `deployment/azure/setup.sh.template` (lines 13–20 and
144–181, the authority for current behaviour), `spec/deployment.md` §5 and
`DEP-D-011`, `spec/reference-data.md` §1.1 and `spec/defects.md`
(`DEP-D-011` row). No Spec Kit feature directory exists for this work, so
this brief is derived directly from those `spec/` files and the source.

**Implementation authorization:** pending explicit user instruction.

## Preconditions

- Current behaviour, as implemented in `deployment/azure/setup.sh.template`:
  - `BLOB_URL="https://daffstandard.blob.core.windows.net/refdata-wf2"`, with
    public container-level read and no SAS token.
  - `azcopy copy "$BLOB_URL" /mnt/nvme --recursive --check-md5 NoCheck --cap-mbps 0`
    downloads into `/mnt/nvme/refdata-wf2`, which is then renamed to
    `/mnt/nvme/refdata`.
  - A warm node is detected by the presence of `/mnt/nvme/refdata/core_nt`
    and skips the download.
- Consumers of the staged data: `deployment/azure/run-taxodactyl.sh` passes
  `BLASTDB_PATH=/mnt/nvme/refdata/core_nt/core_nt` and
  `TAXDB_PATH=/mnt/nvme/refdata/taxdump/taxdump`. `conf/azure.config` mounts
  `/mnt/nvme/refdata` read-only into containers.
- Nothing in runtime code reads `STORAGE_ACCOUNT_PREM`,
  `NXF_AZURE_REFERENCE_ACCOUNT` or `NXF_AZURE_REFERENCE_KEY`. The only uses
  of `STORAGE_ACCOUNT_PREM` are informational echoes in
  `deployment/azure/batch-helpers.sh` (lines 113 and 1465). Confirm this with
  `git grep -n -E "STORAGE_ACCOUNT_PREM|NXF_AZURE_REFERENCE|STORAGE_CONTAINER_REF" -- ':!tasks'`
  before editing.
- The `daffstandard` account is already created with
  `--allow-blob-public-access true` (`docs/azure/01-initial-setup.md` Step 2).

## Objective

An operator who follows `docs/azure/` from scratch must stage reference data
where the start task reads it: `daffstandard/refdata-wf2`, with public
container-level read access. They must not be told to create a premium
account, generate reference-data SAS tokens, or set unused variables.

Agreed variable handling (user decision, 2026-11-17): keep
`STORAGE_CONTAINER_REF`, set it to `refdata-wf2`, and use it with
`$STORAGE_ACCOUNT_STD` in doc commands. Remove `STORAGE_ACCOUNT_PREM`,
`NXF_AZURE_REFERENCE_ACCOUNT` and `NXF_AZURE_REFERENCE_KEY`.

## Implementation

### Phase 1 — Verify the live layout (read-only, before writing docs)

1. List the top-level prefixes of the public container anonymously and
   record the output in the PR description:
   ```sh
   curl -s "https://daffstandard.blob.core.windows.net/refdata-wf2?restype=container&comp=list&delimiter=/" \
     | grep -o '<Name>[^<]*</Name>'
   ```
   Then list one level under each prefix (add `&prefix=core_nt/` and
   `&prefix=taxdump/`). Use the observed layout in the docs.
   The expected layout is `core_nt/core_nt.*` and
   `taxdump/taxdump/*.dmp`, inferred from `run-taxodactyl.sh`. If what you
   observe differs, document what you observed and note the discrepancy.
   Do not fix any scripts. If the request fails (for example, no anonymous
   access), stop and report it, because that would contradict the issue's
   premise.

### Phase 2 — `.env.sample`

2. In `.env.sample`:
   - Delete `STORAGE_ACCOUNT_PREM=yourpremiumstorage`.
   - Change `STORAGE_CONTAINER_REF=refdata` to
     `STORAGE_CONTAINER_REF=refdata-wf2`, with a one-line comment saying it
     lives in `$STORAGE_ACCOUNT_STD` with public read access and must match
     `BLOB_URL` in `deployment/azure/setup.sh.template`.
   - Delete `NXF_AZURE_REFERENCE_ACCOUNT=$STORAGE_ACCOUNT_PREM` and
     `NXF_AZURE_REFERENCE_KEY=...`.
   - Leave `AZCOPY_SAS_TOKEN` and every other variable untouched. They are
     outside this issue (see Risks).

### Phase 3 — Operator docs (`docs/azure/`)

3. `docs/azure/01-initial-setup.md`:
   - Step 2 variable block: remove `STORAGE_ACCOUNT_PREM=daffpremium` and set
     `STORAGE_CONTAINER_REF=refdata-wf2`.
   - Remove the "Create premium storage account for reference data" block
     (the `az storage account create -n $STORAGE_ACCOUNT_PREM ... Premium_LRS`
     command and the matching container create).
   - After the standard-account container creations, add:
     ```sh
     # Reference data container: public container-level read so the pool
     # start task can download without a SAS token.
     az storage container create \
       --name $STORAGE_CONTAINER_REF \
       --account-name $STORAGE_ACCOUNT_STD \
       --public-access container
     ```
     Add a one-line note that only public NCBI data may go in this
     container, because anyone can list and read it.
   - Step 3: remove `az storage account keys list ... -n daffpremium` and the
     `NXF_AZURE_REFERENCE_KEY=<premium_storage_key>` line.
4. `docs/azure/03-reference-data.md` (main rewrite):
   - Overview: reference data lives in the standard account's public
     `refdata-wf2` container and is staged to node NVMe by the start task.
     Remove the claims about premium-storage billing and IOPS.
   - Storage Structure: account `daffstandard` (`$STORAGE_ACCOUNT_STD`),
     container `refdata-wf2` (`$STORAGE_CONTAINER_REF`), with the prefixes
     verified in Phase 1. Explain the `refdata-wf2` → `refdata` rename so
     node paths stay `/mnt/nvme/refdata/...`. Replace the inaccurate
     `params.refdata_path` line (it exists only in
     `deployment/azure/hello-world.nf`) with the real `--blastdb` /
     `--taxdb` values from `deployment/azure/run-taxodactyl.sh`.
   - Uploading: change the role-assignment scope to
     `$STORAGE_ACCOUNT_STD`, and point both `azcopy copy` destinations at
     `https://${STORAGE_ACCOUNT_STD}.blob.core.windows.net/${STORAGE_CONTAINER_REF}/<prefix>/`,
     where the prefixes match Phase 1. Uploading still needs authenticated
     write access; only reads are anonymous.
   - Performance Metrics: keep the figures, but label them as measured on
     the earlier premium-storage setup. Do not invent new numbers. Change the
     "Premium blob storage with high IOPS" bullet to match.
   - Replace the whole "Authentication for Reference Data Access" section
     (Options 1–3) with a short "Access" section. Downloads are anonymous
     because the container has public container-level access, so there is no
     token to generate or rotate. Give a one-line anonymous check (the Phase 1
     `curl`, or `azcopy list "https://daffstandard.blob.core.windows.net/refdata-wf2"`).
   - Troubleshooting: drop the SAS-expiry and URL-encoding items and the
     "verify using premium blob storage" item. Add: check that the container's
     public access level is `container` (`az storage container show-permission
     --name $STORAGE_CONTAINER_REF --account-name $STORAGE_ACCOUNT_STD`), and
     check that the account still allows public blob access.
5. `docs/azure/04-start-tasks.md`:
   - "Generating SAS Tokens": rewrite the intro, which currently says public
     access is disabled. Only the start-task script (`scripts/setup.sh`)
     needs a SAS token; reference data is public. Delete the "Reference Data
     SAS Token" subsection and its note about the container-level SAS. Keep
     the start-task script SAS subsection and the security notes about SAS
     tokens.
   - Replace "Update the Start Task Script with SAS Token" with a short
     section stating that `BLOB_URL` in `deployment/azure/setup.sh.template`
     is the plain public container URL with no token, so a change of
     container only needs that line edited. Keep the
     `*.ignore` / `*.template` security pattern note, which still applies to
     the pool JSON's script SAS.
6. `docs/azure/05-troubleshooting.md`:
   - "Start task fails" item 2: make it the start-task *script* SAS only.
   - "azcopy download" section: remove the reference-data SAS item, and
     change the manual test to an anonymous
     `azcopy copy "https://daffstandard.blob.core.windows.net/refdata-wf2/core_nt" ./test_download --recursive`
     (or `azcopy list`). Change the `az storage blob list` example to
     `--account-name daffstandard --container-name refdata-wf2`.
   - "SAS Token Expired": delete the "For reference data" `generate-sas`
     block and keep the script-token block.
7. `docs/azure/06-maintenance.md` (not named in the issue, but it has the same
   drift): remove the "Reference data SAS URLs" row from the "What needs
   rotating" table, and remove the closing "Repeat `STORAGE_ACCOUNT_PREM`
   separately for the premium account…" sentence in Key Rotation.
8. `docs/azure/README.md`: line 34 says "Uploading and staging reference
   data"; leave its wording unless it implies premium storage or SAS tokens.
   Check `az_sas_generate` (line 85); it stays, because it is used for the
   script SAS.

### Phase 4 — Helper script display

9. `deployment/azure/batch-helpers.sh`: delete line 113
   (`_info "Storage account (prem): ..."`) and line 1465
   (`Storage Account (prem): $STORAGE_ACCOUNT_PREM`) in `az_help`. Make no
   other changes.

### Phase 5 — Spec

10. `spec/defects.md`: change the `DEP-D-011` row's area to
    `docs / deployment — **fixed in <commit>**` (per the convention at the top
    of that file), keep the row text, and update the Low-severity count in the
    summary table (currently "67 (2 of them fixed …)") to reflect 3 fixed,
    adding `DEP-D-011` to the list.
11. `spec/deployment.md`: in the §5 Storage row, replace the trailing
    "`.env.sample` and `docs/azure/*.md` still describe it (`DEP-D-011`)"
    with a past-tense note that the docs were updated. Mark the `DEP-D-011`
    row (line ~101) as fixed in the same style.
12. `spec/reference-data.md` §1.1: replace "the `docs/azure/*.md`
    walkthroughs still describe that older setup (`DEP-D-011`)" with a note
    that they were updated (`DEP-D-011`, fixed).

## Documentation and configuration

All changes above are documentation or sample configuration. No pipeline
configuration (`conf/*.config`, `nextflow.config`, `nextflow_schema.json`)
changes. Remind operators that their own gitignored `.env.azure` can drop the
removed variables, and that leaving them in place is harmless.

## Testing decision

Recorded 2026-11-17, scoped to this task (issue #338):

- **Affected suites:** none. No unit test, integration test, nf-test,
  snapshot, flag baseline or Selenium fixture reads `docs/azure/`,
  `.env.sample`, `deployment/azure/batch-helpers.sh` or the `spec/` text.
  No CI workflow in `.github/workflows/` checks Markdown or docs.
- **New assertions:** none to be written.
- **Who runs checks:** the agent runs the static checks listed under
  Validation, plus the read-only anonymous container listing in Phase 1.
- **Who reviews drift:** the user reviews the rewritten doc wording and the
  observed container layout.
- **Who may update expected results:** no expected results are affected. If
  any snapshot, flag baseline or Selenium fixture appears to change, stop
  and report it without updating it.

## Validation

Agent-run checks (record the commands and outcomes in the PR description):

1. Stale-reference sweep. This must return no hits that describe current
   reference-data staging:
   ```sh
   git grep -n -E "daffpremium|STORAGE_ACCOUNT_PREM|NXF_AZURE_REFERENCE|refdata\?|/refdata/core_nt\?|Premium_LRS" \
     -- docs/azure .env.sample deployment/azure/batch-helpers.sh
   ```
   Any remaining `daffpremium` mention must be an explicit historical note.
2. Confirm that every remaining SAS mention in `docs/azure/` refers to the
   start-task script or the cache connection string:
   `git grep -n -i "sas" -- docs/azure`.
3. Syntax-check the helper script: `bash -n deployment/azure/batch-helpers.sh`.
4. Relative-link check over the edited docs: for each `](...)` target in
   `docs/azure/0[1-6]*.md`, confirm that the path (minus any `#anchor`)
   exists relative to the file. Report any broken links, including ones that
   predate this change (for example, the
   `../../../README.md` link in `03-reference-data.md`); fix only those
   in sections you rewrote.
5. Phase 1 anonymous listing succeeds, and the documented prefixes match it.
6. `git diff --stat` shows changes only in `.env.sample`, `docs/azure/*.md`,
   `deployment/azure/batch-helpers.sh` and `spec/*.md`.

## Test impact and manual review

- **Automated tests:** none affected; see Testing decision. Nothing needs
  to be prepared for observability.
- **Manual review (user-owned):**
  - Read `docs/azure/01-initial-setup.md`, `03-reference-data.md`,
    `04-start-tasks.md` and `05-troubleshooting.md` end to end as a new
    operator. Confirm that no step creates or writes to a premium account or
    generates a reference-data SAS token.
  - Confirm that the documented container layout (from Phase 1) matches what
    you intend to keep in `refdata-wf2`.
  - Optional, not required for completion: next time a pool node is
    provisioned, confirm that `startup/stderr.txt` shows the download from
    `daffstandard/refdata-wf2` (see `docs/azure/05-troubleshooting.md` for
    the download command).
- Implementation status and manual-review status are tracked separately.
  Do not mark manual review as passed without the user's confirmation.

## Completion criteria

- `.env.sample` defines `STORAGE_CONTAINER_REF=refdata-wf2` and no longer
  defines `STORAGE_ACCOUNT_PREM`, `NXF_AZURE_REFERENCE_ACCOUNT` or
  `NXF_AZURE_REFERENCE_KEY`.
- `docs/azure/01`, `03`, `04`, `05` and `06` describe upload to and anonymous
  download from `$STORAGE_ACCOUNT_STD/$STORAGE_CONTAINER_REF` (`refdata-wf2`).
  They contain no reference-data SAS instructions and no premium-account
  creation.
- `deployment/azure/batch-helpers.sh` no longer echoes
  `STORAGE_ACCOUNT_PREM`, and `bash -n` passes.
- `DEP-D-011` is marked fixed in `spec/defects.md` and `spec/deployment.md`,
  and `spec/reference-data.md` no longer says that the docs are stale.
- All Validation checks are run and their outcomes recorded. The user has
  completed the manual review (pending until confirmed).

## Risks

- **Public data exposure:** anyone can list and read `refdata-wf2`. The docs
  must say that only public reference data may be placed there.
- **Out of scope, noted for follow-up:** `AZCOPY_SAS_TOKEN` in `.env.sample`
  is unused by any code. `deployment/azure/issues.md` item 1 (SAS expiry
  around December 2026) now covers fewer tokens. The `daffpremium` account
  itself may now be unused and could be decommissioned. Do not act on any of
  these in this task. List them in the PR description.
- If the Phase 1 listing shows a layout that differs from the
  `run-taxodactyl.sh` paths, that is a possible runtime defect, not a docs
  issue. Report it rather than working around it.
