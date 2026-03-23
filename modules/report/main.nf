process REPORT {

    label 'daff_tax_assign'

    tag "$query_folder"

    containerOptions "--bind ${file(params.allowed_loci_file).parent} --bind ${file(params.outdir)}"

    input:
    path(env_var_file) // Environment variables file
    tuple val(query_folder),
        path(query_folder_path, stageAs: 'files_for_report'),                // Folder with BLAST/BOLD hits
        path(nwk_file, stageAs: 'tree.nwk'),                                 // Newick tree file
        path(versions_file),                                                  // File with version info
        path(params_file),                                                    // File with pipeline parameters
        path(timestamp_file)                                                  // File with timestamps
    path(taxonomy_file) // Taxonomy file
    path(metadata_file) // Metadata file
    path(sequences_file) // Sequences file

    output:
    path("$query_folder/*.html"), emit: html_report // Output: final HTML report
    path("output/run.log"), emit: report_log // Output: log file

    publishDir "${params.outdir}", mode: 'copy', pattern: "$query_folder/*.html" // Publish HTML report to output directory

    script:
    def bold_flag = params.db_type == 'bold' ? '--bold' : ''
    def report_debug_arg = params.report_debug ? "--report-debug" : ''
    def database_name_arg = params.blast_database_name_for_report ? "--database-name '${params.blast_database_name_for_report}'" : ''
    def facility_name_arg = params.facility_name ? "--facility-name '${params.facility_name}'" : ''
    def analyst_name_arg = params.analyst_name ? "--analyst-name '${params.analyst_name}'" : ''
    
    """
    # Source environment variables
    source ${env_var_file}

    # Override INPUT_FASTA_FILEPATH to use local sequences file
    export INPUT_FASTA_FILEPATH=\$(realpath ${sequences_file})
    # Override INPUT_METADATA_CSV_FILEPATH to use local metadata file
    export INPUT_METADATA_CSV_FILEPATH=\$(realpath ${metadata_file})
    # Ensure the query folder exists
    mkdir -p ${query_folder}
    # Move tree file into the query folder with the correct name
    mv tree.nwk ${query_folder}/$params.tree_nwk_filename
    # Move results into the query folder and clean up
    mv files_for_report/* ${query_folder}
    rm -rf files_for_report
    echo "FILES"
    ls ${query_folder}
    echo "FILES"
    # Run the report generation Python script
    python /app/scripts/p6_report.py \
            ${query_folder} \
            --query-fasta ${sequences_file} \
            --metadata-csv ${metadata_file} \
            --output-dir ./ \
            --versions_yml ${versions_file} \
            --params_json ${params_file} \
            ${bold_flag} \
            ${report_debug_arg} \
            ${database_name_arg} \
            ${facility_name_arg} \
            ${analyst_name_arg}
    """
}