process EVALUATE_SOURCE_DIVERSITY {

    label 'daff_tax_assign'

    tag "$query_folder"

    containerOptions "--bind ${file(params.outdir)} --bind ${file(params.temp_root_dir)}"

    input:
    path(env_var_file) // Environment variables file
    tuple val(query_folder), path(query_folder_path, stageAs: 'sources_input/*') // Query folder name and path
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Metadata file

    output:
    tuple val(query_folder), 
        path("$query_folder/*"), emit: independent_sources_files // Output 
    // tuple val(query_folder), 
    //     path("$query_folder/4.flag"), emit: independent_sources_flag // Output: independent sources flag
    // tuple val(query_folder), 
    //     path("$query_folder/$independent_sources_json_filename"), emit: independent_sources_json // Output: independent sources JSON
    // tuple val(query_folder), 
    //     path("$query_folder/errors/next.txt"), optional: true, emit: independent_sources_next_error // Output: independent sources errors
    // tuple val(query_folder), 
    //     path("$query_folder/errors/*.json"), optional: true, emit: independent_sources_json_errors
    path("output/run.log"), emit: source_diversity_log // Output: log file
    // path("$query_folder/1.flag")
    // path("$query_folder/2.flag")
    // path("$query_folder/7.flag")
    // path("$query_folder/$params.candidates_fasta_filename")
    // path("$query_folder/$params.candidates_csv_filename")
    // path("$query_folder/$params.candidates_json_filename")
    // path("$query_folder/$params.boxplot_img_filename"), optional: true

    script:
    def min_source_count_arg = params.min_source_count ? "--min-source-count ${params.min_source_count}" : ''
    def temp_root_dir_arg = params.temp_root_dir ? "--temp-root ${params.temp_root_dir}" : ''
    def temp_dir_name_arg = params.temp_dir_name ? "--temp-dir-name ${params.temp_dir_name}" : ''
    """
    # Source environment variables
    source ${env_var_file}
    # Ensure the query folder exists
    mkdir -p $query_folder
    # Move staged inputs into the query folder to keep upstream outputs intact.
    echo "FILES SOURCE DIVERSITY INPUT:"
    ls sources_input/
    for item in sources_input/*; do
        [ -e "\$item" ] || continue
        mv "\$item" "$query_folder/"
    done
    echo "FILES SOURCE DIVERSITY QUERY FOLDER:"
    ls "$query_folder"
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