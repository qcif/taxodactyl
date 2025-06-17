process REPORT {

    label 'daff_tax_assign'

    tag "$query_folder"

    containerOptions "--bind ${file(params.sequences).parent}  --bind ${file(params.allowed_loci_file).parent}"
    
    input:
    path(env_var_file)
    tuple val(query_folder),  
        path(hits_query_folder, stageAs: 'hits_query_folder'),
        path(nwk_file, stageAs: 'tree.nwk'),
        path(candidates_query_folder, stageAs: 'candidates_query_folder'),
        path(db_coverage_query_folder, stageAs: 'db_coverage_query_folder'),
        path(source_diversity_query_folder, stageAs: 'source_diversity_query_folder'),
        path(versions_file),
        path(params_file),
        path(timestamp_file)
    path(taxonomy_file)
    path(metadata_file)

    output:
    path("$query_folder/*.html")

    publishDir "${params.outdir}", mode: 'copy', pattern:    "$query_folder/*.html"
  
    script:
    def bold_flag = params.db_type == 'bold' ? '--bold' : ''
    """
    source ${env_var_file}
    mkdir -p ${query_folder}
    mv tree.nwk ${query_folder}/$params.tree_nwk_filename
    mv candidates_query_folder/* ${query_folder}
    rm -rf candidates_query_folder
    mv db_coverage_query_folder/* ${query_folder}
    rm -rf db_coverage_query_folder
    mv hits_query_folder/* ${query_folder}
    rm -rf hits_query_folder
    mv source_diversity_query_folder/* ${query_folder}
    rm -rf source_diversity_query_folder
    python /app/scripts/p6_report.py \
            ${query_folder} \
            --output_dir ./ \
            --versions_yml ${versions_file} \
            --params_json ${params_file} \
            ${bold_flag} 
    """
}
