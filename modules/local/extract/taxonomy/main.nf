process EXTRACT_TAXONOMY {

    label 'daff_tax_assign'

    containerOptions "--bind ${file(params.taxdb)}"

    input:
    path(taxids_csv)

    output:
    path params.taxonomy_filename

    script:
    """
    source ${workDir}/env_vars.sh
    python /app/scripts/p2_extract_taxonomy.py \
        --output_dir ./ \
        ${taxids_csv} 
    """
}
