process FASTME {
    tag "$query_folder"

    input:
    tuple val(query_folder), path(infile) // Input: query folder name and PHYLIP alignment file

    output:
    tuple val(query_folder), path("*.nwk")       , emit: nwk    // Output: Newick tree file
    tuple val(query_folder), path("*_stat.txt")  , emit: stats  // Output: statistics file
    tuple val(query_folder), path("*.matrix.phy"), emit: matrix // Output: distance matrix file
    path "versions.yml" , emit: versions                         // Output: FastME version info

    publishDir "${params.outdir}/$query_folder", mode: 'copy', pattern: "$params.tree_nwk_filename" // Publish Newick tree to output directory

    script:
    """
    # Run FastME to construct a phylogenetic tree from the PHYLIP alignment
    fastme \\
        -i $infile \\
        -d \\
        -O ${infile}.matrix.phy \\
        -o $params.tree_nwk_filename \\
        -T $task.cpus

    # Record the FastME version used for reproducibility
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        fastme: \$(fastme --version |& sed '1!d ; s/FastME //')
    END_VERSIONS
    """
}