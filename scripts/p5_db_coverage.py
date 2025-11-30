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
from pathlib import Path

from src.coverage import assess_coverage
from src.utils import existing_path
from src.utils.config import Config
from src.utils.config.mappings import CLI_ARGS

logger = logging.getLogger(__name__)
config = Config()

MODULE_NAME = "Database Coverage"


def main():
    args = _parse_args()
    config.update_from_args(args)
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
        "query_dir",  # Not mapped to config
        type=existing_path,
        help="Path to query output directory")
    parser.add_argument(
        "--bold",  # Not mapped to config
        action="store_true",
        help="Reference the BOLD database instead of GenBank.")
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
        f"--{CLI_ARGS['db_coverage_toi_limit'].cli_name}",
        type=int,
        help="Limit for taxa of interest in coverage analysis",
    )
    parser.add_argument(
        f"--{CLI_ARGS['db_coverage_max_candidates'].cli_name}",
        type=int,
        help="Maximum candidates for coverage assessment",
    )
    parser.add_argument(
        f"--{CLI_ARGS['gbif_limit_records'].cli_name}",
        type=int,
        help="Limit for GBIF taxonomy records",
    )
    parser.add_argument(
        f"--{CLI_ARGS['gbif_max_occurrence_records'].cli_name}",
        type=int,
        help="Maximum GBIF occurrence records",
    )
    parser.add_argument(
        f"--{CLI_ARGS['gbif_accepted_status'].cli_name}",
        type=str,
        help="Comma-separated list of accepted taxonomic statuses",
    )
    parser.add_argument(
        f"--{CLI_ARGS['db_cov_target_min_a'].cli_name}",
        type=int,
        help="Minimum reference database record count for target species flag"
             " 5.1A.",
    )
    parser.add_argument(
        f"--{CLI_ARGS['db_cov_target_min_b'].cli_name}",
        type=int,
        help="Minimum database coverage record count for target species flag"
             " 5.1B.",
    )
    parser.add_argument(
        f"--{CLI_ARGS['db_cov_related_min_a'].cli_name}",
        type=int,
        help="Minimum database species coverage for target genus flag 5.2A.",
    )
    parser.add_argument(
        f"--{CLI_ARGS['db_cov_related_min_b'].cli_name}",
        type=int,
        help="Minimum database species coverage for target genus flag 5.2B",
    )
    parser.add_argument(
        f"--{CLI_ARGS['db_cov_country_missing_a'].cli_name}",
        type=int,
        help="Threshold for missing country data (grade A)",
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


def write_db_coverage(query_dir, results):
    path = query_dir / config.db_coverage_json
    with path.open("w") as f:
        json.dump(results, f, indent=2)
    logger.info(
        f"Database coverage data written to {path}")
    return path


if __name__ == '__main__':
    main()
