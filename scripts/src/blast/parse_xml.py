"""Parse BLAST XML output to JSON format and extract FASTA sequences."""

import logging

from Bio.Blast import NCBIXML
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

logger = logging.getLogger(__name__)


def calculate_hit_bitscore(hsps):
    """Calculate the total scores of all hsps for a hit."""
    return sum(hsp.bits for hsp in hsps)


def calculate_hit_e_value(hit, effective_search_space):
    """Calculate the e_value for a hit."""
    if len(hit.hsps) == 1:
        return hit.hsps[0].expect
    return effective_search_space * 2 ** (-sum(hsp.bits for hsp in hit.hsps))


def calculate_hit_identity(hsps):
    """Calculate the total identity of all hsps for a hit."""
    total_hsps_identity = sum(hsp.identities for hsp in hsps)
    total_hsp_align_length = sum(
        hsp.align_length for hsp in hsps
    )
    hit_identity = round(
        total_hsps_identity / total_hsp_align_length,
        3,
    )
    return min(hit_identity, 1) if total_hsp_align_length > 0 else 0


def calculate_hit_query_coverage(alignment_length, query_length):
    """Calculate query coverage as a percentage."""
    return min(round(
        alignment_length / query_length,
        3,
    ), 1) if query_length > 0 else 0


def calculate_alignment_length(hsps: list[NCBIXML.HSP]) -> int:
    regions = [
        (
            min(hsp.query_start, hsp.query_end),
            max(hsp.query_start, hsp.query_end),
        )
        for hsp in hsps
    ]
    regions.sort(key=lambda x: x[0])

    # Merge overlapping regions
    merged_regions = []
    for start, end in regions:
        if not merged_regions or merged_regions[-1][1] < start:
            merged_regions.append((start, end))
        else:
            # Overlapping region: merge with the last region
            merged_regions[-1] = (
                merged_regions[-1][0],
                max(merged_regions[-1][1], end),
            )

    return sum(
        end - start + 1
        for start, end in merged_regions
    )


def _get_printed_alignment(hsp, length=80):
    """Wrap query, subject and midline strings into a printable alignment."""
    def string_chunk(sequence, chunk_size=10):
        return " ".join(
            sequence[i:i + chunk_size]
            for i in range(0, len(sequence), chunk_size)
        )

    alignment_str = ""
    for i in range(0, len(hsp.query), length):
        digits = max(
            len(str(hsp.query_start + i)),
            len(str(hsp.sbjct_start + i)),
        )
        pad = digits + 8
        query = string_chunk(hsp.query[i:i + length])
        subject = string_chunk(hsp.sbjct[i:i + length])
        midline = string_chunk(hsp.match[i:i + length])
        alignment_str += (
            f"Query  {str(hsp.query_start + i).rjust(digits)} {query}\n")
        alignment_str += f"{' ' * pad}{midline}\n"
        alignment_str += (
            f"Sbjct  {str(hsp.sbjct_start + i).zfill(digits)} {subject}\n\n")

    return alignment_str


def parse_hit_def(hit_def: str) -> str:
    """Parse hit definition and remove synonym identifiers."""
    return hit_def.split('>')[0].strip()


def parse_blast_xml(blast_xml_path: str) -> tuple[
    list[dict],
    list[list[SeqRecord]],
]:
    """Parse BLAST XML output file and extract information about alignments."""
    with open(blast_xml_path, "r") as handle:
        blast_records = NCBIXML.parse(handle)
        results = []
        fasta_results = []

        for i, blast_record in enumerate(blast_records):
            fastas = []
            query_record = {
                "query_title": blast_record.query,
                "query_length": blast_record.query_length,
                "hits": []
            }
            effective_search_space = blast_record.effective_search_space

            for alignment in blast_record.alignments:
                hit_score = calculate_hit_bitscore(alignment.hsps)
                hit_e_value = calculate_hit_e_value(
                    alignment,
                    effective_search_space)
                hit_identity = calculate_hit_identity(
                    alignment.hsps
                )
                alignment_length = calculate_alignment_length(alignment.hsps)
                hit_query_coverage = calculate_hit_query_coverage(
                    alignment_length,
                    blast_record.query_length,
                )
                hit_def_stripped = parse_hit_def(alignment.hit_def)
                hit_record = {
                    "hit_id": alignment.hit_id,
                    "hit_subject": hit_def_stripped,
                    "accession": alignment.accession,
                    "alignment_length": alignment_length,
                    "subject_length": alignment.length,  # poor naming Bio?
                    "query_coverage": hit_query_coverage,
                    "bitscore": hit_score,
                    "e_value": hit_e_value,
                    "identity": hit_identity,
                    "hsps": [],
                }

                for hsp in alignment.hsps:
                    hsp_record = {
                        "bitscore": hsp.bits,
                        "e_value": hsp.expect,
                        "identity": round(
                            hsp.identities / hsp.align_length,
                            3,
                        ),
                        "identities": hsp.identities,
                        "strand_query": hsp.strand[0],
                        "strand_subject": hsp.strand[1],
                        "gaps": hsp.gaps,
                        "query_start": hsp.query_start,
                        "query_end": hsp.query_end,
                        "subject_start": hsp.sbjct_start,
                        "subject_end": hsp.sbjct_end,
                        "alignment_length": hsp.align_length,
                        "alignment": _get_printed_alignment(hsp),
                    }
                    hit_record["hsps"].append(hsp_record)

                fastas.append(SeqRecord(
                    Seq(hsp.sbjct),
                    id=alignment.accession,
                    description=hit_def_stripped))
                query_record["hits"].append(hit_record)

            if not query_record["hits"]:
                logger.info(
                    "No BLAST hits found for query"
                    f" [{query_record['query_title']}]"
                )

            # Re-order hits by identity
            query_record["hits"].sort(
                key=lambda x: x["identity"],
                reverse=True,
            )

            logger.info(f"Query [{i}] - collected {len(query_record["hits"])}"
                        f" BLAST hits")
            fasta_results.append(fastas)
            results.append(query_record)

    return results, fasta_results
