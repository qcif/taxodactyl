"""Harvest a new integration test case from a completed NF workflow run.

Given a ``.nextflow.log`` and a target ``--query`` sample id, this module
resolves the workflow's outdir + profile from the log's first line,
locates every required file (published or task-scratch), filters the
multi-query files down to just the chosen query, and writes a case dir
under ``scripts/tests/test-data/integration/blast/<name>/``.

Public entry: :func:`harvest`. Everything else is a helper.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LAUNCHER_LINE_MARKER = "nextflow.cli.Launcher"
PROFILE_RE = re.compile(r"-profile\s+(\S+)")
OUTDIR_RE = re.compile(r"--outdir\s+(\S+)")
PARAMS_FILE_RE = re.compile(r"-params-file\s+(\S+)")
WITH_TRACE_RE = re.compile(r"-with-trace\s+(\S+)")

AZURE_URI_RE = re.compile(
    r"^az://(?P<container>[^/]+)/(?P<path>.+)$"
)
AZURE_PROFILES = {"azure", "azurebatch", "azure_batch"}

PIPELINE_INFO_DIRNAME = "pipeline_info"
TRACE_GLOB = "execution_trace_*.txt"

TASK_HANDLER_RE = re.compile(
    r"TaskHandler\[id: \d+;\s*name:\s*(?P<name>[^;]+);"
    r".*?workDir:\s*(?P<workdir>[^\]]+)\]"
)

# Process name suffixes (after final ':') to source files from work dirs.
PROC_VALIDATE_INPUT = "VALIDATE_INPUT"
PROC_BLAST_BLASTN = "BLAST_BLASTN"
PROC_BLAST_BLASTDBCMD = "BLAST_BLASTDBCMD"
PROC_EXTRACT_TAXONOMY = "EXTRACT_TAXONOMY"
PROC_FASTME = "FASTME"

# Case-dir file names (destination).
CASE_BLAST_XML = "blast_result.xml"
CASE_QUERY_FASTA = "query.fasta"
CASE_METADATA_CSV = "metadata.csv"
CASE_CANDIDATES_NWK = "candidates.nwk"
CASE_TAXIDS_CSV = "taxids.csv"
CASE_TAXONOMY_CSV = "taxonomy.csv"

# Workdir source file names.
WD_BLAST_XML = "blast_result.xml"
WD_SEQUENCES_FASTA = "sequences.fasta"
WD_METADATA_CSV = "metadata.csv"
WD_CANDIDATES_NWK = "candidates_phylogeny.nwk"
WD_TAXIDS_CSV = "taxids.csv"
WD_TAXONOMY_CSV = "taxonomy.csv"


class HarvestError(Exception):
    """User-facing failure — surfaced as a clean exit."""


# ---------------------------------------------------------------------------
# Log + trace parsing
# ---------------------------------------------------------------------------

@dataclass
class RunInfo:
    profile: str
    outdir: Path
    trace_path: Path | None  # explicit `-with-trace` if present, else None

    @property
    def is_azure(self) -> bool:
        return self.profile.lower() in AZURE_PROFILES


@dataclass
class TaskRow:
    process: str  # last segment after ':' (e.g. "BLAST_BLASTN")
    tag: str
    workdir_uri: str  # local path or "az://container/work/xx/yyy"


def _outdir_from_params_file(params_file: Path) -> Path | None:
    """Return the ``outdir`` entry from a Nextflow -params-file JSON."""
    if not params_file.is_file():
        return None
    try:
        with params_file.open() as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    outdir = data.get("outdir")
    return Path(outdir).expanduser() if outdir else None


def parse_launcher_line(
    log_path: Path,
    *,
    outdir_override: Path | None = None,
) -> RunInfo:
    """Extract profile, outdir, and (optional) trace path from log line 1."""
    if not log_path.is_file():
        raise HarvestError(f"Log file not found: {log_path}")
    with log_path.open() as f:
        first = f.readline()
    if LAUNCHER_LINE_MARKER not in first:
        raise HarvestError(
            f"{log_path} does not look like a Nextflow launcher log"
            f" (line 1 has no {LAUNCHER_LINE_MARKER!r} marker)."
        )
    profile_m = PROFILE_RE.search(first)
    if not profile_m:
        raise HarvestError(
            "Could not find `-profile <name>` in the launcher line."
        )

    outdir: Path | None = outdir_override
    if outdir is None:
        outdir_m = OUTDIR_RE.search(first)
        if outdir_m:
            outdir = Path(outdir_m.group(1)).expanduser()
    if outdir is None:
        params_m = PARAMS_FILE_RE.search(first)
        if params_m:
            outdir = _outdir_from_params_file(
                Path(params_m.group(1)).expanduser()
            )
    if outdir is None:
        raise HarvestError(
            "Could not resolve outdir: launcher line has no `--outdir`,"
            " and no readable `-params-file` with an `outdir` field."
            " Pass --outdir explicitly."
        )

    trace_path: Path | None = None
    trace_m = WITH_TRACE_RE.search(first)
    if trace_m:
        trace_path = Path(trace_m.group(1)).expanduser()

    return RunInfo(
        profile=profile_m.group(1),
        outdir=outdir,
        trace_path=trace_path,
    )


def _split_name(name: str) -> tuple[str, str]:
    """Split "NAMESPACE:PROC (tag)" into (process, tag)."""
    proc_part, _, tag_part = name.partition(" (")
    process = proc_part.rsplit(":", 1)[-1].strip()
    tag = tag_part.rstrip(")").strip()
    return process, tag


def _resolve_trace_path(
    run: RunInfo, trace_override: Path | None,
) -> Path | None:
    """Pick the trace file: override > log's -with-trace > default glob."""
    for candidate in (trace_override, run.trace_path):
        if candidate and candidate.is_file():
            return candidate
    info_dir = run.outdir / PIPELINE_INFO_DIRNAME
    if info_dir.is_dir():
        traces = sorted(info_dir.glob(TRACE_GLOB))
        if traces:
            return max(traces, key=lambda p: p.stat().st_mtime)
    return None


def _load_trace_rows(trace_path: Path | None) -> list[TaskRow]:
    """Return TaskRows with a populated ``workdir`` column, or []."""
    if trace_path is None:
        return []
    rows: list[TaskRow] = []
    with trace_path.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            name = row.get("name", "")
            workdir = row.get("workdir", "")
            if not name or not workdir:
                continue
            process, tag = _split_name(name)
            rows.append(TaskRow(
                process=process, tag=tag, workdir_uri=workdir,
            ))
    return rows


def _scan_log_tasks(log_path: Path) -> list[TaskRow]:
    """Fallback: parse "Task completed > TaskHandler[...]" lines from the log.

    Nextflow's local executor emits these with a full ``workDir`` path even
    when the ``execution_trace_*.txt`` file is empty (e.g. runs that were
    interrupted before flushing the trace, or examples where the trace was
    truncated when copied).
    """
    rows: list[TaskRow] = []
    seen: set[tuple[str, str, str]] = set()
    with log_path.open() as f:
        for line in f:
            m = TASK_HANDLER_RE.search(line)
            if not m:
                continue
            process, tag = _split_name(m.group("name"))
            workdir = m.group("workdir").strip()
            key = (process, tag, workdir)
            if key in seen:
                continue
            seen.add(key)
            rows.append(TaskRow(
                process=process, tag=tag, workdir_uri=workdir,
            ))
    return rows


def load_tasks(
    run: RunInfo,
    log_path: Path,
    trace_override: Path | None = None,
) -> tuple[list[TaskRow], str]:
    """Return ``(tasks, source_label)``; trace preferred, log-scan fallback."""
    trace_path = _resolve_trace_path(run, trace_override)
    rows = _load_trace_rows(trace_path)
    if rows:
        return rows, f"trace:{trace_path}"
    rows = _scan_log_tasks(log_path)
    if not rows:
        raise HarvestError(
            f"Could not resolve any tasks — no populated trace found"
            f" (checked: {trace_path or 'default location'}) and no"
            f" TaskHandler lines in {log_path}."
        )
    return rows, "log_scan"


def find_task(
    tasks: list[TaskRow],
    process: str,
    tag_contains: str | None = None,
) -> TaskRow:
    """Return the single matching task or raise."""
    matches = [t for t in tasks if t.process == process]
    if tag_contains is not None:
        matches = [t for t in matches if tag_contains in t.tag]
    if not matches:
        raise HarvestError(
            f"No task matching process={process!r}"
            + (f" tag~={tag_contains!r}" if tag_contains else "")
        )
    if len(matches) > 1:
        tags = ", ".join(sorted({t.tag for t in matches}))
        raise HarvestError(
            f"Multiple tasks matching process={process!r}"
            + (f" tag~={tag_contains!r}" if tag_contains else "")
            + f": tags=[{tags}]"
        )
    return matches[0]


# ---------------------------------------------------------------------------
# File materialisation (local read or Azure download)
# ---------------------------------------------------------------------------

def _remap_local_workdir(
    workdir_uri: str,
    work_dir_override: Path | None,
) -> Path:
    """Return the local path to a task workdir, applying override if set.

    The override strips the log's stale workdir prefix and rebases onto
    ``work_dir_override``, matching by the trailing two path segments
    (``<hash-prefix>/<hash-tail>``) which uniquely identify a task.
    """
    p = Path(workdir_uri)
    if work_dir_override is None:
        return p
    if len(p.parts) < 2:
        raise HarvestError(
            f"Cannot remap workdir without at least two path segments:"
            f" {workdir_uri}"
        )
    tail = Path(*p.parts[-2:])
    return work_dir_override / tail


def _resolve_stale_symlink(
    src: Path, work_dir_override: Path,
) -> Path | None:
    """Remap a stale Nextflow staging symlink onto ``work_dir_override``.

    Nextflow stages inputs into each task workdir as symlinks to the
    producing task's workdir. When a run is copied off its original
    machine those symlink targets go stale. If the target's last three
    segments are ``<hash-prefix>/<hash-tail>/<filename>`` we can rebase
    them onto the override.
    """
    if not src.is_symlink():
        return None
    target = Path(os.readlink(src))
    if len(target.parts) < 3:
        return None
    rebased = work_dir_override / Path(*target.parts[-3:])
    return rebased if rebased.is_file() else None


CANDIDATE_SUBPATHS = ("", "output")


def _materialise(
    workdir_uri: str,
    filename: str,
    dest: Path,
    is_azure: bool,
    work_dir_override: Path | None = None,
) -> None:
    """Copy a single required file out of a task workdir into ``dest``.

    Tries ``<workdir>/<filename>`` first, then ``<workdir>/output/<filename>``
    (some older workflow versions publish task outputs under ``output/``
    rather than at workdir root — Cloudgene's v1.4.4 runs do this).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if is_azure:
        last_err: HarvestError | None = None
        for sub in CANDIDATE_SUBPATHS:
            blob_name = f"{sub}/{filename}" if sub else filename
            try:
                _azure_download(workdir_uri, blob_name, dest)
                return
            except HarvestError as exc:
                last_err = exc
        raise last_err  # type: ignore[misc]

    base = _remap_local_workdir(workdir_uri, work_dir_override)
    for sub in CANDIDATE_SUBPATHS:
        src = base / sub / filename if sub else base / filename
        if src.is_file():
            shutil.copy2(src, dest)
            return
        if work_dir_override is not None:
            rebased = _resolve_stale_symlink(src, work_dir_override)
            if rebased is not None:
                shutil.copy2(rebased, dest)
                return
    tried = ", ".join(
        str(base / sub / filename if sub else base / filename)
        for sub in CANDIDATE_SUBPATHS
    )
    raise HarvestError(
        f"Expected file missing under local workdir (tried: {tried})"
    )


def _azure_download(workdir_uri: str, filename: str, dest: Path) -> None:
    """Download a single blob individually — never mirror the workdir."""
    m = AZURE_URI_RE.match(workdir_uri)
    if not m:
        raise HarvestError(
            f"Malformed Azure work-dir URI: {workdir_uri}"
        )
    container = m.group("container")
    blob_path = f"{m.group('path').rstrip('/')}/{filename}"
    account = os.environ.get("STORAGE_ACCOUNT_STD", "daffstandard")
    key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
    if not key:
        raise HarvestError(
            "AZURE_STORAGE_ACCOUNT_KEY is not set."
            " Source deployment/azure/batch-helpers.sh and run az_load_env"
            " before harvesting from an Azure run."
        )
    cmd = [
        "az", "storage", "blob", "download",
        "--account-name", account,
        "--account-key", key,
        "--container-name", container,
        "--name", blob_path,
        "--file", str(dest),
        "--only-show-errors",
        "--no-progress",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        msg = (res.stderr or res.stdout).strip()
        raise HarvestError(
            f"az blob download failed for {container}/{blob_path}:\n"
            f"  {msg}"
        )


# ---------------------------------------------------------------------------
# Filters — trim multi-query files down to a single target query
# ---------------------------------------------------------------------------

def filter_blast_xml(src: Path, dest: Path, query_id: str) -> None:
    """Keep only the <Iteration> matching ``query_id``; renumber to 1."""
    tree = ET.parse(src)
    root = tree.getroot()
    iterations_parent = root.find("BlastOutput_iterations")
    if iterations_parent is None:
        raise HarvestError(
            f"{src} has no <BlastOutput_iterations> element."
        )
    kept = None
    for it in list(iterations_parent):
        query_def = it.findtext("Iteration_query-def", "")
        first_token = query_def.split()[0] if query_def else ""
        if first_token == query_id or query_def.startswith(query_id + " "):
            kept = it
        iterations_parent.remove(it)
    if kept is None:
        raise HarvestError(
            f"No <Iteration> in {src} matches query id {query_id!r}."
        )
    iter_num = kept.find("Iteration_iter-num")
    if iter_num is not None:
        iter_num.text = "1"
    iterations_parent.append(kept)
    tree.write(dest, xml_declaration=True, encoding="UTF-8")


def filter_fasta(src: Path, dest: Path, query_id: str) -> None:
    """Keep only the FASTA record whose header starts with ``query_id``."""
    kept_lines: list[str] = []
    keeping = False
    found = False
    with src.open() as f:
        for line in f:
            if line.startswith(">"):
                header = line[1:].split()[0] if len(line) > 1 else ""
                keeping = (header == query_id)
                if keeping:
                    found = True
                    kept_lines.append(line)
                continue
            if keeping:
                kept_lines.append(line)
    if not found:
        raise HarvestError(
            f"No FASTA record in {src} matches query id {query_id!r}."
        )
    dest.write_text("".join(kept_lines))


def filter_metadata_csv(src: Path, dest: Path, query_id: str) -> None:
    """Keep the header row and the single row whose sample_id matches."""
    with src.open() as f:
        rows = list(csv.reader(f))
    if not rows:
        raise HarvestError(f"{src} is empty.")
    header = rows[0]
    try:
        sample_col = header.index("sample_id")
    except ValueError:
        raise HarvestError(
            f"{src} has no 'sample_id' column (header: {header})."
        ) from None
    matches = [r for r in rows[1:] if r and r[sample_col] == query_id]
    if not matches:
        raise HarvestError(
            f"No row in {src} has sample_id={query_id!r}."
        )
    if len(matches) > 1:
        raise HarvestError(
            f"Multiple rows in {src} have sample_id={query_id!r}"
            f" ({len(matches)} matches)."
        )
    with dest.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerow(matches[0])


# ---------------------------------------------------------------------------
# Case-file plan + write
# ---------------------------------------------------------------------------

@dataclass
class SourceFile:
    """Where to find a single required source file for the case."""
    case_name: str          # dest filename in the case dir
    workdir_uri: str        # where to fetch/read from
    filename: str           # basename to look up under workdir_uri
    filter: str | None      # "xml" | "fasta" | "metadata" | None (verbatim)


def _resolve_query_task(
    tasks: list[TaskRow], process: str, query_id: str,
) -> TaskRow:
    """Find a per-query task whose tag contains the query id."""
    return find_task(tasks, process, tag_contains=query_id)


def _resolve_sources(
    run: RunInfo,
    tasks: list[TaskRow],
    query_id: str,
) -> list[SourceFile]:
    validate = find_task(tasks, PROC_VALIDATE_INPUT)
    blastn = find_task(tasks, PROC_BLAST_BLASTN)
    blastdbcmd = find_task(tasks, PROC_BLAST_BLASTDBCMD)
    taxonomy = find_task(tasks, PROC_EXTRACT_TAXONOMY)
    fastme = _resolve_query_task(tasks, PROC_FASTME, query_id)
    return [
        SourceFile(
            CASE_BLAST_XML, blastn.workdir_uri, WD_BLAST_XML, "xml",
        ),
        SourceFile(
            CASE_QUERY_FASTA, validate.workdir_uri, WD_SEQUENCES_FASTA,
            "fasta",
        ),
        SourceFile(
            CASE_METADATA_CSV, validate.workdir_uri, WD_METADATA_CSV,
            "metadata",
        ),
        SourceFile(
            CASE_CANDIDATES_NWK, fastme.workdir_uri, WD_CANDIDATES_NWK,
            None,
        ),
        SourceFile(
            CASE_TAXIDS_CSV, blastdbcmd.workdir_uri, WD_TAXIDS_CSV, None,
        ),
        SourceFile(
            CASE_TAXONOMY_CSV, taxonomy.workdir_uri, WD_TAXONOMY_CSV,
            None,
        ),
    ]


def _apply_filter(kind: str | None, src: Path, dest: Path,
                  query_id: str) -> None:
    if kind is None:
        shutil.copy2(src, dest)
        return
    if kind == "xml":
        filter_blast_xml(src, dest, query_id)
    elif kind == "fasta":
        filter_fasta(src, dest, query_id)
    elif kind == "metadata":
        filter_metadata_csv(src, dest, query_id)
    else:
        raise HarvestError(f"Unknown filter kind: {kind!r}")


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

@dataclass
class HarvestResult:
    case_dir: Path
    written: list[Path]


def harvest(
    log_path: Path,
    query_id: str,
    case_name: str,
    case_root: Path,
    *,
    dry_run: bool = False,
    work_dir_override: Path | None = None,
    outdir_override: Path | None = None,
    trace_override: Path | None = None,
) -> HarvestResult:
    """Scaffold ``<case_root>/<case_name>/`` from the run at ``log_path``."""
    if not case_name or "/" in case_name or case_name.startswith("."):
        raise HarvestError(
            f"Invalid case name: {case_name!r} (no slashes or dot-prefix)"
        )
    case_dir = case_root / case_name
    if case_dir.exists():
        raise HarvestError(
            f"Case already exists: {case_dir}."
            " harvest never overwrites — pick a fresh --name."
        )

    run = parse_launcher_line(log_path, outdir_override=outdir_override)
    print(f"Profile: {run.profile}    Outdir: {run.outdir}")

    tasks, source_label = load_tasks(run, log_path, trace_override)
    print(f"Tasks: {len(tasks)} rows loaded (source: {source_label}).")
    if work_dir_override is not None:
        print(f"Local workdir override: {work_dir_override}")

    sources = _resolve_sources(run, tasks, query_id)

    written: list[Path] = []
    if dry_run:
        print()
        print("Resolution plan (dry-run — no files fetched or written):")
        for source in sources:
            dest = case_dir / source.case_name
            print(
                f"  {source.workdir_uri}/{source.filename}"
                f"  ->  {dest}"
                f"  (filter={source.filter or 'copy'})"
            )
        return HarvestResult(case_dir=case_dir, written=[])

    with tempfile.TemporaryDirectory(prefix="harvest_") as tmp_str:
        tmp = Path(tmp_str)
        for source in sources:
            local = tmp / f"{source.case_name}.raw"
            _materialise(
                source.workdir_uri, source.filename, local,
                is_azure=run.is_azure,
                work_dir_override=work_dir_override,
            )
            dest = case_dir / source.case_name
            case_dir.mkdir(parents=True, exist_ok=True)
            _apply_filter(source.filter, local, dest, query_id)
            written.append(dest)
            print(
                f"  wrote {dest.relative_to(case_root.parent)}"
                f"  (from {source.workdir_uri}/{source.filename})"
            )

    if not dry_run:
        print()
        print(f"Harvested case dir: {case_dir}")
        try:
            rel = case_dir.relative_to(Path.cwd())
        except ValueError:
            rel = case_dir
        print(f"  git add {rel}")
    return HarvestResult(case_dir=case_dir, written=written)


if __name__ == "__main__":
    print(
        "harvest.py is a library module. Use `testkit.py harvest ...`.",
        file=sys.stderr,
    )
    sys.exit(2)
