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
    cp "${sequences_file}" sequences.fasta
    cp "${metadata_file}" metadata.csv
    
    # Verify the files were copied successfully
    if [ ! -f sequences.fasta ]; then
        echo "ERROR: Failed to copy sequences file" >&2
        exit 1
    fi
    
    if [ ! -f metadata.csv ]; then
        echo "ERROR: Failed to copy metadata file" >&2
        exit 1
    fi
    
    echo "Successfully copied input files to work directory"
    echo "Sequences file: \$(wc -l < sequences.fasta) lines"
    echo "Metadata file: \$(wc -l < metadata.csv) lines"
    """
}