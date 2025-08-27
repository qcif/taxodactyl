"""Map CLI arguments and environment variables to configuration keys."""

from pathlib import Path

from . import arguments


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
        arguments.OUTPUT_DIR: ('output_dir',),
        arguments.METADATA_CSV: ('inputs', 'metadata_csv'),
        arguments.QUERY_FASTA: ('inputs', 'query_fasta'),
        arguments.TAXDB_DIR: ('taxdb_dir',),
        arguments.ALLOWED_LOCI_FILE: ('allowed_loci_file',),
        arguments.FLAG_DETAILS_CSV: ('flag_details_csv_path',),

        # BLAST configuration
        arguments.BLAST_MAX_TARGET_SEQS: ('blast_max_target_seqs',),

        # BOLD configuration
        arguments.BOLD_DATABASE: ('bold_database',),

        # GBIF configuration
        arguments.GBIF_LIMIT_RECORDS: ('gbif_limit_records',),
        arguments.GBIF_MAX_OCCURRENCE_RECORDS: (
            'gbif_max_occurrence_records',),
        arguments.GBIF_ACCEPTED_STATUS: ('gbif_accepted_status',),

        # Analysis criteria (nested in criteria object)
        arguments.MIN_ALIGNMENT_LENGTH: ('criteria', 'alignment_min_nt'),
        arguments.MIN_QUERY_COVERAGE: ('criteria', 'alignment_min_q_coverage'),
        arguments.MIN_IDENTITY: ('criteria', 'alignment_min_identity'),
        arguments.MIN_IDENTITY_STRICT: (
            'criteria', 'alignment_min_identity_strict'),
        arguments.MEDIAN_IDENTITY_WARNING_FACTOR: (
            'criteria', 'median_identity_warning_factor'),
        arguments.MAX_CANDIDATES_ANALYSIS: (
            'criteria', 'max_candidates_for_analysis'),
        arguments.MIN_SOURCE_COUNT: ('criteria', 'sources_min_count'),
        arguments.PHYLOGENY_MIN_SEQUENCES: (
            'criteria', 'phylogeny_min_hit_sequences'),
        arguments.PHYLOGENY_MAX_PER_SPECIES: (
            'criteria', 'phylogeny_max_hits_per_species'),

        # Database coverage criteria
        arguments.DB_COV_TARGET_MIN_A: ('criteria', 'db_cov_target_min_a'),
        arguments.DB_COV_TARGET_MIN_B: ('criteria', 'db_cov_target_min_b'),
        arguments.DB_COV_RELATED_MIN_A: ('criteria', 'db_cov_related_min_a'),
        arguments.DB_COV_RELATED_MIN_B: ('criteria', 'db_cov_related_min_b'),
        arguments.DB_COV_COUNTRY_MISSING_A: (
            'criteria', 'db_cov_country_missing_a'),

        # Database coverage settings
        arguments.DB_COVERAGE_TOI_LIMIT: ('db_coverage_toi_limit',),
        arguments.DB_COVERAGE_MAX_CANDIDATES: ('db_coverage_max_candidates',),

        # Input validation settings
        arguments.FASTA_MAX_SEQUENCES: ('inputs', 'fasta_max_sequences'),
        arguments.FASTA_MIN_LENGTH: ('inputs', 'fasta_min_length_nt'),
        arguments.FASTA_MAX_LENGTH: ('inputs', 'fasta_max_length_nt'),

        # Report settings
        arguments.REPORT_DEBUG: ('report', 'debug'),
        arguments.DATABASE_NAME: ('report', 'database_name'),
        arguments.FACILITY_NAME: ('inputs', 'facility_name'),
        arguments.ANALYST_NAME: ('inputs', 'analyst_name'),
    }.items()
}

ENV_VARS = {
    # Input file paths
    'OUTPUT_DIR': ('output_dir', Path),
    'INPUT_FASTA_FILEPATH': ('inputs', 'query_fasta', Path),
    'INPUT_METADATA_CSV_FILEPATH': ('inputs', 'metadata_csv', Path),

    # Input metadata
    'FACILITY_NAME': ('inputs', 'facility_name', str),
    'ANALYST_NAME': ('inputs', 'analyst_name', str),

    # Input validation
    'FASTA_MAX_LENGTH_NT': ('inputs', 'fasta_max_length_nt', int),
    'FASTA_MIN_LENGTH_NT': ('inputs', 'fasta_min_length_nt', int),
    'FASTA_MAX_SEQUENCES': ('inputs', 'fasta_max_sequences', int),

    # File paths
    'ALLOWED_LOCI_FILE': ('allowed_loci_file', Path),
    'FLAG_DETAILS_CSV_PATH': ('flag_details_csv_path', Path),
    'PLACEHOLDER_IMG_PATH': ('placeholder_img_path', Path),
    'TAXONKIT_DATA': ('taxdb_dir', Path),
    'TIMESTAMP_FILENAME': ('timestamp_filename', str),
    'ACCESSIONS_FILENAME': ('accessions_filename', str),
    'TAXONOMY_FILE': ('taxonomy_file', str),
    'QUERY_TITLE_FILE': ('query_title_file', str),
    'HITS_JSON': ('hits_json', str),
    'HITS_FASTA': ('hits_fasta', str),
    'TAXONOMY_ID_CSV': ('taxonomy_id_csv', str),
    'CANDIDATES_FASTA': ('candidates_fasta', str),
    'PHYLOGENY_FASTA': ('phylogeny_fasta', str),
    'CANDIDATES_CSV': ('candidates_csv', str),
    'CANDIDATES_JSON': ('candidates_json', str),
    'CANDIDATES_COUNT_FILE': ('candidates_count_file', str),
    'CANDIDATES_SOURCES_JSON': ('candidates_sources_json', str),
    'INDEPENDENT_SOURCES_JSON': ('independent_sources_json', str),
    'TOI_DETECTED_CSV': ('toi_detected_csv', str),
    'PMI_MATCH_CSV': ('pmi_match_csv', str),
    'BOXPLOT_IMG_FILENAME': ('boxplot_img_filename', str),
    'TREE_NWK_FILENAME': ('tree_nwk_filename', str),
    'DB_COVERAGE_JSON': ('db_coverage_json', str),
    'LOG_FILENAME': ('log_filename', str),
    'QUERY_LOG_FILENAME': ('query_log_filename', str),
    'SQLITE_FILE': ('sqlite_file', str),
    'ENTREZ_CACHE_DIRNAME': ('entrez_cache_dirname', str),
    'ERRORS_DIR': ('errors_dir', str),
    'TEMP_DIR_NAME': ('temp_dir_name', str),

    # BLAST configuration
    'BLAST_MAX_TARGET_SEQS': ('blast_max_target_seqs', int),

    # BOLD configuration
    'BOLD_DATABASE': ('bold_database', str),
    'BOLD_FLAG': ('bold_flag', str),
    'BOLD_TAXON_COUNT_JSON': ('bold_taxon_count_json', str),
    'BOLD_TAXON_COLLECTORS_JSON': ('bold_taxon_collectors_json', str),
    'BOLD_TAXONOMY_JSON': ('bold_taxonomy_json', str),

    # GBIF configuration
    'GBIF_LIMIT_RECORDS': ('gbif_limit_records', int),
    'GBIF_MAX_OCCURRENCE_RECORDS': (
        'gbif_max_occurrence_records', int),
    'GBIF_ACCEPTED_STATUS': (
        'gbif_accepted_status', _parse_status_list),

    # Database coverage
    'DB_COVERAGE_TOI_LIMIT': ('db_coverage_toi_limit', int),
    'DB_COVERAGE_MAX_CANDIDATES': ('db_coverage_max_candidates', int),

    # Other configuration
    'HMMSEARCH_MIN_EVALUE': ('hmmsearch_min_evalue', float),
    'FLAG_FILE_TEMPLATE': ('flag_file_template', str),
    'CACHE_TIMEOUT_HOURS': ('cache_timeout_hours', int),
    'MAX_API_RETRIES': ('max_api_retries', int),
    'TEMP_CLEAN_AFTER_DAYS': ('temp_clean_after_days', int),

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

    # Report configuration
    'REPORT_TITLE': ('report', 'title', str),
    'REPORT_DEBUG': ('report', 'debug', _parse_bool),
    'BLAST_DATABASE_NAME': ('report', 'database_name', str),
}
