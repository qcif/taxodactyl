process EXTRACT_CANDIDATES {

    label 'daff_tax_assign'

    tag "$query_folder"

    containerOptions "--bind ${file(params.outdir)}"

    input:
    path(env_var_file) // Environment variables file
    tuple val(query_folder), path(hits_files, stageAs: 'hits_files/*') // Query folder name and hit files
    path(taxonomy_file) // Taxonomy file
    path(sequences_file) // Copied sequences file
    path(metadata_file) // Metadata file

    output:
    tuple val(query_folder), 
        path("$query_folder/candidates_count.txt"), 
        path("$query_folder/*"), emit: candidates_for_source_diversity // Output for source diversity
    // tuple val(query_folder), 
    //     path("$query_folder/*"), emit: candidates_files // Output 
    tuple val(query_folder), 
        path("$query_folder/$params.candidates_phylogeny_fasta_filename"), emit: candidates_for_alignment // Output for alignment
    path("output/run.log"),    emit: extract_candidates_log // Output run log
    tuple val(query_folder), path("$query_folder/*.flag"), emit: candidates_flags
    tuple val(query_folder), 
        path("$query_folder/$params.candidates_fasta_filename"), emit: candidates_fasta_files
    tuple val(query_folder), 
        path("$query_folder/$params.candidates_csv_filename"), emit: candidates_csv_files
    tuple val(query_folder), 
        path("$query_folder/$params.candidates_json_filename"), emit: candidates_json_files
    tuple val(query_folder), 
        path("$query_folder/$params.boxplot_img_filename"), optional: true, emit: candidates_boxplot_files
    tuple val(query_folder), 
        path("$query_folder/assigned_taxonomy.csv"), optional: true, emit: assigned_taxonomy_files
    tuple val(query_folder), 
        path("$query_folder/preliminary_id_match.csv"), optional: true, emit: preliminary_id_match_files
    tuple val(query_folder), 
        path("$query_folder/taxa_of_concern_detected.csv"), optional: true, emit: taxa_of_concern_detected_files
    
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
    # Move staged hit files into the query folder for processing.
    for item in hits_files/*; do
        [ -e "\$item" ] || continue
        mv "\$item" "$query_folder/"
    done
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