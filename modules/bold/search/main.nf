process BOLD_SEARCH {

    label 'daff_tax_assign'

    input:
    path(env_var_file) // Environment variables file
    path(fasta)        // Input FASTA file
    val ready          // Readiness flag

    output:
    path(params.bold_taxonomy_json), emit: taxonomy // Output taxonomy JSON file
    tuple path("query_*/$params.hits_json_filename"), path("query_*/$params.hits_fasta_filename"), emit: hits // Output tuple: hits JSON and FASTA files

    publishDir "${params.outdir}", mode: 'copy', 
        pattern:    "query_*/$params.hits_fasta_filename" // Publish hit FASTA files to output directory

    script:
    """
    # Source environment variables
    source ${env_var_file}
    # Run the BOLD search Python script
    python /app/scripts/p1_bold_search.py \
        --output_dir ./ \
        ${fasta} 
    """
}