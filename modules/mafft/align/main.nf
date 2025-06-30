process MAFFT_ALIGN {
    tag "$query_folder"

    input:
    tuple val(query_folder), path(candidate_fasta_file), val(query_sequence) // Input: query folder, candidate FASTA, and query sequence

    output:
    tuple val(query_folder), path("$query_folder/$params.candidates_msa_filename"), emit: aligned_sequences // Output: aligned sequences in PHYLIP format
    path "versions.yml"                 , emit: versions // Output: MAFFT version info

    publishDir "${params.outdir}", mode: 'copy',
        pattern:    "$query_folder/$params.candidates_msa_filename" // Publish alignment to output directory

    when:
    task.ext.when == null || task.ext.when

    script:
    def args         = task.ext.args   ?: ''
    """
    # Create the query folder if it doesn't exist
    mkdir -p $query_folder
    # Move candidate FASTA file into the query folder
    mv $candidate_fasta_file $query_folder/
    # Write the query sequence to a temporary FASTA file
    echo ">QUERY" > $query_folder/temp.fasta
    echo $query_sequence >> $query_folder/temp.fasta
    # Append candidate sequences to the temporary FASTA file
    cat $query_folder/$candidate_fasta_file >> $query_folder/temp.fasta
    # Run MAFFT to perform multiple sequence alignment and output in PHYLIP format
    mafft \\
        --thread ${task.cpus} \\
        --phylipout \\
        $query_folder/temp.fasta \\
        > $query_folder/$params.candidates_msa_filename

    # Record the MAFFT version used for reproducibility
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        mafft: \$(mafft --version 2>&1 | sed 's/^v//' | sed 's/ (.*)//')
    END_VERSIONS
    """
}