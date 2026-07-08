"""Public :func:`harvest` entry point — orchestrates the other modules."""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .errors import HarvestError
from .filters import apply_filter
from .log_parse import parse_launcher_line
from .materialise import materialise
from .paths import RemotePath
from .query_id import resolve_query_id
from .remote import remote_fetch, remote_ls
from .sources import resolve_sources
from .tasks import (
    PIPELINE_INFO_DIRNAME,
    load_tasks,
)


@dataclass
class HarvestResult:
    case_dir: Path
    written: list[Path]


def _fetch_control_files(
    log: RemotePath,
    outdir: RemotePath | None,
    trace: RemotePath | None,
    tmp: Path,
) -> tuple[Path, Path | None, Path | None]:
    """SCP the log, params-file (if any), and trace to a local temp dir.

    Returns (local_log, local_outdir_or_None, local_trace_or_None).

    ``outdir`` is a directory, not a single file, so we can't fetch it
    wholesale. Instead we materialise a *view* directory containing only
    the files we need to read locally (params JSON if referenced, trace
    if resolvable). The returned ``local_outdir`` is either the local
    outdir (when outdir is local) or a synthetic directory populated
    only with the pipeline_info trace file.
    """
    assert log.remote is not None
    host = log.remote

    local_log = tmp / "nextflow.log"
    remote_fetch(host, log.path, local_log)

    local_outdir: Path | None = None
    if outdir is not None and outdir.remote is None:
        local_outdir = outdir.path

    local_trace: Path | None = None
    if trace is not None:
        if trace.remote is None:
            local_trace = trace.path
        else:
            local_trace = tmp / "trace.csv"
            try:
                remote_fetch(trace.remote, trace.path, local_trace)
            except HarvestError:
                local_trace = None

    return local_log, local_outdir, local_trace


def _fetch_default_trace(
    outdir: RemotePath, tmp: Path,
) -> Path | None:
    """Try to scp the newest ``execution_trace_*.txt`` from a remote outdir."""
    assert outdir.remote is not None
    try:
        entries = remote_ls(
            outdir.remote, outdir.path / PIPELINE_INFO_DIRNAME,
        )
    except HarvestError:
        return None
    traces = sorted(
        n for n in entries
        if n.startswith("execution_trace_") and n.endswith(".txt")
    )
    if not traces:
        return None
    remote_trace_path = (
        outdir.path / PIPELINE_INFO_DIRNAME / traces[-1]
    )
    local_trace = tmp / "trace_default.csv"
    try:
        remote_fetch(outdir.remote, remote_trace_path, local_trace)
    except HarvestError:
        return None
    return local_trace


def _fetch_outdir_query_dirs(outdir: RemotePath) -> list[str] | None:
    """Return the ``query_NNN_*`` dir names under a remote outdir, or None."""
    if outdir.remote is None:
        return None
    try:
        entries = remote_ls(outdir.remote, outdir.path)
    except HarvestError:
        return []
    return [n for n in entries if n.startswith("query_")]


def _validate_case_name(name: str) -> None:
    if not name or "/" in name or name.startswith("."):
        raise HarvestError(
            f"Invalid case name: {name!r} (no slashes or dot-prefix)"
        )


def _resolve_remote_host(
    log: RemotePath,
    outdir: RemotePath | None,
    trace: RemotePath | None,
    work_dir: RemotePath | None,
) -> str | None:
    """Return the SSH host common to remote args, or None if fully local."""
    hosts = {
        p.remote for p in (log, outdir, trace, work_dir)
        if p is not None and p.remote is not None
    }
    if not hosts:
        return None
    if len(hosts) > 1:
        raise HarvestError(
            f"Multiple remote hosts in one harvest: {sorted(hosts)}."
            " Use a single host for --log / --outdir / --trace / --work-dir."
        )
    return next(iter(hosts))


def _print_header(
    *,
    profile: str,
    outdir_display: str,
    trace_display: str,
    remote_host: str | None,
    work_dir_display: str | None,
    task_count: int,
    case_dir: Path,
) -> None:
    print(f"\nProfile:              {profile}")
    if remote_host is not None:
        print(f"Remote host:          {remote_host}")
    print(f"Outdir:               {outdir_display}")
    print(f"Trace file:           {trace_display}")
    if work_dir_display is not None:
        print(f"Local workdir base:   {work_dir_display}")
    print(f"Tasks:                {task_count} rows loaded")
    print(f"Case dir:             {case_dir}")


def harvest(
    log: RemotePath,
    query_id: str,
    case_name: str,
    case_root: Path,
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    work_dir: RemotePath | None = None,
    outdir: RemotePath | None = None,
    trace: RemotePath | None = None,
) -> HarvestResult:
    """Scaffold ``<case_root>/<case_name>/`` from the run at ``log``.

    ``log``/``outdir``/``trace``/``work_dir`` are :class:`RemotePath`
    instances that may name a local path or a ``host:path`` SSH source.
    """
    _validate_case_name(case_name)
    case_dir = case_root / case_name
    if case_dir.exists():
        raise HarvestError(
            f"Case already exists: {case_dir}."
            " harvest never overwrites — pick a fresh --name."
        )

    remote_host = _resolve_remote_host(log, outdir, trace, work_dir)

    with tempfile.TemporaryDirectory(prefix="harvest_") as tmp_str:
        tmp = Path(tmp_str)

        if log.remote is not None:
            local_log, _, local_trace_override = _fetch_control_files(
                log, outdir, trace, tmp,
            )
        else:
            local_log = log.path
            local_trace_override = (
                trace.path if trace is not None and trace.remote is None
                else None
            )

        run = parse_launcher_line(
            local_log,
            outdir_override=outdir.path if outdir is not None else None,
        )

        # If the trace resolves to a remote-only default location, try
        # to scp it down so ``load_tasks`` can read it. Failure is
        # non-fatal — log-scan will take over.
        effective_trace_override = local_trace_override
        if (
            effective_trace_override is None
            and outdir is not None
            and outdir.remote is not None
        ):
            fetched = _fetch_default_trace(outdir, tmp)
            if fetched is not None:
                effective_trace_override = fetched

        tasks, source = load_tasks(run, local_log, effective_trace_override)

        outdir_query_dirs = (
            _fetch_outdir_query_dirs(outdir) if outdir is not None
            else None
        )
        resolved_query_id = resolve_query_id(
            query_id, tasks,
            outdir=run.outdir if (
                outdir is None or outdir.remote is None
            ) else None,
            outdir_query_dirs=outdir_query_dirs,
        )

        outdir_display = (
            str(outdir) if outdir is not None else str(run.outdir)
        )
        if source.trace_path is not None:
            trace_display = str(source.trace_path)
        elif source.trace_checked is not None:
            trace_display = (
                f"{source.trace_checked} (no workdir column — using"
                f" log-scan of {log})"
            )
        else:
            trace_display = (
                f"(no trace found — using log-scan of {log})"
            )
        work_dir_display = str(work_dir) if work_dir is not None else None

        _print_header(
            profile=run.profile,
            outdir_display=outdir_display,
            trace_display=trace_display,
            remote_host=remote_host,
            work_dir_display=work_dir_display,
            task_count=len(tasks),
            case_dir=case_dir,
        )
        if resolved_query_id != query_id:
            print(
                f"Query:                {query_id!r} -> sample_id"
                f" {resolved_query_id!r}"
            )
        else:
            print(f"Query:                {query_id!r}")
        query_id = resolved_query_id

        source_files = resolve_sources(tasks, query_id)

        print()
        header_line = (
            "Resolution plan (--dry: no files fetched or written):"
            if dry_run
            else "Resolution plan:"
        )
        print(header_line)
        for sf in source_files:
            dest = case_dir / sf.case_name
            src_display = (
                f"{remote_host}:{sf.workdir_uri}/{sf.filename}"
                if remote_host is not None and sf.workdir_uri.startswith("/")
                else f"{sf.workdir_uri}/{sf.filename}"
            )
            print(
                f"  {src_display}  ->  {dest}"
                f"  (filter={sf.filter or 'copy'})"
            )

        if dry_run:
            return HarvestResult(case_dir=case_dir, written=[])

        if not assume_yes:
            print()
            print(
                "Review the resolution plan above — if Outdir, Trace"
                " file or workdir base look wrong, re-run with --outdir"
                " / --trace / --work-dir set."
            )
            reply = input(
                "\nProceed with harvest? [y/N] "
            ).strip().lower()
            if reply not in ("y", "yes"):
                raise HarvestError("Aborted at confirmation prompt.")

        written: list[Path] = []
        work_dir_local_path: Path | None = (
            work_dir.path
            if work_dir is not None and work_dir.remote is None
            else None
        )
        work_dir_remote_path: Path | None = (
            work_dir.path
            if work_dir is not None and work_dir.remote is not None
            else None
        )

        outdir_local_path = (
            outdir.path
            if outdir is not None and outdir.remote is None
            else (run.outdir if outdir is None else None)
        )
        outdir_remote_host = (
            outdir.remote if outdir is not None else None
        )
        outdir_remote_path = (
            outdir.path
            if outdir is not None and outdir.remote is not None
            else None
        )

        for sf in source_files:
            local_scratch = tmp / f"{sf.case_name}.raw"
            materialise(
                sf.workdir_uri, sf.filename, local_scratch,
                is_azure=run.is_azure,
                remote_host=remote_host if not run.is_azure else None,
                work_dir_override=(
                    work_dir_local_path
                    if remote_host is None
                    else work_dir_remote_path
                ),
                work_dir_override_remote=(
                    work_dir.remote if work_dir is not None else None
                ),
                outdir_subpath=sf.outdir_subpath,
                outdir_local=outdir_local_path,
                outdir_remote_host=outdir_remote_host,
                outdir_remote_path=outdir_remote_path,
            )
            dest = case_dir / sf.case_name
            case_dir.mkdir(parents=True, exist_ok=True)
            apply_filter(sf.filter, local_scratch, dest, query_id)
            written.append(dest)
            print(
                f"  wrote {dest.relative_to(case_root.parent)}"
                f"  (from {sf.workdir_uri}/{sf.filename})"
            )

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
        "harvest is a library module. Use `testkit.py harvest ...`.",
        file=sys.stderr,
    )
    sys.exit(2)
