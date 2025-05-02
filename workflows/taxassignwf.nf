/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT MODULES / SUBWORKFLOWS / FUNCTIONS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
include { paramsSummaryMap       } from 'plugin/nf-schema'
include { softwareVersionsToYAML } from '../subworkflows/nf-core/utils_nfcore_pipeline'
include { methodsDescriptionText } from '../subworkflows/local/utils_nfcore_taxassignwf_pipeline'
include { BLAST_BLASTN } from '../modules/local/blast/blastn/main' 
include { MAFFT_ALIGN } from '../modules/local/mafft/align/main'
include { EXTRACT_HITS } from '../modules/local/extract/hits/main'
include { BLAST_BLASTDBCMD } from '../modules/local/blast/blastdbcmd/main'
include { EXTRACT_TAXONOMY } from '../modules/local/extract/taxonomy/main'
include { CONFIGURE_ENVIRONMENT } from '../modules/local/configure/environment/main'
include { EXTRACT_CANDIDATES } from '../modules/local/extract/candidates/main'
include { EVALUATE_SOURCE_DIVERSITY } from '../modules/local/evaluate/sourcediversity/main'
include { EVALUATE_DATABASE_COVERAGE } from '../modules/local/evaluate/databasecoverage/main'
include { FASTME } from '../modules/local/fastme/main'
include { REPORT } from '../modules/local/report/main'
include { VALIDATE_INPUT } from '../modules/local/validate/input/main'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    RUN MAIN WORKFLOW
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow TAXASSIGNWF {

    // take:
    // // ch_samplesheet // channel: samplesheet read in from --input
    // ch_fastaformsa

    main:

    CONFIGURE_ENVIRONMENT (
    )

    VALIDATE_INPUT (
    )

    BLAST_BLASTN (
        file(params.sequences),
        VALIDATE_INPUT.out
    )

    EXTRACT_HITS (
        BLAST_BLASTN.out.blast_output
    )

    BLAST_BLASTDBCMD (
        EXTRACT_HITS.out.accessions
    )

    EXTRACT_TAXONOMY (
        BLAST_BLASTDBCMD.out.taxids
    )

    EXTRACT_HITS.out.hits
        .flatten()
        .map { file-> [file.parent.name, file] }
        .groupTuple()
        .map { folder, files -> [folder, files[0], files[1] ]}
        .set { ch_hits }  


    EXTRACT_CANDIDATES (
       ch_hits,
       EXTRACT_TAXONOMY.out,
       file(params.metadata)
    )

    ch_candidates_for_source_diversity_filtered = EXTRACT_CANDIDATES.out.candidates_for_source_diversity_all
        .filter { tuple -> 
            def (folder, countFile, candidateJsonFile) = tuple
            def count = countFile.text.trim().toInteger()
            return count >= 1 && count <= 3
        }
       .map { tuple -> [tuple[0], tuple[2]] }


    ch_mock_source_diversity = EXTRACT_CANDIDATES.out.candidates_for_source_diversity_all
        .filter { tuple -> 
            def (folder, countFile, candidateJsonFile) = tuple
            def count = countFile.text.trim().toInteger()
            return count == 0 || count > 3
        }
       .map { tuple -> [tuple[0], [file("${projectDir}/assets/QUERY_FOLDER/QUERY_FILE")]] }

    EVALUATE_SOURCE_DIVERSITY (
        ch_candidates_for_source_diversity_filtered
    )

    ch_source_diversity_for_report = EVALUATE_SOURCE_DIVERSITY.out.candidates_sources
        .concat(ch_mock_source_diversity)
        .map { folderVal, filePath -> [folderVal, filePath.parent] } 

    EVALUATE_DATABASE_COVERAGE (
        EXTRACT_CANDIDATES.out.candidates_for_db_coverage,
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

    EXTRACT_HITS.out.hits
        .flatten()
        .map { file-> [file.parent.name, file.parent] }
        .groupTuple()
        .map { folder, files -> [folder, files[0] ]}
        .set { ch_hits_for_alternative_report }

    EXTRACT_CANDIDATES.out.candidates_for_db_coverage
        .map { folderVal, filePath -> [folderVal, filePath.parent] }  
        .set { ch_candidates_for_alternative_report }

    ch_hits_for_alternative_report
        .combine(FASTME.out.nwk, by: 0)
        .combine(ch_candidates_for_alternative_report, by: 0)
        .combine(EVALUATE_DATABASE_COVERAGE.out.db_coverage_for_alternative_report, by: 0)
        .combine(ch_source_diversity_for_report, by: 0)
        .set { ch_files_for_report }

    REPORT (
        ch_files_for_report,
        EXTRACT_TAXONOMY.out,
        file(params.metadata)
    )

    ch_versions = Channel.empty()

    //
    // Collate and save software versions
    //
    softwareVersionsToYAML(ch_versions)
        .collectFile(
            storeDir: "${params.outdir}/pipeline_info",
            name:  'taxassignwf_software_'  + 'versions.yml',
            sort: true,
            newLine: true
        ).set { ch_collated_versions }

    emit:
    versions       = ch_versions                 // channel: [ path(versions.yml) ]

}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    THE END
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
