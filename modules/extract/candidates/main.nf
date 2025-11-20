process EXTRACT_CANDIDATES {

    label 'daff_tax_assign'

    tag "$query_folder"

    containerOptions "--bind ${file(params.outdir)}"

    input:
    path(env_var_file) // Environment variables file
    tuple val(query_folder), path(hits_json_file), path(hits_fasta_file) // Query folder, hits JSON, and hits FASTA
    path(taxonomy_file) // Taxonomy file
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Metadata file

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
    def min_alignment_length_arg = params.min_nt ? "--min-alignment-length ${params.min_nt}" : ''
    def min_query_coverage_arg = params.min_q_coverage ? "--min-query-coverage ${params.min_q_coverage}" : ''
    def min_identity_arg = params.min_identity ? "--min-identity ${params.min_identity}" : ''
    def min_identity_strict_arg = params.min_identity_strict ? "--min-identity-strict ${params.min_identity_strict}" : ''
    def median_identity_warning_factor_arg = params.median_identity_warning_factor ? "--median-identity-warning-factor ${params.median_identity_warning_factor}" : ''
    def max_candidates_analysis_arg = params.max_candidates_for_analysis ? "--max-candidates-analysis ${params.max_candidates_for_analysis}" : ''
    def phylogeny_min_hit_identity_arg = params.phylogeny_min_hit_identity ? "--phylogeny-min-hit-identity ${params.phylogeny_min_hit_identity}" : ''
    def phylogeny_min_seqs_arg = params.phylogeny_min_seqs ? "--phylogeny-min-seqs ${params.phylogeny_min_seqs}" : ''
    def phylogeny_max_seqs_arg = params.phylogeny_max_seqs ? "--phylogeny-max-seqs ${params.phylogeny_max_seqs}" : ''
    def phylogeny_species_max_seqs_arg = params.phylogeny_species_max_seqs ? "--phylogeny-species-max-seqs ${params.phylogeny_species_max_seqs}" : ''
    def phylogeny_candidate_max_seqs_arg = params.phylogeny_candidate_max_seqs ? "--phylogeny-candidate-max-seqs ${params.phylogeny_candidate_max_seqs}" : ''
    """
    # Source environment variables
    source ${env_var_file}
    # Ensure the query folder exists
    mkdir -p $query_folder
    # Move hits files into the query folder
    mv $hits_json_file $query_folder/
    # Only move FASTA file if it exists (may be missing when no hits found)
    if [ -f "$hits_fasta_file" ]; then
        mv $hits_fasta_file $query_folder/
    fi
    # Run the candidate extraction Python script
    python /app/scripts/p3_assign_taxonomy.py \
    $query_folder \
    --query-fasta ${sequences_file} \
    --metadata-csv ${metadata_file} \
    --output-dir ./ \
    ${bold_flag} \
    ${min_alignment_length_arg} \
    ${min_query_coverage_arg} \
    ${min_identity_arg} \
    ${min_identity_strict_arg} \
    ${median_identity_warning_factor_arg} \
    ${max_candidates_analysis_arg} \
    ${phylogeny_min_seqs_arg} \
    ${phylogeny_max_seqs_arg} \
    ${phylogeny_species_max_seqs_arg} \
    ${phylogeny_candidate_max_seqs_arg}
    """
}