#!/usr/bin/env nextflow
/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    qcif/taxodactyl
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Github : https://github.com/qcif/taxodactyl
----------------------------------------------------------------------------------------
*/

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT FUNCTIONS / MODULES / SUBWORKFLOWS / WORKFLOWS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

include { TAXODACTYL  } from './workflows/taxodactyl'
include { PIPELINE_INITIALISATION } from './subworkflows/local/utils_nfcore_taxodactyl_pipeline'
include { PIPELINE_COMPLETION     } from './subworkflows/local/utils_nfcore_taxodactyl_pipeline'
/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    NAMED WORKFLOWS FOR PIPELINE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

//
// WORKFLOW: Run main analysis pipeline depending on type of input
//
workflow QCIF_TAXODACTYL {

    // take:

  
    main:

    //
    // WORKFLOW: Run pipeline
    //
    TAXODACTYL (

    )
}
/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    RUN MAIN WORKFLOW
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow {

    main:
    //
    // SUBWORKFLOW: Run initialisation tasks
    //
    PIPELINE_INITIALISATION (
        params.version,
        params.validate_params,
        params.monochrome_logs,
        args,
        params.outdir,
        params.metadata
    )

    //
    // WORKFLOW: Run main workflow
    //
    QCIF_TAXODACTYL (

    )
    //
    // SUBWORKFLOW: Run completion tasks
    //
    PIPELINE_COMPLETION (
        params.email,
        params.email_on_fail,
        params.plaintext_email,
        params.outdir,
        params.monochrome_logs,
    )

    // ── Log collection ────────────────────────────────────────────────────────
    // After the run, parse the trace file and copy .command.log from each
    // task's (possibly remote) workDir to:
    //   <launchDir>/task_logs/<runName>/<PROCESS>/<tag>.log
    //
    // Driven by the trace file rather than a per-task hook because
    // workflow.onProcessComplete isn't a supported handler. Works with any
    // executor — Nextflow's VFS handles remote → local copies.
    // Capture metadata before the closure — inside the closure, `workflow` and
    // `params` are shadowed by the enclosing workflow block and resolve to null.
    def _launchDir = workflow.launchDir
    def _runName = workflow.runName
    def _outdir = params.outdir
    def _tracePath = "${_outdir}/pipeline_info/execution_trace_${params.trace_report_suffix}.txt"
    workflow.onComplete {
        def logRoot = new File("${_outdir}/task_logs")
        def traceFile = new File(_tracePath)

        if (!traceFile.exists()) {
            log.warn "Task log collection skipped: trace file not found at ${_tracePath}"
            return
        }

        def header = null
        traceFile.eachLine { line, idx ->
            if (idx == 1) {
                header = line.split('\t')
                return
            }
            def cols = line.split('\t')
            def row = [:]
            header.eachWithIndex { h, i -> row[h] = i < cols.size() ? cols[i] : '' }

            def fullName = row['name'] ?: ''
            def workDirStr = row['workdir'] ?: ''
            def taskId = row['task_id'] ?: ''
            if (!fullName || !workDirStr) return

            def process = (fullName =~ /^(.+?)\s*(?:\(.*\))?$/)[0][1].replace(':', '/')
            def tagMatch = (fullName =~ /\((.+?)\)/)
            def tag = tagMatch ? tagMatch[0][1] : taskId

            def destDir = new File("${logRoot}/${process}")
            destDir.mkdirs()

            // Collect both stdout (.command.out) and stderr (.command.err).
            // Use the InputStream copy variant — Path→Path copy attempts to
            // preserve filesystem attributes which Azure Blob's NIO provider
            // does not implement (PosixFileAttributeView).
            ['out', 'err'].each { stream ->
                def dest = new File("${destDir}/${tag}.${stream}").toPath()
                try {
                    def src = nextflow.file.FileHelper.asPath("${workDirStr}/.command.${stream}")
                    if (java.nio.file.Files.exists(src)) {
                        src.withInputStream { ins ->
                            java.nio.file.Files.copy(
                                ins, dest,
                                java.nio.file.StandardCopyOption.REPLACE_EXISTING
                            )
                        }
                    } else {
                        dest.text = "[no .command.${stream} found in ${workDirStr}]\n"
                    }
                } catch (Exception e) {
                    log.warn "Could not collect .command.${stream} for task '${fullName}': ${e.message}"
                }
            }
        }

        log.info "Task logs collected under: ${logRoot}"
    }
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    THE END
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
