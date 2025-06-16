/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT MODULES / SUBWORKFLOWS / FUNCTIONS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
include { paramsSummaryMap       } from 'plugin/nf-schema'
include { softwareVersionsToYAML } from '../subworkflows/nf-core/utils_nfcore_pipeline'
include { methodsDescriptionText } from '../subworkflows/local/utils_nfcore_taxassignwf_pipeline'
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

workflow TAXASSIGNWF {

    main:

    CONFIGURE_ENVIRONMENT (
    )
    env_var_file_ch = CONFIGURE_ENVIRONMENT.out

    VALIDATE_INPUT (
        env_var_file_ch,
    )

    if (params.db_type == 'bold') {
        BOLD_SEARCH (
            env_var_file_ch,
            file(params.sequences),
            VALIDATE_INPUT.out
        )
        ch_hits = BOLD_SEARCH.out.hits

        ch_taxonomy_file = BOLD_SEARCH.out.taxonomy
    } else {
        BLAST_BLASTN (
            file(params.sequences),
            VALIDATE_INPUT.out
        )

        EXTRACT_HITS (
            env_var_file_ch,
            BLAST_BLASTN.out.blast_output
        )
        ch_hits = EXTRACT_HITS.out.hits

        BLAST_BLASTDBCMD (
            EXTRACT_HITS.out.accessions
        )

        EXTRACT_TAXONOMY (
            env_var_file_ch,
            BLAST_BLASTDBCMD.out.taxids
        )

        ch_taxonomy_file = EXTRACT_TAXONOMY.out

    }

     ch_hits
        .flatten()
        .map { file-> [file.parent.name, file] }
        .groupTuple()
        .map { folder, files -> [folder, files[0], files[1] ]}
        .set { ch_hits_to_filter }  

    EXTRACT_CANDIDATES (
        env_var_file_ch,
        ch_hits_to_filter,
        ch_taxonomy_file,
        file(params.metadata)
    )

    Channel.fromPath(file(params.sequences))
        .splitFasta(record: [id: true, sequence: true])
        .map { tuple -> [tuple.id, tuple.sequence.replaceAll(/\n/, "")] }
        .set { ch_queryfasta }

    EXTRACT_CANDIDATES.out.candidates_for_alignment
        .map { tuple -> [tuple[0].replaceFirst(/query_\d\d\d_/, ""), tuple[0], tuple[1]] }
        .combine(ch_queryfasta, by: 0)
        .map { tuple -> [tuple[1], tuple[2], tuple[3]] }
        .set { ch_seqs_for_alignment }

    MAFFT_ALIGN (
        ch_seqs_for_alignment
    )

    FASTME (
        MAFFT_ALIGN.out.aligned_sequences
    )

    ch_candidates_for_source_diversity_filtered = EXTRACT_CANDIDATES.out.candidates_for_source_diversity_all
        .filter { tuple -> 
            def (folder, countFile, candidateJsonFile) = tuple
            def count = countFile.text.trim().toInteger()
            return count >= 1 && count <= 3
        }
        .map { tuple -> [tuple[0], tuple[2]] }
    
    EVALUATE_SOURCE_DIVERSITY (
        env_var_file_ch,
        ch_candidates_for_source_diversity_filtered
    )

    EVALUATE_DATABASE_COVERAGE (
        env_var_file_ch,
        EXTRACT_CANDIDATES.out.candidates_for_db_coverage,
        file(params.metadata)
    )

    ch_hits.flatten()
        .map { file-> [file.parent.name, file.parent] }
        .groupTuple()
        .map { folder, files -> [folder, files[0] ]}
        .set { ch_hits_for_alternative_report }

    EXTRACT_CANDIDATES.out.candidates_for_db_coverage
        .map { folderVal, filePath -> [folderVal, filePath.parent] }  
        .set { ch_candidates_for_alternative_report }


    ch_params_json = Channel.fromPath(dumpParametersToJSON(params.outdir))

    ch_mock_source_diversity = EXTRACT_CANDIDATES.out.candidates_for_source_diversity_all
        .filter { tuple -> 
            def (folder, countFile, candidateJsonFile) = tuple
            def count = countFile.text.trim().toInteger()
            return count == 0 || count > 3
        }
    .map { tuple -> [tuple[0], [file("${projectDir}/assets/optional_input/QUERY_FOLDER/QUERY_FILE")]] }

    ch_source_diversity_for_report = EVALUATE_SOURCE_DIVERSITY.out.independent_sources
        .concat(ch_mock_source_diversity)
        .map { folderVal, filePath -> [folderVal, filePath.parent] } 


    if (params.db_type == 'bold') {

        ch_versions = MAFFT_ALIGN.out.versions
            .mix(FASTME.out.versions)

    } else {

        ch_versions = BLAST_BLASTN.out.versions
            .mix(BLAST_BLASTDBCMD.out.versions)
            .mix(MAFFT_ALIGN.out.versions)
            .mix(FASTME.out.versions)

    }

    softwareVersionsToYAML(ch_versions)
    .collectFile(
        name:  'software_versions.yml',
        sort: true,
        newLine: true
    ).set { ch_collated_versions }
        

    ch_hits_for_alternative_report
        .combine(FASTME.out.nwk, by: 0)
        .combine(ch_candidates_for_alternative_report, by: 0) 
        .combine(EVALUATE_DATABASE_COVERAGE.out.db_coverage_for_alternative_report, by: 0)
        .combine(ch_source_diversity_for_report, by: 0)
        .combine(ch_collated_versions)
        .combine(ch_params_json)
        .set { ch_files_for_report }
         
    REPORT (
        env_var_file_ch,
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
