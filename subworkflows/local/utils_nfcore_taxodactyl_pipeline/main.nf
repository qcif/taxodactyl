//
// Subworkflow with functionality specific to the qcif/taxodactyl pipeline
//

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT FUNCTIONS / MODULES / SUBWORKFLOWS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

include { UTILS_NFSCHEMA_PLUGIN     } from '../../nf-core/utils_nfschema_plugin'
include { paramsSummaryMap          } from 'plugin/nf-schema'
include { samplesheetToList         } from 'plugin/nf-schema'
include { completionEmail           } from '../../nf-core/utils_nfcore_pipeline'
include { completionSummary         } from '../../nf-core/utils_nfcore_pipeline'
include { UTILS_NFCORE_PIPELINE     } from '../../nf-core/utils_nfcore_pipeline'
include { UTILS_NEXTFLOW_PIPELINE   } from '../../nf-core/utils_nextflow_pipeline'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    SUBWORKFLOW TO INITIALISE PIPELINE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow PIPELINE_INITIALISATION {

    take:
    version           // boolean: Display version and exit
    validate_params   // boolean: Boolean whether to validate parameters against the schema at runtime
    monochrome_logs   // boolean: Do not use coloured log outputs
    nextflow_cli_args //   array: List of positional nextflow CLI args
    outdir            //  string: The output directory where the results will be saved
    metadata             //  string: Path to metadata samplesheet

    main:

    ch_versions = Channel.empty()

    //
    // Print version and exit if required and dump pipeline parameters to JSON file
    //
    UTILS_NEXTFLOW_PIPELINE (
        version,
        true,
        outdir,
        workflow.profile.tokenize(',').intersect(['conda', 'mamba']).size() >= 1
    )

    //
    // Validate parameters and generate parameter summary to stdout
    //
    UTILS_NFSCHEMA_PLUGIN (
        workflow,
        validate_params,
        null
    )

    //
    // Check config provided to the pipeline
    //
    UTILS_NFCORE_PIPELINE (
        nextflow_cli_args
    )

    //
    // Custom validation for pipeline parameters
    //
    validateInputParameters()
    
    emit:
    versions    = ch_versions
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    SUBWORKFLOW FOR PIPELINE COMPLETION
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow PIPELINE_COMPLETION {

    take:
    email           //  string: email address
    email_on_fail   //  string: email address sent on pipeline failure
    plaintext_email // boolean: Send plain-text email instead of HTML
    outdir          //    path: Path to output directory where results will be published
    monochrome_logs // boolean: Disable ANSI colour codes in log output

    main:
    summary_params = paramsSummaryMap(workflow, parameters_schema: "nextflow_schema.json")

    //
    // Completion email and summary
    //
    workflow.onComplete {
        if (email || email_on_fail) {
            completionEmail(
                summary_params,
                email,
                email_on_fail,
                plaintext_email,
                outdir,
                monochrome_logs,
                []
            )
        }

        completionSummary(monochrome_logs)
    }

    workflow.onError {
        log.error "Pipeline failed. Please refer to troubleshooting docs: https://nf-co.re/docs/usage/troubleshooting"
    }
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    FUNCTIONS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

def validateInputParameters() {

    // Database coverage mode takes a coverage taxa CSV instead of metadata and sequences
    if (params.metadata && params.coverage_taxa) {
        error("Parameters 'metadata' and 'coverage_taxa' cannot be used together. Use 'coverage_taxa' for database coverage mode (no input sequences), or 'metadata' to analyse sequences.")
    }

    if (!params.metadata && !params.coverage_taxa) {
        error("Either the 'metadata' parameter (with sequences), or the 'coverage_taxa' parameter (database coverage mode) must be set.")
    }

    if (params.coverage_taxa && params.sequences) {
        error("Parameter 'sequences' cannot be used with 'coverage_taxa'. Database coverage mode does not analyse input sequences.")
    }

    // No BLAST search is run in database coverage mode
    if (params.db_type == "blast_core_nt" && !params.blastdb && !params.coverage_taxa) {
        error("'blastdb' parameter must be set when using blast_core_nt database type. 'blastdb' must be a valid path to BLAST database files, and needs to end with 'core_nt', e.g. '/folder_path/blast_db/202505/core_nt'. The folder should contain files with the core_nt prefix and extensions: .nal, .ndb, .njs, .nos, .not, .ntf, .nto. In addition, it should contain multiple volumes of core_nt, named core_nt.NUM with extensions .nhr, .nin, .nnd, .nni, .nog and .nsq.")
    }

    if (params.db_cov_min_a <= params.db_cov_min_b) {
        error("'db_cov_min_a' parameter must be greater than 'db_cov_min_b'. Please check your parameters.")
    }

    if (params.db_cov_related_min_a <= params.db_cov_related_min_b) {
        error("'db_cov_related_min_a' parameter must be greater than 'db_cov_related_min_b'. Please check your parameters.")
    }

}

def prepareTaskBinds() {
    System.setProperty('taxodactyl.bind_app_data', '')

    // App data is optional: only tasks that use local secret persistence need
    // the host mount, so failure here should not stop the workflow.
    try {
        def app_data_dir = file(params.app_data_dir)
        app_data_dir.mkdirs()
        if (app_data_dir.isDirectory()) {
            System.setProperty('taxodactyl.bind_app_data', " --bind ${app_data_dir}:/var/lib/taxodactyl")
        } else {
            log.warn "App data path '${params.app_data_dir}' is not a valid directory and cannot be used for task binds. Tasks will continue without an app data host mount."
        }
    } catch (Exception e) {
        log.warn "Could not create app data directory '${params.app_data_dir}' for task binds: ${e.message}. Tasks will continue without an app data host mount."
    }

    // Temp root is treated as generally required because task code may write
    // cache/throttle state there, so we always try to prepare it up front.
    try {
        def temp_root_dir = file(params.temp_root_dir)
        temp_root_dir.mkdirs()
        if (!temp_root_dir.isDirectory()) {
            log.warn "Temp root path '${params.temp_root_dir}' is not a valid directory and may cause task failures (tasks will still attempt to create/bind it per task)."
        }
    } catch (Exception e) {
        log.warn "Could not create temp root directory '${params.temp_root_dir}' for task binds: ${e.message}. Tasks will continue without a temp root host mount."
    }
}

def toolCitationText() {
    // TODO nf-core: Optionally add in-text citation tools to this list.
    // Can use ternary operators to dynamically construct based conditions, e.g. params["run_xyz"] ? "Tool (Foo et al. 2023)" : "",
    // Uncomment function in methodsDescriptionText to render in MultiQC report
    def citation_text = [
            "Tools used in the workflow included:",
            "."
        ].join(' ').trim()

    return citation_text
}

def toolBibliographyText() {
    // TODO nf-core: Optionally add bibliographic entries to this list.
    // Can use ternary operators to dynamically construct based conditions, e.g. params["run_xyz"] ? "<li>Author (2023) Pub name, Journal, DOI</li>" : "",
    // Uncomment function in methodsDescriptionText to render in MultiQC report
    def reference_text = [
        ].join(' ').trim()

    return reference_text
}

def methodsDescriptionText(mqc_methods_yaml) {
    // Convert  to a named map so can be used as with familiar NXF ${workflow} variable syntax in the MultiQC YML file
    def meta = [:]
    meta.workflow = workflow.toMap()
    meta["manifest_map"] = workflow.manifest.toMap()

    // Pipeline DOI
    if (meta.manifest_map.doi) {
        // Using a loop to handle multiple DOIs
        // Removing `https://doi.org/` to handle pipelines using DOIs vs DOI resolvers
        // Removing ` ` since the manifest.doi is a string and not a proper list
        def temp_doi_ref = ""
        def manifest_doi = meta.manifest_map.doi.tokenize(",")
        manifest_doi.each { doi_ref ->
            temp_doi_ref += "(doi: <a href=\'https://doi.org/${doi_ref.replace("https://doi.org/", "").replace(" ", "")}\'>${doi_ref.replace("https://doi.org/", "").replace(" ", "")}</a>), "
        }
        meta["doi_text"] = temp_doi_ref.substring(0, temp_doi_ref.length() - 2)
    } else meta["doi_text"] = ""
    meta["nodoi_text"] = meta.manifest_map.doi ? "" : "<li>If available, make sure to update the text to include the Zenodo DOI of version of the pipeline used. </li>"

    // Tool references
    meta["tool_citations"] = ""
    meta["tool_bibliography"] = ""

    // TODO nf-core: Only uncomment below if logic in toolCitationText/toolBibliographyText has been filled!
    // meta["tool_citations"] = toolCitationText().replaceAll(", \\.", ".").replaceAll("\\. \\.", ".").replaceAll(", \\.", ".")
    // meta["tool_bibliography"] = toolBibliographyText()


    def methods_text = mqc_methods_yaml.text

    def engine =  new groovy.text.SimpleTemplateEngine()
    def description_html = engine.createTemplate(methods_text).make(meta)

    return description_html.toString()
}

