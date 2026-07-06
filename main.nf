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
    TAXODACTYL (

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
    // After the run, parse the trace file and copy each failed or aborted
    // task's .command.out, .command.err and .command.log from its (possibly remote) workDir
    // to:
    //   <outdir>/errors/<PROCESS>/<tag>.<out|err|log>
    //
    // Driven by the trace file rather than a per-task hook because
    // workflow.onProcessComplete isn't a supported handler. Works with any
    // executor — Nextflow's VFS handles remote → local copies.
    // Capture metadata before the closure — inside the closure, `workflow` and
    // `params` are shadowed by the enclosing workflow block and resolve to null.
    def _outdir = params.outdir
    def _tracePath = params.trace_file
    workflow.onComplete {
        def logRoot = new File("${_outdir}/errors")
        if (!_tracePath) {
            log.warn "Task log collection skipped: trace file path is empty (params.trace_file)"
            return
        }
        def traceFile = new File(_tracePath)
        if (!traceFile.exists()) {
            log.warn "Task log collection skipped: trace file not found at ${_tracePath}"
            return
        }

        def header = null
        def errorsCollected = false
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
            def status = row['status'] ?: ''
            if (!fullName || !workDirStr) return
            // Only collect logs for failed/aborted tasks — skip COMPLETED and CACHED.
            if (status in ['COMPLETED', 'CACHED']) return

            errorsCollected = true
            def process = (fullName =~ /^(.+?)\s*(?:\(.*\))?$/)[0][1].replace(':', '/')
            def tagMatch = (fullName =~ /\((.+?)\)/)
            def tag = tagMatch ? tagMatch[0][1] : taskId

            def destDir = new File("${logRoot}/${process}")
            destDir.mkdirs()

            // Collect stdout (.command.out), stderr (.command.err) and log (.command.log).
            // Use the InputStream copy variant — Path→Path copy attempts to
            // preserve filesystem attributes which Azure Blob's NIO provider
            // does not implement (PosixFileAttributeView).
            ['out', 'err', 'log'].each { stream ->
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

        if (errorsCollected) {
            log.info "Task logs collected under: ${logRoot}"
        }
    }
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    THE END
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
