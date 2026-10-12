/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    DATABASE COVERAGE MODE

    Evaluates the reference database coverage of a list of target taxa, without
    any input sequences. Each row of the coverage CSV is treated as a
    pseudo-sample with its own query folder, and is evaluated in parallel.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
include { dumpParametersToJSON } from '../subworkflows/nf-core/utils_nextflow_pipeline'
include { prepareTaskBinds } from '../subworkflows/local/utils_nfcore_taxodactyl_pipeline'
include { VALIDATE_COVERAGE_TAXA } from '../modules/validate/coverage/main'
include { EVALUATE_DATABASE_COVERAGE } from '../modules/evaluate/databasecoverage/main'
include { REPORT_COVERAGE } from '../modules/report/coverage/main'
include { PREPARE_LOG } from '../modules/prepare/log/main'

workflow TAXODACTYL_COVERAGE {

    main:

    // Format workflow start timestamp and save to file
    def formatter = java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd HHmmss").withZone(java.time.ZoneId.systemDefault())

    ch_workflow_timestamp = channel.of(formatter.format(workflow.start))
        .collectFile(name: 'timestamp.txt', newLine: true).first()

    prepareTaskBinds()

    // Prepare allowed loci file channel (or optional placeholder if not provided)
    ch_allowed_loci = params.allowed_loci_file ?
        channel.fromPath(params.allowed_loci_file) :
        channel.fromPath("${projectDir}/assets/NO_FILE_PLACEHOLDER").ifEmpty(file('OPTIONAL_FILE'))

    // Validate the coverage CSV, de-duplicate it and create one query folder per taxon
    VALIDATE_COVERAGE_TAXA (
        file(params.coverage_taxa),
        ch_allowed_loci
    )
    ch_coverage_csv = VALIDATE_COVERAGE_TAXA.out.coverage_csv.first()

    // One tuple per taxon, the same shape as ch_candidates_files in TAXODACTYL
    ch_queries = VALIDATE_COVERAGE_TAXA.out.query_titles
        .flatten()
        .map { f -> [f.parent.name, [f]] }

    // There are no sequences in this mode: pass the optional-file placeholder
    ch_no_fasta = channel.fromPath("${projectDir}/assets/NO_FILE_PLACEHOLDER")
        .ifEmpty(file('OPTIONAL_FILE')).first()

    // Evaluate database coverage of each taxon in parallel
    EVALUATE_DATABASE_COVERAGE (
        ch_queries,
        ch_no_fasta,
        ch_coverage_csv
    )

    // Dump pipeline parameters to JSON for report
    ch_params_json = channel.fromPath(dumpParametersToJSON(params.outdir)).first()

    // A single report gathers every taxon's query folder. If every taxon fails,
    // collect() emits nothing and no report is produced.
    REPORT_COVERAGE (
        EVALUATE_DATABASE_COVERAGE.out.query_dir.map { it[1] }.collect(),
        ch_coverage_csv,
        ch_params_json,
        ch_workflow_timestamp
    )

    // Collect all run.log files from processes using p\d_ Python scripts
    ch_all_logs = VALIDATE_COVERAGE_TAXA.out.validation_log
        .mix(EVALUATE_DATABASE_COVERAGE.out.db_coverage_log)
        .mix(REPORT_COVERAGE.out.report_log)
        .map { file -> file.text + '\n---------\n' }
        .collectFile(name: 'run.log', newLine: false)

    PREPARE_LOG (
        ch_all_logs
    )

    // Expose final workflow outputs on consistently named channels
    // nf-tests rely on them
    ch_db_coverage_json = EVALUATE_DATABASE_COVERAGE.out.db_coverage_json
    ch_db_coverage_flags = EVALUATE_DATABASE_COVERAGE.out.db_coverage_flags
    ch_db_coverage_maps = EVALUATE_DATABASE_COVERAGE.out.db_coverage_maps
    ch_html_report = REPORT_COVERAGE.out.html_report

    emit:
    ch_db_coverage_json
    ch_db_coverage_flags
    ch_db_coverage_maps
    ch_html_report
}
