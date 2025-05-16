process CONFIGURE_ENVIRONMENT {
    output:
    file 'env_vars.sh'

    script:
    """
    echo 'export OUTPUT_DIR=${params.outdir}' > env_vars.sh
    echo 'export ACCESSIONS_FILENAME=${params.accessions_filename}' >> env_vars.sh
    echo 'export TAXONOMY_FILENAME=${params.taxonomy_filename}' >> env_vars.sh
    echo 'export QUERY_TITLE_FILENAME=${params.query_title_filename}' >> env_vars.sh
    echo 'export HITS_JSON_FILENAME=${params.hits_json_filename}' >> env_vars.sh
    echo 'export HITS_FASTA_FILENAME=${params.hits_fasta_filename}' >> env_vars.sh
    echo 'export FLAGS_JSON_FILENAME=${params.flags_csv_filename}' >> env_vars.sh
    echo 'export TAXONOMY_ID_CSV_FILENAME=${params.taxonomy_id_filename}' >> env_vars.sh
    echo 'export CANDIDATES_FASTA_FILENAME=${params.candidates_fasta_filename}' >> env_vars.sh
    echo 'export CANDIDATES_CSV_FILENAME=${params.candidates_csv_filename}' >> env_vars.sh
    echo 'export CANDIDATES_JSON_FILENAME=${params.candidates_json_filename}' >> env_vars.sh
    echo 'export TOI_DETECTED_CSV_FILENAME=${params.toi_detected_csv_filename}' >> env_vars.sh
    echo 'export MIN_NT=${params.min_nt}' >> env_vars.sh
    echo 'export MIN_Q_COVERAGE=${params.min_q_coverage}' >> env_vars.sh
    echo 'export MIN_IDENTITY=${params.min_identity}' >> env_vars.sh
    echo 'export MIN_IDENTITY_STRICT=${params.min_identity_strict}' >> env_vars.sh
    echo 'export TIMESTAMP_FILENAME=${params.timestamp_filename}' >> env_vars.sh
    echo 'export INPUT_FASTA_FILEPATH=${file(params.sequences)}' >> env_vars.sh
    echo 'export PMI_MATCH_CSV_FILENAME=${params.pmi_match_csv_filename}' >> env_vars.sh
    echo 'export INPUT_METADATA_CSV_FILEPATH=${params.metadata}' >> env_vars.sh
    echo 'export CANDIDATES_SOURCES_JSON_FILENAME=${params.candidates_sources_json_filename}' >> env_vars.sh
    echo 'export DB_COVERAGE_JSON_FILENAME=${params.db_coverage_json_filename}' >> env_vars.sh
    echo 'export GBIF_ACCEPTED_STATUS=${params.gbif_accepted_status}' >> env_vars.sh
    echo 'export GBIF_LIMIT_RECORDS=${params.gbif_limit_records}' >> env_vars.sh
    echo 'export MPLCONFIGDIR=.matplotlib' >> env_vars.sh
    echo 'export LOGGING_DEBUG=1' >> env_vars.sh
    echo 'export TAXONKIT_DATA=${file(params.taxdb)}' >> env_vars.sh
    echo 'export TREE_NWK_FILENAME=${params.tree_nwk_filename}' >> env_vars.sh
    if [ "${params.user_email}" != "none" ]; then
        echo 'export USER_EMAIL=${params.user_email}' >> env_vars.sh
    fi
    if [ "${params.ncbi_api_key}" != "none" ]; then
        echo 'export NCBI_API_KEY=${params.ncbi_api_key}' >> env_vars.sh
    fi
    echo 'export BOXPLOT_IMG_FILENAME=${params.boxplot_img_filename}' >> env_vars.sh
    echo 'export ANALYST_NAME="${params.analyst_name}"' >> env_vars.sh
    echo 'export FACILITY_NAME="${params.facility_name}"' >> env_vars.sh
    echo 'export ALLOWED_LOCI_FILE="${file(params.allowed_loci_file)}"' >> env_vars.sh
    """
}
