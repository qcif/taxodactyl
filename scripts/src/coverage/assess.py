"""Assess database coverage of target species at the given locus.

This module features a lot of threading for requests against the Entrez and
GBIF APIs. There can be thousands of requests made in a single run, so a lock
file is used to limit the number of concurrent requests.
"""

import logging
from pprint import pformat

from src.gbif.maps import draw_occurrence_map
from src.utils import errors
from src.utils.config import Config
from src.utils.flags import FLAGS, Flag

from .fetch import (
    get_related_country_coverage,
    get_related_coverage,
    get_target_coverage,
)
from .targets import fetch_target_taxa, get_targets, get_taxids
from .threads import parallel_process_tasks

logger = logging.getLogger(__name__)
config = Config()

MODULE_NAME = "Database Coverage"


def assess_coverage(query_dir, is_bold) -> dict[str, dict[str, dict]]:
    def get_args(func, query_dir, target, taxid, locus, country):
        if func == get_target_coverage:
            return func, taxid, target, locus, is_bold
        elif func == get_related_coverage:
            return func, target, locus, query_dir, is_bold
        elif func == get_related_country_coverage:
            return func, target, locus, country, query_dir, is_bold

    locus = config.get_locus_for_query(query_dir)
    country = config.get_country_for_query(query_dir, code=True)
    candidate_list, toi_list, pmi = get_targets(query_dir)
    targets = candidate_list + toi_list + [pmi]
    if not targets:
        logger.info(
            "Skipping analysis - no target taxon"
            " identified for database coverage assessment."
        )
        return None

    target_taxids = get_taxids(targets, query_dir)
    taxid_to_taxon = {v: k for k, v in target_taxids.items()}
    unknown_taxa = {
        t for t in targets
        if t not in target_taxids
    }

    logger.info(
        f"Assessing database coverage for {len(targets)}"
        f" taxon at locus '{locus}' in country '{country}'."
    )
    logger.debug(
        f"collected targets:\n"
        f"  - Candidates: {candidate_list}\n"
        f"  - Taxa of interest: {toi_list}\n"
        f"  - PMI: {pmi}"
    )
    logger.debug(
        "Taxids for targets (extracted by taxonkit):\n"
        + pformat(target_taxids, indent=2)
    )

    # 'Higher taxa' are at rank 'family' or higher
    target_gbif_taxa, higher_taxon_targets = fetch_target_taxa(
        targets, query_dir)

    unknown_taxa = unknown_taxa.union({
        t for t in targets
        if t not in target_gbif_taxa
        and t not in higher_taxon_targets
    })

    _draw_occurrence_maps(
        target_gbif_taxa,
        higher_taxon_targets,
        query_dir,
    )

    tasks = [
        get_args(
            func,
            query_dir,
            target_gbif_taxa[target],
            taxid,
            locus,
            country,
        )
        for target, taxid in target_taxids.items()
        for func in (
            get_target_coverage,
            get_related_coverage,
            get_related_country_coverage,
        )
        if target in target_gbif_taxa
    ]

    tasks += [
        (get_target_coverage, taxid, target, locus, is_bold)
        for target, taxid in target_taxids.items()
        if target in higher_taxon_targets
    ]

    if not (len(tasks) + len(unknown_taxa)):
        raise ValueError(
            "No tasks created for database coverage assessment. This likely"
            " indicates a bug in the code - please report this issue.")

    results, is_error = parallel_process_tasks(
        tasks,
        query_dir,
        target_taxids,
        target_gbif_taxa,
        taxid_to_taxon,
        candidate_list,
        toi_list,
        pmi,
    )
    for taxon in unknown_taxa:
        for target_type, targets in {
            'candidate': candidate_list,
            'toi': toi_list,
            'pmi': [pmi],
        }.items():
            if taxon in targets:
                results[target_type][taxon] = {
                    'target': None,
                    'related': None,
                    'country': None,
                }
    _set_flags(results, query_dir, higher_taxon_targets)
    return results, is_error


def _draw_occurrence_maps(
    target_gbif_taxa,
    higher_taxon_targets,
    query_dir,
):
    """Fetch occurrence data and draw world maps showing taxon distribution."""
    taxa = {
        **target_gbif_taxa,
        **higher_taxon_targets,
    }
    for target, gbif_target in taxa.items():
        if not gbif_target.key:
            logger.warning(
                f"No GBIF taxon key found for target"
                f" '{target}'. Occurrence map will not be generated for this"
                " target.")
            continue
        path = query_dir / config.get_map_filename_for_target(target)
        logger.info(
            f"Writing occurrence map for"
            f" '{target}' (taxon key: {gbif_target.key}) to file"
            f" '{path}'..."
        )
        try:
            draw_occurrence_map(gbif_target.key, path)
        except Exception as e:
            msg = ("Taxon distribution map could not be generated due to an"
                   " error in the GBIF occurrence.")
            logger.error(f'{msg} Target: "{target}" Exception: {e}')
            errors.write(
                errors.LOCATIONS.DB_COVERAGE,
                msg,
                exc=e,
                context={'target': target},
            )


def _set_flags(db_coverage, query_dir, higher_taxon_targets):
    """Set flags 5.1 - 5.3 (DB coverage) for each target."""
    def set_target_coverage_flag(
        target,
        target_type,
        count,
        higher_taxon=False,
    ):
        if higher_taxon:
            flag_value = FLAGS.NA
        elif count is None:
            logger.warning(
                f"Could not set DB coverage flags 5.* for target '{target}'"
                f" ({target_type}) - species counts are None but expected"
                " a dict. This indicates an error has occurred above.")
            flag_value = FLAGS.ERROR
        elif not isinstance(count, int):
            raise ValueError(
                f"Unexpected count value for target"
                f" ({target_type}) '{target}': {count}.")
        elif count > config.CRITERIA.DB_COV_TARGET_MIN_A:
            flag_value = FLAGS.A
        elif count > config.CRITERIA.DB_COV_TARGET_MIN_B:
            flag_value = FLAGS.B
        else:
            flag_value = FLAGS.C
        Flag.write(
            query_dir,
            FLAGS.DB_COVERAGE_TARGET,
            flag_value,
            target=target,
            target_type=target_type,
        )

    def set_related_coverage_flag(
        target,
        target_type,
        species_counts,
        higher_taxon=False,
    ):
        if higher_taxon:
            flag_value = FLAGS.NA
        elif species_counts is None:
            logger.warning(
                f"Could not set DB coverage flags 5.* for target '{target}'"
                f" ({target_type}) - species counts are None but expected"
                " a dict. This indicates an error has occurred above.")
            flag_value = FLAGS.ERROR
        elif isinstance(species_counts, str):
            raise ValueError(
                f"Unexpected str count value for related"
                f" species ({target_type}) '{target}': {species_counts}.")
        else:
            total_species = len(species_counts)
            if total_species:
                represented_species = len([
                    count for count in species_counts.values()
                    if count and count > 0
                ])
                percent_coverage = 100 * represented_species / total_species
                if percent_coverage > config.CRITERIA.DB_COV_RELATED_MIN_A:
                    flag_value = FLAGS.A
                elif percent_coverage > config.CRITERIA.DB_COV_RELATED_MIN_B:
                    flag_value = FLAGS.B
                else:
                    flag_value = FLAGS.C
            else:
                flag_value = FLAGS.NA
        Flag.write(
            query_dir,
            FLAGS.DB_COVERAGE_RELATED,
            flag_value,
            target=target,
            target_type=target_type,
        )

    def set_country_coverage_flag(
        target,
        target_type,
        species_counts,
        higher_taxon=False,
    ):
        if higher_taxon or species_counts == FLAGS.NA:
            flag_value = FLAGS.NA
        elif species_counts is None:
            logger.warning(
                f"Could not set DB coverage flags 5.* for target '{target}'"
                f" ({target_type}) - species counts are None but expected"
                " a dict. This indicates an error has occurred above.")
            flag_value = FLAGS.ERROR
        else:
            total_species = len(species_counts)
            represented_species = len([
                count for count in species_counts.values()
                if count and count > 0
            ])
            unrepresented = total_species - represented_species
            if not species_counts:
                flag_value = FLAGS.C
            elif not unrepresented:
                flag_value = FLAGS.A
            else:
                flag_value = FLAGS.B
        Flag.write(
            query_dir,
            FLAGS.DB_COVERAGE_RELATED_COUNTRY,
            flag_value,
            target=target,
            target_type=target_type,
        )

    for target_type, target_data in db_coverage.items():
        for target_species, coverage_data in target_data.items():
            try:
                set_target_coverage_flag(
                    target_species,
                    target_type,
                    coverage_data['target'],
                    higher_taxon=target_species in higher_taxon_targets,
                )
                set_related_coverage_flag(
                    target_species,
                    target_type,
                    coverage_data['related'],
                    higher_taxon=target_species in higher_taxon_targets,
                )
                set_country_coverage_flag(
                    target_species,
                    target_type,
                    coverage_data['country'],
                    higher_taxon=target_species in higher_taxon_targets,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Error setting flags for target ({target_type})"
                    f" '{target_species}'. Exception: {exc}"
                ) from exc
