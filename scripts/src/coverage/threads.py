"""docstring"""

import logging
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.gbif.relatives import RelatedTaxaGBIF
from src.utils import errors
from src.utils.config import Config
from src.utils.flags import TARGETS

from .fetch import (
    get_related_country_coverage,
    get_related_coverage,
    get_target_coverage,
)

logger = logging.getLogger(__name__)
config = Config()

MODULE_NAME = "Database Coverage"


def parallel_process_tasks(
    tasks,
    query_dir,
    target_taxids,
    target_gbif_taxa,
    taxid_to_taxon,
    candidate_list,
    toi_list,
    pmi,
):
    with ThreadPoolExecutor(max_workers=15) as executor:
        results = {
            get_target_coverage.__name__: {},
            get_related_coverage.__name__: {},
            get_related_country_coverage.__name__: {},
        }
        logger.debug(
            f"Threading {len(tasks)} tasks..."
        )
        future_to_task = {
            executor.submit(*task): task
            for task in tasks
        }
        for future in as_completed(future_to_task):
            func, target = future_to_task[future][:2]
            logger.info(f"Task completed: {func.__name__} on target"
                        f" '{target}'")
            try:
                results[func.__name__][target] = future.result()
            except Exception as exc:
                species_name = target
                if isinstance(target, RelatedTaxaGBIF):
                    species_name = target.taxon
                elif isinstance(target, str):
                    species_name = taxid_to_taxon[target]
                target_source = (
                    "candidate" if species_name in candidate_list
                    else "taxon of interest" if species_name in toi_list
                    else "preliminary ID"
                )
                msg = (
                    f"Error processing {func.__name__} for target taxon"
                    f" '{species_name}' ({target_source}). This target could"
                    f" not be evaluated."
                    f" Exception: {type(exc).__name__}: {exc}")
                logger.error(f"{msg}")
                errors.write(
                    errors.LOCATIONS.DB_COVERAGE,
                    msg,
                    exc=exc,
                    query_dir=query_dir,
                    context={'target': species_name})
                if isinstance(exc, urllib.error.URLError):
                    raise errors.APIError(
                        f"Fatal error fetching data from Entrez API: '{exc}'"
                        " This error occurred multiple times and indicates a"
                        " network issue - please resume this"
                        " job at a later time when network issues have"
                        " resolved. If this issue persists, you may need to"
                        " contact the development team to diagnose the"
                        " issue. You can check the status of the Entrez API"
                        " by visiting"
                        " https://eutils.ncbi.nlm.nih.gov"
                        "/entrez/eutils/efetch.fcgi in your browser.")

    logger.debug("Results collected from tasks:")
    for func, result in results.items():
        for k in result:
            logger.debug(f"{func}: {k}")

    return _collect_results(
        results,
        target_taxids,
        target_gbif_taxa,
        candidate_list,
        toi_list,
        pmi,
    )


def _collect_results(
    results,
    target_taxids,
    target_gbif_taxa,
    candidate_list,
    toi_list,
    pmi,
):
    error_detected = False
    candidate_results = {}
    toi_results = {}
    pmi_results = {}

    taxa = list({
        **target_taxids,
        **target_gbif_taxa,
    }.keys())

    for target_taxon in taxa:
        gbif_taxon = target_gbif_taxa.get(target_taxon)
        taxid = target_taxids[target_taxon]
        target_result = results[get_target_coverage.__name__].get(taxid)
        related_result = results[get_related_coverage.__name__].get(
            gbif_taxon)
        country_result = results[get_related_country_coverage.__name__].get(
            gbif_taxon)
        error_detected = (
            error_detected
            or (
                # None result is expected in higher taxon targets
                target_taxon in target_gbif_taxa
                and None in (target_result, related_result, country_result)
                # TODO: But only if country was provided?
            )
        )
        if target_taxon in candidate_list:
            candidate_results[target_taxon] = candidate_results.get(
                target_taxon, {})
            candidate_results[target_taxon]['target'] = target_result
            candidate_results[target_taxon]['related'] = related_result
            candidate_results[target_taxon]['country'] = country_result
        if target_taxon in toi_list:
            toi_results[target_taxon] = toi_results.get(target_taxon, {})
            toi_results[target_taxon]['target'] = target_result
            toi_results[target_taxon]['related'] = related_result
            toi_results[target_taxon]['country'] = country_result
        if target_taxon == pmi:
            pmi_results[target_taxon] = {
                'target': target_result,
                'related': related_result,
                'country': country_result,
            }

    return {
        TARGETS.CANDIDATE: candidate_results,
        TARGETS.TOI: toi_results,
        TARGETS.PMI: pmi_results,
    }, error_detected
