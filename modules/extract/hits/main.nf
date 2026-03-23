process EXTRACT_HITS {

    label 'daff_tax_assign'

    containerOptions "--bind ${file(params.outdir)}"
    // No longer need to bind original file parent directory since we use copied files

    input:
    path(env_var_file) // Environment variables file
    path(blast_xml)    // BLAST XML results file
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Copied metadata file

    output:
    path(params.accessions_filename), emit: hits_accessions // Output: accessions file
    path("query_*"), emit: hits_query_folders // Output: hits folders
    path("output/run.log"), emit: extract_hits_log // Output: log file

    publishDir "${params.outdir}", mode: 'copy',
        pattern:    "query_*/$params.hits_fasta_filename" // Publish hit FASTA files to output directory

    script:
    def blast_max_target_seqs_arg = params.blast_max_target_seqs_for_report ? "--blast-max-target-seqs ${params.blast_max_target_seqs_for_report}" : ''
    """
    # Source environment variables
    source ${env_var_file}
    # Run the BLAST hit parsing Python script
    python /app/scripts/p1_parse_blast.py \
        ${blast_xml} \
        --query-fasta ${sequences_file} \
        --metadata-csv ${metadata_file} \
        --output-dir ./ \
        ${blast_max_target_seqs_arg} \
    """
}
