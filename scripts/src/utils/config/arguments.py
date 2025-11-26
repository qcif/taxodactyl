"""CLI arguments."""

# File paths
OUTPUT_DIR = 'output-dir'
QUERY_DIR = 'query_dir'
METADATA_CSV = 'metadata-csv'
QUERY_FASTA = 'query-fasta'
TAXDB_DIR = 'taxdb-dir'
ALLOWED_LOCI_FILE = 'allowed-loci-file'
FLAG_DETAILS_CSV = 'flag-details-csv'
TEMP_DIR_NAME = 'temp-dir-name'
TEMP_ROOT = 'temp-root'

# Input validation
FASTA_MAX_SEQUENCES = 'fasta-max-sequences'
FASTA_MIN_LENGTH = 'fasta-min-length'
FASTA_MAX_LENGTH = 'fasta-max-length'

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
PHYLOGENY_MIN_HIT_IDENTITY = 'phylogeny-min-hit-identity'
PHYLOGENY_MIN_SEQS = 'phylogeny-min-seqs'
PHYLOGENY_MAX_SEQS = 'phylogeny-max-seqs'
PHYLOGENY_SPECIES_MAX_SEQS = 'phylogeny-species-max-seqs'
PHYLOGENY_CANDIDATE_MAX_SEQS = 'phylogeny-candidate-max-seqs'

# Database coverage criteria
DB_COV_TARGET_MIN_A = 'db-cov-target-min-a'
DB_COV_TARGET_MIN_B = 'db-cov-target-min-b'
DB_COV_RELATED_MIN_A = 'db-cov-related-min-a'
DB_COV_RELATED_MIN_B = 'db-cov-related-min-b'
DB_COV_COUNTRY_MISSING_A = 'db-cov-country-missing-a'

# Database coverage settings
DB_COVERAGE_TOI_LIMIT = 'db-coverage-toi-limit'
DB_COVERAGE_MAX_CANDIDATES = 'db-coverage-max-candidates'

# Report settings
REPORT_DEBUG = 'report-debug'
DATABASE_NAME = 'database-name'
FACILITY_NAME = 'facility-name'
ANALYST_NAME = 'analyst-name'
