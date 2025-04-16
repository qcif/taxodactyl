# daff/taxassignwf

<!-- TODO [![GitHub Actions CI Status](https://github.com/daff/taxassignwf/actions/workflows/ci.yml/badge.svg)](https://github.com/daff/taxassignwf/actions/workflows/ci.yml)
[![GitHub Actions Linting Status](https://github.com/daff/taxassignwf/actions/workflows/linting.yml/badge.svg)](https://github.com/daff/taxassignwf/actions/workflows/linting.yml)[![Cite with Zenodo](http://img.shields.io/badge/DOI-10.5281/zenodo.XXXXXXX-1073c8?labelColor=000000)](https://doi.org/10.5281/zenodo.XXXXXXX)
[![nf-test](https://img.shields.io/badge/unit_tests-nf--test-337ab7.svg)](https://www.nf-test.com)

[![Nextflow](https://img.shields.io/badge/nextflow%20DSL2-%E2%89%A524.04.2-23aa62.svg)](https://www.nextflow.io/)
[![run with conda](http://img.shields.io/badge/run%20with-conda-3EB049?labelColor=000000&logo=anaconda)](https://docs.conda.io/en/latest/)
[![run with docker](https://img.shields.io/badge/run%20with-docker-0db7ed?labelColor=000000&logo=docker)](https://www.docker.com/)
[![run with singularity](https://img.shields.io/badge/run%20with-singularity-1d355c.svg?labelColor=000000)](https://sylabs.io/docs/)
[![Launch on Seqera Platform](https://img.shields.io/badge/Launch%20%F0%9F%9A%80-Seqera%20Platform-%234256e7)](https://cloud.seqera.io/launch?pipeline=https://github.com/daff/taxassignwf) -->

<!-- TODO ## Introduction -->

<!-- TODO **daff/taxassignwf** is a bioinformatics pipeline that ... -->

<!-- TODO nf-core:
   Complete this sentence with a 2-3 sentence summary of what types of data the pipeline ingests, a brief overview of the
   major pipeline sections and the types of output it produces. You're giving an overview to someone new
   to nf-core here, in 15-20 seconds. For an example, see https://github.com/nf-core/rnaseq/blob/master/README.md#introduction
-->

<!-- TODO nf-core: Include a figure that guides the user through the major workflow steps. Many nf-core
     workflows use the "tube map" design for that. See https://nf-co.re/docs/contributing/design_guidelines#examples for examples.   -->
<!-- TODO nf-core: Fill in short bullet-pointed list of the default steps in the pipeline -->

## Prerequisites

### Software

1. Instructions on how to set up Nextflow and a compatible version of Java on [this page](https://www.nextflow.io/docs/latest/install.html#installation).
2. To install singularity follow instructions from [this website](https://docs.sylabs.io/guides/3.7/admin-guide/installation.html#before-you-begin).

The following versions of the programs were used to test this pipeline:

<table border="1" style="border-collapse: collapse;">
    <tr>
        <th style="border: 1px solid;">Program</th>
        <th style="border: 1px solid;">Version</th>
    </tr>
    <tr>
        <td style="border: 1px solid;">Singularity</td>
        <td style="border: 1px solid;">3.7.0</td>
    </tr>
    <tr>
        <td style="border: 1px solid;">Java</td>
        <td style="border: 1px solid;">17.0.13</td>
    </tr>
    <tr>
        <td style="border: 1px solid;">Nextflow</td>
        <td style="border: 1px solid;">24.10.3</td>
    </tr>
</table>

### Databases
1. Download a preformatted NCBI BLAST database `core_nt` database by running the update_blastdb.pl program. Follow instructions from [this book](https://www.ncbi.nlm.nih.gov/books/NBK569850/). [Perl installation](https://www.perl.org/get.html) is required.
The command should look like this:
`perl ~/ncbi-blast-2.16.0+/bin/update_blastdb.pl --decompress core_nt`
2. Download the NCBI taxonomy data files from https://ftp.ncbi.nih.gov/pub/taxonomy/taxdump.tar.gz and extract them to `~/.taxonkit`. Similarly, download the taxonkit tool from https://github.com/shenwei356/taxonkit/releases and move into the same folder.

### Download pipeline
Enter the folder where you want the pipeline to be and run the following:
```
git clone https://github.com/qcif/nf-daff-biosecurity-wf2.git
```
If you want to run a specific version, add a branch to the command (see tags for available versions), e.g.
```
git clone https://github.com/qcif/nf-daff-biosecurity-wf2.git --branch v0.1.0
```

## Input
### Required
The mandatory input includes the following parameters:
- metadata /path/to/metadata.csv: The metadata file containing information about the sequences.
- sequences /path/to/queries.fasta: The FASTA file containing the query sequences (up to 100).
- blastdb /path/to/blastdbs/core_nt: The BLAST database to be used for query searching. Your `/path/to/blastdbs` folder should contain the following files:
- core_nt with extensions `.nal`, `.ndb`, `.njs`, `.nos`, `.not`, `.ntf` and `.nto`
- multiple volumes of core_nt, named core_nt.`NUM` with extensions `.nhr`, `.nin`, `.nnd`, `.nni`, `.nog`, `.nsq`
- taxdb.btd and taxdb.bti files
- outdir /path/to/output: The output directory where the results will be stored.
- taxdb /path/to/.taxonkit/: The path to the taxonomic database NCBI Taxonomy Toolkit. Following files should be available in that folder: citations.dmp, division.dmp, gencode.dmp, merged.dmp, nodes.dmp, taxonkit, delnodes.dmp, gc.prt, images.dmp, names.dmp and readme.txt

### Recommended
You can [generate an NCBI API key](https://support.nlm.nih.gov/kbArticle/?pn=KA-05317) to eliminate restrictions on Entrez queries and make the database coverage evaluation process faster. Pass it with the following parameters:
- ncbi_api_key <your_key_123>
- user_email <me@example.com>


### Sequences file (`queries.fasta`)
#### Example
```
>VE24-1075_COI
TGGATCATCTCTTAGAATTTTAATTCGATTAGAATTAAGACAAATTAATTCTATTATTWATAATAATCAATTATATAATGTAATTGTTCACAATTCATGCTTTTATTATAATTTTTTTTATAACTATACCAATTGTAATTGGTGGATTTGGAAATTGATTAATTCCTATAATAATAGGATGTCCTGATATATCATTTCCACSTTTAAATAATATTAGATTTTGATTATTACCTCCATCATTAATAATAATAATTTGTAGATTTTTAATTAATAATGGAACAGGAACAGGATGAACAATTTAYCCHCCTTTATCAAACAATATTGCACATAATAACATTTCAGTTGATTTAACTATTTTTTCTTTACATTTAGCAGGWATCTCATCAATTTTAGGAGCAATTAACTTTATTTGTACAATTCTTAATATAATAYCAAAYAATATAAAACTAAATCAAATTCCTCTTTTTCCTTGATCAATTTTAATTACAGCTATTTTATTAATTTTATMTTTACCAGTTTTAGCTGGTGCCATTACAATATTATTAACTGATCGTAATTTAAATACATCATTTTTGATCCAGCAGGAGGAGGAGATCC
>VE24-1079_COI
AACTTTATATTTCATTTTTGGAATATGGGCAGGTATATTAGGAACTTCACTAAGATGAATTATTCGAATTGAACTTGGACAACCAGGATCATTTATTGGAGATGATCAAATTTATAATGTAGTAGTTACCGCACACGCATTTATTATAATTTTCTTTATAGTTATACCAATTATAATTGGAGGATTTGGAAATTGATTAGTACCTCTAATAATTGGAGCACCAGATATAGCATTCCCACGGATAAATAATATAAGATTTTGATTATTACCACCCTCAATTACACTTCTTATTATAAGATCTATAGTAGAAAGAGGAGCAGGAACTGGATGAACAGTATATCCCCCACTATCATCAAATATTGCACATAGTGGAGCATCAGTAGACCTAGCAATTTTTTCACTACATTTAGCAGGTGTATCTTCAATTTTAGGAGCAATTAATTTCATCTCAACAATTATTAATATACGACCTGAAGGCATATCTCCAGAACGAATTCCATTATTTGTATGATCAGTAGGTATTACAGCATTACTATTATTATTATCATTACCAGTTCTAGCTGGAGCTATTACAATATTATTAACAGATCGAAACTTTAATACCTCATTCTTTGACCCAGTAGGAGGAGGAGATCCTATCTTATATCAACATTTATTTTGATTTTTT
```

### Metadata file (`metadata.csv`)

The `metadata.csv` file should adhere to the following structure

#### Required Columns
1. **sample_id** - needs to match the sequence id from the `queries.fasta` file
2. **locus**
3. **preliminary_id**

#### Optional Columns
1. **taxa_of_interest** - if multiple, they should be separated by a `|` character
2. **host**
3. **country**

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
        </tr>
        <tr>
            <td>VE24-1079_COI</td>
            <td>COI</td>
            <td>Miridae</td>
            <td>Lygus pratensis</td>
            <td>Cut flower Paenonia</td>
            <td>Netherlands</td>
        </tr>
    </tbody>
</table>

<!-- TODO nf-core: Describe the minimum required steps to execute the pipeline, e.g. how to prepare samplesheets.
     Explain what rows and columns represent. For instance (please edit as appropriate):

First, prepare a samplesheet with your input data that looks as follows:

`samplesheet.csv`:

```csv
sample,fastq_1,fastq_2
CONTROL_REP1,AEG588A1_S1_L002_R1_001.fastq.gz,AEG588A1_S1_L002_R2_001.fastq.gz
```

Each row represents a fastq file (single-end) or a pair of fastq files (paired end).

-->

### Configuration file
The error strategy for the workflow is set to `ignore`. It means that even if a process encounters an error, Nextflow will continue executing subsequent processes rather than terminating the workflow. This is to avoid interrupting the entire workflow with multiple queries when only one of them fails. To overwrite, create a file named nextflow.config, if it does not already exist, in the execution folder. Add or modify the following block in nextflow.config to specify the error strategy 
```
process {
    errorStrategy = 'ignore'
}
```
Replace `ignore` with the desired error handling strategy, such as `terminate`, `retry`, or `finish`, depending on the desired behavior. See https://www.nextflow.io/docs/latest/reference/process.html#process-error-strategy for details. 

## Running the pipeline
You can run the pipeline using:

<!-- TODO nf-core: update the following command to include all required parameters for a minimal example -->

```bash
nextflow run /path/to/pipeline/nf-daff-biosecurity-wf2/main.nf \
    --metadata /path/to/metadata.csv \
    --sequences /path/to/queries.fasta \
    --blastdb /path/to/blastdbs/core_nt \
    --outdir /path/to/output \
    -profile singularity \
    --taxdb /path/to/.taxonkit/ \
    --ncbi_api_key API_KEY \
    --user_email EMAIL \
    -resume
```

## Results folder structure
```
output/
├── blast_result.xml
├── pipeline_info
│   ├── execution_report_2025-03-16_20-39-21.html
│   ├── execution_timeline_2025-03-16_20-39-21.html
│   ├── execution_trace_2025-03-16_20-39-21.txt
│   ├── params_2025-03-16_20-39-27.json
│   ├── pipeline_dag_2025-03-16_20-39-21.html
│   ├── taxassignwf_software_versions.yml
│   └── versions.yml
├── query_001_VE24-1075_COI
│   ├── all_blast_hits.fasta
│   ├── candidates.csv
│   ├── candidates.fasta
│   ├── candidates_identity_boxplot.png
│   ├── candidates.msa
│   ├── candidates.nwk
│   └── report_VE24-1075_COI_NOW.html
└── query_002_VE24-1079_COI
    ├── all_blast_hits.fasta
    ├── candidates.csv
    ├── candidates.fasta
    ├── candidates.msa
    ├── candidates.nwk
    └── report_VE24-1079_COI_NOW.html
```

<!-- TODO 
> [!WARNING]
> Please provide pipeline parameters via the CLI or Nextflow `-params-file` option. Custom config files including those provided by the `-c` Nextflow option can be used to provide any configuration _**except for parameters**_; see [docs](https://nf-co.re/docs/usage/getting_started/configuration#custom-configuration-files). -->

## Credits

daff/taxassignwf was originally written by Magdalena Antczak, Cameron Hyde, Daisy Li.

<!-- TODO 

We thank the following people for their extensive assistance in the development of this pipeline:

-->

<!-- TODO nf-core: If applicable, make list of people who have also contributed -->

<!-- TODO 
## Contributions and Support

If you would like to contribute to this pipeline, please see the [contributing guidelines](.github/CONTRIBUTING.md).

## Citations
-->

<!-- TODO nf-core: Add citation for pipeline after first release. Uncomment lines below and update Zenodo doi and badge at the top of this file. -->
<!-- If you use daff/taxassignwf for your analysis, please cite it using the following doi: [10.5281/zenodo.XXXXXX](https://doi.org/10.5281/zenodo.XXXXXX) -->

<!-- TODO nf-core: Add bibliography of tools and data used in your pipeline -->

<!-- TODO 
An extensive list of references for the tools used by the pipeline can be found in the [`CITATIONS.md`](CITATIONS.md) file.

This pipeline uses code and infrastructure developed and maintained by the [nf-core](https://nf-co.re) community, reused here under the [MIT license](https://github.com/nf-core/tools/blob/main/LICENSE).

> **The nf-core framework for community-curated bioinformatics pipelines.**
>
> Philip Ewels, Alexander Peltzer, Sven Fillinger, Harshil Patel, Johannes Alneberg, Andreas Wilm, Maxime Ulysse Garcia, Paolo Di Tommaso & Sven Nahnsen.
>
> _Nat Biotechnol._ 2020 Feb 13. doi: [10.1038/s41587-020-0439-x](https://dx.doi.org/10.1038/s41587-020-0439-x).
-->