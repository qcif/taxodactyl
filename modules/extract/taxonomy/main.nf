process EXTRACT_TAXONOMY {

    label 'daff_tax_assign'

    containerOptions {
        def bind_app_data = System.getProperty('taxodactyl.bind_app_data', '')
        "--bind ${file(params.taxdb)} --bind ${file(params.outdir)}${bind_app_data}"
    }

    input:
    path(taxids_csv)   // CSV file with taxids to extract
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Copied metadata file

    output:
    path task.ext.taxonomy_file, emit: taxonomy // Output taxonomy file
    path("output/${task.ext.log_filename}"), emit: extract_taxonomy_log // Output: log file

    script:
    """
    # Run the taxonomy extraction Python script
    python /app/scripts/p2_extract_taxonomy.py \
        --query-fasta ${sequences_file} \
        --metadata-csv ${metadata_file} \
        --output-dir ./ \
        ${taxids_csv}
    """
}