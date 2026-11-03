process EXTRACT_HITS {

    label 'daff_tax_assign'

    // Bind output location used for published hit FASTA files.
    containerOptions {
        def bind_app_data = System.getProperty('taxodactyl.bind_app_data', '')
        "--bind ${file(params.outdir)}${bind_app_data}"
    }

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
    // Required complete extraction for inspection/tests; never published or analysed.
    path("query_*/${task.ext.all_xml_hits_json}"), arity: '1..*', emit: all_xml_hits
    // Process run log.
    path("${task.ext.log_filename}"), emit: extract_hits_log // Output: log file

    publishDir "${params.outdir}", mode: 'copy',
        pattern:    "query_*/${task.ext.hits_fasta}" // Publish hit FASTA files to output directory

    // Publish the selected downstream assets only; all_xml_hits.json stays internal.
    publishDir "${params.outdir}", mode: 'copy',
        pattern: "query_*/${task.ext.hits_json}"
    publishDir "${params.outdir}", mode: 'copy',
        pattern: "${task.ext.accessions_filename}"

    script:
    """
    # Run the BLAST hit parsing Python script
    python /app/scripts/p1_parse_blast.py \
        ${blast_xml} \
        --query-fasta ${sequences_file} \
        --metadata-csv ${metadata_file} \
        --output-dir ./ \
        --blast-max-target-seqs ${params.blast_max_target_seqs} \
        --blast-context-min-identity ${params.blast_context_min_identity}

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
