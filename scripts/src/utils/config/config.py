"""Runtime configuration for the workflow.

Read in from YAML and validate with Pydantic.

To view/modify default values for config attributes, refer to default.yml.
"""

import argparse
import csv
import json
import logging
import os
import shutil
import sys
import tempfile
import yaml
from datetime import datetime, timedelta
from functools import cached_property
from logging.config import dictConfig
from pathlib import Path

from Bio import SeqIO
from pydantic import ValidationError

from src.utils import countries
from src.utils.locus import Locus
from src.utils.log import get_logging_config
from src.utils.utils import path_safe_str

from . import mappings
from .schema import ConfigSchema

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parents[4]
MAP_FILENAME_TEMPLATE = "map_{taxon_str}.png"
REPORT_FILENAME = "report_{prefix}{sample_id}_{timestamp}.html"
QUERY_DIR_PREFIX = 'query_'
DEFAULT_CONFIG_PATH = ROOT_DIR / 'scripts/config/default.yml'
METADATA_IGNORE_FIELDS = (
    'sequence',
)
VARS_FROM_ENV = (
    "USER_EMAIL",
    "NCBI_API_KEY",
)
FACILITY_NAME_DEFAULT = "Not provided"
TEMP_FILES = (
    'entrez_cache_dirname',
)


class Config:
    """Singleton configuration class for global config state.

    Config can be read from:

    - CLI arguments
    - YAML with Pydantic validation.
    - Env variables
    """

    _instance = None
    _initialized = False

    # These are used for taxonomic filtering of GBIF/taxonkit records:
    HIGHER_CLASSIFICATIONS = {
        'animalia': {
            'gbif': 1,
            'ncbi': {
                'rank': 'kingdom',
                'taxon': 'metazoa',
            },
        },
        'animal': {
            'gbif': 1,
            'ncbi': {
                'rank': 'kingdom',
                'taxon': 'metazoa',
            },
        },
        'animals': {
            'gbif': 1,
            'ncbi': {
                'rank': 'kingdom',
                'taxon': 'metazoa',
            },
        },
        'plantae': {
            'gbif': 6,
            'ncbi': {
                'rank': 'kingdom',
                'taxon': 'viridiplantae',
            },
        },
        'plant': {
            'gbif': 6,
            'ncbi': {
                'rank': 'kingdom',
                'taxon': 'viridiplantae',
            },
        },
        'plants': {
            'gbif': 6,
            'ncbi': {
                'rank': 'kingdom',
                'taxon': 'viridiplantae',
            },
        },
        'fungi': {
            'gbif': 5,
            'ncbi': {
                'rank': 'kingdom',
                'taxon': 'fungi',
            },
        },
        'chromista': {
            'gbif': 4,
            'ncbi': {
                'rank': 'clade',
                'taxon': 'sar',
            },
        },
        'bacteria': {
            'gbif': 3,
            'ncbi': {
                'rank': 'domain',
                'taxon': 'bacteria',
            },
        },
        'archaea': {
            'gbif': 2,
            'ncbi': {
                'rank': 'domain',
                'taxon': 'archaea',
            },
        },
        'viruses': {
            'gbif': 8,
            'ncbi': {
                'rank': 'acellular root',
                'taxon': 'viruses',
            },
        },
        'virus': {
            'gbif': 8,
            'ncbi': {
                'rank': 'acellular root',
                'taxon': 'viruses',
            },
        },
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if Config._initialized:
            return
        Config._initialized = True
        self._load_cascading_config()
        self.output_dir = Path(os.getenv("OUTPUT_DIR", 'output'))
        self.query_dir = None

    def _get_config_paths(self) -> list[Path]:
        """Parse command line to get config file paths.
        (supports multiple -c flags).
        """
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            '-c', '--config',
            type=Path,
            action='append',
            help='Configuration YAML file path (can be specified multiple'
                 ' times for cascading configs)',
        )

        # Parse known args to get config paths, ignore unknown args
        args, _ = parser.parse_known_args()

        # If no config files specified, use default
        if not args.config:
            return [DEFAULT_CONFIG_PATH]

        return args.config

    def _load_cascading_config(self):
        """Load and merge multiple configuration files with cascading."""
        config_paths = self._get_config_paths()
        try:
            merged_config_data = {}

            for config_path in config_paths:
                if config_path.exists():
                    logger.info(f"Loading config: {config_path}")
                    with open(config_path, 'r') as f:
                        config_data = yaml.safe_load(f) or {}
                    merged_config_data = self._deep_merge_dicts(
                        merged_config_data, config_data)
                else:
                    logger.warning(
                        f"Config file not found: {config_path}. Skipping.")

            if not merged_config_data:
                logger.info("No configuration files found. Using defaults.")

            self._config = ConfigSchema(**merged_config_data)
            self._set_attributes()

        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)

    def _deep_merge_dicts(self, base: dict, override: dict) -> dict:
        """Deep merge two dictionaries, with override taking precedence."""
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge_dicts(result[key], value)
            else:
                result[key] = value

        return result

    def _set_attributes(self):
        """Apply validated configuration to instance attributes."""
        for field_name in self._config.__class__.model_fields:
            field_value = getattr(self._config, field_name)
            setattr(self, field_name, field_value)

        self._apply_env_overrides()
        self._resolve_ncbi_api_key()

    def _apply_env_overrides(self):
        """Apply environment variable overrides for backward compatibility."""
        for mapper in mappings.ENV_VARS.values():
            value = os.getenv(mapper.env_name)
            if value is not None:
                try:
                    mapper.set_value(self, value)
                except (AttributeError, TypeError) as e:
                    logger.warning(
                        f"Failed to update config from CLI arg "
                        f"{mapper.env_name}={value}: {e}")

    def _resolve_ncbi_api_key(self):
        """Resolve NCBI_API_KEY from vault if not provided via env var."""
        if not self.USER_EMAIL:
            logger.warning(
                "USER_EMAIL not set; cannot get or set NCBI_API_KEY"
                " from vault.")
            return
        if self.NCBI_API_KEY:
            self.vault.put('NCBI_API_KEY', self.USER_EMAIL, self.NCBI_API_KEY)
            logger.info("NCBI API key read from env var NCBI_API_KEY and"
                        " stored in vault.")
        else:
            self.NCBI_API_KEY = self.vault.get('NCBI_API_KEY', self.USER_EMAIL)
            if self.NCBI_API_KEY:
                logger.info("NCBI API key retrieved from vault.")
            else:
                logger.info(
                    "No NCBI API key provided via env var or vault. Proceeding"
                    " without an API key, but you may encounter rate limiting."
                )

    def _resolve_facility_name(self):
        """Resolve facility_name from vault if not provided by the user."""
        if not self.USER_EMAIL:
            logger.warning(
                "USER_EMAIL not set; cannot get or set facility_name from"
                " vault.")
            return
        current = self.inputs.facility_name
        if current and current != FACILITY_NAME_DEFAULT:
            self.vault.put('facility_name', self.USER_EMAIL, current)
        else:
            vault_value = self.vault.get('facility_name', self.USER_EMAIL)
            if vault_value:
                self.inputs.facility_name = vault_value

    def update_from_args(self, args: argparse.Namespace):
        """Update config from CLI arguments and setup logging/directories."""
        # Setup logging
        conf = get_logging_config(self.output_dir / self.log_filename)
        dictConfig(conf)

        # Handle BOLD flag
        if hasattr(args, 'bold') and args.bold:
            self.bold_flag_file.write_text('1')

        for arg_name, value in vars(args).items():
            if value is None:
                continue
            param_name = mappings.CLI_TO_ATTR_NAME.get(arg_name)
            if not param_name:
                continue
            mapper = mappings.CLI_ARGS[param_name]

            try:
                mapper.set_value(self, value)
            except (AttributeError, TypeError) as e:
                logger.warning(
                    f"Failed to update config from CLI arg "
                    f"{arg_name}={value}: {e}")
                continue

        self._resolve_facility_name()

    def create_query_dir(self, query_ix, query_title):
        """Create a directory for this query and write query title file."""
        query_dir = self.get_query_dir(query_ix)
        query_title_path = query_dir / self.query_title_file
        with query_title_path.open("w") as f:
            f.write(query_title)
            logger.info(f"Query title written to {query_title_path}")
        return query_dir

    def get_query_ix(self, ix_or_dir):
        """Resolve query index/dir to query index."""
        if (
            isinstance(ix_or_dir, str) and QUERY_DIR_PREFIX in ix_or_dir
        ) or isinstance(ix_or_dir, Path):
            query_dir = Path(ix_or_dir)
            return int(query_dir.name.split("_")[1]) - 1
        return ix_or_dir

    def get_query_dir(self, ix_or_dir=None):
        """Resolve query index/dir to query dir Path."""
        if ix_or_dir is None:
            if self.query_dir:
                return self.query_dir
            raise ValueError(
                "Cannot get a query_dir - no query dir provided and no"
                " query_dir set in config.")
        if (
            isinstance(ix_or_dir, str) and QUERY_DIR_PREFIX in ix_or_dir
        ) or isinstance(ix_or_dir, Path):
            query_dir = Path(ix_or_dir)
            return query_dir

        query_ix = int(ix_or_dir)
        sample_id = self.get_sample_id(query_ix)
        query_dir = (
            self.output_dir
            / f"{QUERY_DIR_PREFIX}{query_ix + 1:>03}_{sample_id}"
        )
        query_dir.mkdir(exist_ok=True, parents=True)
        return query_dir

    def get_sample_id(self, query):
        """Resolve query index/dir to sample ID."""
        query_ix = self.get_query_ix(query)
        return self.read_query_fasta(query_ix).id

    @property
    def bold_flag_file(self):
        """Path to the BOLD flag file."""
        return self.output_dir / self.bold_flag

    @property
    def is_bold(self):
        """Check if this is a BOLD run."""
        return self.bold_flag_file.exists()

    @property
    def database_name(self):
        """Return the name of the reference database."""
        if self.is_bold:
            return 'BOLD'
        return self.report.database_name

    @property
    def allowed_loci(self) -> list[Locus]:
        """Return a list of allowed loci synonyms."""
        allowed_loci_data = json.loads(self.allowed_loci_file.read_text())
        return [
            Locus(name, data)
            for name, data in allowed_loci_data.items()
        ]

    @property
    def taxonomy_path(self):
        return self.output_dir / self.taxonomy_file

    @property
    def entrez_cache_dir(self):
        return self.output_dir / self.entrez_cache_dirname

    @property
    def temp_root_dir(self):
        return Path(
            self.temp_root
            if self.temp_root
            else tempfile.gettempdir()
        )

    @property
    def tempdir(self):
        tempdir = self.temp_root_dir / self.temp_dir_name
        tempdir.mkdir(exist_ok=True, parents=True)
        return tempdir

    @property
    def user_tempdir(self):
        user_dir = self.tempdir / (self.user_email or 'ANONYMOUS')
        user_dir.mkdir(exist_ok=True, parents=True)
        return user_dir

    @property
    def throttle_sqlite_path(self):
        return self.user_tempdir / ('throttle_' + self.sqlite_file)

    @property
    def throttle_sqlite_global_path(self):
        return self.tempdir / ('throttle_' + self.sqlite_file)

    @property
    def redis_ssl(self):
        """Azure Cache for Redis uses SSL on port 6380."""
        return self.redis_port == 6380

    @property
    def cache_sqlite_path(self):
        return self.tempdir / ('cache_' + self.sqlite_file)

    @property
    def start_time(self) -> datetime:
        ts_format = "%Y%m%d %H%M%S"
        path = self.output_dir / self.timestamp_filename
        if path.exists():
            ts = path.read_text().strip(' \n')
            try:
                return datetime.strptime(ts, ts_format)
            except Exception:
                logger.warning(
                    f"Invalid timestamp '{ts}' in {path} (expected format"
                    f" {ts_format})")

    @property
    def timestamp(self) -> str:
        """Return the timestamp as a string."""
        start_time = self.start_time
        if start_time:
            return start_time.strftime("%Y-%m-%d %H:%M:%S")
        return "Unknown"

    @cached_property
    def metadata(self) -> dict[str, dict]:
        """Read metadata from CSV file."""
        def _get_value_for_key(key, row, colname):
            value = (
                row[colname].strip()
                if colname in row
                else None
            )
            if 'interest' in key.lower():
                if not value:
                    return []
                return [
                    x.strip()
                    for x in value.split('|')
                    if x.strip()
                ]
            return value

        data = {}
        with self.inputs.metadata_csv.open() as f:
            reader = csv.DictReader(f)
            header = self.inputs.metadata_csv_header.copy()
            header.update({
                x: x
                for x in reader.fieldnames
                if x not in self.inputs.metadata_csv_header.keys()
                and x not in self.inputs.metadata_csv_header.values()
            })
            for row in reader:
                sample_id = row.pop(header["sample_id"])
                data[sample_id] = {
                    key: _get_value_for_key(key, row, colname)
                    for key, colname in header.items()
                    if key != "sample_id"
                    and key.lower() not in METADATA_IGNORE_FIELDS
                }
        return data

    def _get_metadata_for_query(self, query, field) -> str:
        sample_id = self.get_sample_id(query)
        return self.metadata[sample_id][
            self.inputs.metadata_csv_header[field]
        ]

    def get_locus_for_query(self, query) -> Locus:
        name = (
            'COI'
            if self.is_bold
            else self._get_metadata_for_query(query, "locus")
        )
        if name.endswith(' gene'):
            return name.rsplit(' ', 1)[0]
        if name is None or name.lower().strip() == 'na':
            return Locus('NA', {})
        for locus in self.allowed_loci:
            if name in locus:
                return locus.rename(name)
        loci_list = '\n- '.join([str(locus) for locus in self.allowed_loci])
        raise ValueError(
            f"Unrecognized locus '{name}' for query {query}. This should have"
            " been raised in p0_validation.py. Allowed loci are:\n"
            "- 'NA'\n"
            f"- {loci_list}"
        )

    def locus_was_provided_for(self, query) -> bool:
        """Determine whether a locus was provided."""
        if self.is_bold:
            return True
        if not self.get_locus_for_query(query):
            return False
        return True

    def get_pmi_for_query(self, query) -> str:
        return self._get_metadata_for_query(query, "preliminary_id")

    def get_country_for_query(self, query, code=False) -> str:
        country = self._get_metadata_for_query(query, "country")
        if not country:
            return None
        if code:
            return countries.get_code(country)
        return country

    def get_toi_list_for_query(self, query) -> list[str]:
        """Read taxa of interest from TOI file."""
        return self._get_metadata_for_query(query, "taxa_of_interest")

    def get_classification_for_query(self, query) -> str:
        classification = self._get_metadata_for_query(query, "classification")
        if not (isinstance(classification, str) and classification.strip()):
            return None
        return self.HIGHER_CLASSIFICATIONS[
            classification.lower().strip()
        ]

    def get_report_path(self, query, bold: bool = False) -> Path:
        query_ix = self.get_query_ix(query)
        return self.get_query_dir(query_ix) / path_safe_str(
            REPORT_FILENAME.format(
                sample_id=self.get_sample_id(query_ix).replace('.', '_'),
                timestamp='DEBUG' if self.report.debug else self.timestamp,
                prefix='BOLD_' if bold else '',
            )
        )

    def read_flag_details_csv(self) -> dict[str, dict[str, dict]]:
        data = {}
        with self.flag_details_csv_path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                flag = data.get(row['id'], {'name': row['name']})
                flag['explanation'] = flag.get('explanation', {})
                flag['outcome'] = flag.get('outcome', {})
                flag['level'] = flag.get('level', {})
                flag['explanation'][row['value']] = row['explanation']
                flag['outcome'][row['value']] = row['outcome']
                try:
                    flag['level'][row['value']] = int(row['level'])
                except ValueError:
                    raise ValueError(
                        f"flags.csv: level value must be a valid integer - got"
                        f" '{row['level']}' for flag {row['id']}{row['value']}"
                    )
                data[row['id']] = flag
        return data

    def read_query_fasta(self, index=None) -> list[SeqIO.SeqRecord]:
        """Read query FASTA file."""
        if not hasattr(self, "query_sequences"):
            with open(self.inputs.query_fasta) as f:
                self.query_sequences = list(SeqIO.parse(f, "fasta"))
        if index is not None:
            return self.query_sequences[int(index)]
        return self.query_sequences

    def read_hits_json(self, query):
        """Read BLAST hits from JSON file."""
        query_dir = self.get_query_dir(query)
        path = query_dir / self.hits_json
        return self.read_json(path)

    def read_hits_fasta(self, query) -> list[SeqIO.SeqRecord]:
        """Read BLAST hits from JSON file."""
        query_dir = self.get_query_dir(query)
        path = query_dir / self.hits_fasta
        return self.read_fasta(path)

    def read_taxonomy_file(self) -> dict[str, dict[str, str]]:
        """Read taxonomy from CSV file."""
        taxonomies = {}
        with self.taxonomy_path.open() as f:
            for row in csv.DictReader(f):
                taxonomies[row["accession"]] = row
        return taxonomies

    def read_json(self, path):
        """Read JSON file."""
        with path.open() as f:
            return json.load(f)

    def read_fasta(self, path):
        """Read FASTA file."""
        return list(SeqIO.parse(path, "fasta"))

    def to_json(self) -> dict:
        """Serialize object to JSON-friendly dict."""
        return {
            key: value
            for key, value in self.__dict__.items()
            if key not in (
                'query_sequences', '_config'
            )
        }

    def url_from_accession(self, accession):
        return f"https://www.ncbi.nlm.nih.gov/nuccore/{accession}"

    def get_map_filename_for_target(self, taxon):
        return MAP_FILENAME_TEMPLATE.format(taxon_str=path_safe_str(taxon))

    def cleanup(self):
        """Remove temporary files."""
        logger.info("Cleaning temporary files from output dir...")
        for attr_name in TEMP_FILES:
            filename = getattr(self, attr_name, None)
            if not filename:
                continue
            path = self.output_dir / filename
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        for path in self.tempdir.glob('*'):
            if path.is_dir():
                mtime = get_latest_mtime(path)
                if (
                    mtime
                    < datetime.now()
                    - timedelta(days=self.temp_clean_after_days)
                ):
                    shutil.rmtree(path)

    @cached_property
    def vault(self):
        from src.utils.secrets import Vault
        return Vault(self)

    @property
    def azure_key_vault_enabled(self) -> bool:
        return bool(self.azure_key_vault_url)


def get_latest_mtime(path: str) -> datetime:
    """Return the latest modification time of files/dirs within given dir."""
    latest_mtime = os.path.getmtime(path)
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            full_path = os.path.join(root, name)
            try:
                mtime = os.path.getmtime(full_path)
                if mtime > latest_mtime:
                    latest_mtime = mtime
            except FileNotFoundError:
                continue

    return datetime.fromtimestamp(latest_mtime)
