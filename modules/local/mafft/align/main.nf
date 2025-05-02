process MAFFT_ALIGN {
    tag "$query_folder"

    input:
    tuple val(query_folder), path(candidate_fasta_file), val(query_sequence)

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
    mv $candidate_fasta_file $query_folder/
    echo ">QUERY" > $query_folder/temp.fasta
    echo $query_sequence >> $query_folder/temp.fasta
    cat $query_folder/$candidate_fasta_file >> $query_folder/temp.fasta
    mafft \\
        --thread ${task.cpus} \\
        --phylipout \\
        $query_folder/temp.fasta \\
        > $query_folder/candidates.msa

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        mafft: \$(mafft --version 2>&1 | sed 's/^v//' | sed 's/ (.*)//')
        pigz: \$(echo \$(pigz --version 2>&1) | sed 's/^.*pigz\\w*//' ))
    END_VERSIONS
    """
}
