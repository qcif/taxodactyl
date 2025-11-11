process MAFFT_ALIGN {
    tag "$query_folder"

    input:
    tuple val(query_folder), path(candidate_fasta_file), val(query_sequence) // Input: query folder, candidate FASTA, and query sequence

    output:
    tuple val(query_folder), path("$query_folder/$params.candidates_msa_filename"), path("$query_folder/id_mapping.tsv"), emit: aligned_sequences // Output: aligned sequences in PHYLIP format and id mapping file
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

    # Workaround for https://github.com/qcif/taxodactyl/issues/24
    # Strip everything after the first space in header lines
    sed '/^>/s/ .*//' $candidate_fasta_file > stripped_${candidate_fasta_file}

    # Create an ID mapping file for candidate sequences
    awk '/^>/ {
        id = substr(\$0, 2);  # remove leading ">"
        printf "HIT%d\\t%s\\n", ++count, id
    }' stripped_${candidate_fasta_file} > id_mapping.tsv
    mv id_mapping.tsv $query_folder/id_mapping.tsv

    # Rename candidate sequence headers to HIT1, HIT2, etc.
    awk '/^>/ {
        print ">HIT" ++count
        next
    }
    { print }' stripped_${candidate_fasta_file} > renamed_${candidate_fasta_file}

    # Move candidate FASTA file into the query folder
    mv $candidate_fasta_file $query_folder/
    mv renamed_${candidate_fasta_file} $query_folder/

    # Write the query sequence to a temporary FASTA file
    echo ">QUERY" > $query_folder/temp.fasta
    echo $query_sequence >> $query_folder/temp.fasta

    # Append candidate sequences to the temporary FASTA file
    cat $query_folder/renamed_${candidate_fasta_file} >> $query_folder/temp.fasta
    # Run MAFFT to perform multiple sequence alignment and output in PHYLIP format
    mafft \\
        --thread ${task.cpus} \\
        --phylipout \\
        $query_folder/temp.fasta \\
        > $query_folder/temp.msa

    # Workaround for https://github.com/qcif/taxodactyl/issues/24
    # Replace HIT IDs with original sequence IDs in the alignment,
    # padding the original ID to 11 chars (or adding one space if longer)
    awk -F'\t' '{
        rep = \$2;
        gsub("/", "\\/", rep);                     # escape any slashes in replacement
        n = 11 - length(rep);
        if (n > 0) rep = rep sprintf("%*s", n, "");# pad to 11 characters
        else rep = rep " ";                        # otherwise add single trailing space
        printf "s/\\\\<%s\\\\>[[:space:]]*/%s/g\\n", \$1, rep
    }' $query_folder/id_mapping.tsv | sed -f - $query_folder/temp.msa > $query_folder/$params.candidates_msa_filename

    # Record the MAFFT version used for reproducibility
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        mafft: \$(mafft --version 2>&1 | sed 's/^v//' | sed 's/ (.*)//')
    END_VERSIONS
    """
}