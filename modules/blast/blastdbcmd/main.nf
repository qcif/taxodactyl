process BLAST_BLASTDBCMD {

    label 'blast'

    containerOptions "--bind ${file(params.blastdb).parent}"

    input:
    path(entry_batch) // Input file: list of accession numbers to query

    output:
    path "taxids.csv", emit: taxids      // Output: CSV mapping accession to taxid
    path "versions.yml", emit: versions  // Output: BLAST version info

    when:
    task.ext.when == null || task.ext.when 

    script:
    """
    # Run blastdbcmd to extract accession and taxid pairs for each entry in the batch
    blastdbcmd \\
        -entry_batch ${entry_batch} \\
        -db ${file(params.blastdb)} \\
        -outfmt "%a,%T" > taxids.csv

    # Record the BLAST version used 
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        blast: \$(blastdbcmd -version 2>&1 | head -n1 | sed 's/^.*blastdbcmd: //; s/ .*\$//')
    END_VERSIONS
    """
}