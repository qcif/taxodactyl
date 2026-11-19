process PREPARE_INPUTS {
    // Renders as the staged name (input_metadata.csv). The user filename is
    // deliberately not used: NF-WF-005 parses the tag out of "(...)" in the
    // task name, so parentheses or spaces in it would garble the error-log path.
    tag "$metadata_file"

    input:
    // User inputs are staged under fixed names so the user-supplied
    // filename (which may contain spaces or shell metacharacters) never
    // reaches the task script (NF-PR-012, #358).
    path sequences_file, stageAs: 'input_sequences.fasta'
    path metadata_file, stageAs: 'input_metadata.csv'

    output:
    path "sequences.fasta", emit: sequences, optional: true
    path "metadata.csv", emit: metadata

    script:
    """
    # Copy input files to work directory to ensure they remain available
    # throughout the workflow execution.
    # If no sequences file is provided, do not emit sequences.fasta.

    if [ -e input_sequences.fasta ]; then
        cp input_sequences.fasta sequences.fasta
    fi

    if [ ! -e input_metadata.csv ]; then
        echo "ERROR: Metadata file not found" >&2
        exit 1
    fi
    cp input_metadata.csv metadata.csv

    echo "Successfully prepared input files in work directory"
    if [ -f sequences.fasta ]; then
        echo "Sequences file: \$(wc -l < sequences.fasta) lines"
    else
        echo "Sequences file: not provided"
    fi
    echo "Metadata file: \$(wc -l < metadata.csv) lines"
    """
}
