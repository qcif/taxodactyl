"""Build the workflow report."""

import argparse

from src.report import report
from src.utils import existing_path
from src.utils.config import Config
from src.utils.config.mappings import ARGUMENTS

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
        f"--{ARGUMENTS.OUTPUT_DIR}",
        type=existing_path,
        default=config.output_dir,
        help=f"Path to output directory. Defaults to {config.output_dir}.")
    parser.add_argument(
        f"--{ARGUMENTS.METADATA_CSV}",
        type=existing_path,
        help="Path to metadata.csv input file.",
        required=True,
    )
    parser.add_argument(
        f"--{ARGUMENTS.QUERY_FASTA}",
        type=existing_path,
        help="Path to queries.fasta input file.",
        required=True,
    )
    parser.add_argument(
        f"--{ARGUMENTS.REPORT_DEBUG}",
        action="store_true",
        help="Enable debug mode for report generation"
    )
    parser.add_argument(
        f"--{ARGUMENTS.DATABASE_NAME}",
        type=str,
        help="Name of the reference database"
    )
    parser.add_argument(
        f"--{ARGUMENTS.FACILITY_NAME}",
        type=str,
        help="Name of the analysis facility"
    )
    parser.add_argument(
        f"--{ARGUMENTS.ANALYST_NAME}",
        type=str,
        help="Name of the analyst"
    )
    parser.add_argument(
        f"--{ARGUMENTS.FLAG_DETAILS_CSV}",
        type=existing_path,
        help="Path to CSV file containing flag definitions"
    )

    return parser.parse_args()


if __name__ == '__main__':
    main()
