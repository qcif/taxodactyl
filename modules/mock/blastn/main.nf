process MOCK_BLASTN {

    label 'daff_tax_assign'

    input:
    path(fasta) // Input FASTA file (can be gzipped) - same interface as BLAST_BLASTN
    val ready   // Readiness flag - same interface as BLAST_BLASTN

    output:
    path("$params.blast_xml_filename"), emit: blast_output // Mock BLAST XML output
    path "versions.yml"           , emit: versions         // Mock BLAST version info

    publishDir "${params.outdir}", mode: 'copy', pattern: "$params.blast_xml_filename" // Publish mock BLAST XML to output directory
    
    when:
    task.ext.when == null || task.ext.when 

    script:
    """
    echo "MOCK: Skipping actual BLAST execution for testing purposes"
    echo "MOCK: Input fasta: ${fasta}"
    echo "MOCK: Copying test output file to ${params.blast_xml_filename}"
    
    # Copy the test output file to the expected output location
    cp ${projectDir}/scripts/tests/test-data/output.xml ${params.blast_xml_filename}
    
    # Verify the file was copied successfully
    if [ ! -f ${params.blast_xml_filename} ]; then
        echo "ERROR: Failed to copy mock BLAST output file" >&2
        exit 1
    fi
    
    echo "MOCK: Successfully copied test BLAST output (\$(wc -l < ${params.blast_xml_filename}) lines)"

    # Record a mock BLAST version
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        blast: 2.16.0+ (MOCK)
    END_VERSIONS
    """
}