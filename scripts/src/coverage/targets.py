"""docstring"""

import logging
from pprint import pformat
from dataclasses import dataclass

from src.gbif.relatives import GBIFRecordNotFound, RANK, RelatedTaxaGBIF
from src.taxonomy import extract
from src.utils import errors
from src.utils.config import Config

logger = logging.getLogger(__name__)
config = Config()

MODULE_NAME = "Database Coverage"


@dataclass
class TargetGbifRecords:
    """GBIF records for the target taxa, indexed both by canonical name
    (the GBIF-accepted name used for internal processing) and by the
    original input string (used when writing output that must refer back
    to the user-supplied target).

    `higher_taxa` / `original_higher_taxa` contain records at rank
    'family' or higher; the others contain rank 'genus' or lower.

    `original_to_canonical` / `canonical_to_original` are inverse
    translation maps for renaming between the two name-spaces.
    """

    original_to_canonical: dict[str, str]
    canonical_to_original: dict[str, str]
    lower_taxa: dict[str, RelatedTaxaGBIF]            # keyed by canonical
    higher_taxa: dict[str, RelatedTaxaGBIF]           # keyed by canonical
    all_taxa: dict[str, RelatedTaxaGBIF]              # keyed by canonical
    original_lower_taxa: dict[str, RelatedTaxaGBIF]   # keyed by original
    original_higher_taxa: dict[str, RelatedTaxaGBIF]  # keyed by original


def _read_candidate_species(query_dir):
    candidates = config.read_json(query_dir / config.candidates_json)
    return [
        c["species"]
        for c in candidates["species"]
    ]


def get_targets(query_dir):
    candidates = _read_candidate_species(query_dir)
    if len(candidates) > config.db_coverage_max_candidates:
        logger.info(
            f"Skipping database coverage assessment for"
            f" candidates: more than {config.db_coverage_max_candidates}"
            f" candidates species have been identified ({len(candidates)})."
        )
        candidates = []
    pmi = config.get_pmi_for_query(query_dir)
    toi_list = config.get_toi_list_for_query(query_dir)
    if len(toi_list) > config.db_coverage_toi_limit:
        toi_list = toi_list[:config.db_coverage_toi_limit]
        excluded_tois = toi_list[config.db_coverage_toi_limit:]
        msg = (
            f"Only the first {config.db_coverage_toi_limit} taxa of interest"
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


def get_taxids(target_gbif_records, query_dir):
    targets = [
        t.canonical_name
        for t in target_gbif_records.values()
    ]
    classification = config.get_classification_for_query(query_dir)
    target_taxids = extract.taxids(targets, classification=classification)
    if not all(target_taxids.values()):
        msg = (
            "Taxonkit failed to produce taxids for this taxon."
            " Database coverage for this taxon is assumed to be zero, since"
            " this likely means it is not represented in the reference"
            " database. If this seems unlikely, perhaps check that the"
            " classification provided in the sample metadata is correct for"
            " this sample?")
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
    classification = config.get_classification_for_query(query_dir)
    target_name_map = {}
    target_name_reverse_map = {}
    target_gbif_records = {}
    higher_target_gbif_records = {}  # Taxa at rank 'family' or higher
    for target in targets:
        try:
            gbif_target = RelatedTaxaGBIF(
                target,
                classification=classification,
            )
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

        if not gbif_target.rank:
            msg = (
                f"GBIF record for target taxon '{target}' has no rank,"
                " which can result from a GBIF API error. Processing has"
                " been attempted assuming a higher taxonomic rank (above"
                " genus).")
            logger.warning(msg)
            errors.write(
                errors.LOCATIONS.DB_COVERAGE,
                msg,
                query_dir=query_dir,
                context={"target": target},
            )

        if gbif_target.from_synonym:
            msg = (
                f"Target taxon '{target}' is listed as a synonym in GBIF."
                " This taxon has been processed using the accepted name"
                f" '{gbif_target.canonical_name}'.")
            logger.info(msg)
            errors.write(
                errors.LOCATIONS.DB_COVERAGE,
                msg,
                query_dir=query_dir,
                context={
                    "target": target,
                },
            )

        target_key = (
            gbif_target.canonical_name
            if gbif_target.canonical_name
            else target
        )
        target_name_map[target] = target_key
        target_name_reverse_map[target_key] = target
        if gbif_target.rank > RANK.GENUS or not gbif_target.rank:
            # These get processed differently - broad GB record count only
            higher_target_gbif_records[target_key] = gbif_target

        else:
            target_gbif_records[target_key] = gbif_target

    logger.debug(
        "Targets identified at rank genus or lower:\n"
        + pformat(list(target_gbif_records.keys()), indent=2)
    )
    logger.debug(
        "Targets identified at rank family or higher:\n"
        + pformat(list(higher_target_gbif_records.keys()), indent=2)
    )

    return TargetGbifRecords(
        lower_taxa=target_gbif_records,
        higher_taxa=higher_target_gbif_records,
        all_taxa={**target_gbif_records, **higher_target_gbif_records},
        original_to_canonical=target_name_map,
        canonical_to_original=target_name_reverse_map,
        original_lower_taxa={
            target_name_reverse_map[k]: v
            for k, v in target_gbif_records.items()
        },
        original_higher_taxa={
            target_name_reverse_map[k]: v
            for k, v in higher_target_gbif_records.items()
        }
    )
