process EXTRACT_CANDIDATES {

    label 'daff_tax_assign'

    tag "$query_folder"

    input:
    path(env_var_file) // Environment variables file
    tuple val(query_folder), path(hits_json_file), path(hits_fasta_file) // Query folder, hits JSON, and hits FASTA
    path(taxonomy_file) // Taxonomy file
    path(metadata) // Metadata file

    output:
    tuple val(query_folder), path("$query_folder/candidates_count.txt"), 
        path("$query_folder/$params.candidates_json_filename"), emit: candidates_for_source_diversity_all // Output for source diversity
    tuple val(query_folder), path("$query_folder/$params.candidates_phylogeny_fasta_filename"), 
        emit: candidates_for_alignment // Output for alignment
    tuple val(query_folder), path("$query_folder/$params.candidates_json_filename"), emit: candidates_for_db_coverage // Output for DB coverage
    path("$query_folder/1.flag") // Flag file
    path("$query_folder/2.flag"), optional: true // Optional flag file
    path("$query_folder/$params.candidates_csv_filename") // Candidates CSV
    path("$query_folder/$params.candidates_fasta_filename") // Candidates FASTA
    path("$query_folder/$params.boxplot_img_filename"), optional: true // Optional boxplot image

    publishDir "${params.outdir}", mode: 'copy', 
        pattern:    "$query_folder/$params.candidates_phylogeny_fasta_filename" // Publish phylogeny FASTA
    publishDir "${params.outdir}", mode: 'copy', 
        pattern:    "$query_folder/$params.candidates_fasta_filename"            // Publish candidates FASTA
    publishDir "${params.outdir}", mode: 'copy', 
        pattern:    "$query_folder/$params.candidates_csv_filename"              // Publish candidates CSV
    publishDir "${params.outdir}", mode: 'copy', 
        pattern:    "$query_folder/$params.boxplot_img_filename"                 // Publish boxplot image

    script:
    def bold_flag = params.db_type == 'bold' ? '--bold' : ''
    """
    # Source environment variables
    source ${env_var_file}
    # Ensure the query folder exists
    mkdir -p $query_folder
    # Move hits files into the query folder
    mv $hits_json_file $query_folder/
    mv $hits_fasta_file $query_folder/
    # Run the candidate extraction Python script
    python /app/scripts/p3_assign_taxonomy.py \
    $query_folder \
    --output_dir ./ \
    ${bold_flag} 
    """
}