process REPORT {
      
    input:
    tuple val(common_files_query_list),  
        path(hits_query_folder_list, stageAs: 'hits_query_folder*'),
        path(nwk_file_list, stageAs: 'tree*.nwk'),
        path(candidates_query_folder_list, stageAs: 'candidates_query_folder*'),
        path(db_coverage_query_folder_list, stageAs: 'db_coverage_query_folder*')
    tuple val(source_diversity_query_list), 
        path(source_diversity_json_file_list, stageAs: 'source_diversity*.json')
    path(taxonomy_file)

    script:
    def common_files_size = common_files_query_list.size()
    def source_diversity_size = source_diversity_query_list.size()
    """
    source ${workDir}/env_vars.sh
    common_files_query_list_bash=(${common_files_query_list.join(' ')})
    hits_query_folder_list_bash=(${hits_query_folder_list.join(' ')})
    nwk_file_list_bash=(${nwk_file_list.join(' ')})
    candidates_query_folder_list_bash=(${candidates_query_folder_list.join(' ')})
    db_coverage_query_folder_list_bash=(${db_coverage_query_folder_list.join(' ')})
    source_diversity_query_list_bash=(${source_diversity_query_list.join(' ')})
    source_diversity_json_file_list_bash=(${source_diversity_json_file_list.join(' ')})
    for ((i=0; i<${common_files_size}; i++)); do
        current_query_folder=\${common_files_query_list_bash[\$i]}
        mkdir -p \$current_query_folder
        mv \${nwk_file_list_bash[\$i]} \$current_query_folder/candidates.msa.nwk
        mv \${candidates_query_folder_list_bash[\$i]}/* \$current_query_folder
        rm -rf \${candidates_query_folder_list_bash[\$i]}
        mv \${db_coverage_query_folder_list_bash[\$i]}/* \$current_query_folder
        rm -rf \${db_coverage_query_folder_list_bash[\$i]}
        mv \${hits_query_folder_list_bash[\$i]}/* \$current_query_folder
        rm -rf \${hits_query_folder_list_bash[\$i]}
    done
    for ((i=0; i<${source_diversity_size}; i++)); do
        current_query_folder=\${source_diversity_query_list_bash[\$i]}
        mkdir -p \$current_query_folder
        mv \${source_diversity_json_file_list_bash[\$i]} \$current_query_folder/$params.candidates_sources_json_filename
    done
    # Check if NO_QUERY folder exists and delete it
    if [ -d "NO_QUERY" ]; then
        rm -rf NO_QUERY
    fi
    rm -f */query.log
    for ((i=0; i<${common_files_size}; i++)); do
        current_query_folder=\${common_files_query_list_bash[\$i]}
        python /app/scripts/p6_report.py \
            \$current_query_folder \
            --output_dir ./
    done
    """
}
