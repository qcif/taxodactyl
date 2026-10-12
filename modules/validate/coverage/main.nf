process VALIDATE_COVERAGE_TAXA {

    label 'daff_tax_assign'
    stageInMode 'copy'

    containerOptions {
        def bind_app_data = System.getProperty('taxodactyl.bind_app_data', '')
        "--bind ${file(params.taxdb)} --bind ${file(params.allowed_loci_file).parent} --bind ${file(params.outdir)}${bind_app_data}"
    }

    input:
    path(coverage_csv, stageAs: 'input_coverage.csv') // Coverage taxa CSV (staged under a name that does not clash with the output)
    path(allowed_loci_file, stageAs: 'loci.json') // Allowed loci configuration file

    output:
    val true, emit: ready // Output: validation success flag
    path("${task.ext.coverage_csv}"), emit: coverage_csv // Output: validated, de-duplicated coverage CSV
    path("query_*/${task.ext.query_title_file}"), emit: query_titles // Output: one query title file per taxon
    path("${task.ext.log_filename}"), emit: validation_log // Output: log file

    script:
    def bold_flag = params.db_type == 'bold' ? '--bold' : ''

    // Staging and passing as file base name seems to resolve abspath issues with Azure Batch
    def allowed_loci_arg = allowed_loci_file.name != 'OPTIONAL_FILE' ? "--allowed-loci-file ${allowed_loci_file.name}" : ''
    """
    # Run the coverage taxa validation Python script
    python /app/scripts/p0_validation_coverage.py \
    --output-dir ./ \
    --taxdb-dir ${file(params.taxdb)} \
    --coverage-taxa ${coverage_csv} \
    ${bold_flag} \
    ${allowed_loci_arg}
    """
}
