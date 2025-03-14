process EXTRACT_HITS {
    containerOptions "--bind ${file(params.sequences).parent}"

    debug true

    input:
    path(blast_xml)

    output:
    path(params.accessions_filename), emit: accessions
    // path("query_*"), emit: hits_folders_for_alternative_report
    tuple path("query_*/$params.hits_json_filename"), path("query_*/$params.hits_fasta_filename"), emit: hits
    path("run.log"), emit: extract_hits_log

    publishDir "${params.outdir}", mode: 'copy', 
        pattern:    "query_*/$params.hits_fasta_filename"
    
    script:
    """
    source ${workDir}/env_vars.sh
    python /app/scripts/p1_parse_blast.py ${blast_xml} --output_dir ./
    """
}
