"""Use the BOLD API to search for similar sequences to query."""

import argparse
import json
import logging
from pathlib import Path

from Bio import SeqIO

from src.bold.id_engine import BoldSearch
from src.utils import existing_path
from src.utils.config import Config

logger = logging.getLogger(__name__)
config = Config()


def main():
    args = _parse_args()
    config.configure(args.output_dir, bold=True)

    # Configuration is now handled in Config.__init__ via YAML

    logger.info(f"Searching BOLD with query {args.fasta_file}...")
    result = BoldSearch(args.fasta_file, config.bold_database)
    _write_hits_json(result)
    _write_hits_fasta(result)
    # _write_taxa_metadata(result)  # Not actually used downstream
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
    parser.add_argument(
        "--bold-database",
        type=str,
        help="BOLD database to search",
    )
    return parser.parse_args()


def _write_hits_json(result: BoldSearch):
    """Write the search results to a JSON file."""
    for query_title, hits in result.hits.items():
        query_ix = hits['query_index']
        query_dir = config.create_query_dir(query_ix, query_title)
        path = query_dir / config.hits_json
        with path.open("w") as f:
            json.dump(hits, f, indent=2)
            logger.info(f"BOLD hits for query [{query_ix}] written to {path}")


def _write_hits_fasta(result: BoldSearch):
    """Write the search results to a FASTA file."""
    for query_title, hits in result.hits.items():
        query_ix = hits['query_index']
        query_dir = config.get_query_dir(query_ix)
        path = query_dir / config.hits_fasta
        with path.open("w") as f:
            SeqIO.write(result.hit_sequences[query_title], f, "fasta")
            logger.info(f"BOLD hits for query [{query_ix}] written to {path}")


def _write_taxa_metadata(result: BoldSearch):
    """Write BOLD taxon record metadata to JSON files."""
    path = config.output_dir / config.bold_taxon_count_json
    with path.open("w") as f:
        json.dump(result.taxon_count, f, indent=2)
        logger.info(f"BOLD taxon count written to {path}")

    path = config.output_dir / config.bold_taxon_collectors_json
    with path.open("w") as f:
        json.dump(result.taxon_collectors, f, indent=2)
        logger.info(f"BOLD taxon collectors written to {path}")

    path = config.output_dir / config.bold_taxonomy_json
    with path.open("w") as f:
        json.dump(result.taxon_taxonomy, f, indent=2)
        logger.info(f"BOLD taxonomies written to {path}")


if __name__ == '__main__':
    main()
