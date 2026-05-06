"""Pydantic schema for configuration validation."""

from enum import Enum
from pathlib import Path
from typing import Annotated, List

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

SCRIPTS_ROOT = Path(__file__).parents[3]


def _make_absolute(path: Path) -> Path:
    """Convert a Path to an absolute path."""
    if not path.is_absolute():
        internal_abspath = (SCRIPTS_ROOT / path).resolve()
        if internal_abspath.exists():
            return internal_abspath
        abspath = path.resolve()
        if not abspath.exists():
            raise ValueError(f"Path does not exist: {abspath}")
        return abspath
    return path


AbsolutePath = Annotated[
    Path,
    AfterValidator(_make_absolute)
]


class ThrottleBackend(str, Enum):
    """Enum for throttle backend options."""
    SQLITE = 'sqlite'
    REDIS = 'redis'


class InputsConfig(BaseModel):
    """Input file configuration."""
    facility_name: str = Field(
        default="Not provided", description="Facility name")
    analyst_name: str = Field(
        default="Not provided", description="Analyst name")

    # CSV metadata configuration
    metadata_csv_header: dict = Field(
        default={
            "sample_id": "sample_id",
            "locus": "locus",
            "preliminary_id": "preliminary_id",
            "taxa_of_interest": "taxa_of_interest",
            "country": "country",
            "host": "host",
            "classification": "classification",
            "sequence": "sequence",
        },
        description="CSV header mapping"
    )
    metadata_csv_required_fields: tuple = Field(
        default=("sample_id", "locus", "preliminary_id"),
        description="Required CSV fields"
    )

    # FASTA validation limits
    fasta_max_length: int = Field(
        default=3000, description="Maximum sequence length")
    fasta_min_length: int = Field(
        default=20, description="Minimum sequence length")
    fasta_max_sequences: int = Field(
        default=150, description="Maximum number of sequences")

    # File paths (set by CLI/config)
    query_fasta: Path | None = Field(
        default=None, description="Input FASTA file path"
    )
    metadata_csv: Path | None = Field(
        default=None, description="Input metadata CSV path"
    )


class CriteriaConfig(BaseModel):
    """Analysis criteria configuration."""
    alignment_min_nt: int = Field(
        default=300, description="Minimum alignment length")
    alignment_min_q_coverage: float = Field(
        default=0.85, description="Minimum query coverage")
    alignment_min_identity: float = Field(
        default=0.935, description="Minimum identity")
    alignment_min_identity_strict: float = Field(
        default=0.985, description="Minimum strict identity")
    median_identity_warning_factor: float = Field(
        default=0.95, description="Median identity warning factor")
    max_candidates_for_analysis: int = Field(
        default=3, description="Maximum candidates for analysis")
    sources_min_count: int = Field(
        default=5, description="Minimum source count")

    # Database coverage criteria
    db_cov_target_min_a: int = Field(
        default=5, description="DB coverage target minimum A")
    db_cov_target_min_b: int = Field(
        default=1, description="DB coverage target minimum B")
    db_cov_related_min_a: int = Field(
        default=90, description="DB coverage related minimum A")
    db_cov_related_min_b: int = Field(
        default=10, description="DB coverage related minimum B")
    db_cov_country_missing_a: int = Field(
        default=1, description="DB coverage country missing A")

    # Phylogeny criteria
    phylogeny_min_hit_identity: float = Field(
        default=0.935, description="Phylogeny minimum hit identity")
    phylogeny_min_seqs: int = Field(
        default=20, description="Minimum number of sequences to collect")
    phylogeny_max_seqs: int = Field(
        default=50, description="Maximum number of sequences to collect")
    phylogeny_species_max_seqs: int = Field(
        default=3,
        description=(
            "Maximum number of sequences collected for each (non-candidate)"
            " species."),
    )
    phylogeny_candidate_max_seqs: int = Field(
        default=5,
        description=(
            "Maximum number of sequences collected for each candidate"
            " species."),
    )


class ReportConfig(BaseModel):
    """Report generation configuration."""
    title: str = Field(
        default="Taxonomic identification report", description="Report title")
    debug: bool = Field(default=False, description="Enable debug mode")
    database_name: str = Field(
        default="NCBI Core Nt", description="Database name")


class ConfigSchema(BaseModel):
    """Main configuration schema."""

    # File paths and directories
    output_dir: Path = Field(
        default=Path('output'), description="Output directory")
    query_dir: Path | None = Field(
        default=None, description="Output directory")
    allowed_loci_file: AbsolutePath = Field(
        default_factory=lambda: (
            SCRIPTS_ROOT / 'config/loci.json'),
        description="Path to allowed loci JSON file"
    )
    flag_details_csv_path: AbsolutePath = Field(
        default_factory=lambda: (
            SCRIPTS_ROOT / 'config/flags.csv'),
        description="Path to flag details CSV file"
    )
    placeholder_img_path: AbsolutePath = Field(
        default_factory=lambda: (
            SCRIPTS_ROOT / 'src/report/static/img/placeholder.png'),
        description="Path to placeholder image file"
    )
    taxdb_dir: Path = Field(
        default_factory=lambda: Path('~/.taxonkit').expanduser(),
        description="Path to TaxonKit data directory"
    )

    # User details
    user_email: str | None = Field(
        default='',
        description="User email for API access",
    )
    ncbi_api_key: str | None = Field(
        default='',
        description="NCBI API key for increased rate limits"
    )


    # Output filenames
    timestamp_filename: str = Field(
        default='timestamp.txt', description="Timestamp filename")
    accessions_filename: str = Field(
        default="accessions.txt", description="Accessions filename")
    taxonomy_file: str = Field(
        default='taxonomy.csv', description="Taxonomy filename")
    query_title_file: str = Field(
        default='query_title.txt', description="Query title filename")
    hits_json: str = Field(
        default='hits.json', description="Hits JSON filename")
    hits_fasta: str = Field(
        default='hits.fasta', description="Hits FASTA filename")
    taxonomy_id_csv: str = Field(
        default='assigned_taxonomy.csv',
        description="Taxonomy ID CSV filename")
    candidates_fasta: str = Field(
        default='candidates.fasta', description="Candidates FASTA filename")
    phylogeny_fasta: str = Field(
        default='phylogeny.fasta', description="Phylogeny FASTA filename")
    candidates_csv: str = Field(
        default='candidates.csv', description="Candidates CSV filename")
    candidates_json: str = Field(
        default='candidates.json', description="Candidates JSON filename")
    candidates_count_file: str = Field(
        default='candidates_count.txt',
        description="Candidates count filename")
    candidates_sources_json: str = Field(
        default='candidates_sources.json',
        description="Candidates sources JSON filename")
    independent_sources_json: str = Field(
        default='aggregated_sources.json',
        description="Independent sources JSON filename")
    toi_detected_csv: str = Field(
        default='taxa_of_concern_detected.csv',
        description="TOI detected CSV filename")
    toi_detected_header: List[str] = Field(
        default=[
            "Taxon of interest",
            "Match rank",
            "Match taxon",
            "Match species",
            "Match accession",
            "Match identity",
        ],
        description="TOI detected CSV header")
    pmi_match_csv: str = Field(
        default='preliminary_id_match.csv',
        description="PMI match CSV filename")
    boxplot_img_filename: str = Field(
        default='identity-boxplot.png', description="Boxplot image filename")
    tree_nwk_filename: str = Field(
        default='candidates.nwk', description="Tree NWK filename")
    db_coverage_json: str = Field(
        default='db_coverage.json', description="DB coverage JSON filename")

    # BLAST configuration
    blast_max_target_seqs: int = Field(
        default=2000, description="BLAST maximum target sequences")

    # BOLD configuration
    bold_database: str = Field(
        default="COX1_SPECIES_PUBLIC", description="BOLD database")
    bold_flag: str = Field(default='BOLD', description="BOLD flag")
    bold_taxon_count_json: str = Field(
        default="bold_taxon_counts.json", description="BOLD taxon count JSON")
    bold_taxon_collectors_json: str = Field(
        default="bold_taxon_collectors.json",
        description="BOLD taxon collectors JSON")
    bold_taxonomy_json: str = Field(
        default="bold_taxonomy.json", description="BOLD taxonomy JSON")

    # Database coverage configuration
    db_coverage_toi_limit: int = Field(
        default=10, description="DB coverage TOI limit")
    db_coverage_max_candidates: int = Field(
        default=3, description="DB coverage max candidates")
    hmmsearch_min_evalue: float = Field(
        default=1e-5, description="HMMSEARCH minimum e-value")
    flag_file_template: str = Field(
        default='{identifier}.flag', description="Flag file template")

    # GBIF configuration
    gbif_limit_records: int = Field(
        default=500, description="GBIF limit records")
    gbif_max_occurrence_records: int = Field(
        default=5000, description="GBIF max occurrence records")
    gbif_accepted_status: List[str] = Field(
        default=['ACCEPTED', 'DOUBTFUL'],
        description="GBIF accepted status list"
    )

    # Caching
    sqlite_file: str = Field(
        default='db.sqlite', description="Throttle SQLite filename")
    entrez_cache_dirname: str = Field(
        default='entrez_cache', description="Entrez cache directory name")
    cache_timeout_hours: int = Field(
        default=168, description="Cache timeout in hours")
    cache_disabled: bool = Field(
        default=False, description="Disable caching of API responses")
    cache_backend: str = Field(
        default='sqlite',
        description="Cache backend to use ('sqlite' or 'azure_blob')")
    cache_azure_account_url: str | None = Field(
        default=None,
        description=(
            "Azure Blob Storage account URL, e.g. "
            "'https://<account>.blob.core.windows.net'. Used with "
            "DefaultAzureCredential when cache_backend is 'azure_blob'."))
    cache_azure_connection_string: str | None = Field(
        default=None,
        description=(
            "Azure Blob Storage connection string. Alternative to "
            "cache_azure_account_url when cache_backend is 'azure_blob'."))
    cache_azure_container: str = Field(
        default='biosecurity-cache',
        description="Azure Blob Storage container name for the cache")
    cache_azure_blob_prefix: str = Field(
        default='',
        description="Optional blob name prefix for all cache entries")

    # Throttle / Redis
    throttle_backend: ThrottleBackend = Field(
        default=ThrottleBackend.SQLITE,
        description=(
            "Backend to use for API request throttling. Options are 'local' "
            "for SQLite-based throttling and 'azure' for Redis-based"
            " throttling using Azure Cache for Redis. The 'azure' option"
            " requires additional configuration for Azure credentials and"
            " cache settings.")
    )
    redis_host: str = Field(
        default='localhost', description="Redis host")
    redis_port: int = Field(
        default=6379, description="Redis port")
    redis_password: str | None = Field(
        default=None, description="Redis password")

    # Logging and temporary files
    log_filename: str = Field(default='run.log', description="Log filename")
    query_log_filename: str = Field(
        default='query.log', description="Query log filename")
    max_api_retries: int = Field(
        default=3, description="Maximum API retries")
    errors_dir: str = Field(default='errors', description="Errors directory")
    temp_root: str | None = Field(
        default=None, description="Temporary directory root dir")
    temp_dir_name: str = Field(
        default='biosecurity', description="Temporary directory name")
    temp_clean_after_days: int = Field(
        default=7, description="Temporary files cleanup after days")

    # Nested configurations
    inputs: InputsConfig = Field(
        default_factory=InputsConfig, description="Input configuration")
    criteria: CriteriaConfig = Field(
        default_factory=CriteriaConfig, description="Analysis criteria")
    report: ReportConfig = Field(
        default_factory=ReportConfig, description="Report configuration")

    @field_validator('gbif_accepted_status', mode='before')
    @classmethod
    def parse_gbif_status(cls, v):
        """Parse GBIF status from string or list."""
        if isinstance(v, str):
            return v.upper().replace(' ', '').split(',')
        return [status.upper() for status in v]

    model_config = ConfigDict(
        env_prefix="BIOSEC_",
        env_nested_delimiter="__",
    )
