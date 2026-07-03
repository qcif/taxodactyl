/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT MODULES / SUBWORKFLOWS / FUNCTIONS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
include { paramsSummaryMap       } from 'plugin/nf-schema'
include { softwareVersionsToYAML } from '../subworkflows/nf-core/utils_nfcore_pipeline'
include { methodsDescriptionText } from '../subworkflows/local/utils_nfcore_taxodactyl_pipeline'
include { dumpParametersToJSON } from '../subworkflows/nf-core/utils_nextflow_pipeline'
include { BLAST_BLASTN } from '../modules/blast/blastn/main'
include { MOCK_BLASTN } from '../modules/mock/blastn/main' 
include { MAFFT_ALIGN } from '../modules/mafft/align/main'
include { EXTRACT_HITS } from '../modules/extract/hits/main'
include { BLAST_BLASTDBCMD } from '../modules/blast/blastdbcmd/main'
include { EXTRACT_TAXONOMY } from '../modules/extract/taxonomy/main'
include { EXTRACT_CANDIDATES } from '../modules/extract/candidates/main'
include { EVALUATE_SOURCE_DIVERSITY } from '../modules/evaluate/sourcediversity/main'
include { EVALUATE_DATABASE_COVERAGE } from '../modules/evaluate/databasecoverage/main'
include { FASTME } from '../modules/fastme/main'
include { REPORT } from '../modules/report/main'
include { VALIDATE_INPUT } from '../modules/validate/input/main'
include { BOLD_SEARCH } from '../modules/bold/search/main'
include { PREPARE_INPUTS } from '../modules/prepare/inputs/main'
include { PREPARE_LOG } from '../modules/prepare/log/main'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    RUN MAIN WORKFLOW
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow TAXODACTYL {

    main:

    // Format workflow start timestamp and save to file
    def formatter = java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd HHmmss").withZone(java.time.ZoneId.systemDefault())
	
    ch_workflow_timestamp = channel.of(formatter.format(workflow.start))
        .collectFile(name: 'timestamp.txt', newLine: true).first()

    try {
        file(params.app_data_dir).mkdirs()
        System.setProperty('taxodactyl.bind_app_data', " --bind ${file(params.app_data_dir)}:/var/lib/taxodactyl")
    } catch (Exception e) {
        log.warn "Could not create app data directory '${params.app_data_dir}': ${e.message}"
    }

    try {
        file(params.temp_root_dir).mkdirs()
    } catch (Exception e) {
        log.warn "Could not create temp root directory '${params.temp_root_dir}': ${e.message}"
    }

    // Copy input files to work directory first to ensure availability
    // Pass sequences as an optional list input: one file when provided, empty list when absent
    def sequences_input = params.sequences ? [file(params.sequences)] : []
    PREPARE_INPUTS (
        sequences_input,
        file(params.metadata)
    )
    
    ch_sequences_prepared = PREPARE_INPUTS.out.sequences.ifEmpty([])
    ch_metadata_prepared = PREPARE_INPUTS.out.metadata

    // Prepare allowed loci file channel (or optional placeholder if not provided)
    // This is required on Azure Batch because the file does not exist remotely
    ch_allowed_loci = params.allowed_loci_file ?
        channel.fromPath(params.allowed_loci_file) :
        channel.fromPath("${projectDir}/assets/NO_FILE_PLACEHOLDER").ifEmpty(file('OPTIONAL_FILE'))

    // Validate input files and parameters
    VALIDATE_INPUT (
        ch_sequences_prepared,
        ch_metadata_prepared,
        ch_allowed_loci
    )
    // For Azure Batch: .first() to be able to use a mixture of channels with multiple and single elements as arguments to processes
    ch_sequences = VALIDATE_INPUT.out.sequences.first()
    ch_metadata = VALIDATE_INPUT.out.metadata.first()

    // Run BOLD or BLAST search depending on db_type
    if (params.db_type == 'bold') {
        // BOLD search branch
        BOLD_SEARCH (
            ch_sequences,
            ch_metadata,
            VALIDATE_INPUT.out.ready
        )

        // Capture BOLD search outputs for downstream analysis and reporting
        ch_hits_files = BOLD_SEARCH.out.hits
        ch_taxonomy_file = BOLD_SEARCH.out.taxonomy.first()
    } else {
        // BLAST search branch - use mock or real BLAST based on params.mock_blast
        if (params.mock_blast && params.blast_xml) {
            // Mock BLAST for testing
            MOCK_BLASTN (
                ch_sequences,
                VALIDATE_INPUT.out.ready,
                file(params.blast_xml)
            )
            ch_blast_output = MOCK_BLASTN.out.blast_output
            ch_blast_versions = MOCK_BLASTN.out.versions
        } else {
            BLAST_BLASTN (
                ch_sequences,
                VALIDATE_INPUT.out.ready
            )
            ch_blast_output = BLAST_BLASTN.out.blast_output
            ch_blast_versions = BLAST_BLASTN.out.versions
        }

        // Extract hit lists from BLAST output files
        EXTRACT_HITS (
            ch_blast_output,
            ch_sequences,
            ch_metadata
        )
        
        // Regroup hit files by sample for downstream joins
        ch_hits_files = EXTRACT_HITS.out.hits_files
        ch_hits_files = ch_hits_files
            .flatten()
            .map { file-> [file.parent.name, file] }
            .groupTuple()

        // Retrieve taxonomy identifiers for all extracted hit accessions
        BLAST_BLASTDBCMD (
            EXTRACT_HITS.out.hits_accessions
        )

        // Build the taxonomy lookup file used in later reporting steps
        EXTRACT_TAXONOMY (
            BLAST_BLASTDBCMD.out.taxids,
            ch_sequences,
            ch_metadata
        )

        ch_taxonomy_file = EXTRACT_TAXONOMY.out.taxonomy.first()

    }

    // Extract candidate sequences for further analysis
    EXTRACT_CANDIDATES (
        ch_hits_files,
        ch_taxonomy_file,
        ch_sequences,
        ch_metadata
    )

    // Prepare query sequences for alignment
    ch_query_fasta = ch_sequences
        .splitFasta(record: [id: true, sequence: true])
        .map { tuple -> [tuple.id, tuple.sequence.replaceAll(/\n/, "")] }

    // Prepare candidate records with a shared sample key for joining
    ch_candidates_for_alignment = EXTRACT_CANDIDATES.out.candidates_for_alignment
    ch_candidates_for_join = ch_candidates_for_alignment
        .map { tuple -> [tuple[0].replaceFirst(/query_\d\d\d_/, ""), tuple[0], tuple[1]] }

    // Pair candidate sequences with their matching query sequences for alignment
    ch_seqs_for_alignment = ch_candidates_for_join
        .combine(ch_query_fasta, by: 0)
        .map { tuple -> [tuple[1], tuple[2], tuple[3]] }

    // Multiple sequence alignment with MAFFT
    MAFFT_ALIGN (
        ch_seqs_for_alignment
    )

    // Build phylogenetic tree with FASTME
    FASTME (
        MAFFT_ALIGN.out.aligned_sequences
    )

    // Filter candidates for source diversity evaluation 
    ch_candidates_for_source_diversity_unfiltered = EXTRACT_CANDIDATES.out.candidates_for_source_diversity
    ch_candidates_for_source_diversity = ch_candidates_for_source_diversity_unfiltered
        .filter { tuple ->
            def (folder, countFile, otherFiles) = tuple
            def count = countFile.text.trim().toInteger()
            return count >= 1 && count <= params.max_candidates_for_analysis
        }
        .map { tuple -> [tuple[0], tuple[2]] }

    // Identify samples intentionally skipped from source-diversity based on count thresholds.
    ch_candidates_skipped_source_diversity = ch_candidates_for_source_diversity_unfiltered
        .filter { tuple ->
            def (folder, countFile, otherFiles) = tuple
            def count = countFile.text.trim().toInteger()
            return count < 1 || count > params.max_candidates_for_analysis
        }
        .map { tuple -> tuple[0] }

    // Retain per-sample candidate count files for reporting
    ch_candidates_count_files = ch_candidates_for_source_diversity_unfiltered
        .map { tuple -> [tuple[0], tuple[1]] }

    // Collect all candidate-derived report assets into a single channel
    ch_candidates_files = EXTRACT_CANDIDATES.out.candidates_files
    ch_candidates_for_report = EXTRACT_CANDIDATES.out.candidates_flags
        .mix(EXTRACT_CANDIDATES.out.assigned_taxonomy_files)
        .mix(EXTRACT_CANDIDATES.out.candidates_csv_files)
        .mix(EXTRACT_CANDIDATES.out.candidates_fasta_files)
        .mix(EXTRACT_CANDIDATES.out.candidates_json_files)
        .mix(ch_candidates_count_files)
        .mix(EXTRACT_CANDIDATES.out.candidates_boxplot_files)
        .mix(ch_candidates_for_alignment)
        .mix(EXTRACT_CANDIDATES.out.preliminary_id_match_files)
        .mix(EXTRACT_CANDIDATES.out.taxa_of_concern_detected_files)
        .groupTuple(by: 0)
        .map { sample, files -> tuple(sample, files.flatten()) }
        .map { folderVal, filePath ->
        def sortedFiles = filePath.sort { a, b -> a.name <=> b.name }
        [folderVal, sortedFiles] }
    
    // Evaluate source diversity for filtered candidates
    EVALUATE_SOURCE_DIVERSITY (
        ch_candidates_for_source_diversity,
        ch_sequences,
        ch_metadata
    )
     
    // Evaluate database coverage for candidates
    EVALUATE_DATABASE_COVERAGE (
        ch_candidates_files,
        ch_sequences,
        ch_metadata
    )

    // Dump pipeline parameters to JSON for report
    ch_params_json = channel.fromPath(dumpParametersToJSON(params.outdir)).first()

    // Collect software version information for report
    if (params.db_type == 'bold') {

        ch_versions = MAFFT_ALIGN.out.versions
            .mix(FASTME.out.versions)

    } else {

        ch_versions = ch_blast_versions
            .mix(BLAST_BLASTDBCMD.out.versions)
            .mix(MAFFT_ALIGN.out.versions)
            .mix(FASTME.out.versions)

    }

    // Collate software version metadata into a single YAML artifact
    ch_collated_versions = softwareVersionsToYAML(ch_versions)
        .collectFile(
            name:  'software_versions.yml',
            sort: true,
            newLine: true
        ).first()

    // Gather database coverage outputs that should appear in the report
    ch_db_coverage_json = EVALUATE_DATABASE_COVERAGE.out.db_coverage_json
    ch_db_coverage_flags = EVALUATE_DATABASE_COVERAGE.out.db_coverage_flags
    ch_db_coverage_maps = EVALUATE_DATABASE_COVERAGE.out.db_coverage_maps
    ch_db_coverage_files = ch_db_coverage_json
        .mix(ch_db_coverage_flags)
        .mix(ch_db_coverage_maps)   // optional channel can be empty or partial
        .groupTuple(by: 0)
        .map { sample, files -> tuple(sample, files.flatten()) }

    ch_db_coverage_errors = EVALUATE_DATABASE_COVERAGE.out.db_coverage_errors
        .groupTuple(by: 0)
        .map { sample, files -> tuple(sample, files.flatten()) }

    // Ensure every sample has an errors entry (empty when none) to avoid dropping samples on combine.
    ch_db_coverage_errors_for_report = ch_candidates_files
        .map { sample, files -> tuple(sample, []) }
        .mix(ch_db_coverage_errors)
        .groupTuple(by: 0)
        .map { sample, files -> tuple(sample, files.flatten()) }

    // Gather source-diversity outputs and add explicit empty results for skipped samples.
    ch_independent_sources_flag = EVALUATE_SOURCE_DIVERSITY.out.independent_sources_flag
    ch_independent_sources_json = EVALUATE_SOURCE_DIVERSITY.out.independent_sources_json
    ch_independent_sources_skipped_files = ch_candidates_skipped_source_diversity
        .map { sample -> tuple(sample, []) }
    ch_independent_sources_files = ch_independent_sources_flag
        .mix(ch_independent_sources_json)
        .groupTuple(by: 0)
        .map { sample, files -> tuple(sample, files.flatten()) }
        .mix(ch_independent_sources_skipped_files)
        .groupTuple(by: 0)
        .map { sample, files -> tuple(sample, files.flatten()) }

    ch_independent_sources_errors = EVALUATE_SOURCE_DIVERSITY.out.independent_sources_errors
        .groupTuple(by: 0)
        .map { sample, files -> tuple(sample, files.flatten()) }

    // Ensure every sample has an errors entry (empty when none) to avoid dropping samples on combine.
    ch_independent_sources_errors_for_report = ch_candidates_files
        .map { sample, files -> tuple(sample, []) }
        .mix(ch_independent_sources_errors)
        .groupTuple(by: 0)
        .map { sample, files -> tuple(sample, files.flatten()) }

    // Combine all files needed for the final report
    ch_files_for_report = ch_hits_files
        .combine(ch_candidates_files, by: 0) 
        .combine(ch_db_coverage_files, by: 0)
        .combine(ch_db_coverage_errors_for_report, by: 0)
        .combine(FASTME.out.nwk, by: 0)
        .combine(ch_independent_sources_files, by: 0)
        .combine(ch_independent_sources_errors_for_report, by: 0)
        .combine(ch_collated_versions)
        .combine(ch_params_json)
        .combine(ch_workflow_timestamp)

         
    // Generate the final report
    REPORT (
        ch_files_for_report,
        ch_taxonomy_file,
        ch_metadata,
        ch_sequences
    )

    // Collect all run.log files from processes using p\d_ Python scripts
    ch_all_logs = VALIDATE_INPUT.out.validation_log
        .mix(EXTRACT_HITS.out.extract_hits_log)
        .mix(EXTRACT_CANDIDATES.out.extract_candidates_log)
        .mix(EVALUATE_SOURCE_DIVERSITY.out.source_diversity_log)
        .mix(EVALUATE_DATABASE_COVERAGE.out.db_coverage_log)
        .mix(REPORT.out.report_log)
    
    // Add BOLD_SEARCH log if BOLD is used
    if (params.db_type == 'bold') {
        ch_all_logs = ch_all_logs.mix(BOLD_SEARCH.out.bold_search_log)
    } else {
        // Add EXTRACT_TAXONOMY log if BLAST is used
        ch_all_logs = ch_all_logs.mix(EXTRACT_TAXONOMY.out.extract_taxonomy_log)
    }
    
    ch_all_logs = ch_all_logs
        .map { file -> file.text + '\n---------\n' }
        .collectFile(name: 'run.log', newLine: false)

    // Normalize the aggregated process logs before publishing them
    PREPARE_LOG (
        ch_all_logs
    )

    // Expose final workflow outputs on consistently named channels
    // nf-tests rely on them
    ch_hits_for_report = ch_hits_files
    ch_candidates_for_report = ch_candidates_files
    ch_homology_trees = FASTME.out.nwk
    ch_html_report = REPORT.out.html_report
    ch_source_diversity_for_report = ch_independent_sources_files
        .map { folderVal, filePath ->
        def sortedFiles = filePath.sort { a, b -> a.name <=> b.name }
        [folderVal, sortedFiles] }

    emit:
    ch_hits_for_report
    ch_candidates_for_report
    ch_db_coverage_json
    ch_db_coverage_flags
    ch_db_coverage_maps
    ch_source_diversity_for_report
    ch_homology_trees
    ch_html_report
    ch_collated_versions
    ch_params_json
    ch_workflow_timestamp

}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    THE END
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/  
