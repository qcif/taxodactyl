process CONFIGURE_ENVIRONMENT {
    input:
    path sequences_file
    path metadata_file

    output:
    file 'env_vars.sh' // Output: environment variables file for downstream modules

    script:
    """
    # Set matplotlib config directory to avoid warnings
    echo 'export MPLCONFIGDIR=.matplotlib' > env_vars.sh

    # Export pipeline parameters as environment variables if they are set
    if [ ${params.logging_debug} != null ]; then echo 'export LOGGING_DEBUG=${params.logging_debug}' >> env_vars.sh; fi
    if [ ${params.bold_skip_orientation} != null ]; then echo 'export BOLD_SKIP_ORIENTATION=${params.bold_skip_orientation}' >> env_vars.sh; fi

    # Export NCBI API key
    if [ -n "${params.ncbi_api_key ?: ''}" ]; then
        echo 'export NCBI_API_KEY=${params.ncbi_api_key}' >> env_vars.sh
    elif [ -n "\${NCBI_API_KEY:-}" ]; then
        echo "export NCBI_API_KEY=\${NCBI_API_KEY}" >> env_vars.sh
    fi
    if [ ${params.ncbi_user_email} != null ]; then echo 'export USER_EMAIL=${params.ncbi_user_email}' >> env_vars.sh; fi

    # Export TaxonKit data directory
    if [ ${params.taxdb} != null ]; then echo 'export TAXONKIT_DATA=${file(params.taxdb)}' >> env_vars.sh; fi

    # Export output file names
    if [ ${params.accessions_filename} != null ]; then echo 'export ACCESSIONS_FILENAME=${params.accessions_filename}' >> env_vars.sh; fi
    if [ ${params.bold_taxonomy_json} != null ]; then echo 'export BOLD_TAXONOMY_JSON=${params.bold_taxonomy_json}' >> env_vars.sh; fi
    if [ ${params.boxplot_img_filename} != null ]; then echo 'export BOXPLOT_IMG_FILENAME=${params.boxplot_img_filename}' >> env_vars.sh; fi
    if [ ${params.candidates_csv_filename} != null ]; then echo 'export CANDIDATES_CSV_FILENAME=${params.candidates_csv_filename}' >> env_vars.sh; fi
    if [ ${params.candidates_fasta_filename} != null ]; then echo 'export CANDIDATES_FASTA_FILENAME=${params.candidates_fasta_filename}' >> env_vars.sh; fi
    if [ ${params.candidates_phylogeny_fasta_filename} != null ]; then echo 'export PHYLOGENY_FASTA_FILENAME=${params.candidates_phylogeny_fasta_filename}' >> env_vars.sh; fi
    if [ ${params.candidates_json_filename} != null ]; then echo 'export CANDIDATES_JSON_FILENAME=${params.candidates_json_filename}' >> env_vars.sh; fi
    if [ ${params.candidates_sources_json_filename} != null ]; then echo 'export CANDIDATES_SOURCES_JSON_FILENAME=${params.candidates_sources_json_filename}' >> env_vars.sh; fi
    if [ ${params.hits_fasta_filename} != null ]; then echo 'export HITS_FASTA_FILENAME=${params.hits_fasta_filename}' >> env_vars.sh; fi
    if [ ${params.hits_json_filename} != null ]; then echo 'export HITS_JSON_FILENAME=${params.hits_json_filename}' >> env_vars.sh; fi
    if [ ${params.independent_sources_json_filename} != null ]; then echo 'export INDEPENDENT_SOURCES_JSON_FILENAME=${params.independent_sources_json_filename}' >> env_vars.sh; fi
    if [ ${params.taxonomy_filename} != null ]; then echo 'export TAXONOMY_FILENAME=${params.taxonomy_filename}' >> env_vars.sh; fi
    if [ ${params.tree_nwk_filename} != null ]; then echo 'export TREE_NWK_FILENAME=${params.tree_nwk_filename}' >> env_vars.sh; fi
    """
}