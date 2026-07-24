"""Resolve which files to fetch for a given ``--query`` sample id.

The six case-dir files map to five workflow processes:

- ``VALIDATE_INPUT`` — ``sequences.fasta`` and ``metadata.csv``
- ``BLAST_BLASTN`` (or ``MOCK_BLASTN`` for nf-test) — ``blast_result.xml``
- ``BLAST_BLASTDBCMD`` — ``taxids.csv``
- ``EXTRACT_TAXONOMY`` — ``taxonomy.csv``
- ``FASTME (query_NNN_<sample_id>)`` — ``candidates_phylogeny.nwk``
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import HarvestError
from .tasks import TaskRow, find_task

# Process name suffixes (after final ':') to source files from work dirs.
PROC_VALIDATE_INPUT = "VALIDATE_INPUT"
PROC_BLAST_BLASTN = "BLAST_BLASTN"
PROC_MOCK_BLASTN = "MOCK_BLASTN"  # nf-test drop-in replacement
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


@dataclass
class SourceFile:
    """Where to find a single required source file for the case."""
    case_name: str          # dest filename in the case dir
    workdir_uri: str        # where to fetch/read from
    filename: str           # basename to look up under workdir_uri
    filter: str | None      # "xml" | "fasta" | "metadata" | None (verbatim)
    outdir_subpath: str | None = None  # optional publishDir fallback under
    #                                    outdir (e.g. "blast_result.xml" or
    #                                    "query_008_XYZ/candidates_phylogeny.nwk").
    #                                    Used when a task's workdir is
    #                                    unreachable (stale symlink chain,
    #                                    cleaned scratch, etc.) but the
    #                                    workflow published the file.


def _find_task_or_none(
    tasks: list[TaskRow],
    process: str,
    tag_contains: str | None = None,
) -> TaskRow | None:
    try:
        return find_task(tasks, process, tag_contains=tag_contains)
    except HarvestError:
        return None


def resolve_sources(
    tasks: list[TaskRow],
    query_id: str,
) -> list[SourceFile]:
    """Locate each source, or raise with the list of missing tasks."""
    validate = _find_task_or_none(tasks, PROC_VALIDATE_INPUT)
    blastn = (
        _find_task_or_none(tasks, PROC_BLAST_BLASTN)
        or _find_task_or_none(tasks, PROC_MOCK_BLASTN)
    )
    blastdbcmd = _find_task_or_none(tasks, PROC_BLAST_BLASTDBCMD)
    taxonomy = _find_task_or_none(tasks, PROC_EXTRACT_TAXONOMY)
    fastme = _find_task_or_none(
        tasks, PROC_FASTME, tag_contains=query_id,
    )

    missing = []
    if validate is None:
        missing.append(PROC_VALIDATE_INPUT)
    if blastn is None:
        missing.append(f"{PROC_BLAST_BLASTN} (or {PROC_MOCK_BLASTN})")
    if blastdbcmd is None:
        missing.append(PROC_BLAST_BLASTDBCMD)
    if taxonomy is None:
        missing.append(PROC_EXTRACT_TAXONOMY)
    if fastme is None:
        missing.append(f"{PROC_FASTME} tagged with {query_id!r}")
    if missing:
        raise HarvestError(
            "Cannot build a full case dir — the run did not produce"
            " tasks for the following required workflow steps:\n"
            + "\n".join(f"  - {m}" for m in missing)
            + "\nThis is common for nf-test scenarios that mock or"
            " truncate the workflow — harvest needs a full end-to-end"
            " run."
        )

    # blast_result.xml is published to <outdir>/blast_result.xml; the
    # per-query candidates_phylogeny.nwk is published to
    # <outdir>/<fastme.tag>/candidates_phylogeny.nwk. These publishDir
    # copies rescue us when the source workdir is unreachable (stale
    # staging symlinks, cleaned scratch, etc.).
    return [
        SourceFile(
            CASE_BLAST_XML, blastn.workdir_uri, WD_BLAST_XML, "xml",
            outdir_subpath=CASE_BLAST_XML,
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
            outdir_subpath=f"{fastme.tag}/{WD_CANDIDATES_NWK}",
        ),
        SourceFile(
            CASE_TAXIDS_CSV, blastdbcmd.workdir_uri, WD_TAXIDS_CSV, None,
        ),
        SourceFile(
            CASE_TAXONOMY_CSV, taxonomy.workdir_uri, WD_TAXONOMY_CSV,
            None,
        ),
    ]
