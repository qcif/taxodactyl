process VALIDATE_INPUT {

    label 'daff_tax_assign'

    containerOptions "--bind ${file(params.metadata).parent} --bind ${file(params.taxdb)} --bind ${file(params.sequences).parent} --bind ${file(params.allowed_loci_file).parent}"

    input:
    path(env_var_file) // Environment variables file

    output:
    val true // Output: validation success flag

    script:
    def bold_flag = params.db_type == 'bold' ? '--bold' : ''
    def allowed_loci_arg = params.allowed_loci_file ? "--allowed-loci-file ${file(params.allowed_loci_file)}" : ''
    def input_fasta_arg = params.sequences ? "--input-fasta ${file(params.sequences)}" : ''
    def input_metadata_arg = params.metadata ? "--input-metadata ${file(params.metadata)}" : ''
    def fasta_max_sequences_arg = params.fasta_max_sequences ? "--fasta-max-sequences ${params.fasta_max_sequences}" : ''
    def fasta_min_length_arg = params.fasta_min_length ? "--fasta-min-length ${params.fasta_min_length}" : ''
    def fasta_max_length_arg = params.fasta_max_length ? "--fasta-max-length ${params.fasta_max_length}" : ''
    """
    # Source environment variables
    source ${env_var_file}
    # Run the input validation Python script
    python /app/scripts/p0_validation.py \
    --taxdb_dir ${file(params.taxdb)} \
    --query_fasta ${file(params.sequences)} \
    --metadata_csv ${file(params.metadata)} \
    ${bold_flag} \
    ${allowed_loci_arg} \
    ${input_fasta_arg} \
    ${input_metadata_arg} \
    ${fasta_max_sequences_arg} \
    ${fasta_min_length_arg} \
    ${fasta_max_length_arg}
    """
}