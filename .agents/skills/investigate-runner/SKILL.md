---
name: "investigate-runner"
description: "Investigate nf-test failures on the self-hosted runner (`ssh daff-runner`, `/var/runner/<run_id>-<attempt>/`): find the failing sample or task, read its logs and error files, and trace the cause in the local codebase."
metadata:
  author: "neoformit"
---


## Background

We run NF-test as a GitHub action on a self-hosted runner. It can be reached
with `ssh daff-runner`. Each run writes its output to
`/var/runner/<run_id>-<attempt>/`: the GitHub Actions run ID (the number in
the run's URL) and attempt. For a PR run, the ID is that of the calling
`build-pr` run. Older runs are named `yyyy-mm-dd_HHMMSS` or
`<run_number>-<attempt>`.

Before starting, test `ssh daff-runner`. If it doesn't work - let the user know
they need to create an SSH config for this in order to use this skill.

If the user doesn't give a run path, list `/var/runner/` newest first
(`ls -lt /var/runner/`), check `run_info.txt` (branch, run URL), and confirm
with the user which run they mean (usually the latest).

## Read-only access

Only use read-only commands on the runner: `ls`, `cat`, `head`, `tail`,
`grep`, `find`, `wc`, `stat` and similar. Never write, move or delete files,
change permissions, or run Nextflow, nf-test or pipeline scripts there.

## Run directory layout

- Run root - start here for an overview of failures:
  - `run_info.txt` - event, branch, commit SHAs, GitHub Actions run URL,
    image, and API-cache mode (`api_cache: cached|live`) and fixture version
  - `nf-test_errors_summary.csv`, `nf-test_errors.txt`,
    `nf-test_errors.csv`, `nf-test_results.txt`
  - `flags_errors.txt`, `flags_results.txt`; `flags/evaluated/` holds the
    flags collected from the run
  - `collected_errors/` - links to the work dirs of failed or drifting tasks
  - `review.html` - the Selenium review page
  - `reports.zip` - final HTML reports per sample
  - `api_cache/cache_db.sqlite` - the GBIF/NCBI API cache at the end of the
    run. Its values are Python pickles: inspect it with `sqlite3` only and
    never unpickle it. In a cached run, rows added beyond the fixture are
    cache misses (also reported by the "Report API cache" step).
- `tests/<hash>/output/query_NNN_<sample>/` - published output for each query.
- `tests/<hash>/work/xx/<task-hash>/` - Nextflow work directories. A failing
  task's work dir contains:
  - `.command.sh` - the exact command and parameters that were run
  - `.command.log` - full stdout/stderr, including debug logging of external
    API requests (GBIF, Entrez, BOLD) with their URLs
  - `query_NNN_<sample>/errors/*.json` - structured errors with the analysis
    location (e.g. `5.2`), message and context
- `tests/<hash>/output/pipeline_info/` - Nextflow execution reports.

The fastest way to find the relevant task is usually to grep for the error
message:

```
ssh daff-runner 'cd /var/runner/<run> && grep -rl "<error message>" tests/'
```

### Path mapping

Logs and symlinks refer to paths under
`/mnt/data/ubuntu/actions-runner/_work/_temp/nf-test/`. These correspond to
`/var/runner/<run>/` on the host. Symlinked inputs in work dirs may not
resolve - translate the path manually to read the target.

## Process

Investigate the run directory to address the user's query, relating it to the
local codebase to understand the context of the output you are reading.

The local repo may not be checked out at the same commit the tests ran on.
Read `run_info.txt` in the run root and compare it with the local checkout
(for pull requests, use `pr_head_sha`; `checkout_sha` is a temporary merge
commit). If they differ, check `git log <sha>..HEAD` for the files involved,
or read the code at that commit with `git show <sha>:<path>`. Runs before
2026-11-17 have no `run_info.txt` - for those, confirm the branch or commit
with the user if the relevant code may have changed.
