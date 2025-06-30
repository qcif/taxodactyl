> STILL IN PROGRESS



# [main.nf](../main.nf)

This is the pipeline entry point script. It handles parameter parsing and validation, initial setup, calls the main workflow defined in [workflows/taxassignwf.nf](../workflows/taxassignwf.nf) and finalises the pipeline run (notification emails, reports, etc.). 

---

# Workflows
## [taxassignwf.nf](../workflows/taxassignwf.nf)

This is the main Nextflow workflow script for the pipeline. It orchestrates the execution of all modules and subworkflows, defining the overall logic and data flow. The workflow takes input sequences and metadata, performs taxonomic assignment (via BOLD or BLAST), extracts and analyses candidate sequences, builds phylogenetic trees, evaluates publications and database coverage supporting the taxonomic assignment, and generates a comprehensive report.

---

# Subworkflows

These subworkflows were originally developed by [nf-core](https://nf-co.re/docs/guidelines/) and have been adapted for use in this pipeline. 

## [local/utils_nfcore_taxassignwf_pipeline/main.nf](../subworkflows/local/utils_nfcore_taxassignwf_pipeline/main.nf)

It defines two subworkflows for pipeline initialisation and completion, adapted from nf-core. Additionally, it includes utility functions for parameter validation, citation text, and methods description formatting for reporting. 

Unlike the original nf-core implementation, the metadata samplesheet is no longer processed or validated within the Nextflow workflow itself. Instead, parsing and validation of metadata—as well as more comprehensive parameter validation—are handled externally by a [Python container](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#p0-validate-inputs). The `validateInputParameters()` function within the workflow still checks for the presence of all required parameters and performs basic logical consistency checks (such as ensuring `blastdb` is set when using `blast_core_nt`, and that certain threshold values are in the correct order), but the main responsibility for input validation has been shifted outside the workflow.

---

## [nf-core/utils_nextflow_pipeline/main.nf](../subworkflows/nf-core/utils_nextflow_pipeline/main.nf)

This subworkflow provides general utility functions for any Nextflow pipeline. The only introduced change is that the functionality for dumping pipeline parameters to a JSON file has been moved to the [main workflow](../workflows/taxassignwf.nf). This adjustment ensures that the JSON file with parameters is generated in a way that makes it easy to parse and include in the final HTML report.

## [nf-core/utils_nfcore_pipeline/main.nf](../subworkflows/nf-core/utils_nfcore_pipeline/main.nf)

This file provides utility functions for nf-core pipelines, including configuration checks, workflow version reporting, terminal log colouring, and sending summary emails or notifications (e.g., on completion or failure). It helps ensure users are informed about pipeline status and results, and supports standardised reporting and notifications. No changes were introduced to this file.

## [nf-core/utils_nfschema_plugin/main.nf](../subworkflows/nf-core/utils_nfschema_plugin/main.nf)

This subworkflow (`UTILS_NFSCHEMA_PLUGIN`) uses the nf-schema plugin to validate pipeline parameters and print a summary of parameters that differ from the defaults defined in the JSON schema. It can optionally validate parameters against a specified schema file and outputs a summary to the log. No changes were introduced to this file.

---

# Modules

---

## [configure/environment](../modules/configure/environment/main.nf)

This module generates an environment variable file (`env_vars.sh`) containing all relevant parameters required by the [Python Taxonomic Assignment workflow modules](https://github.com/qcif/daff-biosecurity-wf2). The generated file is sourced by the Nextflow modules that call these Python modules, ensuring consistent parameter passing throughout the workflow. More information about the environment variables and their usage can be found [here](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#environment-variables).

## [validate/input](../modules/validate/input/main.nf)

This process (`VALIDATE_INPUT`) runs a Python validation script inside a container to check the input files and parameters for the workflow. It sources an environment variable file, then calls `p0_validation.py` with paths to the taxonomy database, query FASTA, and metadata CSV. If the database type is BOLD, it adds a `--bold` flag. The process ensures all required inputs are valid before the main analysis begins. More information about the `p0_validation.py` script can be found [here](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#p0-validate-inputs).

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

The `EXTRACT_HITS` process parses BLAST XML results to extract hit information and accession numbers. It takes the environment variable file and the BLAST XML output as input, then runs a Python script (`p1_parse_blast.py`) to generate files listing accessions, hit details in JSON format, and hit sequences in FASTA format. This process is used in the BLAST branch of the workflow, immediately after running BLASTN, to prepare hit data for downstream candidate extraction and analysis. More information about the `p1_parse_blast.py` script can be found [here](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#p1-blast-parser).

## [blast/blastdbcmd](../modules/blast/blastdbcmd/main.nf)

The `BLAST_BLASTDBCMD` module uses the `blastdbcmd` tool to extract taxonomic IDs for a list of accessions from a BLAST database. It takes a batch file of accession numbers as input and outputs a CSV file mapping accessions to taxids (`taxids.csv`). This module is used in the BLAST branch of the workflow, after extracting hits from BLASTN results, to retrieve taxonomic information needed for downstream taxonomy extraction and analysis.

## [extract/taxonomy](../modules/extract/taxonomy/main.nf)

The `EXTRACT_TAXONOMY` module runs a Python script (`p2_extract_taxonomy.py`) to extract taxonomy information for a list of taxids using the NCBI taxonomy database. It takes an environment variable file and a CSV of taxids as input, and outputs a taxonomy file. This module is used after retrieving taxids from BLAST hits, providing detailed taxonomy data needed for downstream candidate extraction and reporting. More information about the `p2_extract_taxonomy.py` script can be found [here](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#p2-ncbi-taxonomy-extractor).






















---

## bold/search


---

## evaluate/databasecoverage

---

## evaluate/sourcediversity


---

## extract/candidates



---

---





## fastme



## mafft/align


## report



---

# Configuration Files Overview

The pipeline uses several configuration files located in the [`conf/`](../conf/) directory to control its behaviour:

- **`params.config`**  
  Defines all pipeline parameters and their default values, such as input file names, thresholds, and output file names. These parameters can be overridden by user-supplied config files or command-line options.  
  See: [`conf/params.config`](../conf/params.config)

- **`process.config`**  
  Sets default resource requirements (CPUs, memory, time) and container images for each process or process label. It also defines the default error strategy and bash options for process execution.  
  See: [`conf/process.config`](../conf/process.config)

- **`profiles.config`**  
  Contains execution profiles for different environments (e.g., `singularity`, `docker`, `conda`, `apptainer`, `test`). Profiles can enable or disable container engines and set other environment-specific options.  
  See: [`conf/profiles.config`](../conf/profiles.config)

- **`test.config`**  
  Provides a minimal test dataset and settings for quick pipeline validation. Used with the `-profile test` option.  
  See: [`conf/test.config`](../conf/test.config)

- **`validation.config`**  
  Controls parameter validation and help behaviour, including which parameters are required and how help is displayed.  
  See: [`conf/validation.config`](../conf/validation.config)

- **`manifest.config`**  
  Contains pipeline metadata such as name, author, contributors, description, and version.  
  See: [`conf/manifest.config`](../conf/manifest.config)

- **`misc.config`**  
  Sets miscellaneous environment variables, disables process selector warnings by default, and enables Nextflow reporting plugins (timeline, report, trace, dag).  
  See: [`conf/misc.config`](../conf/misc.config)

# [Loci](../assets/loci.json)

This file defines the permitted loci (barcoding regions) and their synonyms used in the pipeline. It helps standardise locus names and supports synonym resolution for GenBank queries. For more details on how loci are used and formatted, see the [sample locus section in the pipeline README](https://github.com/qcif/daff-biosecurity-wf2?tab=readme-ov-file#sample-locus).

---

# [SCHEMA_INPUT.JSON](../assets/schema_input.json)

This JSON schema describes the required structure and columns for the metadata CSV file used as input to the pipeline. If you need to add columns or change the metadata format, update this schema accordingly to ensure proper validation and compatibility.

---



# [nextflow_schema.json](../nextflow_schema.json)

This file defines the Nextflow schema for pipeline parameters. It is used for parameter validation, help text generation, and integration with tools like nf-core Launch and Nextflow
