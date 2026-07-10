process PREPARE_INPUTS {
    tag "$metadata_file"
    
    input:
    path sequences_file
    path metadata_file

    output:
    path "sequences.fasta", emit: sequences, optional: true
    path "metadata.csv", emit: metadata
    
    script:
    def sequences_source = sequences_file ? sequences_file[0] : null
    """
    # Copy input files to work directory to ensure they remain available
    # throughout the workflow execution.
    # If no sequences file is provided, do not emit sequences.fasta.
    
    if [ -n "${sequences_source ?: ''}" ] && [ "${sequences_source ?: ''}" != "sequences.fasta" ]; then
        cp "${sequences_source}" sequences.fasta
    fi
    
    if [ "${metadata_file}" != "metadata.csv" ]; then
        cp "${metadata_file}" metadata.csv
    else
        # File already has correct name, just ensure it exists
        if [ ! -f metadata.csv ]; then
            echo "ERROR: Metadata file not found" >&2
            exit 1
        fi
    fi
    
    echo "Successfully prepared input files in work directory"
    if [ -f sequences.fasta ]; then
        echo "Sequences file: \$(wc -l < sequences.fasta) lines"
    else
        echo "Sequences file: not provided"
    fi
    echo "Metadata file: \$(wc -l < metadata.csv) lines"
    """
}