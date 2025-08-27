"""Map CLI arguments and environment variables to configuration keys."""

from pathlib import Path


class ARGUMENTS:
    """Namespace for CLI argument names to ensure single source of truth."""

    # BLAST configuration
    BLAST_MAX_TARGET_SEQS = 'blast-max-target-seqs'

    # BOLD configuration
    BOLD_DATABASE = 'bold-database'

    # GBIF configuration
    GBIF_LIMIT_RECORDS = 'gbif-limit-records'
    GBIF_MAX_OCCURRENCE_RECORDS = 'gbif-max-occurrence-records'
    GBIF_ACCEPTED_STATUS = 'gbif-accepted-status'

    # Analysis criteria
    MIN_ALIGNMENT_LENGTH = 'min-alignment-length'
    MIN_QUERY_COVERAGE = 'min-query-coverage'
    MIN_IDENTITY = 'min-identity'
    MIN_IDENTITY_STRICT = 'min-identity-strict'
    MEDIAN_IDENTITY_WARNING_FACTOR = 'median-identity-warning-factor'
    MAX_CANDIDATES_ANALYSIS = 'max-candidates-analysis'
    MIN_SOURCE_COUNT = 'min-source-count'
    PHYLOGENY_MIN_SEQUENCES = 'phylogeny-min-sequences'
    PHYLOGENY_MAX_PER_SPECIES = 'phylogeny-max-per-species'

    # Database coverage criteria
    DB_COV_TARGET_MIN_A = 'db-cov-target-min-a'
    DB_COV_TARGET_MIN_B = 'db-cov-target-min-b'
    DB_COV_RELATED_MIN_A = 'db-cov-related-min-a'
    DB_COV_RELATED_MIN_B = 'db-cov-related-min-b'
    DB_COV_COUNTRY_MISSING_A = 'db-cov-country-missing-a'

    # Database coverage settings
    DB_COVERAGE_TOI_LIMIT = 'db-coverage-toi-limit'
    DB_COVERAGE_MAX_CANDIDATES = 'db-coverage-max-candidates'

    # Input validation settings
    FASTA_MAX_SEQUENCES = 'fasta-max-sequences'
    FASTA_MIN_LENGTH = 'fasta-min-length'
    FASTA_MAX_LENGTH = 'fasta-max-length'

    # Report settings
    REPORT_DEBUG = 'report-debug'
    DATABASE_NAME = 'database-name'
    FACILITY_NAME = 'facility-name'
    ANALYST_NAME = 'analyst-name'

    # File paths and validation settings
    OUTPUT_DIR = 'output-dir'
    METADATA_CSV = 'metadata-csv'
    QUERY_FASTA = 'query-fasta'
    TAXDB_DIR = 'taxdb-dir'
    ALLOWED_LOCI_FILE = 'allowed-loci-file'
    FLAG_DETAILS_CSV = 'flag-details-csv'


def _parse_status_list(value):
    """Parse GBIF status list from environment variable."""
    return value.upper().replace(' ', '').split(',')


def _parse_bool(value):
    """Parse boolean from environment variable."""
    return value not in (None, "0", "false", "False", "FALSE", "")


CLI_ARGS = {
    k.replace('-', '_'): v
    for k, v in
    {
        # File paths and validation settings
        ARGUMENTS.OUTPUT_DIR: ('output_dir',),
        ARGUMENTS.METADATA_CSV: ('inputs', 'metadata_csv'),
        ARGUMENTS.QUERY_FASTA: ('inputs', 'query_fasta'),
        ARGUMENTS.TAXDB_DIR: ('taxdb_dir',),
        ARGUMENTS.ALLOWED_LOCI_FILE: ('allowed_loci_file',),
        ARGUMENTS.FLAG_DETAILS_CSV: ('flag_details_csv_path',),

        # BLAST configuration
        ARGUMENTS.BLAST_MAX_TARGET_SEQS: ('blast_max_target_seqs',),

        # BOLD configuration
        ARGUMENTS.BOLD_DATABASE: ('bold_database',),

        # GBIF configuration
        ARGUMENTS.GBIF_LIMIT_RECORDS: ('gbif_limit_records',),
        ARGUMENTS.GBIF_MAX_OCCURRENCE_RECORDS: (
            'gbif_max_occurrence_records',),
        ARGUMENTS.GBIF_ACCEPTED_STATUS: ('gbif_accepted_status',),

        # Analysis criteria (nested in criteria object)
        ARGUMENTS.MIN_ALIGNMENT_LENGTH: ('criteria', 'alignment_min_nt'),
        ARGUMENTS.MIN_QUERY_COVERAGE: ('criteria', 'alignment_min_q_coverage'),
        ARGUMENTS.MIN_IDENTITY: ('criteria', 'alignment_min_identity'),
        ARGUMENTS.MIN_IDENTITY_STRICT: (
            'criteria', 'alignment_min_identity_strict'),
        ARGUMENTS.MEDIAN_IDENTITY_WARNING_FACTOR: (
            'criteria', 'median_identity_warning_factor'),
        ARGUMENTS.MAX_CANDIDATES_ANALYSIS: (
            'criteria', 'max_candidates_for_analysis'),
        ARGUMENTS.MIN_SOURCE_COUNT: ('criteria', 'sources_min_count'),
        ARGUMENTS.PHYLOGENY_MIN_SEQUENCES: (
            'criteria', 'phylogeny_min_hit_sequences'),
        ARGUMENTS.PHYLOGENY_MAX_PER_SPECIES: (
            'criteria', 'phylogeny_max_hits_per_species'),

        # Database coverage criteria
        ARGUMENTS.DB_COV_TARGET_MIN_A: ('criteria', 'db_cov_target_min_a'),
        ARGUMENTS.DB_COV_TARGET_MIN_B: ('criteria', 'db_cov_target_min_b'),
        ARGUMENTS.DB_COV_RELATED_MIN_A: ('criteria', 'db_cov_related_min_a'),
        ARGUMENTS.DB_COV_RELATED_MIN_B: ('criteria', 'db_cov_related_min_b'),
        ARGUMENTS.DB_COV_COUNTRY_MISSING_A: (
            'criteria', 'db_cov_country_missing_a'),

        # Database coverage settings
        ARGUMENTS.DB_COVERAGE_TOI_LIMIT: ('db_coverage_toi_limit',),
        ARGUMENTS.DB_COVERAGE_MAX_CANDIDATES: ('db_coverage_max_candidates',),

        # Input validation settings
        ARGUMENTS.FASTA_MAX_SEQUENCES: ('inputs', 'fasta_max_sequences'),
        ARGUMENTS.FASTA_MIN_LENGTH: ('inputs', 'fasta_min_length_nt'),
        ARGUMENTS.FASTA_MAX_LENGTH: ('inputs', 'fasta_max_length_nt'),

        # Report settings
        ARGUMENTS.REPORT_DEBUG: ('report', 'debug'),
        ARGUMENTS.DATABASE_NAME: ('report', 'database_name'),
        ARGUMENTS.FACILITY_NAME: ('inputs', 'facility_name'),
        ARGUMENTS.ANALYST_NAME: ('inputs', 'analyst_name'),
    }.items()
}

ENV_VARS = {
    'OUTPUT_DIR': ('output_dir', Path),
    # Input file paths
    'INPUT_FASTA_FILEPATH': ('inputs', 'query_fasta', Path),
    'INPUT_METADATA_CSV_FILEPATH': ('inputs', 'metadata_csv', Path),
    # BLAST configuration
    'BLAST_MAX_TARGET_SEQS': ('blast_max_target_seqs', int),
    # BOLD configuration
    'BOLD_DATABASE': ('bold_database', str),
    # GBIF configuration
    'GBIF_LIMIT_RECORDS': ('gbif_limit_records', int),
    'GBIF_MAX_OCCURRENCE_RECORDS': (
        'gbif_max_occurrence_records', int),
    'GBIF_ACCEPTED_STATUS': (
        'gbif_accepted_status', _parse_status_list),
    # Analysis criteria
    'MIN_NT': ('criteria', 'alignment_min_nt', int),
    'MIN_Q_COVERAGE': ('criteria', 'alignment_min_q_coverage', float),
    'MIN_IDENTITY': ('criteria', 'alignment_min_identity', float),
    'MIN_IDENTITY_STRICT': (
        'criteria', 'alignment_min_identity_strict', float),
    'MEDIAN_IDENTITY_WARNING_FACTOR': (
        'criteria', 'median_identity_warning_factor', float),
    'MAX_CANDIDATES_FOR_ANALYSIS': (
        'criteria', 'max_candidates_for_analysis', int),
    'MIN_SOURCE_COUNT': ('criteria', 'sources_min_count', int),
    'DB_COV_MIN_A': ('criteria', 'db_cov_target_min_a', int),
    'DB_COV_MIN_B': ('criteria', 'db_cov_target_min_b', int),
    'DB_COV_RELATED_MIN_A': ('criteria', 'db_cov_related_min_a', int),
    'DB_COV_RELATED_MIN_B': ('criteria', 'db_cov_related_min_b', int),
    'DB_COV_COUNTRY_MISSING_A': (
        'criteria', 'db_cov_country_missing_a', int),
    'PHYLOGENY_MIN_HIT_IDENTITY': (
        'criteria', 'phylogeny_min_hit_identity', float),
    'PHYLOGENY_MIN_HIT_SEQUENCES': (
        'criteria', 'phylogeny_min_hit_sequences', int),
    'PHYLOGENY_MAX_HITS_PER_SPECIES': (
        'criteria', 'phylogeny_max_hits_per_species', int),
    # Input configuration
    'FACILITY_NAME': ('inputs', 'facility_name', str),
    'ANALYST_NAME': ('inputs', 'analyst_name', str),
    # Report configuration
    'REPORT_DEBUG': ('report', 'debug', _parse_bool),
    'BLAST_DATABASE_NAME': ('report', 'database_name', str),
    # Database coverage
    'DB_COVERAGE_TOI_LIMIT': ('db_coverage_toi_limit', int),
    # External tools
    'TAXONKIT_DATA': ('taxdb_dir', Path),
}
