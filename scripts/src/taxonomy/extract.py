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


class TaxonkitLineageResult:
    """Represent one line in taxonkit lineage output."""

    def __init__(self, fields: list[str]):
        taxid, taxon_details, ranks = fields[0], fields[1], fields[2]
        lineage_list = taxon_details.split(';')
        ranks_list = ranks.split(';')
        self.taxid = taxid
        self.ranks = ranks_list
        self.lineage = lineage_list
        self.taxonomy = [
            (rank, name)
            for rank, name in zip(ranks_list, lineage_list)
        ]
        self.filtered_taxonomy = {
            rank: name
            for rank, name in self.taxonomy
            if rank in TAXONOMIC_RANKS
        }


class TaxonkitName2TaxidResult:
    """Represent one line in taxonkit name2taxid output."""

    def __init__(self, line: str):
        self.taxid = None
        self.species = None
        fields = [
            x.strip() for x in line.split('\t')
            if x.strip()
        ]
        if len(fields) >= 2:
            self.species, self.taxid = fields[0], fields[1]
        elif fields[0].strip() and len(fields) == 1:
            self.species = fields[0].strip()
            self.taxid = None

    def __bool__(self):
        return self.species is not None


def taxonomies(taxids: list[str]) -> dict[str, dict[str, str]]:
    """Use taxonkit lineage to extract taxonomic data for given taxids."""

    # Because temporary file handling in Windows is different,
    # need to closed and delete temp file explicitly...
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
                '--data-dir', config.taxdb_dir,
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
    for res in _parse_taxonkit_lineage(result.stdout):
        taxonomy_data[res.taxid] = res.filtered_taxonomy
    return taxonomy_data


def taxids(
    species_list: list[str],
    classification: dict = None,
) -> dict[str, str]:
    """Use taxonkit name2taxid to extract taxids for given species.

    These species did not come from the core_nt database, so they might not
    even have a taxid if they are unsequenced/rare/new species.

    If a classification is specified, use that to filter the results to only
    those matching the classification (e.g. animalia). This helps avoid
    issues with ambiguous taxonomic names.
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
        res = subprocess.run(
            [
                'taxonkit',
                'name2taxid',
                temp_file.name,
                '--data-dir', config.taxdb_dir,
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
        + res.stdout[:1000]  # Limit to first 1000 characters
        + " [ ... ]"
    )
    if res.stderr.strip():
        logger.warning(
            "taxonkit name2taxid stderr:\n"
            + res.stderr
        )

    taxid_data = {}
    duplicate_taxids = {}

    for result in _parse_taxonkit_name2taxid(res.stdout, classification):
        existing_taxid = taxid_data.get(result.species)
        if existing_taxid and existing_taxid != result.taxid:
            duplicate_taxids[result.species] = duplicate_taxids.get(
                result.species, []) + [result.taxid]
        else:
            taxid_data[result.species] = result.taxid or None
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


def _parse_taxonkit_lineage(output: str) -> list[TaxonkitLineageResult]:
    """Parse lines from taxonkit lineage stdout."""
    warn = False
    results = []
    for line in output.strip().split('\n'):
        fields = line.split('\t')
        if len(fields) == 4:
            fields = fields[1:]  # Discard the first field (input taxid)
        if len(fields) == 3:
            res = TaxonkitLineageResult(fields)
            results.append(res)
        else:
            warn = True
    if warn:
        logger.warning(
            "Unexpected format in taxonkit stdout. This may result in missing"
            " taxonomy information:\n" + output)
    return results


def _parse_taxonkit_name2taxid(
    stdout: str,
    higher_classification: dict,
) -> list[TaxonkitName2TaxidResult]:
    """Extract ...

    Filter taxonkit name2taxid output lines by higher classification."""
    warn = False
    name_results: list[TaxonkitName2TaxidResult] = []
    for line in stdout.strip().split('\n'):
        if not line.strip():
            continue
        result = TaxonkitName2TaxidResult(line)
        if result:
            name_results.append(result)
        else:
            warn = True
    if warn:
        logger.warning(
            "Unexpected format in taxonkit stdout. This may result in missing"
            " taxid information:\n"
            + line)

    if not higher_classification:
        return name_results

    filtered_name_results: list[TaxonkitName2TaxidResult] = []
    no_taxid_results: list[TaxonkitName2TaxidResult] = []
    for name_result in name_results:
        if not name_result.taxid:
            no_taxid_results.append(name_result)
            continue
        try:
            process = subprocess.run(
                [
                    'taxonkit',
                    'lineage',
                    '-R',
                    '--data-dir', config.taxdb_dir,
                ],
                input=name_result.taxid,
                capture_output=True,
                text=True,
                check=True,
            )
            for lineage_result in _parse_taxonkit_lineage(process.stdout):
                for rank, taxon in lineage_result.taxonomy:
                    if (
                        rank.lower() == higher_classification['ncbi']['rank']
                        and taxon.lower() ==
                            higher_classification['ncbi']['taxon']
                    ):
                        filtered_name_results.append(name_result)
                        break

        except subprocess.CalledProcessError as exc:
            logger.error(
                f"taxonkit lineage failed for taxid {name_result.taxid} with"
                f" error:\n{exc.stderr}"
            )
            filtered_name_results.append(name_result)

    return filtered_name_results + no_taxid_results
