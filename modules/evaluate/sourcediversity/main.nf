process EVALUATE_SOURCE_DIVERSITY {

    label 'daff_tax_assign'

    tag "$query_folder"
    
    input:
    path(env_var_file)
    tuple val(query_folder), path(candididate_json_file)

    output:
    tuple val(query_folder), path("$query_folder/$params.independent_sources_json_filename"), emit: independent_sources
    
    script:
    """
    source ${env_var_file}
    mkdir -p $query_folder
    mv $candididate_json_file $query_folder
    python /app/scripts/p4_source_diversity.py \
    $query_folder \
    --output_dir ./
    """
}
