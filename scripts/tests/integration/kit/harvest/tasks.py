"""Task-list construction from a Nextflow execution trace or launcher log.

The trace TSV (``pipeline_info/execution_trace_*.txt`` by default, or the
path passed via ``-with-trace`` in the launcher line) is preferred. When
its ``workdir`` column is missing or empty, we fall back to scanning the
launcher log for ``Task completed > TaskHandler[...]`` lines — Nextflow
emits those with a full ``workDir`` path regardless of trace state.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import HarvestError
from .log_parse import RunInfo

PIPELINE_INFO_DIRNAME = "pipeline_info"
TRACE_GLOB = "execution_trace_*.txt"

TASK_HANDLER_RE = re.compile(
    r"TaskHandler\[id: \d+;\s*name:\s*(?P<name>[^;]+);"
    r".*?workDir:\s*(?P<workdir>[^\]]+)\]"
)


@dataclass
class TaskRow:
    process: str  # last segment after ':' (e.g. "BLAST_BLASTN")
    tag: str
    workdir_uri: str  # local path or "az://container/work/xx/yyy"


@dataclass
class TaskSource:
    """Where the task list came from and any reason we skipped the trace."""
    trace_path: Path | None       # trace we ended up using (rows populated)
    trace_checked: Path | None    # trace we tried but had no workdir data
    log_scan_used: bool


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
) -> tuple[list[TaskRow], TaskSource]:
    """Return ``(tasks, source)``; trace preferred, log-scan fallback."""
    trace_path = _resolve_trace_path(run, trace_override)
    rows = _load_trace_rows(trace_path)
    if rows:
        return rows, TaskSource(
            trace_path=trace_path,
            trace_checked=None,
            log_scan_used=False,
        )
    trace_checked = trace_path
    rows = _scan_log_tasks(log_path)
    if not rows:
        raise HarvestError(
            f"Could not resolve any tasks — no populated trace found"
            f" (checked: {trace_checked or 'default location'}) and no"
            f" TaskHandler lines in {log_path}."
        )
    return rows, TaskSource(
        trace_path=None,
        trace_checked=trace_checked,
        log_scan_used=True,
    )


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
