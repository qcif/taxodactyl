process PREPARE_LOG {
    input:
    path combined_file

    output:
    path combined_file

    publishDir "${params.outdir}", mode: 'copy'

    script:
    """
    """ 
}

