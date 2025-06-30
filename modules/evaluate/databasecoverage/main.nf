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
        --output_dir ./ \
        ${bold_flag} 
    """
}