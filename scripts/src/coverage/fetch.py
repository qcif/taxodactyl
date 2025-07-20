"""docstring"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.bold.stats import fetch_bold_records_count
from src.entrez import genbank
from src.gbif.relatives import RANK
from src.taxonomy import extract
from src.utils import errors
from src.utils.config import Config
from src.utils.flags import FLAGS

logger = logging.getLogger(__name__)
config = Config()

MODULE_NAME = "Database Coverage"


def get_target_coverage(taxid, gbif_target, locus, is_bold):
    """Return a count of the number of accessions for the given target."""
    # TODO: potential for caching gb count result here
    db_name = 'BOLD' if is_bold else 'Entrez'
    logger.info(
        f"Fetching {db_name} records for target taxid:"
        f"{taxid}, locus: '{locus}'..."
    )
    if is_bold:
        return fetch_bold_records_count(
            gbif_target.taxon,
            rank=RANK.to_string(gbif_target.rank),
        )
    return genbank.fetch_gb_records(locus, taxid, count=True)


def get_related_coverage(gbif_target, locus, query_dir, is_bold):
    """Return a count of the number of related species (same genus) and the
    number of species which have at least one accession in the database.
    """
    db_name = 'BOLD' if is_bold else 'Entrez'
    species_names = list({
        r["canonicalName"]
        for r in gbif_target.relatives
    })
    if not species_names:
        return {}
    logger.info(
        f"Fetching {db_name} records for target"
        f" '{gbif_target.taxon}' (locus: '{locus}') - {len(species_names)}"
        f" related species..."
    )
    # TODO: potential for caching GBIF related taxa here
    if is_bold:
        results, err = _fetch_bold_records_for_species(
            species_names,
            rank=RANK.to_string(gbif_target.rank),
        )
    else:
        results, err = _fetch_gb_records_for_species(species_names, locus)
    if err:
        for species, exc in err:
            msg = (
                f"Error fetching related species records from {db_name} API:\n"
                f"(species: '{species}').")
            errors.write(
                errors.LOCATIONS.DB_COVERAGE_RELATED,
                msg,
                exc=exc,
                query_dir=query_dir,
                context={'target': species},
            )
    return results


def get_related_country_coverage(
    gbif_target,
    locus,
    country,
    query_dir,
    is_bold,
):
    db_name = 'BOLD' if is_bold else 'Entrez'
    if not country:
        return FLAGS.NA
    species_names = [
        r["canonicalName"]
        for r in gbif_target.for_country(country)
    ]
    if not species_names:
        return {}
    # TODO: potential for caching GBIF related/country taxa here
    logger.info(
        f"Fetching {db_name} records for target"
        f" '{gbif_target.taxon}' (locus: '{locus}'; country: '{country}')"
        f" - {len(species_names)} related species"
    )

    if is_bold:
        results, err = _fetch_bold_records_for_species(
            species_names,
            rank=RANK.to_string(gbif_target.rank),
        )
    else:
        results, err = _fetch_gb_records_for_species(species_names, locus)
    if err:
        for species, exc in err:
            msg = (
                f"Error fetching related/country species records from"
                f" {db_name} API (species: '{species}').")
            errors.write(
                errors.LOCATIONS.DB_COVERAGE_RELATED_COUNTRY,
                msg,
                exc=exc,
                query_dir=query_dir,
                context={'target': species},
            )
    return results


def _fetch_gb_records_for_species(species_names, locus):
    """Fetch a count of the number of Genbank accessions for each species in
    the list.
    """
    taxids = extract.taxids(species_names)
    species_without_taxid = [
        k for k, v in taxids.items()
        if v is None
    ]
    taxid_to_species = {
        v: k
        for k, v in taxids.items()
        if v is not None
    }
    tasks = [
        (locus, taxid)
        for taxid in taxids.values()
        if taxid is not None
    ]

    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_task = {
            executor.submit(genbank.fetch_gb_records, *task, count=True): task
            for task in tasks
        }

    results = {}
    errors = []
    for future in as_completed(future_to_task):
        locus, taxid = future_to_task[future]
        try:
            results[taxid] = future.result()
        except Exception as exc:
            logger.error(
                f"Error processing fetch_gb_records for"
                f" taxid {taxid}:\n{exc}")
            errors.append((taxid_to_species[taxid], exc))

    species_counts = {
        taxid_to_species[taxid]: count
        for taxid, count in results.items()
    }
    species_counts.update({
        species: 0
        for species in species_without_taxid
    })
    # TODO: potential for caching related species counts here
    return species_counts, errors


def _fetch_bold_records_for_species(taxa, rank):
    """Fetch a count of the number of BOLD accessions for each species in
    the list.
    """
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_task = {
            executor.submit(fetch_bold_records_count, taxon, rank=rank): taxon
            for taxon in taxa
        }
        results = {}
        errors = []
        for future in as_completed(future_to_task):
            taxon = future_to_task[future]
            try:
                results[taxon] = future.result()
            except Exception as exc:
                logger.error(
                    f"Error processing"
                    f" fetch_bold_records_count for taxon '{taxon}':\n{exc}")
                results[taxon] = None
                errors.append((taxon, exc))
    return results, errors
