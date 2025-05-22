process BOLD_SEARCH {

    label 'daff_tax_assign'

    input:
    path(env_var_file)
    path(fasta)
    val ready

    output:
    path(params.bold_taxonomy_json), emit: taxonomy
    tuple path("query_*/$params.hits_json_filename"), path("query_*/$params.hits_fasta_filename"), emit: hits

    publishDir "${params.outdir}", mode: 'copy', 
        pattern:    "query_*/$params.hits_fasta_filename"
    

    script:
    """
    echo $fasta
    source ${env_var_file}
    python /app/scripts/p1_bold_search.py \
        --output_dir ./ \
        ${fasta} 
    """
}

