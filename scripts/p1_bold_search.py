"""Use the BOLD API to search for similar sequences to query."""

import argparse
import json
import logging
from pathlib import Path

from Bio import SeqIO

from src.bold.id_engine import BOLD_MODES, BoldSearch
from src.utils import existing_path
from src.utils.config import Config

logger = logging.getLogger(__name__)
config = Config()


def main():
    args = _parse_args()
    config.configure(args.output_dir, bold=True)
    logger.info(f"Searching BOLD with query {args.fasta_file}...")
    search = BoldSearch(
        args.fasta_file,
        database=config.BOLD_DATABASE,
        mode=BOLD_MODES.RAPID_SPECIES,
    )
    _write_hits_json(search)
    _write_hits_fasta(search)
    logger.info("BOLD search completed.")


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "fasta_file",
        type=existing_path,
        help="Path to the FASTA file containing sequences to search.",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        help="Directory to save parsed output files (JSON and FASTA). Defaults"
             f" to env variable 'OUTPUT_DIR' or '{config.output_dir}'.",
        default=config.output_dir,
    )
    return parser.parse_args()


def _write_hits_json(search: BoldSearch):
    """Write the search results to a JSON file."""
    for result in search.results.values():
        query_ix = result['query_index']
        query_dir = config.create_query_dir(query_ix, result['query_title'])
        path = query_dir / config.HITS_JSON
        with path.open("w") as f:
            json.dump(result, f, indent=2)
            logger.info(f"BOLD hits for query [{query_ix}] written to {path}")


def _write_hits_fasta(search: BoldSearch):
    """Write the search results to a FASTA file."""
    for query_id, result in search.results.items():
        query_ix = result['query_index']
        query_dir = config.get_query_dir(query_ix)
        path = query_dir / config.HITS_FASTA
        with path.open("w") as f:
            SeqIO.write(search.hit_sequences[query_id], f, "fasta")
            logger.info(f"BOLD hits for query [{query_ix}] written to {path}")


if __name__ == '__main__':
    main()
