"""docstring"""

import logging
from pprint import pformat
from dataclasses import dataclass, field

from src.gbif.relatives import (
    GBIFRecordNotFound,
    RANK,
    ROOT_RANKS,
    RelatedTaxaGBIF,
    is_root_taxon,
    tie_break_message,
)
from src.taxonomy import extract
from src.utils import errors
from src.utils.config import Config

logger = logging.getLogger(__name__)
config = Config()

MODULE_NAME = "Database Coverage"
NO_GENUS_FALLBACK_PREFIX = (
    "Related-species checks (flags 5.2 and 5.3) could not be run for"
    " '{target}': "
)


@dataclass(eq=False)
class NcbiOnlyTarget:
    """A target that is not in COL, resolved through NCBI taxonomy instead.

    It stands in for a `RelatedTaxaGBIF` record wherever database coverage
    needs one: `taxon` and `canonical_name` are the original target name,
    and `rank` is the taxid's own NCBI rank (`RANK.NONE` if it is not one of
    the ranks in `RANK`, e.g. "no rank" or "strain").

    `closest_col_name` / `closest_col_genus` are set when COL suggested a
    different accepted name for the target (a near miss, e.g. 'Grapevine
    virus' -> 'Grapevine virus A') and NCBI has the exact name.

    `genus_record` is the COL record of the target's genus (genus fallback):
    its NCBI genus or, failing that, the genus of its closest COL match.
    When set, `relatives` and `for_country` come from it, so related-species
    and in-country coverage are computed as for a lower target. `eq=False`
    keeps instances hashable by identity, since coverage results are keyed
    by target record.
    """

    taxon: str
    taxid: str | None = None
    rank: int = RANK.NONE
    ncbi_genus: str | None = None
    closest_col_name: str | None = None
    closest_col_genus: str | None = None
    genus_record: RelatedTaxaGBIF | None = None
    canonical_name: str = field(init=False)

    def __post_init__(self):
        self.canonical_name = self.taxon

    @property
    def genus(self):
        """The COL genus name used for related-species checks, if any."""
        return (
            self.genus_record.canonical_name
            if self.genus_record
            else None
        )

    @property
    def is_higher(self):
        """True if the NCBI rank is above genus (family or higher)."""
        return self.rank > RANK.GENUS

    @property
    def relatives(self):
        return self.genus_record.relatives

    def for_country(self, country_code):
        return self.genus_record.for_country(country_code)


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

    `root_taxa` holds the original names of targets at kingdom, domain or
    COL-root level (e.g. "Fungi", "Viruses"), in input order without
    duplicates. These are too broad for database coverage, so they are not
    assessed and are absent from every other field.

    `col_missing_taxa` holds targets with no COL record, keyed by original
    name, resolved through NCBI taxonomy (`NcbiOnlyTarget`). Those without
    a taxid have `taxid=None` and are not assessed. These are also absent
    from every other field.
    """

    original_to_canonical: dict[str, str]
    canonical_to_original: dict[str, str]
    lower_taxa: dict[str, RelatedTaxaGBIF]            # keyed by canonical
    higher_taxa: dict[str, RelatedTaxaGBIF]           # keyed by canonical
    all_taxa: dict[str, RelatedTaxaGBIF]              # keyed by canonical
    original_taxa: dict[str, RelatedTaxaGBIF]         # keyed by original
    original_lower_taxa: dict[str, RelatedTaxaGBIF]   # keyed by original
    original_higher_taxa: dict[str, RelatedTaxaGBIF]  # keyed by original
    root_taxa: list[str]
    col_missing_taxa: dict[str, NcbiOnlyTarget] = field(default_factory=dict)


def _read_candidate_species(query_dir):
    candidates = config.read_json(query_dir / config.candidates_json)
    return [
        c["species"]
        for c in candidates["species"]
    ]


def get_targets(query_dir):
    # No candidates file exists in database coverage mode
    candidates = (
        []
        if config.coverage_mode
        else _read_candidate_species(query_dir)
    )
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
        excluded_tois = toi_list[config.db_coverage_toi_limit:]
        toi_list = toi_list[:config.db_coverage_toi_limit]
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
    if not targets:
        # e.g. every target is a root taxon - nothing to look up
        return {}
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
    original_lower_taxa = {}
    original_higher_taxa = {}
    root_taxa = []
    col_missing = {}  # original name -> _col_missing_entry()

    def add_root_taxon(target, detail=''):
        if target not in root_taxa:
            root_taxa.append(target)
        logger.info(
            f"Target taxon '{target}' is at kingdom, domain or root level"
            f"{detail}. Database coverage will not be assessed for it.")

    for target in targets:
        if is_root_taxon(target):
            add_root_taxon(target)
            continue
        try:
            gbif_target = RelatedTaxaGBIF(
                target,
                classification=classification,
            )
        except GBIFRecordNotFound as exc:
            logger.warning(f"Target taxon '{target}': {exc}")
            col_missing[target] = _col_missing_entry(str(exc))
            continue

        if gbif_target.rank in ROOT_RANKS:
            add_root_taxon(
                target,
                f" (GBIF key {gbif_target.key}:"
                f" '{gbif_target.canonical_name}',"
                f" rank {RANK.to_string(gbif_target.rank)})",
            )
            continue

        is_inexact = (
            gbif_target.canonical_name.lower() != target.lower()
            and not gbif_target.from_synonym
        )
        if is_inexact:
            taxid = extract.taxids(
                [target], classification=classification).get(target)
            if taxid:
                msg = (
                    f"'{target}' is not in the Catalogue of Life (COL)"
                    " taxonomy used by GBIF; its closest COL name,"
                    f" '{gbif_target.canonical_name}', is a different taxon."
                    " NCBI has this exact name, so it is used instead.")
                logger.warning(f"Target taxon '{target}': {msg}")
                col_missing[target] = _col_missing_entry(
                    msg,
                    taxid=taxid,
                    closest_col_name=gbif_target.canonical_name,
                    closest_col_genus=gbif_target.genus,
                )
                continue

        if gbif_target.tie_break:
            msg = tie_break_message(gbif_target.tie_break)
            logger.warning(f"Target taxon '{target}': {msg}")
            errors.write(
                errors.LOCATIONS.DB_COVERAGE,
                msg,
                query_dir=query_dir,
                context={"target": target},
            )

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
            original_higher_taxa[target] = gbif_target
            higher_target_gbif_records[target_key] = gbif_target

        else:
            original_lower_taxa[target] = gbif_target
            target_gbif_records[target_key] = gbif_target

        if is_inexact:
            # No exact NCBI name either: analyse the closest COL name
            errors.write(
                errors.LOCATIONS.DB_COVERAGE,
                f"The query taxon '{target}' has been analyzed based on the"
                f" first GBIF-accepted name, '{gbif_target.canonical_name}'."
                " Please check that this is the intended taxon for analysis.",
                query_dir=query_dir,
                context={
                    "target": target,
                },
            )

    logger.debug(
        "Targets identified at rank genus or lower:\n"
        + pformat(list(target_gbif_records.keys()), indent=2)
    )
    logger.debug(
        "Targets identified at rank family or higher:\n"
        + pformat(list(higher_target_gbif_records.keys()), indent=2)
    )

    col_missing_taxa = _resolve_col_missing_taxa(
        col_missing,
        classification,
        query_dir,
    )

    return TargetGbifRecords(
        lower_taxa=target_gbif_records,
        higher_taxa=higher_target_gbif_records,
        all_taxa={**target_gbif_records, **higher_target_gbif_records},
        original_to_canonical=target_name_map,
        canonical_to_original=target_name_reverse_map,
        original_lower_taxa=original_lower_taxa,
        original_higher_taxa=original_higher_taxa,
        original_taxa={**original_lower_taxa, **original_higher_taxa},
        root_taxa=root_taxa,
        col_missing_taxa=col_missing_taxa,
    )


def _col_missing_entry(
    message,
    taxid=None,
    closest_col_name=None,
    closest_col_genus=None,
):
    """Describe a target that is not in COL, for _resolve_col_missing_taxa.

    `message` explains why the target is not in COL. `taxid` is set when the
    target's NCBI taxid is already known (near-miss COL matches).
    """
    return {
        'message': message,
        'taxid': taxid,
        'closest_col_name': closest_col_name,
        'closest_col_genus': closest_col_genus,
    }


def _resolve_col_missing_taxa(
    col_missing: dict[str, dict],
    classification: dict,
    query_dir,
) -> dict[str, NcbiOnlyTarget]:
    """Resolve targets that are not in COL through NCBI taxonomy.

    `col_missing` maps each original target name to a `_col_missing_entry`.
    Each target without a known taxid gets one from taxonkit name2taxid
    (filtered by the query's classification) and, if found, its NCBI rank
    and genus from taxonkit lineage. A lower target whose genus (NCBI, else
    its closest COL match's) is a genus in COL gets that genus record for
    related-species checks (genus fallback).

    One `DB_COVERAGE_NO_GBIF_RECORD` error is written per target, saying
    which checks could still be run.
    """
    if not col_missing:
        return {}
    taxids = {
        name: entry['taxid']
        for name, entry in col_missing.items()
        if entry['taxid']
    }
    unknown = [name for name in col_missing if name not in taxids]
    if unknown:
        taxids.update(
            extract.taxids(unknown, classification=classification))
    found_taxids = [
        taxids.get(name)
        for name in col_missing
        if taxids.get(name)
    ]
    lineages = extract.lineages(found_taxids) if found_taxids else {}

    resolved = {}
    for name, entry in col_missing.items():
        not_found_msg = entry['message']
        taxid = taxids.get(name)
        target = NcbiOnlyTarget(
            name,
            taxid=taxid,
            closest_col_name=entry['closest_col_name'],
            closest_col_genus=entry['closest_col_genus'],
        )
        resolved[name] = target
        if not taxid:
            _write_no_taxid_errors(target, not_found_msg, query_dir)
            continue

        lineage = lineages.get(taxid)
        if lineage:
            target.rank = RANK.from_string(lineage.ranks[-1])
            target.ncbi_genus = lineage.filtered_taxonomy.get('genus')
        logger.info(
            f"Target taxon '{name}' is not in COL. Resolved by taxonkit to"
            f" NCBI taxid {taxid}"
            + (
                f" ('{lineage.lineage[-1]}', rank {lineage.ranks[-1]},"
                f" genus {target.ncbi_genus})."
                if lineage else
                " (no lineage found)."
            )
        )
        if not target.is_higher:
            _apply_genus_fallback(target, classification, query_dir)

        if target.genus_record:
            outcome = (
                " Reference sequence records (flag 5.1) were counted using"
                f" its NCBI taxid {taxid}. No occurrence map is available.")
        else:
            outcome = (
                " Reference sequence records (flag 5.1) were counted using"
                f" its NCBI taxid {taxid}, but GBIF-based checks (related"
                " species, related species in country and occurrence map)"
                " could not be run.")
        errors.write(
            errors.LOCATIONS.DB_COVERAGE_NO_GBIF_RECORD,
            not_found_msg + outcome,
            query_dir=query_dir,
            context={"target": name},
        )

    return resolved


def _write_no_taxid_errors(target, not_found_msg, query_dir):
    """Explain that a target in neither COL nor NCBI was not evaluated."""
    msg = (
        not_found_msg
        + " No NCBI taxid was found for it either, so its database coverage"
        " could not be evaluated.")
    logger.warning(msg)
    errors.write(
        errors.LOCATIONS.DB_COVERAGE_NO_GBIF_RECORD,
        msg,
        query_dir=query_dir,
        context={"target": target.taxon},
    )
    errors.write(
        errors.LOCATIONS.DB_COVERAGE_TAXONKIT_ERROR,
        "Taxonkit failed to produce a taxid for this taxon. If this seems"
        " unlikely, perhaps check that the taxon name and the"
        " classification provided in the sample metadata are correct for"
        " this sample?",
        query_dir=query_dir,
        context={"target": target.taxon},
    )


def _apply_genus_fallback(target, classification, query_dir):
    """Set `target.genus_record` from the COL record of its genus.

    The genus is the target's NCBI genus or, if NCBI gives none, the genus
    of its closest COL match. Among same-name COL genera, the tie-break
    picks the one with the most descendants. The COL record is accepted only
    if it is a genus with the same name. Otherwise an informational error
    says why the related-species checks could not be run.
    """
    name = target.taxon
    prefix = NO_GENUS_FALLBACK_PREFIX.format(target=name)
    if target.ncbi_genus:
        genus = target.ncbi_genus
        source = f"its NCBI genus '{genus}'"
    elif target.closest_col_genus:
        genus = target.closest_col_genus
        source = (
            f"the genus '{genus}' of its closest COL match,"
            f" '{target.closest_col_name}',")
    else:
        _write_info(
            prefix + f"its NCBI lineage (taxid {target.taxid}) has no genus.",
            name,
            query_dir,
        )
        return

    try:
        record = RelatedTaxaGBIF(genus, classification=classification)
    except GBIFRecordNotFound:
        _write_info(
            prefix + f"{source} is not in COL.",
            name,
            query_dir,
        )
        return

    if (
        record.rank != RANK.GENUS
        or (record.canonical_name or '').lower() != genus.lower()
    ):
        _write_info(
            prefix
            + f"{source} matched the COL record"
            f" '{record.canonical_name}' (key {record.key}, rank"
            f" {RANK.to_string(record.rank)}), which is not the same genus.",
            name,
            query_dir,
        )
        return

    if record.tie_break:
        _write_info(tie_break_message(record.tie_break), name, query_dir)
    target.genus_record = record
    if target.ncbi_genus:
        msg = (
            f"'{name}' is not in COL; related-species checks use its NCBI"
            f" genus '{genus}' (COL key {record.key}).")
    else:
        msg = (
            f"'{name}' is not in COL and NCBI gives it no genus;"
            f" related-species checks use the genus '{genus}' (COL key"
            f" {record.key}) of its closest COL match,"
            f" '{target.closest_col_name}'.")
    _write_info(msg, name, query_dir)


def _write_info(msg, target, query_dir):
    logger.info(f"Target taxon '{target}': {msg}")
    errors.write(
        errors.LOCATIONS.DB_COVERAGE,
        msg,
        query_dir=query_dir,
        context={"target": target},
    )
