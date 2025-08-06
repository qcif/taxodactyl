"""Analyze the database coverage of target species at the given locus.

Database coverage is analysed at three levels:

1. Target species coverage: The number of records for the target species
2. Related species coverage: The number of records for species related to the
   target species
3. Related species from sample country of origin: as for (2), but only for
   species which have occurence records in the same country as the target
   species.
"""

import argparse
import json
import logging
import sys

from src.coverage import assess_coverage
from src.utils import existing_path
from src.utils.config import Config

logger = logging.getLogger(__name__)
config = Config()

MODULE_NAME = "Database Coverage"


def main():
    args = _parse_args()
    config.configure(args.output_dir, query_dir=args.query_dir)

    # Configuration is now handled in Config.__init__ via YAML

    results, error_detected = assess_coverage(
        args.query_dir,
        is_bold=args.bold,
    )
    write_db_coverage(args.query_dir, results)
    config.cleanup()
    if error_detected:
        sys.stderr.write(
            f'[Query {args.query_dir.name}] An error occurred during database'
            ' coverage assessment that'
            ' prevented one or more target species from being assessed.'
            ' For further details, please consult the error files in'
            f' {args.query_dir}/errors/*.json, or view the workflow report.\n'
        )


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "query_dir", type=existing_path, help="Path to query output directory")
    parser.add_argument(
        "--output_dir",
        type=existing_path,
        default=config.output_dir,
        help=f"Path to output directory. Defaults to {config.output_dir}.")
    parser.add_argument(
        "--bold",
        action="store_true",
        help="Reference the BOLD database instead of GenBank.")
    parser.add_argument(
        "--db-coverage-toi-limit",
        type=int,
        help="Limit for taxa of interest in coverage analysis",
    )
    parser.add_argument(
        "--db-coverage-max-candidates",
        type=int,
        help="Maximum candidates for coverage assessment",
    )
    parser.add_argument(
        "--gbif-limit-records",
        type=int,
        help="Limit for GBIF taxonomy records",
    )
    parser.add_argument(
        "--gbif-max-occurrence-records",
        type=int,
        help="Maximum GBIF occurrence records",
    )
    parser.add_argument(
        "--gbif-accepted-status",
        type=str,
        help="Comma-separated list of accepted taxonomic statuses",
    )
    parser.add_argument(
        "--db-cov-target-min-a",
        type=int,
        help="Minimum records for target species (grade A)",
    )
    parser.add_argument(
        "--db-cov-target-min-b",
        type=int,
        help="Minimum records for target species (grade B)",
    )
    parser.add_argument(
        "--db-cov-related-min-a",
        type=int,
        help="Minimum records for related species (grade A)",
    )
    parser.add_argument(
        "--db-cov-related-min-b",
        type=int,
        help="Minimum records for related species (grade B)",
    )
    parser.add_argument(
        "--db-cov-country-missing-a",
        type=int,
        help="Threshold for missing country data (grade A)",
    )
    return parser.parse_args()


def write_db_coverage(query_dir, results):
    path = query_dir / config.db_coverage_json
    with path.open("w") as f:
        json.dump(results, f, indent=2)
    logger.info(
        f"Database coverage data written to {path}")
    return path


if __name__ == '__main__':
    main()
