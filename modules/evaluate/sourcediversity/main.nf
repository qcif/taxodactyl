process EVALUATE_SOURCE_DIVERSITY {

    label 'daff_tax_assign'

    tag "$query_folder"

    input:
    path(env_var_file) // Environment variables file
    tuple val(query_folder), path(candididate_json_file) // Query folder name and candidate JSON file
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Metadata file

    output:
    tuple val(query_folder), path("$query_folder/$params.independent_sources_json_filename"), emit: independent_sources // Output: independent sources JSON

    script:
    def min_source_count_arg = params.min_source_count ? "--min-source-count ${params.min_source_count}" : ''
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
    ${min_source_count_arg}
    """
}