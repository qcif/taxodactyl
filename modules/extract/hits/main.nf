process EXTRACT_HITS {

    label 'daff_tax_assign'

    containerOptions "--bind ${file(params.sequences).parent}"

    input:
    path(env_var_file) // Environment variables file
    path(blast_xml)    // BLAST XML results file

    output:
    path(params.accessions_filename), emit: accessions // Output: accessions file
    tuple path("query_*/$params.hits_json_filename"), path("query_*/$params.hits_fasta_filename"), emit: hits // Output: tuple of hits JSON and FASTA files
    path("run.log"), emit: extract_hits_log // Output: log file

    publishDir "${params.outdir}", mode: 'copy', 
        pattern:    "query_*/$params.hits_fasta_filename" // Publish hit FASTA files to output directory
    
    script:
    """
    # Source environment variables
    source ${env_var_file}
    # Run the BLAST hit parsing Python script
    python /app/scripts/p1_parse_blast.py ${blast_xml} --output_dir ./
    """
}