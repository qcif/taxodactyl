"""Define error handling logic."""

import json
from pathlib import Path
from typing import Union

from .config import Config

config = Config()


class FASTAFormatError(Exception):
    """User provided a FASTA file that does not meet specifications."""

    def __init__(self, msg):
        super().__init__(f"FASTA format error: {msg}")


class MetadataFormatError(Exception):
    """User provided a metadata CSV file that does not meet specifications."""

    def __init__(self, msg):
        super().__init__(f"Metadata CSV format error: {msg}")


class APIError(Exception):
    """Raise this exception when an API request fails."""
    pass


class LOCATIONS:
    """These locations define where a reportable exception occurred and
    can be used to display it in the appropriate location in the report.
    Major numbers refer to the analysis "phase" and minor versions distinguish
    specific report locations within that phase.
    """
    BLAST = 1.0
    BOLD = 1.1
    BOLD_ID_ENGINE = 1.10
    BOLD_TAXA = 1.11
    SOURCE_DIVERSITY_ACCESSION_ERROR = 4.01
    DB_COVERAGE = 5
    DB_COVERAGE_NO_GBIF_RECORD = 5.01
    DB_COVERAGE_TAXONKIT_ERROR = 5.02
    DB_COVERAGE_TARGET = 5.1
    DB_COVERAGE_RELATED = 5.2
    DB_COVERAGE_RELATED_COUNTRY = 5.3

    @classmethod
    def to_json(cls):
        """Convert the location to a JSON serializable format."""
        return {
            k: v
            for k, v in cls.__dict__.items()
            if not k.startswith('_') and isinstance(v, (float, int))
        }


def write(
    location: float,
    msg: str,
    exc: Exception = None,
    query_dir: Path = None,
    context: dict = None,
):
    """Write a non-fatal error to file for later reporting.

    location: display the error message in an appropriate
              location in the report.
    msg: provide the detailed information about the errors.
    exception: optional, can be None.
    query_dir: the location of error output file
               if the error happens in any specific query.
    context: optional, the context of the error to help locate it in the
             report e.g. 'target'.
    """
    parent = query_dir or config.output_dir
    next_path = parent / config.ERRORS_DIR / 'next.txt'
    if next_path.exists():
        i = int(next_path.read_text())
    else:
        next_path.parent.mkdir(parents=True, exist_ok=True)
        i = 1
    next_path.write_text(str(i + 1))
    path = parent / config.ERRORS_DIR / f'{i}.json'
    with path.open('w') as f:
        json.dump({
            "location": location,
            "message": msg,
            "exception": str(exc) if exc else None,
            "context": context,
        }, f, indent=2)


class ErrorLog:
    """Provide access to error messages logged throughout the workflow run."""

    def __init__(self, query_dir: Path = None, errors: list[dict] = None):
        """Read all errors from error files."""
        self.query_dir = query_dir
        self.errors = errors if errors is not None else self._read()

    def __len__(self):
        return len(self.errors)

    def __iter__(self):
        return iter(self.errors)

    def __bool__(self):
        return bool(self.errors)

    def __add__(self, other: 'ErrorLog'):
        """Combine two error logs."""
        if not isinstance(other, ErrorLog):
            raise TypeError("Can only add ErrorLog instances.")
        return ErrorLog(
            query_dir=self.query_dir,
            errors=self.errors + other.errors
        )

    def _read(self):
        """Read all error files from given error directory."""
        errors = []
        parent = self.query_dir or config.output_dir
        for path in (parent / config.ERRORS_DIR).glob('*.json'):
            with path.open() as f:
                errors.append(json.load(f))
        return errors

    def filter(
        self,
        location: float = None,
        location_not: float = None,
        location_gt: float = None,
        location_gte: float = None,
        location_lt: float = None,
        location_lte: float = None,
        location_in: Union[float, int] = None,
        context: dict = None,
    ) -> 'ErrorLog':
        """List requested errors from the error log."""
        errors = self.errors
        if location:
            errors = [
                x for x in errors
                if x['location'] == location
            ]
        if location_not:
            errors = [
                x for x in errors
                if x['location'] != location_not
            ]
        if location_gte is not None:
            errors = [
                x for x in errors
                if x['location'] >= location_gte
            ]
        if location_gt is not None:
            errors = [
                x for x in errors
                if x['location'] > location_gt
            ]
        if location_lte is not None:
            errors = [
                x for x in errors
                if x['location'] <= location_lte
            ]
        if location_lt is not None:
            errors = [
                x for x in errors
                if x['location'] < location_lt
            ]
        if location_in is not None:
            errors = [
                x for x in errors
                if str(x['location']).startswith(str(location_in))
            ]
        if context:
            # Exclude errors that have the context key(s) but do not match
            # the given value
            errors = [
                x for x in errors
                if all(
                    k not in x.get('context', {})
                    or x.get('context', {}).get(k) == v
                    for k, v in context.items()
                )
            ]

        return ErrorLog(query_dir=self.query_dir, errors=errors)

    def to_json(self) -> list[dict]:
        """Convert error log to JSON."""
        return self.errors
