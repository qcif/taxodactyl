process EXTRACT_TAXONOMY {

    label 'daff_tax_assign'

    containerOptions "--bind ${file(params.taxdb)} --bind ${file(params.outdir)}"

    input:
    path(env_var_file) // Environment variables file
    path(taxids_csv)   // CSV file with taxids to extract
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Copied metadata file

    output:
    path params.taxonomy_filename // Output taxonomy file

    script:
    """
    # Source environment variables
    source ${env_var_file}
    # Run the taxonomy extraction Python script
    python /app/scripts/p2_extract_taxonomy.py \
        --query-fasta ${sequences_file} \
        --metadata-csv ${metadata_file} \
        --output-dir ./ \
        ${taxids_csv}
    """
}