## Pipeline specific parameters

This document describes the parameters available for the **qcif/taxodactyl** Nextflow pipeline.

---

### General input

| Name           | Type    | Default           | Description                                                                                      | Requirements                                                                                   |
|----------------|---------|-------------------|--------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| `db_type`      | string  | 'blast_core_nt'   | Type of reference database to use for taxonomic assignment. Allowed: `blast_core_nt`, `bold`.     | Must be one of `blast_core_nt`, `bold`. Default: `blast_core_nt`.                             |
| `metadata`     | string  | 'metadata.csv'    | CSV file containing sample metadata. Must have columns: `sample_id`, `locus`, `preliminary_id`.  | Must be a valid CSV file path, no spaces, `.csv` extension, required columns.                 |
| `outdir`       | string  | 'output'          | Directory where output files will be saved.                                                      | Must be a valid directory path. Default: `output`.                                            |
| `sequences`    | string  | 'sequences.fasta' | FASTA file containing input sequences for analysis.                                              | Must be a valid file path, no spaces, `.fa`, `.fna`, , or `.fasta` extension.        |
| `analyst_name` | string  |                   | Name of the analyst running the workflow.                                                        | Must be a string.                                                                             |
| `facility_name`| string  |                   | Name of the facility where the workflow is executed.                                             | Must be a string.                                                                             |
| `taxdb`        | string  |                   | Directory where NCBI's taxdump files can be found.                                               | Must be a valid directory path. Following files should be present: citations.dmp, division.dmp, gencode.dmp, merged.dmp, nodes.dmp, taxonkit, delnodes.dmp, gc.prt, images.dmp, names.dmp and readme.txt                                                               |

---

### Search NCBI core nt database with blastn
| Name           | Type    | Default           | Description                                                                                      | Requirements                                                                                   |
|----------------|---------|-------------------|--------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| `blastdb`      | string  |                   | Path to the BLAST database files. Must end with 'core_nt'.                                       | Must be a valid path ending with `core_nt`, e.g. '/folder_path/blast_db/202505/core_nt'. Required if `db_type` set to 'blast_core_nt'. The folder should contain files with the core_nt prefix and extensions: .nal, .ndb, .njs, .nos, .not, .ntf, .nto. In addition, it should contain multiple volumes of core_nt, named core_nt.NUM with extensions .nhr, .nin, .nnd, .nni, .nog and .nsq." |

---

### Search BOLD database

| Name                  | Type    | Default | Description                                                                                      | Requirements                        |
|-----------------------|---------|---------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| `bold_skip_orientation` | int   | 0       | If 1, BOLD runs skip orientation and submit both forward and reverse sequences to the API.        | Must be 0 or 1. Default: 0.          |

---

### Extract candidates

| Name                           | Type    | Default | Description                                                                                      | Requirements                        |
|--------------------------------|---------|---------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| `max_candidates_for_analysis`  | int     | 3       | Maximum number of candidate species for further analysis.                                         | Integer ≥ 1. Default: 3.             |
| `median_identity_warning_factor`| float  | 0.95    | Minimum proportion of candidate identity threshold for a median identity to receive WARNING.      | Number 0–1. Default: 0.95.           |
| `min_identity`                 | float   | 0.935   | Minimum identity for a BLAST hit to be considered.                                               | Number 0–1. Default: 0.935.          |
| `min_identity_strict`          | float   | 0.985   | Minimum hit identity to be considered a STRONG candidate.                                        | Number 0–1. Default: 0.985.          |
| `min_nt`                       | int     | 300     | Minimum alignment length for a BLAST hit to be considered.                                       | Integer ≥ 0. Default: 300.           |
| `min_q_coverage`               | float   | 0.85    | Minimum query coverage for a BLAST hit to be considered.                                         | Number 0–1. Default: 0.85.           |
| `phylogeny_min_hit_identity`   | float   | 0.95    | Minimum hit identity (0-1) to be included in the phylogenetic tree.                              | Number 0–1. Default: 0.95.           |
| `phylogeny_min_hit_sequences`  | int     | 10      | Minimum number of sequences to be included in the phylogenetic tree.                             | Integer ≥ 1. Default: 10.            |
| `allowed_loci_file`            | string  |         | JSON file describing permitted loci and their synonyms.                                          | Valid file path, no spaces, `.json`. |

---

### Database coverage

| Name                      | Type    | Default                                   | Description                                                                                      | Requirements                        |
|---------------------------|---------|-------------------------------------------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| `db_cov_country_missing_a`| int     | 1                                         | Flag 5.3B is raised when at least this many species in country of origin have no GenBank records.| Integer ≥ 0. Default: 1.             |
| `db_cov_min_a`            | int     | 5                                         | Minimum number of GenBank records to receive Flag 5.1A.                                          | Integer ≥ 1. Default: 5.             |
| `db_cov_min_b`            | int     | 1                                         | Minimum number of GenBank records to receive Flag 5.1B.                                          | Integer ≥ 1. Default: 1.             |
| `db_cov_related_min_a`    | int     | 90                                        | Minimum percent species coverage of GenBank records to receive Flag 5.2A.                        | Integer 1–100. Default: 90.          |
| `db_cov_related_min_b`    | int     | 10                                        | Minimum percent species coverage of GenBank records to receive Flag 5.2B.                        | Integer 1–100. Default: 10.          |
| `db_coverage_toi_limit`   | int     | 10                                        | Maximum number of taxa of interest analysed by database coverage.                                | Integer ≥ 0. Default: 10.            |
| `gbif_accepted_status`    | string  | 'accepted,doubtful'                       | Comma-separated list of GBIF taxonomic statuses to be considered.                                | Comma-separated, no spaces.          |
| `gbif_limit_records`      | int     | 500                                       | Maximum number of records per request to the GBIF API.                                           | Integer ≥ 1. Default: 500.           |
| `gbif_max_occurrence_records` | int | 5000                                      | Maximum number of GBIF records fetched for plotting occurrence distribution map.                 | Integer ≥ 1. Default: 5000.          |
| `ncbi_api_key` | string  | null              | Used to authenticate with NCBI Entrez API for increased rate limit. You can generate it following the instructions from [this article](https://support.nlm.nih.gov/kbArticle/?pn=KA-05317).                              | Must not contain spaces.                                                                      |
| `ncbi_user_email` | string | null             | Email for NCBI Entrez API if API key not provided.                                               | Must be a valid email address.                                                                |

---

### Publications supporting taxonomic association

| Name              | Type    | Default | Description                                                                                      | Requirements                        |
|-------------------|---------|---------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| `min_source_count`| int     | 5       | Minimum number of independent publications for a candidate species to receive Flag 4A.            | Integer ≥ 1. Default: 5.             |

---

### Report

| Name                           | Type    | Default                | Description                                                                                      | Requirements                        |
|--------------------------------|---------|------------------------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| `blast_database_name_for_report`| string | "NCBI Core Nt"         | Name of the BLAST database for reporting.                                                        | Must be a string.                   |
| `blast_max_target_seqs_for_report`| int  | 2000                   | Maximum number of hits collected per query for BLAST search (for reporting only).                | Integer ≥ 1. Default: 2000.          |
| `report_debug`                 | int     | 0                      | If 1, replaces the timestamp in the report file name with DEBUG.                                 | 0 or 1. Default: 0.                  |

---

### General

| Name           | Type    | Default | Description                                                                                      | Requirements                        |
|----------------|---------|---------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| `email`        | string  | null    | Email address for notifications and reports.                                                     | Must be a valid email address.       |
| `logging_debug`| int     | 0       | If 1, verbose log statements will be emitted.                                                    | 0 or 1. Default: 0.                  |

---

### Output filenames

#### Search BLAST database filenames

| Name                | Type    | Default           | Description                                                                                      | Requirements                        |
|---------------------|---------|-------------------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| `accessions_filename`| string | 'accessions.txt'  | Filename for the file containing BLAST accession numbers.                                        | No spaces, `.txt` extension.         |
| `blast_xml_filename` | string | 'blast_results.xml'| Filename for the BLAST XML results file.                                                         | No spaces, `.xml` extension.         |

---

#### General database search filenames

| Name                | Type    | Default           | Description                                                                                      | Requirements                        |
|---------------------|---------|-------------------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| `hits_fasta_filename`| string | 'all_hits.fasta'  | Filename for the FASTA file containing all BLAST hits.                                           | No spaces, `.fa`, `.fna`, , or `.fasta` extension. |
| `hits_json_filename` | string | 'all_hits.json'   | Filename for the JSON file containing all BLAST hits.                                            | No spaces, `.json` extension.        |

---

#### Extract candidates filenames

| Name                             | Type    | Default                        | Description                                                                                      | Requirements                        |
|----------------------------------|---------|--------------------------------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| `boxplot_img_filename`           | string  | 'candidates_identity_boxplot.png' | Filename for the PNG image of candidate identity boxplot.                                     | No spaces, `.png` extension.         |
| `candidates_csv_filename`        | string  | 'candidates.csv'               | Filename for the CSV file listing candidate hits.                                                | No spaces, `.csv` extension.         |
| `candidates_fasta_filename`      | string  | 'candidates.fasta'             | Filename for the FASTA file of candidate sequences.                                              | No spaces, `.fa`, `.fna`, , or `.fasta` extension. |
| `candidates_phylogeny_fasta_filename` | string | 'candidates_phylogeny.fasta'  | Filename for the FASTA file of candidate sequences for the phylogenetic tree.                    | No spaces, `.fa`, `.fna`, , or `.fasta` extension. |
| `candidates_json_filename`       | string  | 'candidates.json'              | Filename for the JSON file of candidate hits.                                                    | No spaces, `.json` extension.        |
| `candidates_sources_json_filename`| string | 'candidates_sources.json'      | Filename for the JSON file listing sources of candidate species.                                 | No spaces, `.json` extension.        |
| `independent_sources_json_filename`| string | 'aggregated_sources.json'      | Filename for the JSON file listing aggregated publications supporting taxonomic associations.     | No spaces, `.json` extension.        |

---

#### Taxonomy filenames

| Name                   | Type    | Default               | Description                                                                                      | Requirements                        |
|------------------------|---------|-----------------------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| `bold_taxonomy_json`   | string  | 'bold_taxonomy.json'  | Filename for the JSON file containing BOLD taxonomy data.                                        | No spaces, `.json` extension.        |
| `taxonomy_filename`    | string  | 'taxonomy.csv'        | Filename for the CSV file containing BLAST taxonomy assignments.                                 | No spaces, `.csv` extension.         |

---

#### Multiple sequence alignment filename

| Name                    | Type    | Default                    | Description                                                                                      | Requirements                        |
|-------------------------|---------|----------------------------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| `candidates_msa_filename`| string | 'candidates_phylogeny.msa' | Filename for the multiple sequence alignment file of candidate sequences.                        | No spaces, `.msa` extension.         |

---

#### Phylogenetic tree filename

| Name                | Type    | Default                    | Description                                                                                      | Requirements                        |
|---------------------|---------|----------------------------|--------------------------------------------------------------------------------------------------|--------------------------------------|
| `tree_nwk_filename` | string  | 'candidates_phylogeny.nwk' | Filename for the Newick tree file of candidate sequences.                                        | No spaces, `.nwk`

   
---