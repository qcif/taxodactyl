"""Build the workflow report."""

import argparse

from src.report import report
from src.utils.config import Config
from src.utils.config.mappings import PARAMS

config = Config()


def main():
    """Build the workflow report."""
    args = _parse_args()
    config.update_from_args(args)
    report.render(
        args.query_dir,
        args.is_bold,
        params_json=args.params_json,
        versions_yml=args.versions_yml,
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
        PARAMS['params_json'],
        PARAMS['versions_yml'],
        PARAMS['metadata_csv'].required(),
        PARAMS['query_fasta'].required(),
        PARAMS['debug'],
        PARAMS['database_name'],
        PARAMS['facility_name'],
        PARAMS['analyst_name'],
        PARAMS['flag_details_csv_path'],
    ])
    return parser.parse_args()


if __name__ == '__main__':
    main()
