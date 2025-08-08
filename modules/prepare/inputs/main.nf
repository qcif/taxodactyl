process PREPARE_INPUTS {
    tag "$metadata_file"
    
    input:
    path sequences_file
    path metadata_file
    
    output:
    path "sequences.fasta", emit: sequences
    path "metadata.csv", emit: metadata
    
    script:
    """
    # Copy input files to work directory to ensure they remain available
    # throughout the workflow execution
    # Use different temporary names first to avoid same-file copy errors
    
    if [ "${sequences_file}" != "sequences.fasta" ]; then
        cp "${sequences_file}" sequences.fasta
    else
        # File already has correct name, just ensure it exists
        if [ ! -f sequences.fasta ]; then
            echo "ERROR: Sequences file not found" >&2
            exit 1
        fi
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
    echo "Sequences file: \$(wc -l < sequences.fasta) lines"
    echo "Metadata file: \$(wc -l < metadata.csv) lines"
    """
}