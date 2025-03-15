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

The following versions of the programs were used to test this pipeline:

<table border="1" style="border-collapse: collapse;">
    <tr>
        <th style="border: 1px solid;">Program</th>
        <th style="border: 1px solid;">Version</th>
    </tr>
    <tr>
        <td style="border: 1px solid;">Singularity</td>
        <td style="border: 1px solid;">3.10.2-1</td>
    </tr>
    <tr>
        <td style="border: 1px solid;">Java</td>
        <td style="border: 1px solid;">11.0.15.1</td>
    </tr>
    <tr>
        <td style="border: 1px solid;">Nextflow</td>
        <td style="border: 1px solid;">24.10.2</td>
    </tr>
</table>

### Nextflow
If you are new to Nextflow, please refer to [this page](https://www.nextflow.io/docs/latest/install.html#installation) on how to set-up Nextflow.

## Input
The mandatory input includes the following parameters:

--metadata /path/to/metadata.csv: The metadata file containing information about the sequences.

--sequences /path/to/queries.fasta: The FASTA file containing the query sequences (up to 100).

--blastdb /path/to/blastdbs/core_nt: The BLAST database to be used for query searching.

--outdir /path/to/output: The output directory where the results will be stored.

--taxdb /path/to/.taxonkit/: The path to the taxonomic database NCBI Taxonomy Toolkit.

### sequences

### Metadata file (`metadata.csv`)

The `metadata.csv` file should adhere to the following structure

#### Required Columns
1. **sample_id**
2. **locus**
3. **preliminary_id**

#### Optional Columns
1. **taxa_of_interest** - if multiple, they should be separated by |
2. **country**
3. **host**

#### Example
```csv
sample_id,locus,preliminary_id,taxa_of_interest,country,host
sample1,locus1,PMI1,taxa1,USA,host1
sample2,locus2,PMI2,taxa2,CAN,host2
sample3,locus3,PMI3,taxa3|taxa4,UK,host3
```

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

Now, you can run the pipeline using:

<!-- TODO nf-core: update the following command to include all required parameters for a minimal example -->

```bash
nextflow run ../../daff-taxassignwf/main.nf --metadata metadata_bacteria.csv --sequences queries_bacteria.fasta --blastdb ../../../blastdbs/core_nt --outdir output150301 -profile singularity --taxdb ../../../.taxonkit/ -c ../nextflow.config -resume
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