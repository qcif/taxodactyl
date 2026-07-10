import logging
import os
import subprocess
import tempfile
import threading

from markupsafe import Markup

from src.utils import errors, ncbi
from src.utils.config import Config

logger = logging.getLogger(__name__)
config = Config()

_taxonkit_semaphore = threading.Semaphore(1)

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
        result = _run_taxonkit(
            [
                'taxonkit',
                'lineage',
                '-R',
                '-c', temp_file_name,
                '--data-dir', config.taxdb_dir,
            ],
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
    taxon_names: list[str],
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
        f" name2taxid with {len(taxon_names)} species:\n"
        + "\n".join(taxon_names[:3] + ['...'])
    )

    # Because temporary file handling in Windows is different,
    # delete parameter need to be set to False and closed manually
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
        temp_file.write("\n".join(taxon_names))
        temp_file.flush()
        temp_file_name = temp_file.name
    try:
        res = _run_taxonkit(
            [
                'taxonkit',
                'name2taxid',
                temp_file_name,
                '--data-dir', config.taxdb_dir,
            ],
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

    for result in _parse_and_filter_taxonkit_name2taxid(
        res.stdout,
        classification,
    ):
        existing_taxid = taxid_data.get(result.species)
        if existing_taxid and existing_taxid != result.taxid:
            duplicate_taxids[result.species] = duplicate_taxids.get(
                result.species, []) + [result.taxid]
        else:
            taxid_data[result.species] = result.taxid or None
    for species, taxids in duplicate_taxids.items():
        taxid_links = [
            Markup("<a href='{url}' target='_blank'>{taxid}</a>").format(
                url=ncbi.build_taxonomy_url(taxid),
                taxid=taxid,
            )
            for taxid in [taxid_data[species]] + taxids
        ]
        taxid_links_str = Markup(", ").join(taxid_links)
        msg = Markup(
            'Duplicate taxid(s) {links} found for taxon "{species}"'
            " in taxonkit name2taxid output. The first taxid returned"
            " ({first})"
            " has been used to retrieve Genbank sequence record counts for"
            " this species. You can better understand this issue by checking"
            " these taxonomy records."
        ).format(
            links=taxid_links_str,
            species=species,
            first=taxid_links[0],
        )
        logger.warning(msg.striptags())
        errors.write(
            errors.LOCATIONS.DB_COVERAGE_TAXONKIT_ERROR,
            msg,
            query_dir=config.get_query_dir(),
            context={'target': species},
        )

    return taxid_data


def _run_taxonkit(args, kwargs={}) -> subprocess.CompletedProcess:
    """Call taxonkit using a semaphore to ensure only one concurrent call."""
    kwargs = {
        'capture_output': True,
        'text': True,
        'check': True,
        **kwargs,
    }
    with _taxonkit_semaphore:
        return subprocess.run(args, **kwargs)


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


def _parse_and_filter_taxonkit_name2taxid(
    stdout: str,
    higher_classification: dict,
) -> list[TaxonkitName2TaxidResult]:
    """Extract taxids from taxonkit name2taxid output.

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
            " taxid information:\n" + line)

    if not higher_classification:
        return name_results

    # Separate results with and without taxids, and group results by taxid.
    taxid_to_results: dict[str, list[TaxonkitName2TaxidResult]] = {}
    filtered_name_results: list[TaxonkitName2TaxidResult] = []
    no_taxid_results: list[TaxonkitName2TaxidResult] = []

    for name_result in name_results:
        if not name_result.taxid:
            no_taxid_results.append(name_result)
            continue
        taxid_to_results.setdefault(name_result.taxid, []).append(name_result)

    if not taxid_to_results:
        return filtered_name_results + no_taxid_results

    try:
        process = _run_taxonkit(
            [
                'taxonkit',
                'lineage',
                '-R',
                '--data-dir', config.taxdb_dir,
            ],
            {
                'input': "\n".join(taxid_to_results.keys()),
            },
        )
        matching_taxids: set[str] = set()
        for lineage_result in _parse_taxonkit_lineage(process.stdout):
            # Assume it provides the taxid corresponding to the input
            lineage_taxid = getattr(lineage_result, "taxid", None)
            if not lineage_taxid:
                continue
            for rank, taxon in lineage_result.taxonomy:
                if (
                    rank.lower()
                    == higher_classification['ncbi']['rank']
                    and taxon.lower()
                    == higher_classification['ncbi']['taxon']
                ):
                    matching_taxids.add(lineage_taxid)
                    break
        if taxid_to_results and not matching_taxids:
            observed_ranks = {
                rank
                for lr in _parse_taxonkit_lineage(process.stdout)
                for rank, _ in lr.taxonomy
            }
            ncbi = higher_classification['ncbi']
            logger.warning(
                f"Classification filter"
                f" (rank='{ncbi['rank']}', taxon='{ncbi['taxon']}')"
                f" matched none of the {len(taxid_to_results)} taxid(s)"
                f" returned by taxonkit. All targets will be excluded from"
                f" DB coverage assessment. Ranks observed in taxonkit"
                f" lineage output: {sorted(observed_ranks)}. This may"
                f" indicate a mismatch between the configured classification"
                f" rank and the taxonkit database version."
            )
        for taxid in matching_taxids:
            for name_result in taxid_to_results.get(taxid, []):
                filtered_name_results.append(name_result)
    except subprocess.CalledProcessError as exc:
        logger.error(
            "taxonkit lineage failed for batched taxid lookup with error:\n"
            f"{exc.stderr}"
        )
        # On error, include all taxid results without filtering
        for results in taxid_to_results.values():
            filtered_name_results.extend(results)

    return filtered_name_results + no_taxid_results
