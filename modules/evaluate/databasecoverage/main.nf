process EVALUATE_DATABASE_COVERAGE {

    label 'daff_tax_assign'

    tag "$query_folder"

    containerOptions "--bind ${file(params.taxdb)} --bind ${file(params.allowed_loci_file).parent}"

    input:
    path(env_var_file) // Environment variables file
    tuple val(query_folder), path(candidate_json_file) // Query folder name and candidate JSON file
    path(metadata) // Metadata file

    output:
    tuple val(query_folder),
        path("$query_folder"), emit: db_coverage_for_alternative_report // Output: query folder with results

    script:
    def bold_flag = params.db_type == 'bold' ? '--bold' : '' // Set --bold flag if using BOLD database
    def db_coverage_toi_limit_arg = params.db_coverage_toi_limit ? "--db-coverage-toi-limit ${params.db_coverage_toi_limit}" : ''
    def db_coverage_max_candidates_arg = params.db_coverage_max_candidates ? "--db-coverage-max-candidates ${params.db_coverage_max_candidates}" : ''
    def gbif_limit_records_arg = params.gbif_limit_records ? "--gbif-limit-records ${params.gbif_limit_records}" : ''
    def gbif_max_occurrence_records_arg = params.gbif_max_occurrence_records ? "--gbif-max-occurrence-records ${params.gbif_max_occurrence_records}" : ''
    def gbif_accepted_status_arg = params.gbif_accepted_status ? "--gbif-accepted-status ${params.gbif_accepted_status}" : ''
    def db_cov_target_min_a_arg = params.db_cov_min_a ? "--db-cov-target-min-a ${params.db_cov_min_a}" : ''
    def db_cov_target_min_b_arg = params.db_cov_min_b ? "--db-cov-target-min-b ${params.db_cov_min_b}" : ''
    def db_cov_related_min_a_arg = params.db_cov_related_min_a ? "--db-cov-related-min-a ${params.db_cov_related_min_a}" : ''
    def db_cov_related_min_b_arg = params.db_cov_related_min_b ? "--db-cov-related-min-b ${params.db_cov_related_min_b}" : ''
    def db_cov_country_missing_a_arg = params.db_cov_country_missing_a ? "--db-cov-country-missing-a ${params.db_cov_country_missing_a}" : ''
    """
    # Source environment variables
    source ${env_var_file}
    # Ensure the query folder exists
    mkdir -p $query_folder
    # Move candidate JSON file into the query folder
    mv $candidate_json_file $query_folder
    # Run the database coverage Python script
    python /app/scripts/p5_db_coverage.py \
        $query_folder \
        --output-dir ./ \
        ${bold_flag} \
        ${db_coverage_toi_limit_arg} \
        ${db_coverage_max_candidates_arg} \
        ${gbif_limit_records_arg} \
        ${gbif_max_occurrence_records_arg} \
        ${gbif_accepted_status_arg} \
        ${db_cov_target_min_a_arg} \
        ${db_cov_target_min_b_arg} \
        ${db_cov_related_min_a_arg} \
        ${db_cov_related_min_b_arg} \
        ${db_cov_country_missing_a_arg}
    """
}