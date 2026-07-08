"""Resolve ``--query`` to a sample_id (accepting sample_id or 1-3 digit index).

Nextflow tags every per-query task with ``query_NNN_<sample_id>`` and
publishes an ``<outdir>/query_NNN_<sample_id>/`` directory per query.
Either source can be used to translate a numeric index (e.g. ``008``) to
the corresponding sample_id.
"""

from __future__ import annotations

import re
from pathlib import Path

from .errors import HarvestError
from .tasks import TaskRow

# Per-query task tag format: ``query_NNN_<sample_id>`` (three-digit index,
# left-padded).
QUERY_TAG_RE = re.compile(r"^query_(?P<index>\d{3})_(?P<sample_id>.+)$")


def resolve_query_id(
    query_arg: str,
    tasks: list[TaskRow],
    outdir: Path | None = None,
    outdir_query_dirs: list[str] | None = None,
) -> str:
    """Return a sample_id given either a sample_id or a 1-3 digit index.

    Sources tried, in order:

    1. Per-query task tags in ``tasks``.
    2. ``outdir_query_dirs`` — a pre-fetched list of directory names
       under the run's outdir (useful when outdir is on a remote host).
    3. Local glob of ``outdir/query_NNN_*/``.

    A non-digit ``query_arg`` is returned unchanged (assumed to already
    be a sample_id).
    """
    if not query_arg.isdigit():
        return query_arg
    padded = query_arg.zfill(3)
    prefix = f"query_{padded}_"

    for t in tasks:
        m = QUERY_TAG_RE.match(t.tag)
        if m and m.group("index") == padded:
            return m.group("sample_id")

    if outdir_query_dirs is not None:
        for name in outdir_query_dirs:
            m = QUERY_TAG_RE.match(name)
            if m and m.group("index") == padded:
                return m.group("sample_id")

    if outdir is not None:
        for entry in outdir.glob(f"{prefix}*"):
            if not entry.is_dir():
                continue
            m = QUERY_TAG_RE.match(entry.name)
            if m and m.group("index") == padded:
                return m.group("sample_id")

    known_from_tags = sorted({
        t.tag for t in tasks if QUERY_TAG_RE.match(t.tag)
    })
    known_from_outdir_list = sorted({
        n for n in (outdir_query_dirs or [])
        if QUERY_TAG_RE.match(n)
    })
    known_from_outdir_glob = sorted({
        p.name for p in (outdir.glob("query_*") if outdir else [])
        if p.is_dir() and QUERY_TAG_RE.match(p.name)
    })
    known = (
        known_from_tags or known_from_outdir_list or known_from_outdir_glob
    )
    raise HarvestError(
        f"No per-query task tag or outdir directory matching {prefix!r}"
        f"* — cannot resolve query index {query_arg!r} to a sample_id."
        + (f" Known: {known}" if known else "")
    )
