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
// After the run, parse the trace file and append details for each failed
// task into a single report at:
//   <outdir>/failed_tasks.log
    // Capture metadata before the closure — inside the closure, `workflow` and
    // `params` are shadowed by the enclosing workflow block and resolve to null.
    def _launchDir = workflow.launchDir
    def _runName = workflow.runName
    def _outdir = params.outdir
    def traceFilePath = params.traceFile
    def tracePaths = [
        traceFilePath,
        "${_launchDir}/logs/step1-trace.csv"
    ]
    workflow.onComplete {
        def failedLog = new File("${_outdir}/failed_tasks.log")
        def tracePath = tracePaths.find { new File(it).exists() } ?: tracePaths[0]
        def traceFile = new File(tracePath)

        if (!traceFile.exists()) {
            log.warn "Task log collection skipped: trace file not found at ${tracePaths.join(', ')}"
            return
        }

        failedLog.text = ''

        def readLog = { String filePath ->
            try {
                def src = nextflow.file.FileHelper.asPath(filePath)
                if (!java.nio.file.Files.exists(src)) {
                    return "[no ${src.fileName} found in ${src.parent}]\n"
                }

                src.withInputStream { ins ->
                    def text = new String(ins.bytes, java.nio.charset.StandardCharsets.UTF_8)
                    return text + (text.endsWith(System.lineSeparator()) ? '' : System.lineSeparator())
                }
            } catch (Exception e) {
                def fileName = filePath.tokenize('/')[-1]
                return "[could not read ${fileName}: ${e.message}]\n"
            }
        }

        def header = null
        traceFile.eachLine { line, idx ->
            if (idx == 1) {
                header = line.split('\t')
                return
            }
            try {
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

                def process = (fullName =~ /^(.+?)\s*(?:\(.*\))?$/)[0][1]
                def tagMatch = (fullName =~ /\((.+?)\)/)
                def tag = tagMatch ? tagMatch[0][1] : taskId

                failedLog << "\nProcess: ${process}\n"
                failedLog << "Tag: ${tag}\n"
                failedLog << "Workdir: ${workDirStr}\n\n"
                failedLog << "Full stderr:\n"
                failedLog << readLog("${workDirStr}/.command.err")
                failedLog << "\nFull stdout:\n"
                failedLog << readLog("${workDirStr}/.command.out")
                failedLog << "\n-----------------------------\n"
            } catch (Exception e) {
                log.warn "Could not collect failed task log entry from '${fullName ?: line}': ${e.message}"
            }
        }

        log.info "Failed task log collected at: ${failedLog}"
    }
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    THE END
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
