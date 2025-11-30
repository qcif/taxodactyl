"""Build the workflow report."""

import argparse

from src.report import report
from src.utils import existing_path
from src.utils.config import Config
from src.utils.config.mappings import CLI_ARGS

config = Config()


def main():
    """Build the workflow report."""
    args = _parse_args()
    config.update_from_args(args)
    report.render(
        args.query_dir,
        args.bold,
        params_json=args.params_json,
        versions_yml=args.versions_yml,
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
        help="If set, will enable the 'bold' logic for rendering the report."
    )
    parser.add_argument(
        "--params_json",  # Not mapped to config
        type=existing_path,
        help="Path to params JSON file."
    )
    parser.add_argument(
        "--versions_yml",  # Not mapped to config
        type=existing_path,
        help="Path to versions YAML file."
    )
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
        f"--{CLI_ARGS['debug'].cli_name}",
        action="store_true",
        help="Enable debug mode for report generation"
    )
    parser.add_argument(
        f"--{CLI_ARGS['database_name'].cli_name}",
        type=str,
        help="Name of the reference database"
    )
    parser.add_argument(
        f"--{CLI_ARGS['facility_name'].cli_name}",
        type=str,
        help="Name of the analysis facility"
    )
    parser.add_argument(
        f"--{CLI_ARGS['analyst_name'].cli_name}",
        type=str,
        help="Name of the analyst"
    )
    parser.add_argument(
        f"--{CLI_ARGS['flag_details_csv_path'].cli_name}",
        type=existing_path,
        help="Path to CSV file containing flag definitions"
    )

    return parser.parse_args()


if __name__ == '__main__':
    main()
