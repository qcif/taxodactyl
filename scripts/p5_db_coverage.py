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
from src.utils.config import Config
from src.utils.config.mappings import PARAMS

logger = logging.getLogger(__name__)
config = Config()

MODULE_NAME = "Database Coverage"


def main():
    args = _parse_args()
    config.update_from_args(args)
    results, error_detected = assess_coverage(
        args.query_dir,
        is_bold=args.is_bold,
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
        PARAMS['query_dir'].cli_name,
        type=PARAMS['query_dir'].cast,
        help=PARAMS['query_dir'].help_text,
    )
    parser = config.add_cli_args(parser, [
        PARAMS['is_bold'],
        PARAMS['metadata_csv'].required(),
        PARAMS['query_fasta'].required(),
        PARAMS['db_coverage_toi_limit'],
        PARAMS['db_coverage_max_candidates'],
        PARAMS['gbif_limit_records'],
        PARAMS['gbif_max_occurrence_records'],
        PARAMS['gbif_accepted_status'],
        PARAMS['db_cov_target_min_a'],
        PARAMS['db_cov_target_min_b'],
        PARAMS['db_cov_related_min_a'],
        PARAMS['db_cov_related_min_b'],
        PARAMS['db_cov_country_missing_a'],
        PARAMS['temp_root'],
        PARAMS['temp_dir_name'],
    ])
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
