"""Trim multi-query files down to a single target query.

Each filter operates on a locally-materialised source file (an XML, a
FASTA, or a CSV) and writes a filtered copy to a destination path. The
``_apply_filter`` dispatcher is used by the harvest core to route each
:class:`SourceFile` to its filter (or straight-copy for verbatim files).
"""

from __future__ import annotations

import csv
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from .errors import HarvestError


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


def apply_filter(
    kind: str | None, src: Path, dest: Path, query_id: str,
) -> None:
    """Route ``src`` to the appropriate filter (or a straight copy)."""
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
