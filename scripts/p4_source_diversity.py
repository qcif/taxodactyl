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

from src.sources import collect
from src.utils import existing_path, serialize
from src.utils.config import Config
from src.utils.flags import FLAGS, Flag

logger = logging.getLogger(__name__)
config = Config()


def main():
    args = _parse_args()
    config.configure(args.output_dir, query_dir=args.query_dir)
    species, hits = _read_candidate_hits(args.query_dir)
    candidate_hits = [
        hit for hit in hits
        if hit['is_candidate_hit']
    ]
    species, hits, aggregated_sources = collect.sources_per_species(
        species, candidate_hits)
    _set_flags(species, args.query_dir)
    _write_sources(aggregated_sources, args.query_dir)

    # Current unused output:
    # candidates = {
    #     "species": species,
    #     "hits": hits,
    # }
    # _write_candidates(candidates, args.query_dir)

    config.cleanup()


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "query_dir", type=existing_path, help="Path to query output directory")
    parser.add_argument(
        "--output_dir",
        type=existing_path,
        default=config.output_dir,
        help=f"Path to output directory. Defaults to {config.output_dir}.")
    return parser.parse_args()


def _read_candidate_hits(query_dir):
    candidates = config.read_json(query_dir / config.CANDIDATES_JSON)
    species = candidates["species"]
    hits = candidates["hits"]
    return species, hits


def _set_flags(species_sources, query_dir):
    """Set flag 4 (source diversity) from output data."""
    for species in species_sources:
        flag_value = (
            FLAGS.A
            if species['independent_sources']
            > config.CRITERIA.SOURCES_MIN_COUNT
            else FLAGS.B
        )
        Flag.write(
            query_dir,
            FLAGS.SOURCES,
            flag_value,
            target=species['species'],
        )


def _write_candidates(candidates, query_dir):
    path = query_dir / config.CANDIDATES_SOURCES_JSON
    with path.open('w') as f:
        json.dump(candidates, f, default=serialize, indent=2)
    logger.info(f"Candidate hits with source diversity data written to {path}")


def _write_sources(sources, query_dir):
    path = query_dir / config.INDEPENDENT_SOURCES_JSON
    with path.open('w') as f:
        json.dump(sources, f, default=serialize, indent=2)
    logger.info(f"Aggregated reference sequence sources written to {path}")


if __name__ == '__main__':
    main()
