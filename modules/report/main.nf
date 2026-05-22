process REPORT {

    label 'daff_tax_assign'

    tag "$query_folder"

    // Bind config/output locations required by report generation.
    containerOptions {
        def bind_app_data = params.app_data_created ? " --bind ${file(params.app_data_dir)}:/var/lib/taxodactyl" : ""
        "--bind ${file(params.allowed_loci_file).parent} --bind ${file(params.outdir)}${bind_app_data}"
    }

    input:
    // Per-query report asset bundle assembled in the workflow.
    tuple val(query_folder),
        path(hits_files, stageAs: 'hits_files/*'),                // Folder with BLAST/BOLD hits
        path(candidates_files, stageAs: 'candidates_files/*'),
        path(db_coverage_files, stageAs: 'db_coverage_files/*'),
        path(db_coverage_errors, stageAs: 'db_coverage_errors/*'),
        path(nwk_file, stageAs: 'tree.nwk'),                                 // Newick tree file
        path(independent_sources_files, stageAs: 'independent_sources_files/*'), // Folder with independent sources file
        path(independent_sources_errors, stageAs: 'independent_sources_errors/*'),
        path(versions_file),                                                  // File with version info
        path(params_file),                                                    // File with pipeline parameters
        path(timestamp_file)                                                  // File with timestamps
    path(taxonomy_file) // Taxonomy file
    path(metadata_file) // Metadata file
    path(sequences_file) // Sequences file

    output:
    // Final per-query report page(s).
    path("$query_folder/*.html"), emit: html_report // Output: final HTML report
    // Process run log.
    path("output/${task.ext.log_filename}"), emit: report_log // Output: log file

    publishDir "${params.outdir}", mode: 'copy', pattern: "$query_folder/*.html" // Publish HTML report to output directory

    script:
    // Build optional CLI flags only when corresponding params are set.
    def bold_flag = params.db_type == 'bold' ? '--bold' : ''
    def report_debug_arg = params.report_debug ? "--report-debug" : ''
    def database_name_arg = params.blast_database_name_for_report ? "--database-name '${params.blast_database_name_for_report}'" : ''
    def facility_name_arg = params.facility_name ? "--facility-name '${params.facility_name}'" : ''
    def analyst_name_arg = params.analyst_name ? "--analyst-name '${params.analyst_name}'" : ''

    """
    # Override INPUT_FASTA_FILEPATH to use local sequences file
    export INPUT_FASTA_FILEPATH=\$(realpath "${sequences_file}")

    # Override INPUT_METADATA_CSV_FILEPATH to use local metadata file
    export INPUT_METADATA_CSV_FILEPATH=\$(realpath "${metadata_file}")

    # Ensure the query folder exists
    mkdir -p "${query_folder}"

    # Move tree file into the query folder with the correct name
    mv tree.nwk "${query_folder}/${task.ext.tree_nwk}"

    # Move staged report inputs into the query folder to keep upstream outputs intact
    for item in hits_files/*; do
        [ -e "\$item" ] || continue
        mv "\$item" "$query_folder/"
    done
    rm -r hits_files

    for item in candidates_files/*; do
        [ -e "\$item" ] || continue
        mv "\$item" "$query_folder/"
    done
    rm -r candidates_files

    for item in db_coverage_files/*; do
        [ -e "\$item" ] || continue
        mv "\$item" "$query_folder/"
    done
    rm -r db_coverage_files

    # Stage database-coverage errors under a shared errors folder.
    if [ -d db_coverage_errors ]; then
        mkdir -p "$query_folder/errors"
        for item in db_coverage_errors/*; do
            [ -e "\$item" ] || continue
            mv "\$item" "$query_folder/errors/"
        done
        rm -r db_coverage_errors
    fi

    if [ -d independent_sources_files ]; then
        for item in independent_sources_files/*; do
            [ -e "\$item" ] || continue
            mv "\$item" "$query_folder/"
        done
        rm -r independent_sources_files
    fi

    # Stage source-diversity errors under the same shared errors folder.
    if [ -d independent_sources_errors ]; then
        mkdir -p "$query_folder/errors"
        for item in independent_sources_errors/*; do
            [ -e "\$item" ] || continue
            mv "\$item" "$query_folder/errors/"
        done
        rm -r independent_sources_errors
    fi

    # Run the report generation Python script
    python /app/scripts/p6_report.py \
            "${query_folder}" \
            --query-fasta "${sequences_file}" \
            --metadata-csv "${metadata_file}" \
            --output-dir ./ \
            --versions_yml "${versions_file}" \
            --params_json "${params_file}" \
            ${bold_flag} \
            ${report_debug_arg} \
            ${database_name_arg} \
            ${facility_name_arg} \
            ${analyst_name_arg}
    """
}