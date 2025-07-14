process CONFIGURE_ENVIRONMENT {
    output:
    file 'env_vars.sh' // Output: environment variables file for downstream modules

    script:
    """
    # Set matplotlib config directory to avoid warnings
    echo 'export MPLCONFIGDIR=.matplotlib' > env_vars.sh

    # Export pipeline parameters as environment variables if they are set
    if [ ${params.accessions_filename} != null ]; then echo 'export ACCESSIONS_FILENAME=${params.accessions_filename}' >> env_vars.sh; fi
    if [ ${params.allowed_loci_file} != null ]; then echo 'export ALLOWED_LOCI_FILE=${file(params.allowed_loci_file)}' >> env_vars.sh; fi
    if [ "${params.analyst_name}" != null ]; then echo 'export ANALYST_NAME="${params.analyst_name}"' >> env_vars.sh; fi
    if [ "${params.blast_database_name_for_report}" != null ]; then echo 'export BLAST_DATABASE_NAME="${params.blast_database_name_for_report}"' >> env_vars.sh; fi
    if [ ${params.blast_max_target_seqs_for_report} != null ]; then echo 'export BLAST_MAX_TARGET_SEQS=${params.blast_max_target_seqs_for_report}' >> env_vars.sh; fi
    if [ ${params.bold_skip_orientation} != null ]; then echo 'export BOLD_SKIP_ORIENTATION=${params.bold_skip_orientation}' >> env_vars.sh; fi
    if [ ${params.bold_taxonomy_json} != null ]; then echo 'export BOLD_TAXONOMY_JSON=${params.bold_taxonomy_json}' >> env_vars.sh; fi
    if [ ${params.boxplot_img_filename} != null ]; then echo 'export BOXPLOT_IMG_FILENAME=${params.boxplot_img_filename}' >> env_vars.sh; fi
    if [ ${params.candidates_csv_filename} != null ]; then echo 'export CANDIDATES_CSV_FILENAME=${params.candidates_csv_filename}' >> env_vars.sh; fi
    if [ ${params.candidates_fasta_filename} != null ]; then echo 'export CANDIDATES_FASTA_FILENAME=${params.candidates_fasta_filename}' >> env_vars.sh; fi
    if [ ${params.candidates_phylogeny_fasta_filename} != null ]; then echo 'export PHYLOGENY_FASTA_FILENAME=${params.candidates_phylogeny_fasta_filename}' >> env_vars.sh; fi
    if [ ${params.candidates_json_filename} != null ]; then echo 'export CANDIDATES_JSON_FILENAME=${params.candidates_json_filename}' >> env_vars.sh; fi
    if [ ${params.candidates_sources_json_filename} != null ]; then echo 'export CANDIDATES_SOURCES_JSON_FILENAME=${params.candidates_sources_json_filename}' >> env_vars.sh; fi
    if [ ${params.db_coverage_toi_limit} != null ]; then echo 'export DB_COVERAGE_TOI_LIMIT=${params.db_coverage_toi_limit}' >> env_vars.sh; fi
    if [ ${params.db_cov_country_missing_a} != null ]; then echo 'export DB_COV_COUNTRY_MISSING_A=${params.db_cov_country_missing_a}' >> env_vars.sh; fi
    if [ ${params.db_cov_min_a} != null ]; then echo 'export DB_COV_MIN_A=${params.db_cov_min_a}' >> env_vars.sh; fi
    if [ ${params.db_cov_min_b} != null ]; then echo 'export DB_COV_MIN_B=${params.db_cov_min_b}' >> env_vars.sh; fi
    if [ ${params.db_cov_related_min_a} != null ]; then echo 'export DB_COV_RELATED_MIN_A=${params.db_cov_related_min_a}' >> env_vars.sh; fi
    if [ ${params.db_cov_related_min_b} != null ]; then echo 'export DB_COV_RELATED_MIN_B=${params.db_cov_related_min_b}' >> env_vars.sh; fi
    if [ "${params.facility_name}" != null ]; then echo 'export FACILITY_NAME="${params.facility_name}"' >> env_vars.sh; fi
    if [ ${params.gbif_accepted_status} != null ]; then echo 'export GBIF_ACCEPTED_STATUS=${params.gbif_accepted_status}' >> env_vars.sh; fi
    if [ ${params.gbif_limit_records} != null ]; then echo 'export GBIF_LIMIT_RECORDS=${params.gbif_limit_records}' >> env_vars.sh; fi
    if [ ${params.gbif_max_occurrence_records} != null ]; then echo 'export GBIF_MAX_OCCURRENCE_RECORDS=${params.gbif_max_occurrence_records}' >> env_vars.sh; fi
    if [ ${params.hits_fasta_filename} != null ]; then echo 'export HITS_FASTA_FILENAME=${params.hits_fasta_filename}' >> env_vars.sh; fi
    if [ ${params.hits_json_filename} != null ]; then echo 'export HITS_JSON_FILENAME=${params.hits_json_filename}' >> env_vars.sh; fi
    if [ ${params.independent_sources_json_filename} != null ]; then echo 'export INDEPENDENT_SOURCES_JSON_FILENAME=${params.independent_sources_json_filename}' >> env_vars.sh; fi
    if [ ${params.sequences} != null ]; then echo 'export INPUT_FASTA_FILEPATH=${file(params.sequences)}' >> env_vars.sh; fi
    if [ ${params.metadata} != null ]; then echo 'export INPUT_METADATA_CSV_FILEPATH=${file(params.metadata)}' >> env_vars.sh; fi
    if [ ${params.logging_debug} != null ]; then echo 'export LOGGING_DEBUG=${params.logging_debug}' >> env_vars.sh; fi
    if [ ${params.max_candidates_for_analysis} != null ]; then echo 'export MAX_CANDIDATES_FOR_ANALYSIS=${params.max_candidates_for_analysis}' >> env_vars.sh; fi
    if [ ${params.median_identity_warning_factor} != null ]; then echo 'export MEDIAN_IDENTITY_WARNING_FACTOR=${params.median_identity_warning_factor}' >> env_vars.sh; fi
    if [ ${params.min_identity} != null ]; then echo 'export MIN_IDENTITY=${params.min_identity}' >> env_vars.sh; fi
    if [ ${params.min_identity_strict} != null ]; then echo 'export MIN_IDENTITY_STRICT=${params.min_identity_strict}' >> env_vars.sh; fi
    if [ ${params.min_nt} != null ]; then echo 'export MIN_NT=${params.min_nt}' >> env_vars.sh; fi
    if [ ${params.min_q_coverage} != null ]; then echo 'export MIN_Q_COVERAGE=${params.min_q_coverage}' >> env_vars.sh; fi
    if [ ${params.min_source_count} != null ]; then echo 'export MIN_SOURCE_COUNT=${params.min_source_count}' >> env_vars.sh; fi
    if [ ${params.ncbi_api_key} != null ]; then echo 'export NCBI_API_KEY=${params.ncbi_api_key}' >> env_vars.sh; fi
    if [ ${params.outdir} != null ]; then echo 'export OUTPUT_DIR=${params.outdir}' >> env_vars.sh; fi
    if [ ${params.phylogeny_min_hit_identity} != null ]; then echo 'export PHYLOGENY_MIN_HIT_IDENTITY=${params.phylogeny_min_hit_identity}' >> env_vars.sh; fi
    if [ ${params.phylogeny_min_hit_sequences} != null ]; then echo 'export PHYLOGENY_MIN_HIT_SEQUENCES=${params.phylogeny_min_hit_sequences}' >> env_vars.sh; fi
    if [ ${params.phylogeny_max_hits_per_species} != null ]; then echo 'export PHYLOGENY_MAX_HITS_PER_SPECIES=${params.phylogeny_max_hits_per_species}' >> env_vars.sh; fi
    if [ ${params.report_debug} != null ]; then echo 'export REPORT_DEBUG=${params.report_debug}' >> env_vars.sh; fi
    if [ ${params.taxdb} != null ]; then echo 'export TAXONKIT_DATA=${file(params.taxdb)}' >> env_vars.sh; fi
    if [ ${params.taxonomy_filename} != null ]; then echo 'export TAXONOMY_FILENAME=${params.taxonomy_filename}' >> env_vars.sh; fi
    if [ ${params.tree_nwk_filename} != null ]; then echo 'export TREE_NWK_FILENAME=${params.tree_nwk_filename}' >> env_vars.sh; fi
    if [ ${params.ncbi_user_email} != null ]; then echo 'export USER_EMAIL=${params.ncbi_user_email}' >> env_vars.sh; fi
   """
}