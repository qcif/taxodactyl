process EXTRACT_CANDIDATES {

    label 'daff_tax_assign'

    tag "$query_folder"

    input:
    path(env_var_file)
    tuple val(query_folder), path(hits_json_file), path(hits_fasta_file)
    path(taxonomy_file)
    path(metadata)

    output:
    tuple val(query_folder), path("$query_folder/candidates_count.txt"), 
        path("$query_folder/$params.candidates_json_filename"), emit: candidates_for_source_diversity_all
    tuple val(query_folder), path("$query_folder/$params.candidates_fasta_filename"), 
        emit: candidates_for_alignment
    tuple val(query_folder), path("$query_folder/$params.candidates_json_filename"), emit: candidates_for_db_coverage
    path("$query_folder/1.flag")
    path("$query_folder/2.flag"), optional: true
    path("$query_folder/$params.candidates_csv_filename")
    path("$query_folder/$params.boxplot_img_filename"), optional: true
    // tuple val(query_folder), 
    //     path("$query_folder/$params.candidates_json_filename"), 
    //     path("$query_folder/$params.candidates_fasta_filename"), 
    //     path("$query_folder/1.flag"), 
    //     path("$query_folder/2.flag"),
    //     path("$query_folder/$params.toi_detected_csv_filename"), emit: candidates_for_report
    // tuple val(query_folder), 
    //     path("$query_folder"), emit: candidates_for_alternative_report

    publishDir "${params.outdir}", mode: 'copy', 
        pattern:    "$query_folder/$params.candidates_fasta_filename"         
    publishDir "${params.outdir}", mode: 'copy', 
        pattern:    "$query_folder/$params.candidates_csv_filename"
    publishDir "${params.outdir}", mode: 'copy', 
        pattern:    "$query_folder/$params.boxplot_img_filename"

    script:
    def bold_flag = params.db_type == 'bold' ? '--bold' : ''
    """
    source ${env_var_file}
    mkdir -p $query_folder
    mv $hits_json_file $query_folder/
    mv $hits_fasta_file $query_folder/
    python /app/scripts/p3_assign_taxonomy.py \
    $query_folder \
    --output_dir ./ \
    ${bold_flag} 
    """
    


}
