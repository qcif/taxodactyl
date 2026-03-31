process EVALUATE_DATABASE_COVERAGE {

    label 'daff_tax_assign'

    tag "$query_folder"

    containerOptions "--bind ${file(params.taxdb)} --bind ${file(params.allowed_loci_file).parent} --bind ${file(params.outdir)} --bind ${file(params.temp_root_dir)} --writable-tmpfs"

    input:
    path(env_var_file) // Environment variables file
    tuple val(query_folder), path(query_folder_path, stageAs: 'db_coverage_input/*') // Query folder name and path
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Metadata file

    output:
    tuple val(query_folder), path("$query_folder/*"), 
        emit: db_coverage_files // Output: query folder with results (that should include all relevant files and folders with errors)
    tuple val(query_folder),
        path("$query_folder/db_coverage.json"), emit: db_coverage_json // Output: db_coverage.json file
    tuple val(query_folder),
        path("$query_folder/*flag"), emit: db_coverage_flags // Output: flag files
    tuple val(query_folder),
        path("$query_folder/map*png"), emit: db_coverage_maps, optional: true // Output: coverage map PNG files
    path("output/run.log"), emit: db_coverage_log // Output: log file
    // path("$query_folder/errors"), optional: true
    
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
    def temp_root_dir_arg = params.temp_root_dir ? "--temp-root ${params.temp_root_dir}" : ''
    def temp_dir_name_arg = params.temp_dir_name ? "--temp-dir-name ${params.temp_dir_name}" : ''
    """
    # Source environment variables
    source ${env_var_file}
    # Ensure the query folder exists
    mkdir -p $query_folder
    # Move staged inputs into the query folder to keep upstream outputs intact.
    echo "FILES COVERAGE INPUT:"
    ls db_coverage_input/
    for item in db_coverage_input/*; do
        [ -e "\$item" ] || continue
        mv "\$item" "$query_folder/"
    done
    echo "FILES COVERAGE QUERY FOLDER:"
    ls "$query_folder"
    # Run the database coverage Python script
    python /app/scripts/p5_db_coverage.py \
        $query_folder \
        --output-dir ./ \
        --query-fasta ${sequences_file} \
        --metadata-csv ${metadata_file} \
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
        ${db_cov_country_missing_a_arg} \
        ${temp_root_dir_arg} \
        ${temp_dir_name_arg}
    """
}