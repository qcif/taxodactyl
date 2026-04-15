process EXTRACT_HITS {

    label 'daff_tax_assign'

    // Bind output location used for published hit FASTA files.
    containerOptions "--bind ${file(params.outdir)}"

    input:
    path(env_var_file) // Environment variables file
    path(blast_xml)    // BLAST XML results file
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Copied metadata file

    output:
    // Accession list used for taxonomy lookup.
    path(params.accessions_filename), emit: hits_accessions // Output: accessions file
    // Per-query parsed hit assets.
    tuple path("query_*/$params.hits_fasta_filename"), 
        path("query_*/$params.hits_json_filename"), 
        path("query_*/query_title.txt"), emit: hits_files // Output: tuple of hits FASTA, JSON, and title files
    // Process run log.
    path("output/run.log"), emit: extract_hits_log // Output: log file

    publishDir "${params.outdir}", mode: 'copy',
        pattern:    "query_*/$params.hits_fasta_filename" // Publish hit FASTA files to output directory

    script:
    // Build optional CLI flags only when corresponding params are set.
    def blast_max_target_seqs_arg = params.blast_max_target_seqs_for_report ? "--blast-max-target-seqs ${params.blast_max_target_seqs_for_report}" : ''
    """
    # Load environment exported by upstream setup step.
    source ${env_var_file}

    # Run the BLAST hit parsing Python script
    python /app/scripts/p1_parse_blast.py \
        ${blast_xml} \
        --query-fasta ${sequences_file} \
        --metadata-csv ${metadata_file} \
        --output-dir ./ \
        ${blast_max_target_seqs_arg}

    # Ensure each query folder has a FASTA file so downstream matching/publishing is stable.
    shopt -s nullglob
    for qdir in query_*/; do
        [ -d "\$qdir" ] || continue
        if [[ ! -f "\${qdir}${params.hits_fasta_filename}" ]]; then
            : > "\${qdir}${params.hits_fasta_filename}"
        fi
    done
    
    """
}
