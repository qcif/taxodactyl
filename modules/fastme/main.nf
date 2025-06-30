process FASTME {
    tag "$query_folder"

    input:
    tuple val(query_folder), path(infile)

    output:
    tuple val(query_folder), path("*.nwk")       , emit: nwk
    tuple val(query_folder), path("*_stat.txt")  , emit: stats
    tuple val(query_folder), path("*.matrix.phy"), emit: matrix
    path "versions.yml" , emit: versions

    publishDir "${params.outdir}/$query_folder", mode: 'copy', pattern:    "$params.tree_nwk_filename"

    script:
    """
    fastme \\
        -i $infile \\
        -d \\
        -O ${infile}.matrix.phy \\
        -o $params.tree_nwk_filename \\
        -T $task.cpus


    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        fastme: \$(fastme --version |& sed '1!d ; s/FastME //')
    END_VERSIONS
    """
}
