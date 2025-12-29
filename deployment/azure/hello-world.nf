#!/usr/bin/env nextflow

/*
 * Simple Hello World pipeline for testing Azure Batch environment
 * This pipeline tests basic Nextflow functionality with Azure Batch
 */

nextflow.enable.dsl=2

// Parameters
params.greeting = "Hello from Azure Batch!"
params.count = 3
params.refdata_path = "/mnt/nvme/refdata/core_nt"

// Process to print a greeting
process sayHello {
    debug true

    input:
    val x

    output:
    stdout

    script:
    """
    echo "Task ${x}: ${params.greeting}"
    echo "Hostname: \$(hostname)"
    echo "Date: \$(date)"
    """
}

// Process to test file operations
process createFile {
    publishDir 'results', mode: 'copy'

    input:
    val x

    output:
    path "test_${x}.txt"

    script:
    """
    echo "Test file ${x}" > test_${x}.txt
    echo "Created on: \$(date)" >> test_${x}.txt
    echo "Hostname: \$(hostname)" >> test_${x}.txt
    """
}

// Process to check reference data staging
process checkRefData {
    publishDir 'results', mode: 'copy'
    debug true

    output:
    path "refdata_check.txt"

    script:
    """
    echo "=== Reference Data Check ===" > refdata_check.txt
    echo "Checking path: ${params.refdata_path}" >> refdata_check.txt
    echo "Hostname: \$(hostname)" >> refdata_check.txt
    echo "Date: \$(date)" >> refdata_check.txt
    echo "" >> refdata_check.txt

    echo "Contents of /mnt/nvme/refdata:" >> refdata_check.txt
    ls -lh /mnt/nvme/refdata >> refdata_check.txt 2>&1
    echo "" >> refdata_check.txt

    if [ -d "${params.refdata_path}" ]; then
        echo "SUCCESS: Directory exists" >> refdata_check.txt
        echo "" >> refdata_check.txt
        echo "Directory listing:" >> refdata_check.txt
        ls -lh ${params.refdata_path} >> refdata_check.txt 2>&1
    else
        echo "ERROR: Directory does not exist" >> refdata_check.txt
        echo "Available mounts:" >> refdata_check.txt
        df -h >> refdata_check.txt 2>&1
    fi
    """
}

// Process to merge results
process mergeResults {
    publishDir 'results', mode: 'copy'

    input:
    path files
    path refdata_check

    output:
    path "summary.txt"

    script:
    """
    echo "=== Azure Batch Test Summary ===" > summary.txt
    echo "Processed ${files.size()} files" >> summary.txt
    echo "" >> summary.txt
    cat ${files} >> summary.txt
    echo "" >> summary.txt
    echo "=== Reference Data Check ===" >> summary.txt
    cat ${refdata_check} >> summary.txt
    echo "" >> summary.txt
    echo "Test completed at: \$(date)" >> summary.txt
    """
}

// Main workflow
workflow {
    // Create a channel with numbers 1 to params.count
    numbers = Channel.of(1..params.count)

    // Run the hello process
    sayHello(numbers)

    // Create test files
    test_files = createFile(numbers)

    // Check reference data staging
    refdata_check = checkRefData()

    // Collect and merge all files
    mergeResults(test_files.collect(), refdata_check)
}

workflow.onComplete {
    println "Pipeline completed!"
    println "Status: ${workflow.success ? 'SUCCESS' : 'FAILED'}"
    println "Duration: ${workflow.duration}"
}
