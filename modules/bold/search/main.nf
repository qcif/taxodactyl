process BOLD_SEARCH {

    label 'daff_tax_assign'

    input:
    path(fasta)        // Input FASTA file
    path(metadata)     // Input metadata CSV file
    val ready          // Readiness flag

    output:
    path(task.ext.bold_taxonomy_json), emit: taxonomy // Output taxonomy JSON file
    path("query_*"), emit: hits // // Output: hits folders
    path("${task.ext.log_filename}"), emit: bold_search_log // Output: log file

    publishDir "${params.outdir}", mode: 'copy',
        pattern:    "query_*/${task.ext.hits_fasta}" // Publish hit FASTA files to output directory

    script:
    def bold_database_arg = params.bold_database_name ? "--bold-database ${params.bold_database_name}" : ''
    """
    # Run the BOLD search Python script
    python /app/scripts/p1_bold_search.py \
        --output-dir ./ \
        ${bold_database_arg} \
        --query-fasta ${fasta} \
        --metadata-csv ${metadata}
    """
}
