"""Map CLI arguments and environment variables to configuration keys."""

from abc import ABC, abstractmethod
from pathlib import Path


def get_mapper(
    name: str,
    cli: bool = False,
    env: bool = False,
) -> 'AbstractMapping':
    """Get the mapping object for a given configuration name."""
    if cli:
        return CLI_ARGS.get(name)
    if env:
        return ENV_VARS.get(name)
    raise ValueError("Either cli or env must be True.")


class AbstractMapping(ABC):
    """Abstract base class for configuration mappings.

    If a namespace is provided, the value will be accessible through an
    intermediate namespace of that name in the config object. For example, with
    namespace='inputs' and name='query_fasta', the value will be accessible as
    config.inputs.query_fasta.

    Global args are implicitly added to every script that calls
    config.add_cli_args()
    """

    def __init__(
        self,
        name,
        namespace=None,
        cli_name=None,
        env_name=None,
        is_global=False,
        help_text=None,
        required=False,
    ):
        self.name = name
        self.cli_name = cli_name
        self.env_name = env_name
        self.namespace = namespace
        self.is_global = is_global
        self.help_text = help_text
        self._required = required

    def set_value(self, config, value):
        """Set the value in the config object."""
        if self.namespace:
            namespace = getattr(config, self.namespace)
            setattr(namespace, self.name, self.cast(value))
        else:
            setattr(config, self.name, self.cast(value))

    def as_argparse(self):
        """Return a tuple of args, kwargs to add to argparse parser."""
        args = [
            f"--{self.cli_name}",
            *self._argparse_extra_args()
        ]
        kwargs = {
            "dest": self.name,
            "type": self.cast,
            "help": self.help_text,
            "required": self._required,
            **self._argparse_extra_kwargs()
        }
        return args, kwargs

    @abstractmethod
    def cast(self, value):
        """Cast the value to the appropriate type."""
        pass

    def _argparse_extra_args(self):
        """Return any extra positional args for argparse."""
        return []

    def _argparse_extra_kwargs(self):
        """Return any extra keyword args for argparse."""
        return {}

    def required(self, val: bool = True) -> 'AbstractMapping':
        """Return mapper with specified required value."""
        self._required = val
        return self


class StringMapping(AbstractMapping):
    def cast(self, value):
        return str(value) if value is not None else None


class IntMapping(AbstractMapping):
    def cast(self, value):
        return int(value) if value is not None else None


class FloatMapping(AbstractMapping):
    def cast(self, value):
        return float(value) if value is not None else None


class BoolMapping(AbstractMapping):
    def cast(self, value):
        return str(value).lower() not in ("none", "0", "false", "")

    def as_argparse(self):
        """Return a tuple of args, kwargs to add to argparse parser."""
        args = [
            f"--{self.cli_name}",
            *self._argparse_extra_args()
        ]
        kwargs = {
            "help": self.help_text,
            'action': 'store_true',
            "dest": self.name,
            **self._argparse_extra_kwargs()
        }
        return args, kwargs


class PathMapping(AbstractMapping):

    def __init__(self, *args, create=False, assert_exists=False, **kwargs):
        self.create = create
        self.assert_exists = assert_exists
        super().__init__(*args, **kwargs)

    def cast(self, value):
        v = Path(value) if value is not None else None
        if v and self.assert_exists and not v.exists():
            raise FileNotFoundError(
                f"Path provided for param '{self.name}' does not exist: {v}")
        if v and self.create:
            v.mkdir(parents=True, exist_ok=True)
        return v


class ListMapping(AbstractMapping):
    def cast(self, value):
        return value.replace(' ', '').split(',') if value else []


class UppercaseListMapping(AbstractMapping):
    def cast(self, value):
        return value.upper().replace(' ', '').split(',') if value else []


PARAMS = {
    'config_file': PathMapping(
        'config_file',
        cli_name='c',
        is_global=True,
        assert_exists=True,
        help_text=(
            "Path to configuration YAML file. Explicit CLI args and env vars"
            " will override values in this file."
        ),
    ),
    'output_dir': PathMapping(
        'output_dir',
        cli_name='output-dir',
        env_name='OUTPUT_DIR',
        create=True,
        is_global=True,
        help_text=(
            "Directory where all output files will be saved. Will be created"
            " if it doesn't exist."
        ),
    ),
    'blast_xml_path': PathMapping(
        'blast_xml_path',
        cli_name='blast_xml_path',
        assert_exists=True,
        help_text="Path to the BLAST XML file to parse.",
    ),
    'taxids_csv': PathMapping(
        'taxids_csv',
        cli_name='taxids_csv',
        assert_exists=True,
        help_text=(
            "CSV file with columns (accession,taxid) to extract"
            " taxonomy information for."
        ),
    ),
    'params_json': PathMapping(
        'params_json',
        cli_name='params-json',
        assert_exists=True,
        help_text="Path to params JSON file.",
    ),
    'versions_yml': PathMapping(
        'versions_yml',
        cli_name='versions-yml',
        assert_exists=True,
        help_text="Path to versions YAML file.",
    ),
    'query_dir': PathMapping(
        'query_dir',
        cli_name='query_dir',
        env_name='QUERY_DIR',
        assert_exists=True,
        help_text="Path to query output directory.",
    ),
    'query_fasta': PathMapping(
        'query_fasta',
        namespace='inputs',
        cli_name='query-fasta',
        env_name='INPUT_FASTA_FILEPATH',
        assert_exists=True,
        help_text="Path to queries.fasta input file.",
    ),
    'metadata_csv': PathMapping(
        'metadata_csv',
        namespace='inputs',
        cli_name='metadata-csv',
        env_name='INPUT_METADATA_CSV_FILEPATH',
        assert_exists=True,
        help_text="Path to metadata.csv input file.",
    ),
    'taxdb_dir': PathMapping(
        'taxdb_dir',
        cli_name='taxdb-dir',
        env_name='TAXONKIT_DATA',
        assert_exists=True,
        help_text="Path to NCBI taxdump directory (for taxonkit).",
    ),
    'allowed_loci_file': PathMapping(
        'allowed_loci_file',
        cli_name='allowed-loci-file',
        env_name='ALLOWED_LOCI_FILE',
        assert_exists=True,
        help_text="Path to JSON file containing allowed loci definitions.",
    ),
    'flag_details_csv_path': PathMapping(
        'flag_details_csv_path',
        cli_name='flag-details-csv',
        env_name='FLAG_DETAILS_CSV_PATH',
        assert_exists=True,
        help_text="Path to CSV file containing flag definitions.",
    ),
    'placeholder_img_path': PathMapping(
        'placeholder_img_path',
        env_name='PLACEHOLDER_IMG_PATH',
    ),

    # String filenames/paths
    'timestamp_filename': StringMapping(
        'timestamp_filename',
        env_name='TIMESTAMP_FILENAME',
    ),
    'accessions_filename': StringMapping(
        'accessions_filename',
        env_name='ACCESSIONS_FILENAME',
    ),
    'taxonomy_file': StringMapping(
        'taxonomy_file',
        env_name='TAXONOMY_FILE',
    ),
    'query_title_file': StringMapping(
        'query_title_file',
        env_name='QUERY_TITLE_FILE',
    ),
    'hits_json': StringMapping(
        'hits_json',
        env_name='HITS_JSON',
    ),
    'hits_fasta': StringMapping(
        'hits_fasta',
        env_name='HITS_FASTA',
    ),
    'taxonomy_id_csv': StringMapping(
        'taxonomy_id_csv',
        env_name='TAXONOMY_ID_CSV',
    ),
    'candidates_fasta': StringMapping(
        'candidates_fasta',
        env_name='CANDIDATES_FASTA',
    ),
    'phylogeny_fasta': StringMapping(
        'phylogeny_fasta',
        env_name='PHYLOGENY_FASTA',
    ),
    'candidates_csv': StringMapping(
        'candidates_csv',
        env_name='CANDIDATES_CSV',
    ),
    'candidates_json': StringMapping(
        'candidates_json',
        env_name='CANDIDATES_JSON',
    ),
    'candidates_count_file': StringMapping(
        'candidates_count_file',
        env_name='CANDIDATES_COUNT_FILE',
    ),
    'candidates_sources_json': StringMapping(
        'candidates_sources_json',
        env_name='CANDIDATES_SOURCES_JSON',
    ),
    'independent_sources_json': StringMapping(
        'independent_sources_json',
        env_name='INDEPENDENT_SOURCES_JSON',
    ),
    'toi_detected_csv': StringMapping(
        'toi_detected_csv',
        env_name='TOI_DETECTED_CSV',
    ),
    'pmi_match_csv': StringMapping(
        'pmi_match_csv',
        env_name='PMI_MATCH_CSV',
    ),
    'boxplot_img_filename': StringMapping(
        'boxplot_img_filename',
        env_name='BOXPLOT_IMG_FILENAME',
    ),
    'tree_nwk_filename': StringMapping(
        'tree_nwk_filename',
        env_name='TREE_NWK_FILENAME',
    ),
    'db_coverage_json': StringMapping(
        'db_coverage_json',
        env_name='DB_COVERAGE_JSON',
    ),
    'log_filename': StringMapping(
        'log_filename',
        env_name='LOG_FILENAME',
    ),
    'query_log_filename': StringMapping(
        'query_log_filename',
        env_name='QUERY_LOG_FILENAME',
    ),
    'sqlite_file': StringMapping(
        'sqlite_file',
        env_name='SQLITE_FILE',
    ),
    'entrez_cache_dirname': StringMapping(
        'entrez_cache_dirname',
        env_name='ENTREZ_CACHE_DIRNAME',
    ),
    'errors_dir': StringMapping(
        'errors_dir',
        env_name='ERRORS_DIR',
    ),
    'temp_dir_name': StringMapping(
        'temp_dir_name',
        env_name='TEMP_DIR_NAME',
        cli_name='temp-dir-name',
        help_text="Name of the temp directory to create within the temp root.",
    ),
    'temp_root': StringMapping(
        'temp_root',
        env_name='TEMP_ROOT',
        cli_name='temp-root',
        help_text="Path to temp root directory.",
    ),

    # Input validation
    'fasta_max_sequences': IntMapping(
        'fasta_max_sequences',
        namespace='inputs',
        cli_name='fasta-max-sequences',
        env_name='FASTA_MAX_SEQUENCES',
        help_text="Maximum number of sequences allowed.",
    ),
    'fasta_min_length': IntMapping(
        'fasta_min_length',
        namespace='inputs',
        cli_name='fasta-min-length',
        env_name='FASTA_MIN_LENGTH_NT',
        help_text="Minimum sequence length in nucleotides.",
    ),
    'fasta_max_length': IntMapping(
        'fasta_max_length',
        namespace='inputs',
        cli_name='fasta-max-length',
        env_name='FASTA_MAX_LENGTH_NT',
        help_text="Maximum sequence length in nucleotides.",
    ),

    # Input metadata
    'facility_name': StringMapping(
        'facility_name',
        namespace='inputs',
        cli_name='facility-name',
        env_name='FACILITY_NAME',
        help_text="Name of the analysis facility.",
    ),
    'analyst_name': StringMapping(
        'analyst_name',
        namespace='inputs',
        cli_name='analyst-name',
        env_name='ANALYST_NAME',
        help_text="Name of the analyst.",
    ),

    # BLAST configuration
    'blast_max_target_seqs': IntMapping(
        'blast_max_target_seqs',
        cli_name='blast-max-target-seqs',
        env_name='BLAST_MAX_TARGET_SEQS',
        help_text="Maximum number of target sequences for BLAST.",
    ),

    # BOLD configuration
    'is_bold': BoolMapping(
        'is_bold',
        cli_name='bold',
        env_name='IS_BOLD',
        help_text="Enable BOLD analysis mode.",
    ),
    'bold_database': StringMapping(
        'bold_database',
        cli_name='bold-database',
        env_name='BOLD_DATABASE',
        help_text="BOLD database to search.",
    ),
    'bold_flag': StringMapping(
        'bold_flag',
        env_name='BOLD_FLAG',
    ),
    'bold_taxon_count_json': StringMapping(
        'bold_taxon_count_json',
        env_name='BOLD_TAXON_COUNT_JSON',
    ),
    'bold_taxon_collectors_json': StringMapping(
        'bold_taxon_collectors_json',
        env_name='BOLD_TAXON_COLLECTORS_JSON',
    ),
    'bold_taxonomy_json': StringMapping(
        'bold_taxonomy_json',
        env_name='BOLD_TAXONOMY_JSON',
    ),

    # GBIF configuration
    'gbif_limit_records': IntMapping(
        'gbif_limit_records',
        cli_name='gbif-limit-records',
        env_name='GBIF_LIMIT_RECORDS',
        help_text="Limit for GBIF taxonomy records.",
    ),
    'gbif_max_occurrence_records': IntMapping(
        'gbif_max_occurrence_records',
        cli_name='gbif-max-occurrence-records',
        env_name='GBIF_MAX_OCCURRENCE_RECORDS',
        help_text="Maximum GBIF occurrence records.",
    ),
    'gbif_accepted_status': UppercaseListMapping(
        'gbif_accepted_status',
        cli_name='gbif-accepted-status',
        env_name='GBIF_ACCEPTED_STATUS',
        help_text="Comma-separated list of accepted taxonomic statuses.",
    ),

    # Database coverage
    'db_coverage_toi_limit': IntMapping(
        'db_coverage_toi_limit',
        cli_name='db-coverage-toi-limit',
        env_name='DB_COVERAGE_TOI_LIMIT',
        help_text="Limit for taxa of interest in coverage analysis.",
    ),
    'db_coverage_max_candidates': IntMapping(
        'db_coverage_max_candidates',
        cli_name='db-coverage-max-candidates',
        env_name='DB_COVERAGE_MAX_CANDIDATES',
        help_text="Maximum candidates for coverage assessment.",
    ),

    # Other configuration
    'hmmsearch_min_evalue': FloatMapping(
        'hmmsearch_min_evalue',
        env_name='HMMSEARCH_MIN_EVALUE',
    ),
    'flag_file_template': StringMapping(
        'flag_file_template',
        env_name='FLAG_FILE_TEMPLATE',
    ),
    'cache_timeout_hours': IntMapping(
        'cache_timeout_hours',
        env_name='CACHE_TIMEOUT_HOURS',
    ),
    'cache_disabled': BoolMapping(
        'cache_disabled',
        env_name='CACHE_DISABLED',
    ),
    'max_api_retries': IntMapping(
        'max_api_retries',
        env_name='MAX_API_RETRIES',
    ),
    'temp_clean_after_days': IntMapping(
        'temp_clean_after_days',
        env_name='TEMP_CLEAN_AFTER_DAYS',
    ),

    # Analysis criteria (nested in criteria object)
    'alignment_min_nt': IntMapping(
        'alignment_min_nt',
        namespace='criteria',
        cli_name='min-alignment-length',
        env_name='MIN_NT',
        help_text="Minimum alignment length in nucleotides.",
    ),
    'alignment_min_q_coverage': FloatMapping(
        'alignment_min_q_coverage',
        namespace='criteria',
        cli_name='min-query-coverage',
        env_name='MIN_Q_COVERAGE',
        help_text="Minimum query coverage fraction.",
    ),
    'alignment_min_identity': FloatMapping(
        'alignment_min_identity',
        namespace='criteria',
        cli_name='min-identity',
        env_name='MIN_IDENTITY',
        help_text="Minimum sequence identity for moderate matches.",
    ),
    'alignment_min_identity_strict': FloatMapping(
        'alignment_min_identity_strict',
        namespace='criteria',
        cli_name='min-identity-strict',
        env_name='MIN_IDENTITY_STRICT',
        help_text="Minimum sequence identity for strong matches.",
    ),
    'median_identity_warning_factor': FloatMapping(
        'median_identity_warning_factor',
        namespace='criteria',
        cli_name='median-identity-warning-factor',
        env_name='MEDIAN_IDENTITY_WARNING_FACTOR',
        help_text="Factor for median identity warnings.",
    ),
    'max_candidates_for_analysis': IntMapping(
        'max_candidates_for_analysis',
        namespace='criteria',
        cli_name='max-candidates-analysis',
        env_name='MAX_CANDIDATES_FOR_ANALYSIS',
        help_text="Maximum candidates to include in detailed analysis.",
    ),
    'sources_min_count': IntMapping(
        'sources_min_count',
        namespace='criteria',
        cli_name='min-source-count',
        env_name='MIN_SOURCE_COUNT',
        help_text="Minimum number of independent sources required.",
    ),
    'phylogeny_min_hit_identity': FloatMapping(
        'phylogeny_min_hit_identity',
        namespace='criteria',
        cli_name='phylogeny-min-hit-identity',
        env_name='PHYLOGENY_MIN_HIT_IDENTITY',
        help_text="Minimum hit identity for collecting phylogeny sequences.",
    ),
    'phylogeny_min_seqs': IntMapping(
        'phylogeny_min_seqs',
        namespace='criteria',
        cli_name='phylogeny-min-seqs',
        env_name='PHYLOGENY_MIN_SEQS',
        help_text="Minimum number of sequences to collect for phylogeny.",
    ),
    'phylogeny_max_seqs': IntMapping(
        'phylogeny_max_seqs',
        namespace='criteria',
        cli_name='phylogeny-max-seqs',
        env_name='PHYLOGENY_MAX_SEQS',
        help_text="Maximum number of sequences to collect for phylogeny.",
    ),
    'phylogeny_species_max_seqs': IntMapping(
        'phylogeny_species_max_seqs',
        namespace='criteria',
        cli_name='phylogeny-species-max-seqs',
        env_name='PHYLOGENY_SPECIES_MAX_SEQS',
        help_text=(
            "Maximum number of sequences per species to collect"
            " for phylogeny."
        ),
    ),
    'phylogeny_candidate_max_seqs': IntMapping(
        'phylogeny_candidate_max_seqs',
        namespace='criteria',
        cli_name='phylogeny-candidate-max-seqs',
        env_name='PHYLOGENY_CANDIDATE_MAX_SEQS',
        help_text=(
            "Maximum number of sequences per candidate species to"
            " collect for phylogeny."
        ),
    ),

    # Database coverage criteria
    'db_cov_target_min_a': IntMapping(
        'db_cov_target_min_a',
        namespace='criteria',
        cli_name='db-cov-target-min-a',
        env_name='DB_COV_MIN_A',
        help_text=(
            "Minimum reference database record count for target"
            " species flag 5.1A."
        ),
    ),
    'db_cov_target_min_b': IntMapping(
        'db_cov_target_min_b',
        namespace='criteria',
        cli_name='db-cov-target-min-b',
        env_name='DB_COV_MIN_B',
        help_text=(
            "Minimum database coverage record count for target"
            " species flag 5.1B."
        ),
    ),
    'db_cov_related_min_a': IntMapping(
        'db_cov_related_min_a',
        namespace='criteria',
        cli_name='db-cov-related-min-a',
        env_name='DB_COV_RELATED_MIN_A',
        help_text=(
            "Minimum database species coverage for target genus"
            " flag 5.2A."
        ),
    ),
    'db_cov_related_min_b': IntMapping(
        'db_cov_related_min_b',
        namespace='criteria',
        cli_name='db-cov-related-min-b',
        env_name='DB_COV_RELATED_MIN_B',
        help_text=(
            "Minimum database species coverage for target genus"
            " flag 5.2B."
        ),
    ),
    'db_cov_country_missing_a': IntMapping(
        'db_cov_country_missing_a',
        namespace='criteria',
        cli_name='db-cov-country-missing-a',
        env_name='DB_COV_COUNTRY_MISSING_A',
        help_text="Threshold for missing country data (grade A).",
    ),

    # Report settings
    'debug': BoolMapping(
        'debug',
        namespace='report',
        cli_name='report-debug',
        env_name='REPORT_DEBUG',
        help_text="Enable debug mode for report generation.",
    ),
    'database_name': StringMapping(
        'database_name',
        namespace='report',
        cli_name='database-name',
        env_name='BLAST_DATABASE_NAME',
        help_text="Name of the reference database.",
    ),
    'title': StringMapping(
        'title',
        namespace='report',
        env_name='REPORT_TITLE',
    ),
}
CLI_ARGS = {
    k: v for k, v in PARAMS.items()
    if v.cli_name is not None
}
GLOBAL_CLI_ARGS = {
    k: v for k, v in CLI_ARGS.items()
    if v.is_global
}
CLI_TO_ATTR_NAME = {
    v.name: k for k, v in CLI_ARGS.items()
}
ENV_VARS = {
    k: v for k, v in PARAMS.items()
    if v.env_name is not None
}
