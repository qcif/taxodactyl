"""Map CLI arguments and environment variables to configuration keys."""

from abc import ABC, abstractmethod
from pathlib import Path

from . import arguments, env_vars


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
    """Abstract base class for configuration mappings."""

    def __init__(self, name, namespace=None, cli_name=None, env_name=None):
        self.name = name
        self.cli_name = cli_name
        self.env_name = env_name
        self.namespace = namespace

    def set_value(self, config, value):
        """Set the value in the config object."""
        if self.namespace:
            namespace = getattr(config, self.namespace)
            setattr(namespace, self.name, self.cast(value))
        else:
            setattr(config, self.name, self.cast(value))

    @abstractmethod
    def cast(self, value):
        """Cast the value to the appropriate type."""
        pass


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
        return value not in (None, "0", "false", "False", "FALSE", "")


class PathMapping(AbstractMapping):

    def __init__(self, *args, create=False, **kwargs):
        self.create = create
        super().__init__(*args, **kwargs)

    def cast(self, value):
        v = Path(value) if value is not None else None
        if v and self.create:
            v.mkdir(parents=True, exist_ok=True)
        return v


class ListMapping(AbstractMapping):
    def cast(self, value):
        return value.replace(' ', '').split(',') if value else []


class UppercaseListMapping(AbstractMapping):
    def cast(self, value):
        return value.upper().replace(' ', '').split(',') if value else []


parameters = [
    # File paths
    PathMapping(
        'output_dir',
        cli_name=arguments.OUTPUT_DIR,
        env_name=env_vars.OUTPUT_DIR,
        create=True,
    ),
    PathMapping(
        'query_fasta',
        namespace='inputs',
        cli_name=arguments.QUERY_FASTA,
        env_name=env_vars.INPUT_FASTA_FILEPATH,
    ),
    PathMapping(
        'metadata_csv',
        namespace='inputs',
        cli_name=arguments.METADATA_CSV,
        env_name=env_vars.INPUT_METADATA_CSV_FILEPATH,
    ),
    PathMapping(
        'taxdb_dir',
        cli_name=arguments.TAXDB_DIR,
        env_name=env_vars.TAXONKIT_DATA,
    ),
    PathMapping(
        'allowed_loci_file',
        cli_name=arguments.ALLOWED_LOCI_FILE,
        env_name=env_vars.ALLOWED_LOCI_FILE,
    ),
    PathMapping(
        'flag_details_csv_path',
        cli_name=arguments.FLAG_DETAILS_CSV,
        env_name=env_vars.FLAG_DETAILS_CSV_PATH,
    ),
    PathMapping(
        'placeholder_img_path',
        env_name=env_vars.PLACEHOLDER_IMG_PATH,
    ),

    # String filenames/paths
    StringMapping(
        'timestamp_filename',
        env_name=env_vars.TIMESTAMP_FILENAME,
    ),
    StringMapping(
        'accessions_filename',
        env_name=env_vars.ACCESSIONS_FILENAME,
    ),
    StringMapping(
        'taxonomy_file',
        env_name=env_vars.TAXONOMY_FILE,
    ),
    StringMapping(
        'query_title_file',
        env_name=env_vars.QUERY_TITLE_FILE,
    ),
    StringMapping(
        'hits_json',
        env_name=env_vars.HITS_JSON,
    ),
    StringMapping(
        'hits_fasta',
        env_name=env_vars.HITS_FASTA,
    ),
    StringMapping(
        'taxonomy_id_csv',
        env_name=env_vars.TAXONOMY_ID_CSV,
    ),
    StringMapping(
        'candidates_fasta',
        env_name=env_vars.CANDIDATES_FASTA,
    ),
    StringMapping(
        'phylogeny_fasta',
        env_name=env_vars.PHYLOGENY_FASTA,
    ),
    StringMapping(
        'candidates_csv',
        env_name=env_vars.CANDIDATES_CSV,
    ),
    StringMapping(
        'candidates_json',
        env_name=env_vars.CANDIDATES_JSON,
    ),
    StringMapping(
        'candidates_count_file',
        env_name=env_vars.CANDIDATES_COUNT_FILE,
    ),
    StringMapping(
        'candidates_sources_json',
        env_name=env_vars.CANDIDATES_SOURCES_JSON,
    ),
    StringMapping(
        'independent_sources_json',
        env_name=env_vars.INDEPENDENT_SOURCES_JSON,
    ),
    StringMapping(
        'toi_detected_csv',
        env_name=env_vars.TOI_DETECTED_CSV,
    ),
    StringMapping(
        'pmi_match_csv',
        env_name=env_vars.PMI_MATCH_CSV,
    ),
    StringMapping(
        'boxplot_img_filename',
        env_name=env_vars.BOXPLOT_IMG_FILENAME,
    ),
    StringMapping(
        'tree_nwk_filename',
        env_name=env_vars.TREE_NWK_FILENAME,
    ),
    StringMapping(
        'db_coverage_json',
        env_name=env_vars.DB_COVERAGE_JSON,
    ),
    StringMapping(
        'log_filename',
        env_name=env_vars.LOG_FILENAME,
    ),
    StringMapping(
        'query_log_filename',
        env_name=env_vars.QUERY_LOG_FILENAME,
    ),
    StringMapping(
        'sqlite_file',
        env_name=env_vars.SQLITE_FILE,
    ),
    StringMapping(
        'entrez_cache_dirname',
        env_name=env_vars.ENTREZ_CACHE_DIRNAME,
    ),
    StringMapping(
        'errors_dir',
        env_name=env_vars.ERRORS_DIR,
    ),
    StringMapping(
        'temp_dir_name',
        env_name=env_vars.TEMP_DIR_NAME,
    ),

    # Input validation
    IntMapping(
        'fasta_max_sequences',
        namespace='inputs',
        cli_name=arguments.FASTA_MAX_SEQUENCES,
        env_name=env_vars.FASTA_MAX_SEQUENCES,
    ),
    IntMapping(
        'fasta_min_length_nt',
        namespace='inputs',
        cli_name=arguments.FASTA_MIN_LENGTH,
        env_name=env_vars.FASTA_MIN_LENGTH_NT,
    ),
    IntMapping(
        'fasta_max_length_nt',
        namespace='inputs',
        cli_name=arguments.FASTA_MAX_LENGTH,
        env_name=env_vars.FASTA_MAX_LENGTH_NT,
    ),

    # Input metadata
    StringMapping(
        'facility_name',
        namespace='inputs',
        cli_name=arguments.FACILITY_NAME,
        env_name=env_vars.FACILITY_NAME,
    ),
    StringMapping(
        'analyst_name',
        namespace='inputs',
        cli_name=arguments.ANALYST_NAME,
        env_name=env_vars.ANALYST_NAME,
    ),

    # BLAST configuration
    IntMapping(
        'blast_max_target_seqs',
        cli_name=arguments.BLAST_MAX_TARGET_SEQS,
        env_name=env_vars.BLAST_MAX_TARGET_SEQS,
    ),

    # BOLD configuration
    StringMapping(
        'bold_database',
        cli_name=arguments.BOLD_DATABASE,
        env_name=env_vars.BOLD_DATABASE,
    ),
    StringMapping(
        'bold_flag',
        env_name=env_vars.BOLD_FLAG,
    ),
    StringMapping(
        'bold_taxon_count_json',
        env_name=env_vars.BOLD_TAXON_COUNT_JSON,
    ),
    StringMapping(
        'bold_taxon_collectors_json',
        env_name=env_vars.BOLD_TAXON_COLLECTORS_JSON,
    ),
    StringMapping(
        'bold_taxonomy_json',
        env_name=env_vars.BOLD_TAXONOMY_JSON,
    ),

    # GBIF configuration
    IntMapping(
        'gbif_limit_records',
        cli_name=arguments.GBIF_LIMIT_RECORDS,
        env_name=env_vars.GBIF_LIMIT_RECORDS,
    ),
    IntMapping(
        'gbif_max_occurrence_records',
        cli_name=arguments.GBIF_MAX_OCCURRENCE_RECORDS,
        env_name=env_vars.GBIF_MAX_OCCURRENCE_RECORDS,
    ),
    UppercaseListMapping(
        'gbif_accepted_status',
        cli_name=arguments.GBIF_ACCEPTED_STATUS,
        env_name=env_vars.GBIF_ACCEPTED_STATUS,
    ),

    # Database coverage
    IntMapping(
        'db_coverage_toi_limit',
        cli_name=arguments.DB_COVERAGE_TOI_LIMIT,
        env_name=env_vars.DB_COVERAGE_TOI_LIMIT,
    ),
    IntMapping(
        'db_coverage_max_candidates',
        cli_name=arguments.DB_COVERAGE_MAX_CANDIDATES,
        env_name=env_vars.DB_COVERAGE_MAX_CANDIDATES,
    ),

    # Other configuration
    FloatMapping(
        'hmmsearch_min_evalue',
        env_name=env_vars.HMMSEARCH_MIN_EVALUE,
    ),
    StringMapping(
        'flag_file_template',
        env_name=env_vars.FLAG_FILE_TEMPLATE,
    ),
    IntMapping(
        'cache_timeout_hours',
        env_name=env_vars.CACHE_TIMEOUT_HOURS,
    ),
    IntMapping(
        'max_api_retries',
        env_name=env_vars.MAX_API_RETRIES,
    ),
    IntMapping(
        'temp_clean_after_days',
        env_name=env_vars.TEMP_CLEAN_AFTER_DAYS,
    ),

    # Analysis criteria (nested in criteria object)
    IntMapping(
        'alignment_min_nt',
        namespace='criteria',
        cli_name=arguments.MIN_ALIGNMENT_LENGTH,
        env_name=env_vars.MIN_NT,
    ),
    FloatMapping(
        'alignment_min_q_coverage',
        namespace='criteria',
        cli_name=arguments.MIN_QUERY_COVERAGE,
        env_name=env_vars.MIN_Q_COVERAGE,
    ),
    FloatMapping(
        'alignment_min_identity',
        namespace='criteria',
        cli_name=arguments.MIN_IDENTITY,
        env_name=env_vars.MIN_IDENTITY,
    ),
    FloatMapping(
        'alignment_min_identity_strict',
        namespace='criteria',
        cli_name=arguments.MIN_IDENTITY_STRICT,
        env_name=env_vars.MIN_IDENTITY_STRICT,
    ),
    FloatMapping(
        'median_identity_warning_factor',
        namespace='criteria',
        cli_name=arguments.MEDIAN_IDENTITY_WARNING_FACTOR,
        env_name=env_vars.MEDIAN_IDENTITY_WARNING_FACTOR,
    ),
    IntMapping(
        'max_candidates_for_analysis',
        namespace='criteria',
        cli_name=arguments.MAX_CANDIDATES_ANALYSIS,
        env_name=env_vars.MAX_CANDIDATES_FOR_ANALYSIS,
    ),
    IntMapping(
        'sources_min_count',
        namespace='criteria',
        cli_name=arguments.MIN_SOURCE_COUNT,
        env_name=env_vars.MIN_SOURCE_COUNT,
    ),
    IntMapping(
        'phylogeny_min_hit_sequences',
        namespace='criteria',
        cli_name=arguments.PHYLOGENY_MIN_SEQUENCES,
        env_name=env_vars.PHYLOGENY_MIN_HIT_SEQUENCES,
    ),
    IntMapping(
        'phylogeny_max_hits_per_species',
        namespace='criteria',
        cli_name=arguments.PHYLOGENY_MAX_PER_SPECIES,
        env_name=env_vars.PHYLOGENY_MAX_HITS_PER_SPECIES,
    ),
    FloatMapping(
        'phylogeny_min_hit_identity',
        namespace='criteria',
        env_name=env_vars.PHYLOGENY_MIN_HIT_IDENTITY,
    ),

    # Database coverage criteria
    IntMapping(
        'db_cov_target_min_a',
        namespace='criteria',
        cli_name=arguments.DB_COV_TARGET_MIN_A,
        env_name=env_vars.DB_COV_MIN_A,
    ),
    IntMapping(
        'db_cov_target_min_b',
        namespace='criteria',
        cli_name=arguments.DB_COV_TARGET_MIN_B,
        env_name=env_vars.DB_COV_MIN_B,
    ),
    IntMapping(
        'db_cov_related_min_a',
        namespace='criteria',
        cli_name=arguments.DB_COV_RELATED_MIN_A,
        env_name=env_vars.DB_COV_RELATED_MIN_A,
    ),
    IntMapping(
        'db_cov_related_min_b',
        namespace='criteria',
        cli_name=arguments.DB_COV_RELATED_MIN_B,
        env_name=env_vars.DB_COV_RELATED_MIN_B,
    ),
    IntMapping(
        'db_cov_country_missing_a',
        namespace='criteria',
        cli_name=arguments.DB_COV_COUNTRY_MISSING_A,
        env_name=env_vars.DB_COV_COUNTRY_MISSING_A,
    ),

    # Report settings
    BoolMapping(
        'debug',
        namespace='report',
        cli_name=arguments.REPORT_DEBUG,
        env_name=env_vars.REPORT_DEBUG,
    ),
    StringMapping(
        'database_name',
        namespace='report',
        cli_name=arguments.DATABASE_NAME,
        env_name=env_vars.BLAST_DATABASE_NAME,
    ),
    StringMapping(
        'title',
        namespace='report',
        env_name=env_vars.REPORT_TITLE,
    ),
]

CLI_ARGS = {
    mapping.cli_name.replace('-', '_'): mapping
    for mapping in parameters
    if mapping.cli_name is not None
}
ENV_VARS = [
    mapping
    for mapping in parameters
    if mapping.env_name is not None
]
