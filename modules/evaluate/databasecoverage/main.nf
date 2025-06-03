process EVALUATE_DATABASE_COVERAGE {

    label 'daff_tax_assign'

    tag "$query_folder"

    containerOptions "--bind ${file(params.taxdb)} --bind ${file(params.allowed_loci_file).parent}"
    
    input:
    path(env_var_file)
    tuple val(query_folder), path(candidate_json_file)
    path(metadata)

    output:
    tuple val(query_folder), 
        path("$query_folder"), emit: db_coverage_for_alternative_report
    
    script:
    def bold_flag = params.db_type == 'bold' ? '--bold' : ''
    """
    source ${env_var_file}
    mkdir -p $query_folder
    mv $candidate_json_file $query_folder
    python /app/scripts/p5_db_coverage.py \
    $query_folder \
    --output_dir ./ \
    ${bold_flag} 
    """
}
