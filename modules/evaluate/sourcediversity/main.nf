process EVALUATE_SOURCE_DIVERSITY {

    label 'daff_tax_assign'

    tag "$query_folder"

    containerOptions "--bind ${file(params.outdir)} --bind ${file(params.temp_root_dir)}"

    input:
    path(env_var_file) // Environment variables file
    tuple val(query_folder), path(candididate_json_file) // Query folder name and candidate JSON file
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Metadata file

    output:
    tuple val(query_folder), path("$query_folder/$params.independent_sources_json_filename"), emit: independent_sources // Output: independent sources JSON

    script:
    def min_source_count_arg = params.min_source_count ? "--min-source-count ${params.min_source_count}" : ''
    def temp_root_dir_arg = params.temp_root_dir ? "--temp-root ${params.temp_root_dir}" : ''
    def temp_dir_name_arg = params.temp_dir_name ? "--temp-dir-name ${params.temp_dir_name}" : ''
    """
    # Source environment variables
    source ${env_var_file}
    # Ensure the query folder exists
    mkdir -p $query_folder
    # Move candidate JSON file into the query folder
    mv $candididate_json_file $query_folder
    # Run the source diversity Python script
    python /app/scripts/p4_source_diversity.py \
    $query_folder \
    --query-fasta ${sequences_file} \
    --metadata-csv ${metadata_file} \
    --output-dir ./ \
    ${min_source_count_arg} \
    ${temp_root_dir_arg} \
    ${temp_dir_name_arg}
    """
}