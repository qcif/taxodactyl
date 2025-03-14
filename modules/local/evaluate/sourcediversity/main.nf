process EVALUATE_SOURCE_DIVERSITY {
    tag "$query_folder"
    
    input:
    tuple val(query_folder), path(candididate_json_file)

    output:
    tuple val(query_folder), path("$query_folder/$params.candidates_sources_json_filename"), emit: candidates_sources

    // publishDir "${params.outdir}", mode: 'copy', pattern: "$query_folder/$params.candidates_sources_json_filename"

    
    script:
    """
    source ${workDir}/env_vars.sh
    mkdir -p $query_folder
    mv $candididate_json_file $query_folder
    python /app/scripts/p4_source_diversity.py \
    $query_folder \
    --output_dir ./
    """
}
