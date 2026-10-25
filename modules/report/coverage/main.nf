process REPORT_COVERAGE {

    label 'daff_tax_assign'

    // Bind config/output locations required by report generation.
    containerOptions {
        def bind_app_data = System.getProperty('taxodactyl.bind_app_data', '')
        "--bind ${file(params.allowed_loci_file).parent} --bind ${file(params.outdir)}${bind_app_data}"
    }

    publishDir "${params.outdir}", mode: 'copy', pattern: "report_*.html" // Publish HTML report to output directory

    input:
    path(query_dirs) // Every taxon's query folder (names are unique: query_NNN_<sample_id>)
    path(coverage_csv) // Validated coverage taxa CSV
    path(params_file) // File with pipeline parameters
    path(timestamp_file) // File with timestamps (read by the report as the analysis start time)

    output:
    path("report_*.html"), emit: html_report // Output: final HTML report
    path("${task.ext.log_filename}"), emit: report_log // Output: log file

    script:
    // Build optional CLI flags only when corresponding params are set.
    def bold_flag = params.db_type == 'bold' ? '--bold' : ''
    def report_debug_arg = params.report_debug ? "--report-debug" : ''
    def database_name_arg = params.blast_database_name_for_report ? "--database-name '${params.blast_database_name_for_report}'" : ''
    def facility_name_arg = params.facility_name ? "--facility-name '${params.facility_name}'" : ''
    def analyst_name_arg = params.analyst_name ? "--analyst-name '${params.analyst_name}'" : ''

    // No --versions_yml: no versioned tools run in this mode
    """
    # Run the report generation Python script
    python /app/scripts/p6_report.py \
            --coverage-taxa "${coverage_csv}" \
            --output-dir ./ \
            --params_json "${params_file}" \
            ${bold_flag} \
            ${report_debug_arg} \
            ${database_name_arg} \
            ${facility_name_arg} \
            ${analyst_name_arg}
    """
}
