
This document provides a comprehensive technical overview of the `qcif/taxapus` workflow. It describes the structure and function of the main pipeline scripts, subworkflows, and modules, as well as the configuration files and schemas that control pipeline behaviour. You will find detailed explanations of each process, how data flows through the workflow, and guidance on customisation, container usage, and parameter management. This guide is intended for users and developers who want to understand, modify, or extend the pipeline for their own for their own bioinformatics applications.

# [main.nf](../main.nf)

This is the pipeline entry point script. It handles parameter parsing and validation, initial setup, calls the main workflow defined in [workflows/taxapus.nf](../workflows/taxapus.nf) and finalises the pipeline run (notification emails, reports, etc.). 

---

# Workflows
## [taxapus.nf](../workflows/taxapus.nf)

This is the main Nextflow workflow script for the pipeline. It orchestrates the execution of all modules and subworkflows, defining the overall logic and data flow. The workflow takes input sequences and metadata, performs taxonomic assignment (via BOLD or BLAST), extracts and analyses candidate sequences, builds phylogenetic trees, evaluates publications and database coverage supporting the taxonomic assignment, and generates a comprehensive report.

---

# Subworkflows

These subworkflows were originally developed by [nf-core](https://nf-co.re/docs/guidelines/) and have been adapted for use in this pipeline. 

## [local/utils_nfcore_taxapus_pipeline/main.nf](../subworkflows/local/utils_nfcore_taxapus_pipeline/main.nf)

It defines two subworkflows for pipeline initialisation and completion, adapted from nf-core. Additionally, it includes utility functions for parameter validation, citation text, and methods description formatting for reporting. 

Unlike the original nf-core implementation, the metadata samplesheet is no longer processed or validated within the Nextflow workflow itself. Instead, parsing and validation of metadata - as well as more comprehensive parameter validation - are handled externally by a [Python container](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#p0-validate-inputs). The `validateInputParameters()` function within the workflow still checks for the presence of all required parameters and performs basic logical consistency checks (such as ensuring `blastdb` is set when using `blast_core_nt`, and that certain threshold values are in the correct order), but the main responsibility for input validation has been shifted outside the workflow.

---

## [nf-core/utils_nextflow_pipeline/main.nf](../subworkflows/nf-core/utils_nextflow_pipeline/main.nf)

This subworkflow provides general utility functions for any Nextflow pipeline. The only introduced change is that the functionality for dumping pipeline parameters to a JSON file has been moved to the [main workflow](../workflows/taxapus.nf). This adjustment ensures that the JSON file with parameters is generated in a way that makes it easy to parse and include in the final HTML report.

## [nf-core/utils_nfcore_pipeline/main.nf](../subworkflows/nf-core/utils_nfcore_pipeline/main.nf)

This file provides utility functions for nf-core pipelines, including configuration checks, workflow version reporting, terminal log colouring, and sending summary emails or notifications (e.g. on completion or failure). It helps ensure users are informed about pipeline status and results, and supports standardised reporting and notifications. No changes were introduced to this file.

## [nf-core/utils_nfschema_plugin/main.nf](../subworkflows/nf-core/utils_nfschema_plugin/main.nf)

This subworkflow (`UTILS_NFSCHEMA_PLUGIN`) uses the nf-schema plugin to validate pipeline parameters and print a summary of parameters that differ from the defaults defined in the JSON schema. It can optionally validate parameters against a specified schema file and outputs a summary to the log. No changes were introduced to this file.

---

# Modules

## [configure/environment](../modules/configure/environment/main.nf)

This module generates an environment variables file (`env_vars.sh`) containing all relevant parameters required by the [Python Taxonomic Assignment workflow modules](https://github.com/qcif/daff-biosecurity-wf2). The generated file is sourced by the Nextflow modules that call these Python modules, ensuring consistent parameter passing throughout the workflow. More information about the environment variables and their usage can be found [here](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#environment-variables).

## [validate/input](../modules/validate/input/main.nf)

This process (`VALIDATE_INPUT`) runs a Python validation script inside a container to check the input files and parameters for the workflow. It sources an environment variables file, then calls `p0_validation.py` with paths to the taxonomy database, query FASTA, and metadata CSV. If the database type is BOLD, it adds a `--bold` flag. The process ensures all required inputs are valid before the main analysis begins. More information about the `p0_validation.py` script can be found [here](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#p0-validate-inputs).

## [blast/blastn](../modules/blast/blastn/main.nf)

The `BLAST_BLASTN` process runs a BLASTN search on input FASTA sequences against a specified BLAST database. It supports both uncompressed and gzipped FASTA files, decompressing them if needed. The process uses parameters for the database path, output XML filename, and output directory, and runs BLASTN with the following options:

- `-num_threads ${task.cpus}`: Number of CPU threads to use.
- `-db ${file(params.blastdb)}`: Path to the BLAST database.
- `-query ${fasta_name}`: Input FASTA file with query sequences.
- `-outfmt 5`: Output format set to XML.
- `-out $params.blast_xml_filename`: Output XML filename.
- `-task megablast`: Uses the megablast algorithm for highly similar sequences.
- `-max_target_seqs 500`: Reports up to 500 hits per query.
- `-evalue 0.05`: E-value threshold for reporting matches.
- `-reward 1`: Match reward score.
- `-penalty -3`: Mismatch penalty score.

The results are saved as an XML file, and a `versions.yml` file is generated to record the BLAST version used. The process is containerised and binds the BLAST database directory for access.

## [extract/hits](../modules/extract/hits/main.nf)

The `EXTRACT_HITS` process parses BLAST XML results to extract hit information and accession numbers. It takes the environment variables file and the BLAST XML output as input, then runs a Python script (`p1_parse_blast.py`) to generate files listing accessions, hit details in JSON format, and hit sequences in FASTA format. This process is used in the BLAST branch of the workflow, immediately after running BLASTN, to prepare hit data for downstream candidate extraction and analysis. More information about the `p1_parse_blast.py` script can be found [here](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#p1-blast-parser).

## [blast/blastdbcmd](../modules/blast/blastdbcmd/main.nf)

The `BLAST_BLASTDBCMD` module uses the `blastdbcmd` tool to extract taxonomic IDs for a list of accessions from a BLAST database. It takes a batch file of accession numbers as input and outputs a CSV file mapping accessions to taxids (`taxids.csv`). This module is used in the BLAST branch of the workflow, after extracting hits from BLASTN results, to retrieve taxonomic information needed for downstream taxonomy extraction and analysis.

## [extract/taxonomy](../modules/extract/taxonomy/main.nf)

The `EXTRACT_TAXONOMY` module runs a Python script (`p2_extract_taxonomy.py`) to extract taxonomy information for a list of taxids using the NCBI taxonomy database. It takes an environment variables file and a CSV of taxids as input, and outputs a taxonomy file. This module is used after retrieving taxids from BLAST hits, providing detailed taxonomy data needed for downstream candidate extraction and reporting. More information about the `p2_extract_taxonomy.py` script can be found [here](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#p2-ncbi-taxonomy-extractor).

## [bold/search](../modules/bold/search/main.nf)

The `BOLD_SEARCH` module runs a Python script (`p1_bold_search.py`) to perform a taxonomic assignment search using the BOLD database. It takes an environment variables file and a FASTA file as input, and outputs a taxonomy JSON file and hit files (JSON and FASTA) for each query. This module is used in the BOLD branch of the workflow as an alternative to the BLAST-based search, providing taxonomic assignments and hit details based on BOLD data.

## [extract/candidates](../modules/extract/candidates/main.nf)

The `EXTRACT_CANDIDATES` module runs a Python script (`p3_assign_taxonomy.py`) to extract and process candidate sequences from BLAST or BOLD hits for each query. It takes as input the environment variables file, hit files (JSON and FASTA), taxonomy file, and metadata, and outputs candidate information in multiple formats (JSON, CSV, FASTA), as well as summary and flag files for downstream analysis. This module is used after taxonomy extraction to prepare candidate data for alignment, source diversity, and database coverage evaluation. For phylogenetic analysis, a FASTA file is generated containing a subset of sequences from the BLAST or BOLD hits. The selection is based on identity thresholds and a minimum number of sequences. Specifically, hits are sorted by identity, and accessions are included as long as the identity is above a minimum threshold or until a minimum number of sequences is reached. More information about the `p3_assign_taxonomy.py` script can be found [here](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#p3-evaluate-taxonomy).

## [evaluate/sourcediversity](../modules/evaluate/sourcediversity/main.nf)

The `EVALUATE_SOURCE_DIVERSITY` module runs a Python script (`p4_source_diversity.py`) to assess the diversity of sources, such as publications, supporting candidate taxonomic assignments for each query. It takes the environment variables file and a candidate JSON file as input, and outputs a JSON file summarising independent sources for each query. This module is used after candidate extraction to provide additional evidence for taxonomic assignments. Only candidate sets with the maximum allowed count (`params.max_candidates_for_analysis`) are passed on for source diversity analysis. More information about the `p4_source_diversity.py` script can be found [here](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#p4-analysis-of-reference-sequence-publications).

## [evaluate/databasecoverage](../modules/evaluate/databasecoverage/main.nf)

The `EVALUATE_DATABASE_COVERAGE` module runs a Python script (`p5_db_coverage.py`) to assess database coverage for candidate sequences in each query. It takes the environment variables file, a candidate JSON file, and metadata as input and outputs results to the query folder. This module is used after candidate extraction to evaluate how well candidate taxa are represented in the reference database, supporting downstream reporting and analysis. More information about the `p5_db_coverage.py` script can be found [here](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#p5-analysis-of-database-coverage).

## [mafft/align](../modules/mafft/align/main.nf)

The `MAFFT_ALIGN` module performs multiple sequence alignment using the MAFFT tool. It takes as input a FASTA file containing the selected candidate sequences for phylogenetic analysis (generated by the `EXTRACT_CANDIDATES` module) and the query sequence, combines them, and runs MAFFT to produce an alignment in PHYLIP format. The aligned sequences are output to a specified file, and a `versions.yml` file is generated to record the MAFFT version used. 

## [fastme](../modules/fastme/main.nf)

The `FASTME` module performs phylogenetic tree construction using the FastME tool. It takes as input a PHYLIP alignment file of DNA sequences (`-d`) produced by the `MAFFT_ALIGN` module and outputs a Newick tree file (`*.nwk`), a statistics file (`*_stat.txt`), and a distance matrix (`*.matrix.phy`). The module also generates a `versions.yml` file to record the FastME version used. 

## [report](../modules/report/main.nf)

The `REPORT` module generates the final HTML report for each query. It collects all relevant outputs from previous steps - including hits, phylogenetic trees, candidate data, database coverage, source diversity, version info, parameters, timestamps, taxonomy, and metadata - organises them into the query folder, and runs the Python script [`p6_report.py`](https://github.com/qcif/daff-biosecurity-wf2/tree/v1.0.0?tab=readme-ov-file#p6-report-generation) to produce the report.

> [!NOTE]
> - The modules for BLAST (`blast/blastn` and `blast/blastdbcmd`), MAFFT (`mafft/align`), and FastME (`fastme`) were originally downloaded from nf-core and have been adjusted as needed for this pipeline. 
> - To publish a file to the output directory, use the `publishDir` directive within your process definition. This directive specifies where output files should be copied or moved after the process completes, e.g. `publishDir "${params.outdir}", mode: 'copy', pattern: "$params.blast_xml_filename"`. More information in the [Nextflow documentation]( https://www.nextflow.io/docs/latest/process.html). 
> - Some input parameters are not parsed to the scripts executed in the modules as arguments, but rather using the environment variables. In those cases, we need to ensure they are available within the module’s container, e.g. `containerOptions "--bind ${file(params.sequences).parent}"`.

---

# Configuration

The pipeline uses several configuration files located in the [`conf/` folder](../conf/). They are all linked to the pipeline using [nextflow.config](../nextflow.config) file placed in the main project directory. See the [Nextflow configuration documentation](https://www.nextflow.io/docs/latest/config.html) for more details.

## [`conf/params.config`](../conf/params.config) 
Defines all pipeline parameters and their default values, such as input file names, thresholds, and output file names. These parameters can be overridden by user-supplied config files, command-line options or directly in this file. See the [customisation document](customise.md) for examples.

## [`conf/process.config`](../conf/process.config)
Sets default resource requirements (CPUs, memory, time) and container images for each process or process label. It also defines the default error strategy and bash options for process execution. You can override these settings as required. See the [customisation document](customise.md) for examples of assigning different resources or error strategies to the processes. 

You can also change the container for a process but we cannot guarantee the compatibility in downstream analysis. Currently, the following containers are used by each process or process label:

| Process / Label         | Container Image                                                                                   |
|------------------------ |--------------------------------------------------------------------------------------------------|
| `daff_tax_assign` label (`EXTRACT_HITS`, `EXTRACT_TAXONOMY`, `BOLD_SEARCH`, `EXTRACT_CANDIDATES`, `EVALUATE_SOURCE_DIVERSITY`, `EVALUATE_DATABASE_COVERAGE`, `REPORT`) | `docker://neoformit/daff-taxonomic-assignment:v1.0.0`                                            |
| `blast` label (`BLAST_BLASTN`, `BLAST_BLASTDBCMD`)          | `docker://ncbi/blast:2.16.0`                                                                     |
| `MAFFT_ALIGN`           | `quay.io/biocontainers/mulled-v2-12eba4a074f913c639117640936668f5a6a01da6:425707898cf4f85051b77848be253b88f1d2298a-0` |
| `FASTME`                | `quay.io/biocontainers/fastme:2.1.6.3--h7b50bb2_1`                                               |

Use `withLabel` or `withName` selectors to specify a container. If a process matches both a `withLabel` and a `withName` rule, the most specific rule (usually `withName`) takes precedence for the container.

## [`conf/profiles.config`](../conf/profiles.config)
Contains execution profiles for different environments (e.g., `singularity`, `docker`, `conda`, `apptainer`, `test`). Profiles can enable or disable container engines and set other environment-specific options. This pipeline was only tested with the `singularity` and `test` profiles.

## [`conf/test.config`](../conf/test.config)
Provides a minimal test dataset and settings for quick pipeline validation. Used with the `-profile test` option.

## [`conf/validation.config`](../conf/validation.config)
Controls parameter validation and help behaviour, including which parameters are required and how help is displayed.

## [`conf/manifest.config`](../conf/manifest.config)  
Contains pipeline metadata such as name, author, contributors, description, and version.

## [`conf/misc.config`](../conf/misc.config)
Sets miscellaneous environment variables, disables process selector warnings by default, and enables Nextflow reporting plugins (timeline, report, trace, dag).

---

# [nextflow_schema.json](../nextflow_schema.json)

This file defines the Nextflow schema for pipeline parameters. It is used for parameter validation and help text generation. If you add a parameter here, remember to initialise its value in [params.config](../conf/params.config). For more information about the Nextflow schema specification and how to use or customise pipeline parameter schemas, see the [Nextflow Schema Specification](https://nextflow-io.github.io/nf-validation/nextflow_schema/nextflow_schema_specification/) or [nf-core Tools: Pipeline Schema Documentation](https://nf-co.re/docs/nf-core-tools/pipelines/schema).

---

# [schema_input.json](../assets/schema_input.json)

This JSON schema describes the required structure and columns for the metadata CSV file used as input to the pipeline. If you need to add columns or change the metadata format, update this schema accordingly to ensure proper validation and compatibility. The [Python P6 module](https://github.com/qcif/daff-biosecurity-wf2/tree/v1.0.0?tab=readme-ov-file#p6-report-generation) will handle the additional columns and put the metadata in the report.

---

# [loci.json](../assets/loci.json)

This file defines the permitted loci (genes) and their synonyms used in the pipeline. It helps standardise locus names and supports synonym resolution for GenBank queries. For more details on how loci are used and formatted, see the [sample locus section in the Python modules README](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#sample-locus). 

You can overwrite the contents of `loci.json` to customise which loci (genes) and synonyms are recognised by the pipeline. To do this:

1. **Edit the File:**  
   Open [`assets/loci.json`](../assets/loci.json) and modify, add, or remove loci and their synonyms as needed for your use case. Make sure the JSON structure matches the expected format described in the [Python modules README](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#sample-locus).

2. **Provide a Custom File:**  
   If you want to keep the original file unchanged, you can create your own custom `loci.json` and specify its path using the appropriate pipeline parameter (e.g., `--allowed_loci_file my_loci.json` on the command line or by setting `allowed_loci_file` in your config).

3. **Using a Config File:**  
   You can also set the path to your custom loci file in a Nextflow config file (such as `params.config` or a custom config), for example:
   ```nextflow
   params {
     allowed_loci_file = '/path/to/my_loci.json'
   }


