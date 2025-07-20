"""docstring"""

import logging
from pprint import pformat

from src.gbif.relatives import GBIFRecordNotFound, RANK, RelatedTaxaGBIF
from src.taxonomy import extract
from src.utils import errors
from src.utils.config import Config

logger = logging.getLogger(__name__)
config = Config()

MODULE_NAME = "Database Coverage"


def _read_candidate_species(query_dir):
    candidates = config.read_json(query_dir / config.CANDIDATES_JSON)
    return [
        c["species"]
        for c in candidates["species"]
    ]


def get_targets(query_dir):
    candidates = _read_candidate_species(query_dir)
    if len(candidates) > config.DB_COVERAGE_MAX_CANDIDATES:
        logger.info(
            f"Skipping database coverage assessment for"
            f" candidates: more than {config.DB_COVERAGE_MAX_CANDIDATES}"
            f" candidates species have been identified ({len(candidates)})."
        )
        candidates = []
    pmi = config.get_pmi_for_query(query_dir)
    toi_list = config.get_toi_list_for_query(query_dir)
    if len(toi_list) > config.DB_COVERAGE_TOI_LIMIT:
        toi_list = toi_list[:config.DB_COVERAGE_TOI_LIMIT]
        excluded_tois = toi_list[config.DB_COVERAGE_TOI_LIMIT:]
        msg = (
            f"Only the first {config.DB_COVERAGE_TOI_LIMIT} taxa of interest"
            f" will be evaluated. The following taxa of interest will be"
            f" excluded: {', '.join(excluded_tois)}. This limit can be raised"
            f" by setting the 'DB_COVERAGE_TOI_LIMIT' environment variable.")
        logger.warning(f"{msg}")
        errors.write(
            errors.LOCATIONS.DB_COVERAGE,
            msg,
            query_dir=query_dir,
        )
    return candidates, toi_list, pmi


def get_taxids(targets, query_dir):
    target_taxids = extract.taxids(targets)
    if not all(target_taxids.values()):
        msg = (
            "Taxonkit failed to produce taxids for this taxon."
            " Database coverage for this taxon is assumed to be zero, since"
            " this likely means it is not represented in the reference"
            " database.")
        for target in [
            k for k, v in target_taxids.items()
            if v is None
        ]:
            logger.warning(
                f"{msg} ({target})")
            errors.write(
                errors.LOCATIONS.DB_COVERAGE_TAXONKIT_ERROR,
                msg,
                query_dir=query_dir,
                context={"target": target},
            )
    return target_taxids


def fetch_target_taxa(targets, query_dir):
    target_gbif_taxa = {}
    higher_taxon_targets = {}  # Taxa at rank 'family' or higher
    for target in targets:
        try:
            gbif_target = RelatedTaxaGBIF(target)
        except GBIFRecordNotFound as exc:
            msg = (f"No GBIF record found for target taxon '{target}'."
                   " This target could not be evaluated.")
            logger.warning(
                f"{msg}")
            errors.write(
                errors.LOCATIONS.DB_COVERAGE_NO_GBIF_RECORD,
                msg,
                exc=exc,
                query_dir=query_dir,
                context={"target": target},
            )
            continue
        if gbif_target.rank and gbif_target.rank > RANK.GENUS:
            # These get processed differently - broad GB record count only
            higher_taxon_targets[target] = gbif_target
        else:
            target_gbif_taxa[target] = gbif_target

    logger.debug(
        "Targets identified at rank genus or lower:\n"
        + pformat(list(target_gbif_taxa.keys()), indent=2)
    )
    logger.debug(
        "Targets identified at rank family or higher:\n"
        + pformat(list(higher_taxon_targets.keys()), indent=2)
    )

    return target_gbif_taxa, higher_taxon_targets
