process MOCK_BLASTN {

    label 'daff_tax_assign'

    input:
    path(fasta) // Input FASTA file (can be gzipped) - same interface as BLAST_BLASTN
    val ready   // Readiness flag - same interface as BLAST_BLASTN
    path(test_output) // Test output file to copy

    output:
    path("${task.ext.blast_xml_filename}"), emit: blast_output // Mock BLAST XML output
    path "${task.ext.versions_yml}"           , emit: versions         // Mock BLAST version info

    publishDir "${params.outdir}", mode: 'copy', pattern: "${task.ext.blast_xml_filename}" // Publish mock BLAST XML to output directory
    
    when:
    task.ext.when == null || task.ext.when 

    script:
    """
    echo "MOCK: Skipping actual BLAST execution for testing purposes"
    echo "MOCK: Input fasta: ${fasta}"
    echo "MOCK: Copying test output file to ${task.ext.blast_xml_filename}"
    
    # Copy the test output file to the expected output location only if it doesn't exist
    if [ ! -f ${task.ext.blast_xml_filename} ]; then
        cp ${test_output} ${task.ext.blast_xml_filename}
        
        # Verify the file was copied successfully
        if [ ! -f ${task.ext.blast_xml_filename} ]; then
            echo "ERROR: Failed to copy mock BLAST output file" >&2
            exit 1
        fi
    else
        echo "MOCK: Output file already exists, skipping copy"
    fi
    
    echo "MOCK: Successfully copied test BLAST output (\$(wc -l < ${task.ext.blast_xml_filename}) lines)"

    # Record a mock BLAST version
    cat <<-END_VERSIONS > ${task.ext.versions_yml}
    "${task.process}":
        blast: 2.16.0+ (MOCK)
    END_VERSIONS
    """
}