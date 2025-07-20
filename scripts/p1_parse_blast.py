"""Parse BLAST output into per-query JSON and FASTA files."""

import argparse
import json
import logging
from Bio import SeqIO
from pathlib import Path

from src.blast.parse_xml import parse_blast_xml
from src.utils import existing_path
from src.utils.config import Config

logger = logging.getLogger(__name__)
config = Config()


def main():
    args = _parse_args()
    config.configure(args.output_dir)
    hits, fastas = parse_blast_xml(args.blast_xml_path)
    _write_hits(hits)
    _write_fastas(fastas)
    _write_accessions(hits)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Parse BLAST XML output file."
    )
    parser.add_argument(
        "blast_xml_path",
        type=existing_path,
        help="Path to the BLAST XML file to parse.",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        help="Directory to save parsed output files (JSON and FASTA). Defaults"
             f" to env variable 'OUTPUT_DIR' or '{config.output_dir}'.",
        default=config.output_dir,
    )
    return parser.parse_args()


def _write_hits(hits):
    """Write a JSON file of BLAST hits for each query sequence."""
    for i, query_hits in enumerate(hits):
        query_dir = config.create_query_dir(i, query_hits['query_title'])
        path = query_dir / config.HITS_JSON
        with path.open("w") as f:
            json.dump(query_hits, f, indent=2)
            logger.info(f"BLAST hits for query [{i}] written to {path}")


def _write_fastas(query_fastas):
    """Write a fasta file of hit subjects for each query sequence."""
    for i, fastas in enumerate(query_fastas):
        if not fastas:
            continue
        path = config.get_query_dir(i) / config.HITS_FASTA
        with open(path, "w") as f:
            SeqIO.write(fastas, f, "fasta")
            logger.info(
                f"BLAST hit sequences for query [{i}] written to {path}")


def _write_accessions(hits):
    """Write a unique list of BLAST hit accession IDs to a file.

    These will be used for extracting taxonomy data.
    """
    hit_accesssions_path = config.output_dir / config.ACCESSIONS_FILENAME
    all_accessions = list({
        hit["accession"]
        for query in hits
        for hit in query["hits"]
    })
    with open(hit_accesssions_path, "w") as f:
        f.write('\n'.join(all_accessions) + '\n')
        logger.info(
            f"BLAST hit accession IDs written to {hit_accesssions_path}")


if __name__ == "__main__":
    main()
