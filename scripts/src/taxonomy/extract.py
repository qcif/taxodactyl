import logging
import os
import subprocess
import tempfile

from src.utils import errors
from src.utils.config import Config

logger = logging.getLogger(__name__)
config = Config()


TAXONOMIC_RANKS = [
    "domain",
    "superkingdom",
    'kingdom',
    'phylum',
    'class',
    'order',
    'family',
    'genus',
    'species',
]


def taxonomies(taxids: list[str]) -> dict[str, dict[str, str]]:
    """Use taxonkit lineage to extract taxonomic data for given taxids."""

    # Because temporary file handling in Windows is different,
    # delete parameter need to be set to False and closed manually
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
        temp_file.write("\n".join(taxids))
        temp_file.flush()
        temp_file_name = temp_file.name
    try:
        result = subprocess.run(
            [
                'taxonkit',
                'lineage',
                '-R',
                '-c', temp_file_name,
                '--data-dir', config.TAXONKIT_DATA,
            ],
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.error(
            "Taxonkit lineage failed with error:\n"
            + exc.stderr
        )
        raise exc
    finally:
        if temp_file:
            temp_file.close()
        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)
            logger.debug(
                f"Temporary file {temp_file_name} deleted successfully."
            )

    logger.debug(
        "taxonkit name2taxid stdout:\n"
        + result.stdout[:1000]  # Limit to first 1000 characters
        + " [ ... ]"
    )
    if result.stderr.strip():
        logger.warning(
            "Taxonkit name2taxid stderr:\n"
            + result.stderr
        )

    taxonomy_data = {}
    for line in result.stdout.strip().split('\n'):
        fields = line.split('\t')[1:]
        if len(fields) == 3:
            taxid, taxon_details, ranks = fields[0], fields[1], fields[2]
            lineage_list = taxon_details.split(';')
            ranks_list = ranks.split(';')
            taxonomy = {
                rank: name for rank,
                name in zip(ranks_list, lineage_list)
                if rank in TAXONOMIC_RANKS
            }
            taxonomy_data[taxid] = taxonomy
        else:
            logger.warning(
                "Unexpected format in taxonkit"
                " stdout. This may result in missing taxonomy information")
    return taxonomy_data


def taxids(species_list: list[str]) -> dict[str, str]:
    """Use taxonkit name2taxid to extract taxids for given species.

    These species did not come from the core_nt database, so they might not
    even have a taxid if they are unsequenced/rare/new species.
    """
    logger.debug(
        "Extracting taxids for species using taxonkit"
        f" name2taxid with {len(species_list)} species:\n"
        + "\n".join(species_list[:3] + ['...'])
    )

    # Because temporary file handling in Windows is different,
    # delete parameter need to be set to False and closed manually
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
        temp_file.write("\n".join(species_list))
        temp_file.flush()
        temp_file_name = temp_file.name
    try:
        result = subprocess.run(
            [
                'taxonkit',
                'name2taxid',
                temp_file.name,
                '--data-dir', config.TAXONKIT_DATA,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.error(
            "taxonkit name2taxid failed with error:\n"
            + exc.stderr
        )
        raise exc
    finally:
        if temp_file:
            temp_file.close()
        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)
            logger.debug(
                f"Temporary file {temp_file_name} deleted successfully."
            )

    logger.debug(
        "taxonkit name2taxid stdout:\n"
        + result.stdout[:1000]  # Limit to first 1000 characters
        + " [ ... ]"
    )
    if result.stderr.strip():
        logger.warning(
            "taxonkit name2taxid stderr:\n"
            + result.stderr
        )

    taxid_data = {}
    duplicate_taxids = {}
    lines = [
        x for x in result.stdout.strip().split('\n')
        if x.strip()
    ]

    for line in lines:
        fields = line.split('\t')
        if len(fields) == 2:
            species, taxid = fields
        elif fields[0].strip() and len(fields) == 1:
            species = fields[0].strip()
            taxid = None
        else:
            logger.warning(
                "Unexpected format in taxonkit"
                " stdout. This may result in missing taxid information:\n"
                + line)

        existing_taxid = taxid_data.get(species)
        if existing_taxid and existing_taxid != taxid:
            duplicate_taxids[species] = duplicate_taxids.get(
                species, []) + [taxid]
        else:
            taxid_data[species] = taxid or None

    for species, taxids in duplicate_taxids.items():
        msg = (
            f'Duplicate taxid(s) {taxids} found for taxon "{species}" in'
            " taxonkit name2taxid output. The first taxid returned"
            f" ({taxid_data[species]})"
            " has been used. This may result in incorrect taxid information."
        )
        logger.warning(msg)
        errors.write(
            errors.LOCATIONS.DB_COVERAGE_TAXONKIT_ERROR,
            msg,
            query_dir=config.get_query_dir(),
            context={'target': species},
        )

    return taxid_data
