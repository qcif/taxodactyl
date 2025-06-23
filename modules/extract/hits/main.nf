process EXTRACT_HITS {

    label 'daff_tax_assign'

    containerOptions "--bind ${file(params.sequences).parent}"

    debug true

    input:
    path(env_var_file)
    path(blast_xml)

    output:
    path(params.accessions_filename), emit: accessions
    tuple path("query_*/$params.hits_json_filename"), path("query_*/$params.hits_fasta_filename"), emit: hits
    path("run.log"), emit: extract_hits_log

    publishDir "${params.outdir}", mode: 'copy', 
        pattern:    "query_*/$params.hits_fasta_filename"
    
    script:
    """
    source ${env_var_file}
    python /app/scripts/p1_parse_blast.py ${blast_xml} --output_dir ./
    """
}
