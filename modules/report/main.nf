process REPORT {

    label 'daff_tax_assign'

    tag "$query_folder"

    containerOptions "--bind ${file(params.sequences).parent}  --bind ${file(params.allowed_loci_file).parent}"

    input:
    path(env_var_file) // Environment variables file
    tuple val(query_folder),  
        path(hits_query_folder, stageAs: 'hits_query_folder'),                // Folder with BLAST/BOLD hits
        path(nwk_file, stageAs: 'tree.nwk'),                                 // Newick tree file
        path(candidates_query_folder, stageAs: 'candidates_query_folder'),    // Folder with candidate data
        path(db_coverage_query_folder, stageAs: 'db_coverage_query_folder'),  // Folder with database coverage results
        path(source_diversity_query_folder, stageAs: 'source_diversity_query_folder'), // Folder with source diversity results
        path(versions_file),                                                  // File with version info
        path(params_file),                                                    // File with pipeline parameters
        path(timestamp_file)                                                  // File with timestamps
    path(taxonomy_file) // Taxonomy file
    path(metadata_file) // Metadata file

    output:
    path("$query_folder/*.html") // Output: final HTML report

    publishDir "${params.outdir}", mode: 'copy', pattern: "$query_folder/*.html" // Publish HTML report to output directory

    script:
    def bold_flag = params.db_type == 'bold' ? '--bold' : ''
    """
    # Source environment variables
    source ${env_var_file}
    # Ensure the query folder exists
    mkdir -p ${query_folder}
    # Move tree file into the query folder with the correct name
    mv tree.nwk ${query_folder}/$params.tree_nwk_filename
    # Move candidate results into the query folder and clean up
    mv candidates_query_folder/* ${query_folder}
    rm -rf candidates_query_folder
    # Move database coverage results into the query folder and clean up
    mv db_coverage_query_folder/* ${query_folder}
    rm -rf db_coverage_query_folder
    # Move hits into the query folder and clean up
    mv hits_query_folder/* ${query_folder}
    rm -rf hits_query_folder
    # Move source diversity results into the query folder and clean up
    mv source_diversity_query_folder/* ${query_folder}
    rm -rf source_diversity_query_folder
    # Run the report generation Python script
    python /app/scripts/p6_report.py \
            ${query_folder} \
            --output_dir ./ \
            --versions_yml ${versions_file} \
            --params_json ${params_file} \
            ${bold_flag} 
    """
}