"""Parse the first line of a Nextflow launcher log.

The launcher line encodes the run's profile, ``--outdir`` (or a
``-params-file`` we can fall back to), and an optional ``-with-trace``
path. Everything else in the harvest flow is downstream of these three
values.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import HarvestError

LAUNCHER_LINE_MARKER = "nextflow.cli.Launcher"
PROFILE_RE = re.compile(r"-profile\s+(\S+)")
OUTDIR_RE = re.compile(r"--outdir\s+(\S+)")
PARAMS_FILE_RE = re.compile(r"-params-file\s+(\S+)")
WITH_TRACE_RE = re.compile(r"-with-trace\s+(\S+)")

AZURE_PROFILES = {"azure", "azurebatch", "azure_batch"}


@dataclass
class RunInfo:
    profile: str
    outdir: Path
    trace_path: Path | None  # explicit `-with-trace` if present, else None

    @property
    def is_azure(self) -> bool:
        return self.profile.lower() in AZURE_PROFILES


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
