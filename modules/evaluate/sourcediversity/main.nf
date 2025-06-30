process EVALUATE_SOURCE_DIVERSITY {

    label 'daff_tax_assign'

    tag "$query_folder"
    
    input:
    path(env_var_file) // Environment variables file
    tuple val(query_folder), path(candididate_json_file) // Query folder name and candidate JSON file

    output:
    tuple val(query_folder), path("$query_folder/$params.independent_sources_json_filename"), emit: independent_sources // Output: independent sources JSON

    script:
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
    --output_dir ./
    """
}