process EVALUATE_SOURCE_DIVERSITY {

    label 'daff_tax_assign'

    tag "$query_folder"

    // Bind output and temp locations needed by p4_source_diversity.py.
    containerOptions {
        def bind_app_data = System.getProperty('taxodactyl.bind_app_data', '')
        "--bind ${file(params.outdir)}${bind_app_data} --bind ${file(params.temp_root_dir)}"
    }

    input:
    tuple val(query_folder), path(query_folder_path, stageAs: 'sources_input/*') // Query folder name and path
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Metadata file

    output:
    // Flag indicating independent-source criteria status.
    tuple val(query_folder),
        path("$query_folder/4.flag"), emit: independent_sources_flag // Output: independent sources flag
    // Aggregated source-diversity summary JSON.
    tuple val(query_folder),
        path("$query_folder/${task.ext.independent_sources_json}"), emit: independent_sources_json // Output: independent sources JSON
    // Optional error files for this query.
    tuple val(query_folder),
        path("$query_folder/errors/*"), optional: true, emit: independent_sources_errors // Output: error files
    // Process run log.
    path("output/${task.ext.log_filename}"), emit: source_diversity_log // Output: log file

    script:
    // Build optional CLI flags only when corresponding params are set.
    def min_source_count_arg = params.min_source_count ? "--min-source-count ${params.min_source_count}" : ''
    def temp_root_dir_arg = params.temp_root_dir ? "--temp-root ${params.temp_root_dir}" : ''
    def temp_dir_name_arg = params.temp_dir_name ? "--temp-dir-name ${params.temp_dir_name}" : ''
    """
    # Ensure the per-query output folder exists.
    mkdir -p $query_folder

    # Move staged inputs into the query folder to keep upstream outputs intact.
    for item in sources_input/*; do
        [ -e "\$item" ] || continue
        mv "\$item" "$query_folder/"
    done
    rm -r sources_input

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