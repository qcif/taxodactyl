process BLAST_BLASTN {

    label 'blast'

    containerOptions "--bind ${file(params.blastdb).parent}"

    input:
    path(fasta) // Input FASTA file (can be gzipped)
    val ready   // Readiness flag

    output:
    path("$params.blast_xml_filename"), emit: blast_output // BLAST XML output
    path "versions.yml"           , emit: versions         // BLAST version info

    publishDir "${params.outdir}", mode: 'copy', pattern: "$params.blast_xml_filename" // Publish BLAST XML to output directory
    
    when:
    task.ext.when == null || task.ext.when 

    script:
    def is_compressed = fasta.getExtension() == "gz" ? true : false
    def fasta_name = is_compressed ? fasta.getBaseName() : fasta

    """
    # Decompress input FASTA if it is gzipped
    if [ "${is_compressed}" == "true" ]; then
        gzip -c -d ${fasta} > ${fasta_name}
    fi

    # Run BLASTN with specified parameters
    blastn \\
        -num_threads ${task.cpus} \\
        -db ${file(params.blastdb)} \\
        -query ${fasta_name} \\
        -outfmt 5 \\
        -out $params.blast_xml_filename \\
        -task megablast \\
        -max_target_seqs 500 \\
        -evalue 0.05 \\
        -reward 1 \\
        -penalty -3

    # Record the BLAST version used
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        blast: \$(blastn -version 2>&1 | sed 's/^.*blastn: //; s/ .*\$//')
    END_VERSIONS
    """
}

