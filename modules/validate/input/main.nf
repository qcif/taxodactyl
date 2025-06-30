process VALIDATE_INPUT {

    label 'daff_tax_assign'

    containerOptions "--bind ${file(params.metadata).parent} --bind ${file(params.taxdb)} --bind ${file(params.sequences).parent} --bind ${file(params.allowed_loci_file).parent}"

    input:
    path(env_var_file) // Environment variables file

    output:
    val true // Output: validation success flag

    script:
    def bold_flag = params.db_type == 'bold' ? '--bold' : ''
    """
    # Source environment variables
    source ${env_var_file}
    # Run the input validation Python script
    python /app/scripts/p0_validation.py \
    --taxdb_dir ${file(params.taxdb)} \
    --query_fasta ${file(params.sequences)} \
    --metadata_csv ${file(params.metadata)} \
    ${bold_flag} 
    """
}