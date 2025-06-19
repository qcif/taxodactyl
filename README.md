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

**Software**

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

**TaxonKit**

Download the NCBI taxonomy data files from https://ftp.ncbi.nih.gov/pub/taxonomy/taxdump.tar.gz and extract them to `~/.taxonkit`. Similarly, download the taxonkit tool from https://github.com/shenwei356/taxonkit/releases and move into the same folder.

**NCBI core nt database**

To search sequences against the NCBI core nt database, you must download the BLAST-formatted core nt database from NCBI. We recommend running the `update_blastdb.pl` program. Follow instructions from [this book](https://www.ncbi.nlm.nih.gov/books/NBK569850/). [Perl installation](https://www.perl.org/get.html) is required.
The command should look like this:
`perl ~/ncbi-blast-2.16.0+/bin/update_blastdb.pl --decompress core_nt`

**Sequences file (`queries.fasta`)**

You will need a FASTA file containing the query sequences (up to 100), e.g.
```
>VE24-1075_COI
TGGATCATCTCTTAGAATTTTAATTCGATTAGAATTAAGACAAATTAATTCTATTATTWATAATAATCAATTATATAATGTAATTGTTCACAATTCATGCTTTTATTATAATTTTTTTTATAACTATACCAATTGTAATTGGTGGATTTGGAAATTGATTAATTCCTATAATAATAGGATGTCCTGATATATCATTTCCACSTTTAAATAATATTAGATTTTGATTATTACCTCCATCATTAATAATAATAATTTGTAGATTTTTAATTAATAATGGAACAGGAACAGGATGAACAATTTAYCCHCCTTTATCAAACAATATTGCACATAATAACATTTCAGTTGATTTAACTATTTTTTCTTTACATTTAGCAGGWATCTCATCAATTTTAGGAGCAATTAACTTTATTTGTACAATTCTTAATATAATAYCAAAYAATATAAAACTAAATCAAATTCCTCTTTTTCCTTGATCAATTTTAATTACAGCTATTTTATTAATTTTATMTTTACCAGTTTTAGCTGGTGCCATTACAATATTATTAACTGATCGTAATTTAAATACATCATTTTTGATCCAGCAGGAGGAGGAGATCC
>VE24-1079_COI
AACTTTATATTTCATTTTTGGAATATGGGCAGGTATATTAGGAACTTCACTAAGATGAATTATTCGAATTGAACTTGGACAACCAGGATCATTTATTGGAGATGATCAAATTTATAATGTAGTAGTTACCGCACACGCATTTATTATAATTTTCTTTATAGTTATACCAATTATAATTGGAGGATTTGGAAATTGATTAGTACCTCTAATAATTGGAGCACCAGATATAGCATTCCCACGGATAAATAATATAAGATTTTGATTATTACCACCCTCAATTACACTTCTTATTATAAGATCTATAGTAGAAAGAGGAGCAGGAACTGGATGAACAGTATATCCCCCACTATCATCAAATATTGCACATAGTGGAGCATCAGTAGACCTAGCAATTTTTTCACTACATTTAGCAGGTGTATCTTCAATTTTAGGAGCAATTAATTTCATCTCAACAATTATTAATATACGACCTGAAGGCATATCTCCAGAACGAATTCCATTATTTGTATGATCAGTAGGTATTACAGCATTACTATTATTATTATCATTACCAGTTCTAGCTGGAGCTATTACAATATTATTAACAGATCGAAACTTTAATACCTCATTCTTTGACCCAGTAGGAGGAGGAGATCCTATCTTATATCAACATTTATTTTGATTTTTT
```

**Metadata file (`metadata.csv`)**

The metadata file provides essential information about each sequence and must follow the structure below. Each row corresponds to a sample and should include required and, optionally, additional columns.

#### Required Columns
1. **sample_id** - Unique identifier for the sample. Must match the sequence ID in the `queries.fasta` file. Cannot contain spaces.
2. **locus** - Name of the genetic locus for the sample. Check available loci in `assets/loci.json`. You can override allowed loci by setting the `allowed_loci_file` parameter. For samples with no locus (e.g., viruses or BOLD runs), enter `NA`.
3. **preliminary_id** - Preliminary morphology ID of the sample.

#### Optional Columns
1. **taxa_of_interest** - Taxa of interest for the sample. If multiple, separate them with a `|` character.
2. **host** - Host organism of the sample.
3. **country** - Country of origin for the sample.
4. **sequencing_platform** - Sequencing platform used for the sample.
5. **sequencing_read_coverage** - Sequencing read coverage for the sample.

#### Example

<table>
    <thead>
        <tr>
            <th>sample_id</th>
            <th>locus</th>
            <th>preliminary_id</th>
            <th>taxa_of_interest</th>
            <th>host</th>
            <th>country</th>
            <th>sequencing_platform</th>
            <th>sequencing_read_coverage</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>VE24-1075_COI</td>
            <td>COI</td>
            <td>Aphididae</td>
            <td>Myzus persicae | Aphididae</td>
            <td>Cut flower Rosa</td>
            <td>Ecuador</td>
            <td>Illumina</td>
            <td>100x</td>
        </tr>
        <tr>
            <td>VE24-1079_COI</td>
            <td>COI</td>
            <td>Miridae</td>
            <td>Lygus pratensis</td>
            <td>Cut flower Paenonia</td>
            <td>Netherlands</td>
            <td>Nanopore</td>
            <td>50x</td>
        </tr>
    </tbody>
</table>

> [!NOTE]
> - All required columns must be present for every sample.
> - Optional columns can be left blank if not applicable.
> - For more details on the metadata schema, see [`assets/schema_input.json`](assets/schema_input.json).


