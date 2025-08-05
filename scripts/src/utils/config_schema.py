"""Pydantic schema for configuration validation."""

from pathlib import Path
from typing import List

from pydantic import BaseModel, Field, field_validator


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
        },
        description="CSV header mapping"
    )
    metadata_csv_required_fields: tuple = Field(
        default=("sample_id", "locus", "preliminary_id"),
        description="Required CSV fields"
    )

    # FASTA validation limits
    fasta_max_length_nt: int = Field(
        default=3000, description="Maximum sequence length")
    fasta_min_length_nt: int = Field(
        default=20, description="Minimum sequence length")
    fasta_max_sequences: int = Field(
        default=150, description="Maximum number of sequences")

    # File paths (set by CLI/config)
    fasta_filepath: Path = Field(
        default=None, description="Input FASTA file path")
    metadata_path: Path = Field(
        default=None, description="Input metadata CSV path")


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
        default=0.95, description="Phylogeny minimum hit identity")
    phylogeny_min_hit_sequences: int = Field(
        default=20, description="Phylogeny minimum hit sequences")
    phylogeny_max_hits_per_species: int = Field(
        default=30, description="Phylogeny maximum hits per species")


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
    allowed_loci_file: Path = Field(
        default_factory=lambda: (
            Path(__file__).parents[3] / 'scripts/config/loci.json'),
        description="Path to allowed loci JSON file"
    )
    flag_details_csv_path: Path = Field(
        default_factory=lambda: (
            Path(__file__).parents[3] / 'scripts/config/flags.csv'),
        description="Path to flag details CSV file"
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

    # Logging and temporary files
    log_filename: str = Field(default='run.log', description="Log filename")
    query_log_filename: str = Field(
        default='query.log', description="Query log filename")
    entrez_cache_dirname: str = Field(
        default='entrez_cache', description="Entrez cache directory name")
    throttle_sqlite_file: str = Field(
        default='throttle.sqlite', description="Throttle SQLite filename")
    max_api_retries: int = Field(
        default=3, description="Maximum API retries")
    errors_dir: str = Field(default='errors', description="Errors directory")
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

    @field_validator(
        'allowed_loci_file', 'flag_details_csv_path', mode='before')
    @classmethod
    def validate_paths(cls, v):
        """Convert string paths to Path objects."""
        if isinstance(v, str):
            return Path(v)
        return v

    class Config:
        """Pydantic configuration."""
        # Allow environment variable overrides with BIOSEC_ prefix
        env_prefix = 'BIOSEC_'
        env_nested_delimiter = '__'
