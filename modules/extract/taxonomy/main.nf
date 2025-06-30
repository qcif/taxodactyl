process EXTRACT_TAXONOMY {

    label 'daff_tax_assign'

    containerOptions "--bind ${file(params.taxdb)}" // Bind the taxonomy database directory

    input:
    path(env_var_file) // Environment variables file
    path(taxids_csv)   // CSV file with taxids to extract

    output:
    path params.taxonomy_filename // Output taxonomy file

    script:
    """
    # Source environment variables
    source ${env_var_file}
    # Run the taxonomy extraction Python script
    python /app/scripts/p2_extract_taxonomy.py \
        --output_dir ./ \
        ${taxids_csv} 
    """
}