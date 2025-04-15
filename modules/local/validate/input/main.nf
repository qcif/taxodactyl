process VALIDATE_INPUT {

    output:
    val true

    script:
    """
    python /app/scripts/p0_validation.py \
    --taxdb_dir ${file(params.taxdb)} \
    --query_fasta ${file(params.sequences)} \
    --metadata_csv ${file(params.metadata)}
    """
}
