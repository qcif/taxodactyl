process EXTRACT_HITS {

    label 'daff_tax_assign'

    // Bind output location used for published hit FASTA files.
    containerOptions "--bind ${file(params.outdir)}"

    input:
    path(blast_xml)    // BLAST XML results file
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Copied metadata file

    output:
    // Accession list used for taxonomy lookup.
    path(task.ext.accessions_filename), emit: hits_accessions // Output: accessions file
    // Per-query parsed hit assets.
    tuple path("query_*/${task.ext.hits_fasta}"), 
        path("query_*/${task.ext.hits_json}"), 
        path("query_*/${task.ext.query_title_file}"), emit: hits_files // Output: tuple of hits FASTA, JSON, and title files
    // Process run log.
    path("output/${task.ext.log_filename}"), emit: extract_hits_log // Output: log file

    publishDir "${params.outdir}", mode: 'copy',
        pattern:    "query_*/${task.ext.hits_fasta}" // Publish hit FASTA files to output directory

    script:
    // Build optional CLI flags only when corresponding params are set.
    def blast_max_target_seqs_arg = params.blast_max_target_seqs_for_report ? "--blast-max-target-seqs ${params.blast_max_target_seqs_for_report}" : ''
    """
    echo '===== FULL TASK ENVIRONMENT ====='
    env | sort
    echo '===== END TASK ENVIRONMENT ====='

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
        if [[ ! -f "\${qdir}${task.ext.hits_fasta}" ]]; then
            : > "\${qdir}${task.ext.hits_fasta}"
        fi
    done
    
    """
}
