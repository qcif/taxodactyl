process VALIDATE_INPUT {

    label 'daff_tax_assign'

    containerOptions "--bind ${file(params.metadata).parent} --bind ${file(params.taxdb)} --bind ${file(params.sequences).parent}"

    output:
    val true

    script:
    """
    python /app/scripts/p0_validation.py \
    --taxdb_dir ${file(params.taxdb)} \
    ---query_fasta ${file(params.sequences)} \
    --metadata_csv ${file(params.metadata)}
    """
}
