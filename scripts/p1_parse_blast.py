"""Parse BLAST output into per-query JSON and FASTA files."""

import argparse
import json
import logging
from Bio import SeqIO

from src.blast.parse_xml import parse_blast_xml
from src.utils.config import Config
from src.utils.config.mappings import PARAMS

logger = logging.getLogger(__name__)
config = Config()


def main():
    args = _parse_args()
    config.update_from_args(args)
    hits, fastas = parse_blast_xml(args.blast_xml_path)
    _write_hits(hits)
    _write_fastas(fastas)
    _write_accessions(hits)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Parse BLAST XML output file."
    )
    parser.add_argument(
        PARAMS['blast_xml_path'].cli_name,
        type=PARAMS['blast_xml_path'].cast,
        help=PARAMS['blast_xml_path'].help_text,
    )
    parser = config.add_cli_args(parser, [
        PARAMS['metadata_csv'].required(),
        PARAMS['query_fasta'].required(),
        PARAMS['blast_max_target_seqs'],
    ])
    return parser.parse_args()


def _write_hits(hits):
    """Write a JSON file of BLAST hits for each query sequence."""
    for i, query_hits in enumerate(hits):
        query_dir = config.create_query_dir(i, query_hits['query_title'])
        path = query_dir / config.hits_json
        with path.open("w") as f:
            json.dump(query_hits, f, indent=2)
            logger.info(f"BLAST hits for query [{i}] written to {path}")


def _write_fastas(query_fastas):
    """Write a fasta file of hit subjects for each query sequence."""
    for i, fastas in enumerate(query_fastas):
        if not fastas:
            continue
        path = config.get_query_dir(i) / config.hits_fasta
        with open(path, "w") as f:
            SeqIO.write(fastas, f, "fasta")
            logger.info(
                f"BLAST hit sequences for query [{i}] written to {path}")


def _write_accessions(hits):
    """Write a unique list of BLAST hit accession IDs to a file.

    These will be used for extracting taxonomy data.
    """
    hit_accesssions_path = config.output_dir / config.accessions_filename
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
