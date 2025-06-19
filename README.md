# daff/taxassignwf

## Introduction

**daff/taxassignwf** is a modular, reproducible Nextflow workflow for the conservative taxonomy assignment to DNA sequences, designed for high-confidence, auditable results in biosecurity and biodiversity contexts. The workflow integrates multiple bioinformatics tools and databases, automates best-practice analysis steps, and produces detailed reports with supporting evidence for each taxonomic assignment.
<p align="center" style="max-width:400px; margin:auto;">
    <img src="docs/images/daff-wf2.png" alt="daff-tax-assignment-wf2-diagram" width="350"/>
</p>

### Workflow Overview

The pipeline orchestrates a series of analytical steps, each encapsulated in a dedicated module or subworkflow. The main stages are:

1. **Environment Configuration** Sets up environment variables and paths required for downstream processes, ensuring reproducibility and portability.

2. **Input Validation** Checks the integrity and compatibility of input files (FASTA sequences, metadata, databases), preventing downstream errors.

3. **Sequence Search**  
   - **NCBI core nt (BLASTN):** Queries input sequences against the NCBI nucleotide database using BLASTN.
   - **BOLD (API):** Queries input sequences against the Barcode of Life Data. Taxonomic lineage included in the results.

4. **Hit Extraction** Parses BLAST results to extract relevant hits for each query.

5. **Taxonomic ID Extraction** Retrieves taxonomic IDs for BLAST hits.

6. **Taxonomic Lineage Extraction** Maps taxonomic IDs to full lineages, enabling downstream filtering and reporting.

7. **Candidate Extraction** Identifies candidate species for each query, applying user-defined thresholds for identity and coverage.

8. **Supporting Evidence Evaluation**  
   - **Publications Diversity:** Assesses the diversity of data sources supporting each candidate.
   - **Database Coverage:** Evaluates the representation of candidates in global databases (GBIF, NCBI, BOLD).

9. **Multiple Sequence Alignment (MAFFT)** Aligns candidate and query sequences to prepare for phylogenetic analysis.

10. **Phylogenetic Tree Construction (FASTME)** Builds a phylogenetic tree to visualise relationships among candidates and queries.

11. **Comprehensive Reporting** Generates detailed HTML and text reports, including sequence alignments, phylogenetic trees, database coverage, and all supporting evidence for each assignment.

## Usage

### Software

To run the **daff/taxassignwf** pipeline, you will need the following software installed:

- **Nextflow**  
  *Tested versions: 24.10.3, 24.10.6*  

- **Java**  
  Required by Nextflow.  
  *Tested version: 17.0.13*  

- **Singularity**  
  Used for containerised execution of all bioinformatics tools, ensuring reproducibility.  
  *Tested version: 3.7.0*  

> [!NOTE]
> If you are new to these programs, more details are available [here](docs/software.md).

