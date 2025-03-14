process MAFFT_ALIGN {
    tag "$query_folder"

    input:
    tuple val(query_folder), path(candididate_fasta_file)

    output:
    tuple val(query_folder), path("$query_folder/candidates.msa"), emit: aligned_sequences
    path "versions.yml"                 , emit: versions

    
    publishDir "${params.outdir}", mode: 'copy',
        pattern:    "$query_folder/candidates.msa"

    when:
    task.ext.when == null || task.ext.when

    script:
    def args         = task.ext.args   ?: ''
    """
    mkdir -p $query_folder
    mv $candididate_fasta_file $query_folder/
    mafft \\
        --thread ${task.cpus} \\
        --phylipout \\
        $query_folder/$params.candidates_fasta_filename \\
        > $query_folder/candidates.msa

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        mafft: \$(mafft --version 2>&1 | sed 's/^v//' | sed 's/ (.*)//')
        pigz: \$(echo \$(pigz --version 2>&1) | sed 's/^.*pigz\\w*//' ))
    END_VERSIONS
    """
}
