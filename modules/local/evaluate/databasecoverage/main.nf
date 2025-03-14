process EVALUATE_DATABASE_COVERAGE {
    tag "$query_folder"

    containerOptions "--bind ${file(params.taxdb)}"
    
    input:
    tuple val(query_folder), path(candidate_json_file)
    path(metadata)

    output:
    // tuple val(query_folder), 
    //     path("$query_folder/$params.db_coverage_json_filename"), 
    //     path("$query_folder/errors"),   emit: db_coverage_for_report
    tuple val(query_folder), 
        path("$query_folder"), emit: db_coverage_for_alternative_report

    // publishDir "${params.outdir}", mode: 'copy', pattern: "$query_folder/$params.db_coverage_json_filename"


    // errorStrategy { task, e ->
    //     def outputFile = "$query_folder/error.p5.log"
    //     if (outputFile.exists()) {
    //         // Ignore the error if the specified output file was generated
    //         return 'ignore'
    //     }
    //     // Terminate the process for other errors
    //     return 'terminate'
    // }
    

    
    script:
    """
    source ${workDir}/env_vars.sh
    mkdir -p $query_folder
    mv $candidate_json_file $query_folder
    python /app/scripts/p5_db_coverage.py \
    $query_folder \
    --output_dir ./
    """
}
