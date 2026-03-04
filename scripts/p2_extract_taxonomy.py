"""Extract taxids and taxonomic information from NCBI databases.

This requires access to the NCBI taxdump files (configurable by CLI param).

"""

import argparse
import csv
import logging

from src.taxonomy import extract
from src.taxonomy.extract import TAXONOMIC_RANKS
from src.utils.config import Config
from src.utils.config.mappings import PARAMS

logger = logging.getLogger(__name__)
config = Config()


def main():
    args = _parse_args()
    config.update_from_args(args)
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
        PARAMS['taxids_csv'].cli_name,
        type=PARAMS['taxids_csv'].cast,
        help=PARAMS['taxids_csv'].help_text,
    )
    parser = config.add_cli_args(parser, [
        PARAMS['metadata_csv'].required(),
        PARAMS['query_fasta'].required(),
    ])
    return parser.parse_args()


def _write_csv(taxonomies, accession_taxids):
    path = config.output_dir / config.taxonomy_file
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=['accession', 'taxid'] + TAXONOMIC_RANKS,
        )
        writer.writeheader()
        rows = [
            {
                # Split off trailing .\d to match BLAST result format
                'accession': accession.split('.')[0],
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
