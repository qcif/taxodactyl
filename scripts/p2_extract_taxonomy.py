"""Extract taxids and taxonomic information from NCBI databases.

This requires access to the NCBI taxdump files (configurable by CLI param).

"""

import argparse
import csv
import logging

from src.taxonomy import extract
from src.taxonomy.extract import TAXONOMIC_RANKS
from src.utils import existing_path
from src.utils.config import Config

logger = logging.getLogger(__name__)
config = Config()


def main():
    args = _parse_args()
    config.configure(args.output_dir)
    with args.taxids_csv.open() as taxids_file:
        accession_taxids = {
            row[0]: row[1]
            for row in csv.reader(taxids_file)
        }
    taxids = sorted(set(accession_taxids.values()))
    taxonomies = extract.taxonomies(taxids)
    _write_csv(taxonomies, accession_taxids)


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'taxids_csv',
        type=existing_path,
        help='CSV file with columns (accession,taxid) to extract taxonomy'
             ' information for.',
    )
    parser.add_argument(
        "--output_dir",
        type=existing_path,
        help="Directory to save parsed output files (JSON and FASTA). Defaults"
             f" to env variable 'OUTPUT_DIR' or '{config.output_dir}'.",
        default=config.output_dir,
    )
    return parser.parse_args()


def _write_csv(taxonomies, accession_taxids):
    path = config.output_dir / config.TAXONOMY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=['accession', 'taxid'] + TAXONOMIC_RANKS,
        )
        writer.writeheader()
        rows = [
            {
                'accession': accession,
                'taxid': taxid,
                **taxonomies[taxid]
            }
            for accession, taxid in accession_taxids.items()
            if taxid in taxonomies
        ]
        writer.writerows(rows)
    logger.info(f"Taxonomy records written to {path}")


if __name__ == '__main__':
    main()
