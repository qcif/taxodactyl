process FASTME {
    tag "$query_folder"

    input:
    tuple val(query_folder), path(infile), path(id_mapping_file) // Input: query folder name and PHYLIP alignment file and ID mapping file

    output:
    tuple val(query_folder), path("${task.ext.tree_nwk}")       , emit: nwk    // Output: Newick tree file
    tuple val(query_folder), path("*_stat.txt")  , emit: stats  // Output: statistics file
    tuple val(query_folder), path("*.matrix.phy"), emit: matrix // Output: distance matrix file
    path "${task.ext.versions_yml}" , emit: versions                         // Output: FastME version info

    publishDir "${params.outdir}/$query_folder", mode: 'copy', pattern: "${task.ext.tree_nwk}" // Publish Newick tree to output directory

    script:
    """
    # Run FastME to construct a phylogenetic tree from the PHYLIP alignment
    fastme \\
        -i $infile \\
        -d \\
        -O ${infile}.matrix.phy \\
        -o temp.nwk \\
        -T $task.cpus

    # Workaround for https://github.com/qcif/taxodactyl/issues/24
    # Rename the tree tips using the provided ID mapping file
    # sed with word boundaries to avoid partial matches
    awk -F'\t' '{ printf "s/\\\\<%s\\\\>/%s/g\\n", \$1, \$2 }' "$id_mapping_file" | sed -f - temp.nwk > ${task.ext.tree_nwk}

    # Record the FastME version used for reproducibility
    cat <<-END_VERSIONS > ${task.ext.versions_yml}
    "${task.process}":
        fastme: \$(fastme --version |& sed '1!d ; s/FastME //')
    END_VERSIONS
    """
}