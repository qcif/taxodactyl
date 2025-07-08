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
include { MAFFT_ALIGN } from '../modules/mafft/align/main'
include { EXTRACT_HITS } from '../modules/extract/hits/main'
include { BLAST_BLASTDBCMD } from '../modules/blast/blastdbcmd/main'
include { EXTRACT_TAXONOMY } from '../modules/extract/taxonomy/main'
include { CONFIGURE_ENVIRONMENT } from '../modules/configure/environment/main'
include { EXTRACT_CANDIDATES } from '../modules/extract/candidates/main'
include { EVALUATE_SOURCE_DIVERSITY } from '../modules/evaluate/sourcediversity/main'
include { EVALUATE_DATABASE_COVERAGE } from '../modules/evaluate/databasecoverage/main'
include { FASTME } from '../modules/fastme/main'
include { REPORT } from '../modules/report/main'
include { VALIDATE_INPUT } from '../modules/validate/input/main'
include { BOLD_SEARCH } from '../modules/bold/search/main'

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
        .collectFile(name: 'timestamp.txt', newLine: true)

    // Set up environment variables
    CONFIGURE_ENVIRONMENT ()
	 
    ch_env_var_file = CONFIGURE_ENVIRONMENT.out

    // Validate input files and parameters
    VALIDATE_INPUT (
        ch_env_var_file,
    )

    // Run BOLD or BLAST search depending on db_type
    if (params.db_type == 'bold') {
        // BOLD search branch
        BOLD_SEARCH (
            ch_env_var_file,
            file(params.sequences),
            VALIDATE_INPUT.out
        )
        ch_hits = BOLD_SEARCH.out.hits

        ch_taxonomy_file = BOLD_SEARCH.out.taxonomy
    } else {
        // BLAST search branch
        BLAST_BLASTN (
            file(params.sequences),
            VALIDATE_INPUT.out
        )

        EXTRACT_HITS (
            ch_env_var_file,
            BLAST_BLASTN.out.blast_output
        )
        ch_hits = EXTRACT_HITS.out.hits

        BLAST_BLASTDBCMD (
            EXTRACT_HITS.out.accessions
        )

        EXTRACT_TAXONOMY (
            ch_env_var_file,
            BLAST_BLASTDBCMD.out.taxids
        )

        ch_taxonomy_file = EXTRACT_TAXONOMY.out

    }

    // Prepare hits for candidate extraction
    ch_hits_to_filter = ch_hits
        .flatten()
        .map { file-> [file.parent.name, file] }
        .groupTuple()
        .map { folder, files -> [folder, files[0], files[1] ]} 

    // Extract candidate sequences for further analysis
    EXTRACT_CANDIDATES (
        ch_env_var_file,
        ch_hits_to_filter,
        ch_taxonomy_file,
        file(params.metadata)
    )

    // Prepare query sequences for alignment
    ch_query_fasta = Channel.fromPath(file(params.sequences))
        .splitFasta(record: [id: true, sequence: true])
        .map { tuple -> [tuple.id, tuple.sequence.replaceAll(/\n/, "")] }

    // Combine candidate and query sequences for alignment
    ch_seqs_for_alignment = EXTRACT_CANDIDATES.out.candidates_for_alignment
        .map { tuple -> [tuple[0].replaceFirst(/query_\d\d\d_/, ""), tuple[0], tuple[1]] }
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
    ch_candidates_for_source_diversity_filtered = EXTRACT_CANDIDATES.out.candidates_for_source_diversity_all
        .filter { tuple -> 
            def (folder, countFile, candidateJsonFile) = tuple
            def count = countFile.text.trim().toInteger()
            return count >= 1 && count <= params.max_candidates_for_analysis
        }
        .map { tuple -> [tuple[0], tuple[2]] }
    
    // Evaluate source diversity for filtered candidates
    EVALUATE_SOURCE_DIVERSITY (
        ch_env_var_file,
        ch_candidates_for_source_diversity_filtered
    )

    // Evaluate database coverage for candidates
    EVALUATE_DATABASE_COVERAGE (
        ch_env_var_file,
        EXTRACT_CANDIDATES.out.candidates_for_db_coverage,
        file(params.metadata)
    )

    // Prepare hits for report
    ch_hits_for_report = ch_hits.flatten()
        .map { file-> [file.parent.name, file.parent] }
        .groupTuple()
        .map { folder, files -> [folder, files[0] ]}

    // Prepare candidates for report
    ch_candidates_for_report = EXTRACT_CANDIDATES.out.candidates_for_db_coverage
        .map { folderVal, filePath -> [folderVal, filePath.parent] }  

    // Dump pipeline parameters to JSON for report
    ch_params_json = Channel.fromPath(dumpParametersToJSON(params.outdir))

    // Prepare mock source diversity for cases with 0 or >3 candidates
    ch_mock_source_diversity = EXTRACT_CANDIDATES.out.candidates_for_source_diversity_all
        .filter { 
            tuple -> 
            def (folder, countFile, candidateJsonFile) = tuple
            def count = countFile.text.trim().toInteger()
            return count == 0 || count > 3 
            }
        .map { tuple -> [tuple[0], [file("${projectDir}/assets/optional_input/QUERY_FOLDER/QUERY_FILE")]] }

    // Combine real and mock source diversity for report
    ch_source_diversity_for_report = EVALUATE_SOURCE_DIVERSITY.out.independent_sources
        .concat(ch_mock_source_diversity)
        .map { folderVal, filePath -> [folderVal, filePath.parent] } 


    // Collect software version information for report
    if (params.db_type == 'bold') {

        ch_versions = MAFFT_ALIGN.out.versions
            .mix(FASTME.out.versions)

    } else {

        ch_versions = BLAST_BLASTN.out.versions
            .mix(BLAST_BLASTDBCMD.out.versions)
            .mix(MAFFT_ALIGN.out.versions)
            .mix(FASTME.out.versions)

    }

    ch_collated_versions = softwareVersionsToYAML(ch_versions)
        .collectFile(
            name:  'software_versions.yml',
            sort: true,
            newLine: true
        )
        
    // Combine all files needed for the final report
    ch_files_for_report = ch_hits_for_report
        .combine(FASTME.out.nwk, by: 0)
        .combine(ch_candidates_for_report, by: 0) 
        .combine(EVALUATE_DATABASE_COVERAGE.out.db_coverage_for_alternative_report, by: 0)
        .combine(ch_source_diversity_for_report, by: 0)
        .combine(ch_collated_versions)
        .combine(ch_params_json)
        .combine(ch_workflow_timestamp)
         
    // Generate the final report
    REPORT (
        ch_env_var_file,
        ch_files_for_report,
        ch_taxonomy_file,
        file(params.metadata)
    )

}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    THE END
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/  
