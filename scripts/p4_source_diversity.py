"""Analyze the diversity of reference sequence sources oer target.

A source is defined as a publication or set of authors that are linked to the
genbank record for that sequence. If there are no references, no sources are
returned and the sequence is classified as "anonymous".

Many anonymous records are from automated genome annotation projects, often
carried out by NCBI themselves. These records are flagged so that the user can
be aware of the potential reduced credibility of these annotation.
"""

import argparse
import json
import logging
from pathlib import Path

from src.sources import collect
from src.utils import existing_path, serialize
from src.utils.config import Config
from src.utils.config.mappings import CLI_ARGS
from src.utils.flags import FLAGS, Flag

logger = logging.getLogger(__name__)
config = Config()


def main():
    args = _parse_args()
    config.update_from_args(args)
    species, hits = _read_candidate_hits(args.query_dir)
    candidate_hits = [
        hit for hit in hits
        if hit['is_candidate_hit']
    ]
    species, hits, aggregated_sources = collect.sources_per_species(
        species, candidate_hits)
    _set_flags(species, args.query_dir)
    _write_sources(aggregated_sources, args.query_dir)
    config.cleanup()


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        CLI_ARGS['query_dir'].cli_name,
        type=existing_path,
        help="Path to query output directory")
    parser.add_argument(
        f"--{CLI_ARGS['output_dir'].cli_name}",
        type=existing_path,
        default=config.output_dir,
        help=f"Path to output directory. Defaults to {config.output_dir}.")
    parser.add_argument(
        f"--{CLI_ARGS['metadata_csv'].cli_name}",
        type=existing_path,
        help="Path to metadata.csv input file.",
        required=True,
    )
    parser.add_argument(
        f"--{CLI_ARGS['query_fasta'].cli_name}",
        type=existing_path,
        help="Path to queries.fasta input file.",
        required=True,
    )
    parser.add_argument(
        f"--{CLI_ARGS['sources_min_count'].cli_name}",
        type=int,
        help="Minimum number of independent sources required",
    )
    parser.add_argument(
        f"--{CLI_ARGS['temp_root'].cli_name}",
        type=Path,
        help="Path to temp root directory (defaults to"
             f" '{config.temp_root_dir}')",
    )
    parser.add_argument(
        f"--{CLI_ARGS['temp_dir_name'].cli_name}",
        type=str,
        help="The name of the temp dir to create within the temp root"
             f" (defaults to '{config.temp_dir_name}')",
    )
    return parser.parse_args()


def _read_candidate_hits(query_dir):
    candidates = config.read_json(query_dir / config.candidates_json)
    species = candidates["species"]
    hits = candidates["hits"]
    return species, hits


def _set_flags(species_sources, query_dir):
    """Set flag 4 (source diversity) from output data."""
    for species in species_sources:
        flag_value = (
            FLAGS.A
            if species['independent_sources']
            > config.criteria.sources_min_count
            else FLAGS.B
        )
        Flag.write(
            query_dir,
            FLAGS.SOURCES,
            flag_value,
            target=species['species'],
        )


def _write_sources(sources, query_dir):
    path = query_dir / config.independent_sources_json
    with path.open('w') as f:
        json.dump(sources, f, default=serialize, indent=2)
    logger.info(f"Aggregated reference sequence sources written to {path}")


if __name__ == '__main__':
    main()
