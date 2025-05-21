process EXTRACT_TAXONOMY {

    label 'daff_tax_assign'

    containerOptions "--bind ${file(params.taxdb)}"

    input:
    path(env_var_file)
    path(taxids_csv)

    output:
    path params.taxonomy_filename

    script:
    """
    source ${env_var_file}
    python /app/scripts/p2_extract_taxonomy.py \
        --output_dir ./ \
        ${taxids_csv} 
    """
}
