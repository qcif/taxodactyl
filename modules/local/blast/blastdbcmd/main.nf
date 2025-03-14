process BLAST_BLASTDBCMD {
    containerOptions "--bind ${file(params.blastdb).parent}"

    input:
    path(entry_batch)

    output:
    path "taxids.csv", emit: taxids
    path "versions.yml", emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    blastdbcmd \\
        -entry_batch ${entry_batch} \\
        -db ${file(params.blastdb)} \\
        -outfmt "%a,%T" > taxids.csv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        blast: \$(blastdbcmd -version 2>&1 | head -n1 | sed 's/^.*blastdbcmd: //; s/ .*\$//')
    END_VERSIONS
    """
}
