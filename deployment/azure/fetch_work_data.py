"""Download Azure Batch work data from a Nextflow run, organised by task.

Parses .nextflow.log to map work directories (e.g. work/85/66eef4...) to
their submitting process names + tags, then mirrors the full blob tree
under each work directory into a local ``<process>__<tag>/`` folder so
that nested outputs (e.g. ``<workdir>/query_001/db_coverage.json``) are
captured - not just the .command.* artifacts at the workdir root.

Optionally filter to tasks whose tag contains a query ID substring -
useful for runs with hundreds of queries.

Requires the following environment (load via `az_load_env` from
deployment/azure/batch-helpers.sh):
  AZURE_STORAGE_ACCOUNT_KEY
  STORAGE_ACCOUNT_STD (default: daffstandard)
  STORAGE_CONTAINER_WORK (default: workdata)

Usage:
  python deployment/azure/fetch_work_data.py \
      --log .nextflow.log \
      --outdir output/debug_synonym \
      [--query VE24-1351] \
      [--include '*.json' '.command.*'] \
      [--jobs 8]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from fnmatch import fnmatch
from pathlib import Path

COLLAPSED_OUTPUT_DIRNAME = "output"
TASKS_DIRNAME = "tasks"

SUBMIT_RE = re.compile(
    r"Submitting task\s+"
    r"(?P<process>[\w:]+)"
    r"\s+\((?P<tag>[^)]+)\)"
    r"\s+-\s+work-dir=az://(?P<container>[^/]+)/"
    r"(?P<workdir>work/[a-f0-9]+/[a-f0-9]+)"
)

DEFAULT_ACCOUNT = "daffstandard"
DEFAULT_CONTAINER = "workdata"


def parse_log(log_path: Path) -> list[dict]:
    """Return one record per Submitted task in the log."""
    tasks = []
    with log_path.open() as f:
        for line in f:
            m = SUBMIT_RE.search(line)
            if not m:
                continue
            process = m.group("process").split(":")[-1]
            tasks.append({
                "process": process,
                "tag": m.group("tag"),
                "container": m.group("container"),
                "workdir": m.group("workdir"),
            })
    return tasks


def slugify(value: str) -> str:
    """Filesystem-safe slug, preserving readability."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")


def task_dirname(task: dict, seen: dict) -> str:
    """Build a unique dirname like PROCESS__TAG (suffixed if duplicated)."""
    base = f"{task['process']}__{slugify(task['tag'])}"
    n = seen.get(base, 0)
    seen[base] = n + 1
    if n:
        # Multiple submissions with same (process, tag) - e.g. retries.
        # Disambiguate by short workdir hash.
        short = task['workdir'].split('/')[-1][:8]
        base = f"{base}__{short}"
    return base


def list_blobs(
    account: str,
    container: str,
    prefix: str,
    account_key: str,
) -> list[str]:
    """List all blob names under a prefix."""
    cmd = [
        "az", "storage", "blob", "list",
        "--account-name", account,
        "--account-key", account_key,
        "--container-name", container,
        "--prefix", prefix.rstrip("/") + "/",
        "--query", "[].name",
        "--output", "json",
        "--only-show-errors",
        "--num-results", "*",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            f"blob list failed for {prefix}: "
            f"{(res.stderr or res.stdout).strip()}"
        )
    return json.loads(res.stdout or "[]")


def download_blob(
    account: str,
    container: str,
    blob: str,
    dest: Path,
    account_key: str,
) -> tuple[bool, str]:
    """Return (success, message)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "az", "storage", "blob", "download",
        "--account-name", account,
        "--account-key", account_key,
        "--container-name", container,
        "--name", blob,
        "--file", str(dest),
        "--only-show-errors",
        "--no-progress",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        msg = (res.stderr or res.stdout).strip().splitlines()[-1] if (
            res.stderr or res.stdout
        ) else f"exit {res.returncode}"
        return False, msg
    return True, "ok"


def matches_any(rel_path: str, patterns: list[str]) -> bool:
    name = rel_path.rsplit("/", 1)[-1]
    return any(fnmatch(rel_path, p) or fnmatch(name, p) for p in patterns)


def is_internal(rel: Path) -> bool:
    """Skip Nextflow/executor scaffolding when collapsing outputs."""
    for part in rel.parts:
        if part.startswith(".command.") or part in (
            ".exitcode", ".azure_blob_dir",
        ):
            return True
    return False


def build_collapsed_output(
    outdir: Path,
    task_dirs: list[Path],
) -> tuple[int, int]:
    """Symlink workflow output files into a flat ``<outdir>/output/`` tree.

    Mimics the publishDir layout - a file at
    ``<task>/query_001/db_coverage.json`` becomes
    ``<outdir>/output/query_001/db_coverage.json``.
    """
    collapsed = outdir / COLLAPSED_OUTPUT_DIRNAME
    if collapsed.is_symlink() or collapsed.exists():
        if collapsed.is_dir() and not collapsed.is_symlink():
            shutil.rmtree(collapsed)
        else:
            collapsed.unlink()
    collapsed.mkdir(parents=True)

    links = 0
    collisions = 0
    for task_dir in task_dirs:
        if not task_dir.is_dir():
            continue
        for file in sorted(task_dir.rglob("*")):
            if not file.is_file():
                continue
            rel = file.relative_to(task_dir)
            if is_internal(rel):
                continue
            link = collapsed / rel
            link.parent.mkdir(parents=True, exist_ok=True)
            if link.is_symlink() or link.exists():
                collisions += 1
                print(
                    f"  [SKIP] output/{rel}:"
                    f" already linked from another task"
                )
                continue
            target = os.path.relpath(file, link.parent)
            link.symlink_to(target)
            links += 1
    return links, collisions


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--log", default=".nextflow.log", type=Path,
        help="Nextflow log file (default: .nextflow.log)",
    )
    parser.add_argument(
        "--outdir", required=True, type=Path,
        help="Destination directory for downloaded files",
    )
    parser.add_argument(
        "--query", default=None,
        help=(
            "Optional substring filter applied to the task tag - useful"
            " for runs with many queries (e.g. 'VE24-1351')"
        ),
    )
    parser.add_argument(
        "--include", nargs="+", default=None,
        help=(
            "Optional fnmatch patterns to limit which blobs are"
            " downloaded (e.g. '*.json' '.command.*'). Patterns match"
            " against both the basename and the path relative to the"
            " task workdir. Default: download everything."
        ),
    )
    parser.add_argument(
        "--account", default=os.environ.get(
            "STORAGE_ACCOUNT_STD", DEFAULT_ACCOUNT
        ),
        help="Azure storage account (default from $STORAGE_ACCOUNT_STD)",
    )
    parser.add_argument(
        "--container", default=os.environ.get(
            "STORAGE_CONTAINER_WORK", DEFAULT_CONTAINER
        ),
        help="Blob container (default from $STORAGE_CONTAINER_WORK)",
    )
    parser.add_argument(
        "--jobs", type=int, default=8,
        help="Parallel download workers (default: 8)",
    )
    parser.add_argument(
        "--no-collapse", action="store_true",
        help=(
            "Skip building the collapsed <outdir>/output/ symlink tree."
            " By default a flat publishDir-style view is created from all"
            " non-internal task outputs."
        ),
    )
    args = parser.parse_args()

    account_key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
    if not account_key:
        sys.exit(
            "AZURE_STORAGE_ACCOUNT_KEY is not set."
            " Source deployment/azure/batch-helpers.sh and run az_load_env."
        )
    if not args.log.exists():
        sys.exit(f"Log file not found: {args.log}")

    tasks = parse_log(args.log)
    if args.query:
        tasks = [t for t in tasks if args.query in t["tag"]]
    if not tasks:
        sys.exit(
            f"No matching tasks found in {args.log}"
            + (f" for query '{args.query}'" if args.query else "")
        )

    args.outdir.mkdir(parents=True, exist_ok=True)

    seen: dict = {}
    enumerated = []
    for task in tasks:
        dirname = task_dirname(task, seen)
        enumerated.append((dirname, task))

    print(
        f"Found {len(tasks)} tasks; listing blobs under"
        f" {args.account}/{args.container}/..."
    )

    jobs = []
    manifest_lines = []
    for dirname, task in enumerated:
        container = task["container"] or args.container
        try:
            names = list_blobs(
                args.account, container, task["workdir"], account_key,
            )
        except RuntimeError as e:
            print(f"  [WARN] {dirname}: {e}", file=sys.stderr)
            names = []

        kept = 0
        for blob in names:
            rel = blob[len(task["workdir"]) + 1:]
            if not rel:
                continue
            if args.include and not matches_any(rel, args.include):
                continue
            dest = args.outdir / TASKS_DIRNAME / dirname / rel
            jobs.append((container, blob, dest))
            kept += 1
        manifest_lines.append(
            f"{dirname}\t{task['workdir']}\t{task['process']}\t"
            f"{task['tag']}\t{kept}"
        )
        print(f"  {dirname}: {kept} blob(s)")

    if not jobs:
        sys.exit("No blobs matched - nothing to download.")

    print(f"\nDownloading {len(jobs)} blobs with {args.jobs} workers...\n")

    ok = miss = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futs = {
            pool.submit(
                download_blob,
                args.account,
                container,
                blob,
                dest,
                account_key,
            ): (blob, dest)
            for container, blob, dest in jobs
        }
        for fut in as_completed(futs):
            blob, dest = futs[fut]
            success, msg = fut.result()
            rel_display = dest.relative_to(args.outdir)
            if success:
                ok += 1
                print(f"  [OK]   {rel_display}")
            else:
                miss += 1
                if dest.exists() and dest.stat().st_size == 0:
                    dest.unlink()
                print(f"  [MISS] {rel_display}: {msg}")

    manifest = args.outdir / "tasks.tsv"
    manifest.write_text(
        "dirname\tworkdir\tprocess\ttag\tblob_count\n"
        + "\n".join(manifest_lines)
        + "\n"
    )
    print(
        f"\nDone: {ok} downloaded, {miss} failed."
        f" Manifest: {manifest}"
    )

    if not args.no_collapse:
        print(
            f"\nBuilding collapsed output tree at"
            f" {args.outdir / COLLAPSED_OUTPUT_DIRNAME}/ ..."
        )
        task_dirs = [
            args.outdir / TASKS_DIRNAME / d for d, _ in enumerated
        ]
        links, collisions = build_collapsed_output(args.outdir, task_dirs)
        print(
            f"Linked {links} file(s) into"
            f" {COLLAPSED_OUTPUT_DIRNAME}/"
            + (
                f" ({collisions} skipped due to path collisions)"
                if collisions
                else ""
            )
        )


if __name__ == "__main__":
    main()
