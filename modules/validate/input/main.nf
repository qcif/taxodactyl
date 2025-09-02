process VALIDATE_INPUT {

    label 'daff_tax_assign'

    containerOptions "--bind ${file(params.taxdb)} --bind ${file(params.allowed_loci_file).parent}"

    input:
    path(env_var_file) // Environment variables file
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Copied metadata file

    output:
    val true // Output: validation success flag

    script:
    def bold_flag = params.db_type == 'bold' ? '--bold' : ''
    def allowed_loci_arg = params.allowed_loci_file ? "--allowed-loci-file ${file(params.allowed_loci_file)}" : ''
    def fasta_max_sequences_arg = params.fasta_max_sequences ? "--fasta-max-sequences ${params.fasta_max_sequences}" : ''
    def fasta_min_length_arg = params.fasta_min_length ? "--fasta-min-length ${params.fasta_min_length}" : ''
    def fasta_max_length_arg = params.fasta_max_length ? "--fasta-max-length ${params.fasta_max_length}" : ''
    """
    # Source environment variables
    source ${env_var_file}
    # Run the input validation Python script
    python /app/scripts/p0_validation.py \
    --taxdb-dir ${file(params.taxdb)} \
    --query-fasta ${sequences_file} \
    --metadata-csv ${metadata_file} \
    ${bold_flag} \
    ${allowed_loci_arg} \
    ${fasta_max_sequences_arg} \
    ${fasta_min_length_arg} \
    ${fasta_max_length_arg}
    """
}
