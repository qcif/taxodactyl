> STILL IN PROGRESS

# Pipeline Module Details

Below is a description of each module in the pipeline, including which parameters are used as inputs.

---

## blast/blastdbcmd

**Purpose:**  
Extracts taxonomic IDs from a BLAST database using an entry batch file.

**Inputs:**  
- `entry_batch` (from parameter: `params.accessions_filename`)
- BLAST database path (from parameter: `params.blastdb`)
- Output directory (from parameter: `params.outdir`)

**Outputs:**  
- `taxids.csv` (accession and taxid mapping)
- `versions.yml` (tool version info)

---

## blast/blastn

**Purpose:**  
Runs `blastn` to search nucleotide sequences against a BLAST database.

**Inputs:**  
- Query FASTA file (from parameter: `params.sequences`)
- BLAST database path (from parameter: `params.blastdb`)
- Output directory (from parameter: `params.outdir`)
- Additional BLAST options (from parameters: `params.blast_max_target_seqs_for_report`, `params.min_identity`, `params.min_nt`, `params.min_q_coverage`)

**Outputs:**  
- BLAST XML results
- `versions.yml` (tool version info)

---

## bold/search

**Purpose:**  
Performs a BOLD (Barcode of Life Data System) search for taxonomic assignment.

**Inputs:**  
- Query FASTA file (from parameter: `params.sequences`)
- Output directory (from parameter: `params.outdir`)
- BOLD-specific options (from parameters: `params.bold_skip_orientation`, `params.bold_taxonomy_json`)

**Outputs:**  
- BOLD taxonomy JSON
- BLAST hits (JSON and FASTA)

---

## configure/environment

**Purpose:**  
Generates an environment variable file (`env_vars.sh`) with all relevant parameters for downstream processes.

**Inputs:**  
- All pipeline parameters (e.g., `params.metadata`, `params.sequences`, `params.db_type`, `params.analyst_name`, `params.facility_name`, etc.)

**Outputs:**  
- `env_vars.sh` (environment variables for the workflow)

---

## evaluate/databasecoverage

**Purpose:**  
Evaluates database coverage for candidate sequences.

**Inputs:**  
- Candidate JSON (from parameter: `params.candidates_json_filename`)
- Metadata (from parameter: `params.metadata`)
- Output directory (from parameter: `params.outdir`)
- Coverage thresholds (from parameters: `params.db_cov_min_a`, `params.db_cov_min_b`, `params.db_cov_related_min_a`, `params.db_cov_related_min_b`, `params.db_cov_country_missing_a`, `params.db_coverage_toi_limit`)

**Outputs:**  
- Coverage results in the query folder

---

## evaluate/sourcediversity

**Purpose:**  
Assesses the diversity of sources supporting candidate taxonomic assignments.

**Inputs:**  
- Candidate JSON (from parameter: `params.candidates_json_filename`)
- Output directory (from parameter: `params.outdir`)
- Source thresholds (from parameter: `params.min_source_count`)

**Outputs:**  
- Aggregated sources JSON in the query folder

---

## extract/candidates

**Purpose:**  
Extracts candidate sequences and related information from BLAST/BOLD hits.

**Inputs:**  
- Hits JSON (from parameter: `params.hits_json_filename`)
- Hits FASTA (from parameter: `params.hits_fasta_filename`)
- Taxonomy file (from parameter: `params.taxonomy_filename`)
- Metadata (from parameter: `params.metadata`)
- Output directory (from parameter: `params.outdir`)
- Candidate thresholds (from parameters: `params.max_candidates_for_analysis`, `params.min_identity_strict`, `params.median_identity_warning_factor`)

**Outputs:**  
- Candidate count, JSON, FASTA, CSV, boxplot image, and flags in the query folder

---

## extract/hits

**Purpose:**  
Parses BLAST XML results to extract hit information and accession numbers.

**Inputs:**  
- BLAST XML (from parameter: `params.blast_xml_filename`)
- Output directory (from parameter: `params.outdir`)
- Minimum identity and coverage (from parameters: `params.min_identity`, `params.min_nt`, `params.min_q_coverage`)

**Outputs:**  
- Accessions file
- Hits JSON and FASTA
- Log file

---

## extract/taxonomy

**Purpose:**  
Extracts taxonomy information for given taxids using the NCBI taxonomy dump.

**Inputs:**  
- Taxids CSV (from parameter: `params.accessions_filename`)
- Taxonomy database directory (from parameter: `params.taxdb`)
- Output directory (from parameter: `params.outdir`)

**Outputs:**  
- Taxonomy CSV

---

## fastme

**Purpose:**  
Builds phylogenetic trees from sequence alignments using FastME.

**Inputs:**  
- Alignment file (from parameter: `params.candidates_msa_filename`)
- Output directory (from parameter: `params.outdir`)

**Outputs:**  
- Newick tree file
- Statistics
- Optional matrix and bootstrap files
- `versions.yml` (tool version info)

---

## mafft/align

**Purpose:**  
Performs multiple sequence alignment using MAFFT.

**Inputs:**  
- Candidate FASTA (from parameter: `params.candidates_phylogeny_fasta_filename`)
- Query sequence (from parameter: `params.sequences`)
- Output directory (from parameter: `params.outdir`)

**Outputs:**  
- MSA file
- `versions.yml` (tool version info)

---

## report

**Purpose:**  
Generates the final HTML report for each query.

**Inputs:**  
- Various result files and folders (from parameters: `params.outdir`, `params.candidates_json_filename`, `params.candidates_csv_filename`, `params.boxplot_img_filename`, etc.)
- Environment variable file (from `configure/environment`)

**Outputs:**  
- HTML report in the output directory

---

## validate/input

**Purpose:**  
Validates input files and parameters


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

# SUBWORKFLOWS - what we've changed & default nf-core

This section is intended to document any modifications made to the default nf-core subworkflows, as well as any custom subworkflows added for this pipeline. It helps users and developers understand how the pipeline diverges from or extends nf-core standards.

---

# [WORKFLOWS - main workflow](../workflows/taxassignwf.nf)

This is the main Nextflow workflow script for the pipeline. It orchestrates the execution of all modules and subworkflows, defining the overall logic and data flow.

---

# [main.nf](../main.nf)

This is the pipeline entry point script. It typically handles parameter parsing, initial setup, and calls the main workflow defined in `workflows/taxassignwf.nf`.

---

# [nextflow_schema.json](../nextflow_schema.json)

This file defines the Nextflow schema for pipeline parameters. It is used for parameter validation, help text generation, and integration with tools like nf-core Launch and Nextflow
