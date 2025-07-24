"""Describe how flags are used to record outcomes."""

import json
import logging
from typing import Union

from .config import Config

FLAG_DETAILS_LOCUS_PHRASES = (
    " given locus for this",
    " at the given locus",
    " for this locus",
)

logger = logging.getLogger(__name__)
config = Config()


def level_to_bs_class(level):
    if level == 0:
        return "secondary"
    if level == 1:
        return "success"
    if level == 2:
        return "warning"
    return "danger"


class Flag:
    """A flag to record discrete analytical outcomes.

    If a target is provided, it should be the target species name, with
    target_type being one of ['candidate', 'pmi', 'toi'].
    """

    def __init__(
        self,
        flag_id,
        value: str = None,
        target: str = None,
        target_type: str = None,
        query: Union[int, str] = None,
    ):
        self.flag_id = flag_id
        self.value = value
        self.target = target
        self.target_type = target_type
        self.query = query

    def __str__(self):
        return f"{self.flag_id}{self.value}"

    def __repr__(self):
        return f"{self.flag_id}{self.value}"

    def to_json(self):
        data = {
            "flag_id": self.flag_id,
            "value": self.value,
            "target": self.target,
            "target_type": self.target_type,
            "level": self.level,
            "outcome": self.outcome,
            "explanation": self.explanation,
            "bs-class": self.bs_class,
        }

        return data

    def _filter_locus_msg(self, msg):
        """Filter the message to remove mention of a locus.
        For samples where no locus was provided.
        """
        query_dir = config.get_query_dir(self.query)
        locus_provided = config.locus_was_provided_for(query_dir)
        if not locus_provided:
            for phrase in FLAG_DETAILS_LOCUS_PHRASES:
                # Remove text that says "for given locus" if no locus was
                # provided
                msg = msg.replace(phrase, '')
        return msg

    @property
    def name(self):
        return FLAG_DETAILS[self.flag_id]["name"]

    @property
    def explanation(self):
        return self._filter_locus_msg(
            FLAG_DETAILS[self.flag_id]["explanation"][self.value]
        )

    @property
    def outcome(self):
        return self._filter_locus_msg(
            FLAG_DETAILS[self.flag_id]["outcome"][self.value]
        )

    @property
    def level(self):
        """Return the warning level for the given value."""
        return FLAG_DETAILS[self.flag_id]['level'][self.value]

    @property
    def bs_class(self):
        """Return the bootstrap css class for self.level."""
        level = self.level
        return level_to_bs_class(level)

    @classmethod
    def read(cls, query, as_json=False):
        """Read flags from *.flag files containing JSON data."""
        def get_level(flag):
            """Get the warning level for the given flag."""
            if as_json:
                return flag['level']
            return flag.level

        query_dir = config.get_query_dir(query)

        flags = {}
        for path in query_dir.glob("*.flag"):
            if path.is_file():
                file_flags = cls._process_flag_file(path, query, as_json)
                # Merge file_flags into flags
                for flag_id, flag_data in file_flags.items():
                    if flag_id in flags:
                        is_dict_merge = (isinstance(flags[flag_id], dict) and
                                         isinstance(flag_data, dict))
                        if is_dict_merge:
                            # Merge nested dictionaries for target-based flags
                            for key, value in flag_data.items():
                                if key in flags[flag_id]:
                                    existing_key = flags[flag_id][key]
                                    is_nested_dict = (
                                        isinstance(existing_key, dict) and
                                        isinstance(value, dict)
                                    )
                                    if is_nested_dict:
                                        flags[flag_id][key].update(value)
                                    else:
                                        flags[flag_id][key] = value
                                else:
                                    flags[flag_id][key] = value
                        else:
                            flags[flag_id] = flag_data
                    else:
                        flags[flag_id] = flag_data

        flags = cls._post_process_flags(flags, query, as_json,
                                        get_level)
        return flags

    @classmethod
    def _process_flag_file(cls, path, query, as_json):
        """Process a single flag file and return flags dictionary."""
        flags = {}
        try:
            with path.open('r') as f:
                flag_data_list = json.load(f)

            # Handle both single dict and list of dicts
            if isinstance(flag_data_list, dict):
                flag_data_list = [flag_data_list]

            for flag_data in flag_data_list:
                flag_id = flag_data['flag_id']
                value = flag_data['value']
                target = flag_data.get('target')
                target_type = flag_data.get('target_type')

                flag = Flag(flag_id, value=value, target=target,
                            target_type=target_type, query=query)
                if as_json:
                    flag = flag.to_json()

                if target:
                    flags[flag_id] = flags.get(flag_id, {})
                    if target_type:
                        flags[flag_id][target_type] = flags[flag_id].get(
                            target_type, {})
                        flags[flag_id][target_type][target] = flag
                    else:
                        flags[flag_id][target] = flag
                else:
                    flags[flag_id] = flag
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Error reading flag file {path}: {e}")

        return flags

    @classmethod
    def _post_process_flags(cls, flags, query, as_json, get_level):
        """Post-process flags to handle missing data and create summary flags.
        """
        # Create a copy to avoid modifying the original
        processed_flags = flags.copy()

        # Ensure all DB coverage flags have all target types
        for flag, data in processed_flags.items():
            if flag.startswith('5'):
                target_types = [TARGETS.CANDIDATE, TARGETS.PMI, TARGETS.TOI]
                for ttype in target_types:
                    if ttype not in data:
                        data[ttype] = {}

        if FLAGS.SOURCES not in processed_flags:
            # Number of candidates did not meet requirements to run P4
            processed_flags[FLAGS.SOURCES] = None

        processed_flags[FLAGS.DB_COVERAGE_ALL] = {}
        target_types = [TARGETS.CANDIDATE, TARGETS.PMI, TARGETS.TOI]
        for ttype in target_types:
            # Create a null flag for missing targets to fall back on
            null_flag = Flag(
                FLAGS.DB_COVERAGE_ALL,
                value=FLAGS.NA,
                query=query,
            )
            if as_json:
                null_flag = null_flag.to_json()
            coverage_all = processed_flags[FLAGS.DB_COVERAGE_ALL]
            coverage_all[ttype] = {'null': null_flag}
            target_flag_key = FLAGS.DB_COVERAGE_TARGET
            db_coverage_target = processed_flags.get(target_flag_key, {})
            if db_coverage_target.get(ttype):
                # For each target taxon, set flag 5 to represent all 5.* flags
                # (NA or max warning level)
                coverage_target = db_coverage_target[ttype]
                for target in coverage_target:
                    flag_5_1 = coverage_target[target]
                    db_related_flags = FLAGS.DB_COVERAGE_RELATED
                    coverage_related = processed_flags[db_related_flags]
                    flag_5_2 = coverage_related[ttype][target]
                    coverage_country = processed_flags[
                        FLAGS.DB_COVERAGE_RELATED_COUNTRY]
                    flag_5_3 = coverage_country[ttype][target]
                    repr_flag_func = max
                    if 0 in (
                        get_level(flag_5_1),
                        get_level(flag_5_2),
                        get_level(flag_5_3),
                    ):
                        # If any of the flags are level 0, take that flag to
                        # represent the analysis
                        repr_flag_func = min
                    repr_flag = repr_flag_func([
                        flag_5_1,
                        flag_5_2,
                        flag_5_3,
                    ], key=lambda x: get_level(x))
                    needs_special_flag = (
                        get_level(repr_flag) < 2 and
                        not config.locus_was_provided_for(query)
                    )
                    if needs_special_flag:
                        # If no locus provided, level should be 2
                        # (warning) or higher, so provide a special flag
                        repr_flag = Flag(
                            FLAGS.DB_COVERAGE_ALL,
                            value=FLAGS.B,
                            target=target,
                            target_type=ttype,
                            query=query,
                        )
                    db_coverage_all = processed_flags[FLAGS.DB_COVERAGE_ALL]
                    coverage_all_ttype = db_coverage_all[ttype]
                    coverage_all_ttype[target] = repr_flag

        return processed_flags

    @classmethod
    def write(
        cls,
        query_dir,
        flag_id,
        value,
        target=None,
        target_type=None,
    ):
        """Write flag data to JSON file.

        target: the target taxon name
        target_type: one of TARGETS.[candidate, pmi, toi]
        """
        path = query_dir / f"{flag_id}.flag"

        # Create flag data dict
        flag_data = {
            'flag_id': flag_id,
            'value': value,
            'target': target,
            'target_type': target_type
        }

        # Read existing flags from file if it exists
        existing_flags = []
        if path.exists():
            try:
                with path.open('r') as f:
                    existing_data = json.load(f)
                    # Handle both single dict and list of dicts
                    if isinstance(existing_data, dict):
                        existing_flags = [existing_data]
                    else:
                        existing_flags = existing_data
            except (json.JSONDecodeError, IOError) as e:
                msg = f"Error reading existing flag file {path}: {e}"
                logger.warning(msg)
                existing_flags = []

        # Check if this exact flag already exists and if so update it
        flag_updated = False
        for i, existing_flag in enumerate(existing_flags):
            if (
                existing_flag.get('flag_id') == flag_id
                and existing_flag.get('target') == target
                and existing_flag.get('target_type') == target_type
            ):
                existing_flags[i] = flag_data
                flag_updated = True
                break

        if not flag_updated:
            existing_flags.append(flag_data)

        # Write back to file
        with path.open('w') as f:
            json.dump(existing_flags, f, indent=2)

        logger.info(f"Flag {flag_id}{value} written to {path}")


class TARGETS:
    CANDIDATE = "candidate"
    PMI = "pmi"
    TOI = "toi"


class FLAGS:
    """Flags for reporting outcomes."""
    POSITIVE_ID = '1'
    TOI = '2'
    SOURCES = '4'
    DB_COVERAGE_ALL = '5'
    DB_COVERAGE_TARGET = '5.1'
    DB_COVERAGE_RELATED = '5.2'
    DB_COVERAGE_RELATED_COUNTRY = '5.3'
    INTRASPECIES_DIVERSITY = '6'
    PMI = '7'
    NA = 'NA'
    ERROR = 'ERR'
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


FLAG_DETAILS = config.read_flag_details_csv()
