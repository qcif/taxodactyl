process PREPARE_LOG {
    publishDir "results", mode: 'copy'

    input:
    path combined_file

    output:
    path combined_file

    publishDir "${params.outdir}", mode: 'copy'

    script:
    """
    """ 
}

