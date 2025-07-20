"""Describe how flags are used to record outcomes."""

import logging
from typing import Union

from .config import Config

PATH_SUB_STR = '(~)'
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
        """Read flags from *.flag files.
        If a flag file doesn't exist for a given <flag_id, type, target>
        combination, it will be created with a default value of 'NA'.

        TODO: Honestly this is an abomination - should probably refactor this
        to serialize each flag to a JSON file with a standard structure rather
        than encoding metadata in the filename.
        """
        def get_level(flag):
            """Get the warning level for the given flag."""
            if as_json:
                return flag['level']
            return flag.level

        pattern = (
            config.get_query_dir(query)
            / config.FLAG_FILE_TEMPLATE.format(identifier="*")
        )

        flags = {}
        for path in pattern.parent.glob(pattern.name):
            if path.is_file():
                flag_id, target, target_type = cls._parse_flag_filename(path)
                value = path.read_text().strip()
                flag = Flag(flag_id, value=value, target=target, query=query)
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
        for flag, data in flags.items():
            if flag.startswith('5'):
                for ttype in [TARGETS.CANDIDATE, TARGETS.PMI, TARGETS.TOI]:
                    if ttype not in data:
                        data[ttype] = {}

        if FLAGS.SOURCES not in flags:
            # Number of candidates did not meet requirements to run P4
            flags[FLAGS.SOURCES] = None

        flags[FLAGS.DB_COVERAGE_ALL] = {}
        for ttype in [TARGETS.CANDIDATE, TARGETS.PMI, TARGETS.TOI]:
            # Create a null flag for missing targets to fall back on
            null_flag = Flag(
                FLAGS.DB_COVERAGE_ALL,
                value=FLAGS.NA,
                query=query,
            )
            if as_json:
                null_flag = null_flag.to_json()
            flags[FLAGS.DB_COVERAGE_ALL][ttype] = {'null': null_flag}
            if flags[FLAGS.DB_COVERAGE_TARGET][ttype]:
                # For each target taxon, set flag 5 to represent all 5.* flags
                # (NA or max warning level)
                for target in flags[FLAGS.DB_COVERAGE_TARGET][ttype]:
                    flag_5_1 = flags[FLAGS.DB_COVERAGE_TARGET][ttype][target]
                    flag_5_2 = flags[FLAGS.DB_COVERAGE_RELATED][ttype][target]
                    flag_5_3 = flags[FLAGS.DB_COVERAGE_RELATED_COUNTRY][ttype][
                        target]
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
                    if (
                        get_level(repr_flag) < 2
                        and not config.locus_was_provided_for(query)
                    ):
                        # If no locus provided, level should be 2
                        # (warning) or higher, so provide a special flag
                        repr_flag = Flag(
                            FLAGS.DB_COVERAGE_ALL,
                            value=FLAGS.B,
                            target=target,
                            target_type=ttype,
                            query=query,
                        )
                    flags[FLAGS.DB_COVERAGE_ALL][ttype][target] = repr_flag

        return flags

    @staticmethod
    def _parse_flag_filename(path):
        """Parse flag filename to extract flag_id, target, target_type."""
        stem = path.stem
        target_type = None
        try:
            if '-' in stem:
                flag_id, target = stem.split("-", 1)
                if '-' in target:
                    target_type, target = target.split("-", 1)
                # Reconstitute BOLD unclassified species chars:
                target = target.replace("_", " ").replace(PATH_SUB_STR, '-')
            else:
                flag_id = stem
                target = None
            return flag_id, target, target_type
        except Exception as exc:
            raise ValueError(
                f"Error parsing flag filename {path}"
            ) from exc

    @staticmethod
    def _build_flag_identifier(flag_id, target, target_type):
        """Build flag identifier from flag_id, target, target_type."""
        identifier = flag_id
        target_str = ''
        if target:
            if '-' in target:
                # Preserve special chars (BOLD unclassified species ID):
                target = target.replace('-', PATH_SUB_STR)
            type_str = f"{target_type}-" if target_type else ''
            target_str = f"-{type_str}{target}".replace(' ', '_')
            identifier += target_str
            target_str = ' ' + target_str.strip('-')
        return identifier

    @classmethod
    def write(
        cls,
        query_dir,
        flag_id,
        value,
        target=None,
        target_type=None,
    ):
        """Write flags value to JSON file.

        target: the target taxon name
        target_type: one of TARGETS.[candidate, pmi, toi]
        """
        identifier = cls._build_flag_identifier(
            flag_id, target, target_type
        )
        path = query_dir / config.FLAG_FILE_TEMPLATE.format(
            identifier=identifier)
        with path.open('w') as f:
            f.write(value)
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
