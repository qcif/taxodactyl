# Taxonomic Assignment workflow modules (DAFF Biosecurity Workflows)

- [Workflow setup and configuration](https://github.com/qcif/taxodactyl/tree/main)
- [Documentation of the analysis](https://qcif.github.io/taxodactyl/understanding-the-analysis.html)

These Python modules are used for intermediate data processing as part of a
[Nextflow workflow](https://github.com/qcif/taxodactyl/tree/main)
for taxonomic assigment of sample DNA sequences. The purpose of this analysis
is not metabarcoding, but a comprehensive analysis of samples at the individual
level. Taxonomic identities are assigned conservatively, with various measures
of confidence provided to support analytical conclusions. You can see an
example workflow report
[here](https://qcif.github.io/taxodactyl/example_report.html).

A user guide for each module is listed below. Examples of running
each script can be found in the [.vscode/launch.json](.vscode/launch.json) file,
which shows CLI arguments and environment variables for each script.

# Table of Contents

1. [FAQs](#faqs)
    1. [How to update the workflow report?](#how-to-update-the-workflow-report)
1. [Developer setup](#developer-setup)
1. [Building a Docker image](#building-a-docker-image)
1. [Debugging in Singularity](#debugging-in-singularity)
1. [Running tests](#running-tests)
    1. [Units tests](#unit-tests)
    1. [Integration tests](#integration-tests)
1. [Running the scripts](#workflow-steps-python-scripts)
    1. [Environment variables](#environment-variables)
    1. [P0 validate inputs](#p0-validate-inputs)
    1. [P1 BLAST parser](#p1-blast-parser)
    1. [BLASTDBCMD](#blastdbcmd)
    1. [P2 NCBI Taxonomy extractor](#p2-ncbi-taxonomy-extractor)
    1. [P3 Evaluate taxonomy](#p3-evaluate-taxonomy)
    1. [P4 Analysis of reference sequence publications](#p4-analysis-of-reference-sequence-publications)
    1. [P5 Analysis of database coverage](#p5-analysis-of-database-coverage)
    1. [P6 Report generation](#p6-report-generation)
1. [Building the docs](#building-the-docs)
1. [Version release](#version-release)
1. [Application features](#application-features)
    1. [Configuration](#application-configuration)
    1. [Handling errors](#handling-errors)
    1. [Throttling API requests](#throttling-api-requests)
    1. [Caching API responses](#caching-api-responses)
    1. [Secrets vault](#secrets-vault)
    1. [Flags](#flags)
    1. [Sample locus](#sample-locus)


# FAQs

### How to update the workflow report?

- For editing flag detail text, see the [Flags sections](#flags)
- Some constants e.g. title, database names, can be modified in the [config](#application-configuration)
- Most report text is defined in HTML templates, so try:
    - Repo-wide search for the text you're trying to update
    - Looking through the [report templates](./src/report/templates/) for the component you want to update


# Developer setup

Development is easier on Linux/MacOS because the program was developed on
Unix. One of our team has run this in Windows (using git-bash or WSL) but
it was more painful to get going.

1. Clone the repository
   ```sh
   git clone https://github.com/qcif/taxodactyl.git
   ```
2. Install dependencies
   ```sh
   # Go to python scripts folder
   cd scripts

   # Create a virtual environment for python3.12
   python3.12 -m venv venv
   source venv/bin/activate

   # Install dependencies with pip
   pip install -r requirements.txt
   ```
3. Install [taxonkit](https://bioinf.shenwei.me/taxonkit/download/) (used for obtaining taxonomy data)
   ```sh
   # Change URL to download appropriate for your platform
   wget https://github.com/shenwei356/taxonkit/releases/download/v0.20.0/taxonkit_linux_amd64.tar.gz
   tar xf taxonkit_linux_amd64.tar.gz
   cp taxonkit/taxonkit /usr/local/bin  # Choose an appropriate PATH location

   # Download taxdump from NCBI
   mkdir -p $HOME/.taxonkit
   cd $HOME/.taxonkit
   wget -c ftp://ftp.ncbi.nih.gov/pub/taxonomy/taxdump.tar.gz
   tar -xzf taxdump.tar.gz && rm taxdump.tar.gz
   ```
4. (Optional) Install HMMSearch for orientation of BOLD queries. If you omit this step you will need to run p1_bold_search.py with env var `SKIP_ORIENTATION=1`. See [Dockerfile](./Dockerfile) for installation instructions.



# Building a Docker image

> [!NOTE]
> The GitHub repo [qcif/taxodactyl](https://github.com/qcif/taxodactyl) has a GitHub workflow that automates the build/push of Docker images when a [release](https://github.com/qcif/taxodactyl/releases) is made. This is the preferred method of generating images as it removes human error.

> [!NOTE]
> Make sure you update the VERSION file before publishing a new version!

We've pushed a lot of versions, so there's a script for this.

Update the image path before running if required. You will need to have push access to the remote repository (e.g. DockerHub) if you intend to push this:

```sh
# nano docker_build.sh
IMAGE=neoformit/taxodactyl
```

Now to build image `neoformit/taxodactyl:v1.2.0`:

```sh
# Build an image from the current working directory:
./docker_build.sh -t v1.2.0  # it will ask for a tag if you don't provide one

# To build and push in one go:
./docker_build.sh -t v1.2.0 -p
```



# Debugging in Singularity

When debugging issues that only reproduce inside the container environment,
you can run scripts inside a Singularity container with the VSCode debugger
attached. This uses `debugpy` for remote debugging.

## Prerequisites

1. **Install Singularity** (v3.7+):
   Follow the [Singularity Quick Start Guide](https://docs.sylabs.io/guides/3.7/user-guide/quick_start.html).

2. **Build a Singularity image from the Docker image:**
   ```sh
   # Save Docker image to tar (required if Singularity is too old to talk
   # to the Docker daemon directly)
   docker save neoformit/taxodactyl:<tag> -o /tmp/taxodactyl.tar

   # Build .sif from the tar archive
   singularity build scripts/output/issues/225/taxodactyl-<tag>.sif \
       docker-archive:///tmp/taxodactyl.tar

   # Clean up
   rm /tmp/taxodactyl.tar
   ```

   If your Singularity version supports it, you can build directly:
   ```sh
   singularity build taxodactyl-<tag>.sif docker-daemon://neoformit/taxodactyl:<tag>
   ```

3. **Ensure taxonkit data is available** at `~/.taxonkit` (see
   [Developer setup](#developer-setup)).

## Running with the VSCode debugger

A launch configuration and helper script are provided for debugging inside the
container.

1. **Update the task arguments** in `.vscode/tasks.json` under the
   `start-singularity-debug` task. The script takes three arguments:
   - `<sample_dir>` - path to the sample directory (relative to project root)
   - `<sample_id>` - the query directory name (e.g. `query_001_barcode_55...`)
   - `<sif_image>` - path to the `.sif` Singularity image

2. **Start the debug session** by selecting **"Attach to Singularity
   container"** from the VSCode Run and Debug panel (F5). This will:
   - Launch the Singularity container as a pre-launch task (installing
     `debugpy` at runtime via `--writable-tmpfs`)
   - Wait for the VSCode debugger to attach on port 5678
   - Run the target script (currently `p5_db_coverage.py`)
   - Kill the container process when the debug session ends

3. **Set breakpoints** in the scripts as normal - the `pathMappings` in the
   launch config maps `scripts/` to `/app/scripts/` inside the container.

Alternatively, you can start the container manually from a terminal:
```sh
bash scripts/run_in_singularity.sh <sample_dir> <sample_id> <sif_image>
```
Then attach the VSCode debugger using the **"Attach to Singularity container"**
launch config.

## Adapting for other scripts/samples

Update the arguments in `.vscode/tasks.json` (`start-singularity-debug` task)
to point to a different sample directory, query ID or container image. To change
the Python script being executed or its arguments, edit
`scripts/run_in_singularity.sh`.


# Running tests

## Unit tests

```sh
python -m unittest discover \
  -s tests \
  -p test*.py \
  -b \
  -p test_gbif.py  # optional, to run a specific test only
```

## Integration tests

The integration tests do not make any assertions, they just run a bunch of different tests cases, some of which contain edge cases that have caused errors in the past. Some assertions of the output data and HTML report content would be nice, but would take a while to generate and require constant updates as the code changes. These tests are mainly for broad coverage to ensure that we haven't introduced any fatal errors.

> [!NOTE]
> The integration tests have no mocking or fancy machinery, so they make real API calls and can take a while to run. I usually run them on a server so I can leave them to run for the ~15 minutes required.

The integration tests are actually run with unittest (see [test_integration.py](./tests/integration/test_integration.py)).

```sh
./tests/integration/run_tests.sh

# Or, for BOLD test cases:
./tests/integration/run_tests.sh --bold
```



# Workflow steps (Python scripts)

Six Python scripts provide entrypoints which can be called by Nextflow to run
the steps required for this pipeline. Some workflow steps (BLASTN, BLASTDBCMD,
MAFFT, FastME) are actioned with other tools, but most steps require invoking one
of the Python scripts included in this repository. For ease of reference, the
scripts are enumerated as P1-P6.

Each script can also accept an optional argument `-c config.yml` that can be used
in place of CLI arguments, though CLI arguments will override any parameters
provided by the config file. See the
[configuration section](#application-configuration) for more info on
configuration options.

## Environment variables

Some environment variables that can be useful in development. These can all be passed as CLI params to the relevant scripts, or declared in a config.yml file, but sometimes this might be easier:

```sh
INPUT_FASTA_FILEPATH="/my/input/folder/query.fasta"
INPUT_METADATA_CSV_FILEPATH="/my/input/folder/metadata.csv"
LOGGING_DEBUG=0  # 1 to enable additional logging to help with debugging
SKIP_ORIENTATION=0  # 1 to skip orientation of BOLD sequences (requires setup)
GBIF_MAX_OCCURRENCE_RECORDS=200  # Reduce to 200 for testing/dev to speed up p5. Default 5000.
REPORT_DEBUG=0  # 1 to omit timestamp from report filename for browser reload between changes
FACILITY_NAME="Hogwarts"  # Displayed in report
ANALYST_NAME="Harry Potter"  # Displayed in report
```

Environment variables are fully documented [here](https://qcif.github.io/taxodactyl/environment.html).


## P0 validate inputs

This script takes user inputs and validates them to ensure that the format and
content are valid for the requested analysis. If one of the inputs are found to
have erroneous content, this will raise an exception with an error message that
should be sufficient for the user to understand what's wrong with their input
data.

See [config.INPUTS](./src/utils/config.py#L113)
for some parameters which are used for validation, such as permitted FASTA
sequence lengths and required metadata.csv fields.

```
$ python p0_validation.py -h

usage: p0_validation.py [-h] --metadata-csv METADATA_CSV --query-fasta
                        QUERY_FASTA --taxdb-dir TAXDB_DIR [--bold]
                        [--allowed-loci-file ALLOWED_LOCI_FILE]
                        [--input-fasta INPUT_FASTA]
                        [--input-metadata INPUT_METADATA]
                        [--fasta-max-sequences FASTA_MAX_SEQUENCES]
                        [--fasta-min-length FASTA_MIN_LENGTH]
                        [--fasta-max-length FASTA_MAX_LENGTH]

Validate user input.

options:
  -h, --help            show this help message and exit
  --metadata-csv METADATA_CSV
                        Path to metadata.csv input file.
  --query-fasta QUERY_FASTA
                        Path to queries.fasta input file.
  --taxdb-dir TAXDB_DIR
                        Path to queries.fasta input file.
  --bold                Validate inputs for a BOLD analysis (accept blank
                        locus field).
  --allowed-loci-file ALLOWED_LOCI_FILE
                        Path to JSON file containing allowed loci definitions
  --input-fasta INPUT_FASTA
                        Path to input FASTA file containing query sequences
  --input-metadata INPUT_METADATA
                        Path to input metadata CSV file
  --fasta-max-sequences FASTA_MAX_SEQUENCES
                        Maximum number of sequences allowed
  --fasta-min-length FASTA_MIN_LENGTH
                        Minimum sequence length in nucleotides
  --fasta-max-length FASTA_MAX_LENGTH
                        Maximum sequence length in nucleotides
```


## P1 BLAST parser

This script parses a BLAST XML output into JSON format that is more easily
readable by Python and other programs. It also extracts FASTA sequences for
BLAST hit subjects, and writes a list of hit accessions to be used as the input
for the next workflow step.

```
$ python scripts/p1_parse_blast.py -h

Parse BLAST XML output file.

positional arguments:
  blast_xml_path        Path to the BLAST XML file to parse.

options:
  -h, --help            show this help message and exit
  --output-dir OUTPUT_DIR
                        Directory to save parsed output files (JSON and FASTA).
                        Defaults to env variable 'OUTPUT_DIR' or 'output'.
  --blast-max-target-seqs BLAST_MAX_TARGET_SEQS
                        Maximum number of target sequences for BLAST
```

Output is in per-query directories corresponding to the sequence index in
the query FASTA file:

```
output/
├── accessions.txt  # input file for blastdbcmd
├── query_001
│   ├── hits.fasta
│   ├── hits.json
│   └── query_title.txt
├── query_002
│   ├── hits.fasta
│   ├── hits.json
│   └── query_title.txt
├── ...
...
```

## P1 BOLD search

This script uses the BOLD API to search for similar sequences to query sequences.
It's an alternative to BLAST when using the BOLD database for taxonomic identification.

```
$ python scripts/p1_bold_search.py -h

Use the BOLD API to search for similar sequences to query.

positional arguments:
  fasta_file            Path to the FASTA file containing sequences to search.

options:
  -h, --help            show this help message and exit
  --output-dir OUTPUT_DIR
                        Directory to save parsed output files (JSON and FASTA).
                        Defaults to env variable 'OUTPUT_DIR' or 'output'.
  --bold-database BOLD_DATABASE
                        BOLD database to search
```

## BLASTDBCMD

This is not a Python module but is a required intermediate step between modules
1 and 2 implemented in the parent Nextflow workflow. The `blastdbcmd` tool
should be used to extract taxids for each accession as follows:

```sh
blastdbcmd -entry_batch output/accessions.txt -db </path/to/blastdb> -outfmt "%a,%T" > output/taxids.csv
```

NOTE: Some weird behaviour observed by this tool - it seems to extract more
accessions than it is provided. I passed a file of 1830 taxids and found that
2169 were written. There were no duplicates, just extra accessions that weren't
in the input list! For the purpose of this pipeline it's a no-op, but worth
noting the unexpected behaviour (bug).


## P2 NCBI Taxonomy extractor

This script is used for fetching taxonomy information for a list of taxids. The
input should be provided in CSV format with columns (accession,taxid). The
output is a CSV file with columns (accession,taxid,superkingdom,kingdom,phylum,
class,order,family,genus,species). This script requires access to both a
`taxonkit` executable in PATH and NCBI taxdump directory. A custom directory
for the latter can be specified with the `--taxdb` param.

```
$ python scripts/p2_extract_taxonomy.py -h
usage: ncbi_taxonomy.py [-h] [--output OUTPUT_CSV] [--taxdb TAXDB_PATH] taxids_csv

Extract taxids and taxonomic information from NCBI databases. This requires access to the NCBI taxdump files via a CLI argument.

positional arguments:
  taxids_csv           CSV file with columns (accession,taxid) to extract taxonomy information for.

options:
  -h, --help           show this help message and exit
  --output OUTPUT_CSV  CSV file where taxonomy data will be written. Defaults to taxonomy.csv
  --taxdb TAXDB_PATH   Path to directory containing NCBI taxdump files for taxonkit. Defaults to $HOME/.taxonkit
  ```


## P3 Evaluate taxonomy

This script evaluates BLAST/BOLD hits enumerating the number of hits that fall
within the candidate match criteria, and then enumerating the number of species
represented by those hits. It generates several reportable outcomes:

- Attempt to assign a taxonomic identity for the sample (Flag 1)
- Check for Taxa of Interest matching the sample (Flag 2)
- Check whether the Preliminary ID matches the taxonomic identity (Flag 7; only if Flag 1A)
- If more than 3 candidate species, produces a boxplot showing distribution of hit identity % for each species

```
$ python p3_assign_taxonomy.py -h
usage: p3_assign_taxonomy.py [-h] [--output-dir OUTPUT_DIR] [--bold]
                             [--min-alignment-length MIN_ALIGNMENT_LENGTH]
                             [--min-query-coverage MIN_QUERY_COVERAGE]
                             [--min-identity MIN_IDENTITY]
                             [--min-identity-strict MIN_IDENTITY_STRICT]
                             [--median-identity-warning-factor MEDIAN_IDENTITY_WARNING_FACTOR]
                             [--max-candidates-analysis MAX_CANDIDATES_ANALYSIS]
                             [--phylogeny-min-sequences PHYLOGENY_MIN_SEQUENCES]
                             [--phylogeny-max-per-species PHYLOGENY_MAX_PER_SPECIES]
                             query_dir

Run logic for pipeline phase 1-2. - Attempt species ID from BLAST results.json (flag 1) - Detect Taxa of Interest (flag 2) Taxa of Interest output has the following CSV
fields: Taxon of interest: The provided TOI that matched a candidate species Match rank: The taxonomic rank of the match (TOI rank may be above species) Match taxon: The taxon
that matched the TOI Match species: The species of the candidate match Match accession: The NCBI accession of the candidate match

positional arguments:
  query_dir             Path to query output directory

options:
  -h, --help            show this help message and exit
  --output-dir OUTPUT_DIR
                        Path to output directory. Defaults to output.
  --bold                Outputs are from BOLD query.
  --min-alignment-length MIN_ALIGNMENT_LENGTH
                        Minimum alignment length in nucleotides
  --min-query-coverage MIN_QUERY_COVERAGE
                        Minimum query coverage fraction
  --min-identity MIN_IDENTITY
                        Minimum sequence identity for moderate matches
  --min-identity-strict MIN_IDENTITY_STRICT
                        Minimum sequence identity for strong matches
  --median-identity-warning-factor MEDIAN_IDENTITY_WARNING_FACTOR
                        Factor for median identity warnings
  --max-candidates-analysis MAX_CANDIDATES_ANALYSIS
                        Maximum candidates to include in detailed analysis
  --phylogeny-min-sequences PHYLOGENY_MIN_SEQUENCES
                        Minimum sequences required for phylogeny
  --phylogeny-max-per-species PHYLOGENY_MAX_PER_SPECIES
                        Maximum sequences per species for phylogeny
```


## P4 Analysis of reference sequence publications

This script fetches publications from GenBank metadata for each BLAST/BOLD hit
for each candidate species. The publications are then grouped into "independent
publications" depending on whether they are from the same authors. For BOLD hits
which lack a GenBank record, the BOLD `collector` field is used instead. This
analysis results in an aggregated_sources.json file which enumerates the
independent publication sources for each candidate species by hit, and lists the
publication author, journal and title for each publication.

```
$ python p4_source_diversity.py -h

usage: p4_source_diversity.py [-h] [--output-dir OUTPUT_DIR]
                               [--min-source-count MIN_SOURCE_COUNT]
                               query_dir

Analyze the diversity of reference sequence sources oer target. A source is
defined as a publication or set of authors that are linked to the genbank
record for that sequence. If there are no references, no sources are returned
and the sequence is classified as "anonymous". Many anonymous records are from
automated genome annotation projects, often carried out by NCBI themselves.
These records are flagged so that the user can be aware of the potential
reduced credibility of these annotation.

positional arguments:
  query_dir             Path to query output directory

options:
  -h, --help            show this help message and exit
  --output-dir OUTPUT_DIR
                        Path to output directory. Defaults to output.
  --min-source-count MIN_SOURCE_COUNT
                        Minimum number of independent sources required
```


## P5 Analysis of database coverage

This is the most complex analysis, because it forks multiple times into three
different analyses (5.1, 5.2, 5.3) that are run against each target taxon in
the candidates, PMI and TOIs. This results in a minimum of 3x1=3 analyses (no
candidates, no TOI provided) and beyond 3x6=18 analyses (3 candidates, 2 TOIs
provided). If more than 3 candidate species are present, they will be dropped
from the targets and the analysis will only be performed for the PMI and TOIs.
This analysis also includes the generation of geographic occurrence maps for
each target taxon.

```
$ python p5_db_coverage.py -h

usage: p5_db_coverage.py [-h] [--output-dir OUTPUT_DIR] [--bold]
                         [--db-coverage-toi-limit DB_COVERAGE_TOI_LIMIT]
                         [--db-coverage-max-candidates DB_COVERAGE_MAX_CANDIDATES]
                         [--gbif-limit-records GBIF_LIMIT_RECORDS]
                         [--gbif-max-occurrence-records GBIF_MAX_OCCURRENCE_RECORDS]
                         [--gbif-accepted-status GBIF_ACCEPTED_STATUS]
                         [--db-cov-target-min-a DB_COV_TARGET_MIN_A]
                         [--db-cov-target-min-b DB_COV_TARGET_MIN_B]
                         [--db-cov-related-min-a DB_COV_RELATED_MIN_A]
                         [--db-cov-related-min-b DB_COV_RELATED_MIN_B]
                         [--db-cov-country-missing-a DB_COV_COUNTRY_MISSING_A]
                         query_dir

Analyze the database coverage of target species at the given locus. Database coverage is analysed at three levels: 1. Target species coverage: The number of records for the
target species 2. Related species coverage: The number of records for species related to the target species 3. Related species from sample country of origin: as for (2), but
only for species which have occurence records in the same country as the target species.

positional arguments:
  query_dir             Path to query output directory

options:
  -h, --help            show this help message and exit
  --output-dir OUTPUT_DIR
                        Path to output directory. Defaults to output.
  --bold                Reference the BOLD database instead of GenBank.
  --db-coverage-toi-limit DB_COVERAGE_TOI_LIMIT
                        Limit for taxa of interest in coverage analysis
  --db-coverage-max-candidates DB_COVERAGE_MAX_CANDIDATES
                        Maximum candidates for coverage assessment
  --gbif-limit-records GBIF_LIMIT_RECORDS
                        Limit for GBIF taxonomy records
  --gbif-max-occurrence-records GBIF_MAX_OCCURRENCE_RECORDS
                        Maximum GBIF occurrence records
  --gbif-accepted-status GBIF_ACCEPTED_STATUS
                        Comma-separated list of accepted taxonomic statuses
  --db-cov-target-min-a DB_COV_TARGET_MIN_A
                        Minimum records for target species (grade A)
  --db-cov-target-min-b DB_COV_TARGET_MIN_B
                        Minimum records for target species (grade B)
  --db-cov-related-min-a DB_COV_RELATED_MIN_A
                        Minimum records for related species (grade A)
  --db-cov-related-min-b DB_COV_RELATED_MIN_B
                        Minimum records for related species (grade B)
  --db-cov-country-missing-a DB_COV_COUNTRY_MISSING_A
                        Threshold for missing country data (grade A)
```

The code for these analyses is fairly abstract in order to accomodate the range
of cases described above, and is heavily threaded to complete the analysis in a
reasonable time. The [Throttle](#throttling-api-requests)
is critical here to avoid exceeding API rate limits, since the analysis involves
sending LOTS of API requests (sometimes many hundreds per-sample). The entrypoint
for the `coverage` module is
[assess.py](https://github.com/qcif/taxodactyl/blob/main/scripts/src/coverage/assess.py).

1. **Setup** (see [targets.py](https://github.com/qcif/taxodactyl/blob/main/scripts/src/coverage/targets.py))
    1. A list of target taxa is generated from candidate species, PMIs and TOIs
    1. TaxIDs are extracted for each target taxon
    1. GBIF records are extracted for each target taxon (see
      [relatives.py](https://github.com/qcif/taxodactyl/blob/main/scripts/src/gbif/relatives.py))
1. **Occurrence maps** are drawn (see [maps.py](https://github.com/qcif/taxodactyl/blob/main/scripts/src/gbif/maps.py))
1. **Generate tasks**: a list of analysis tasks (targets x 3 analyses) is generated for threading
1. **Thread tasks** - for each target taxon:
    1. **5.1** - DB coverage of target taxon. How many records are in the
      reference database for the target taxon?
    1. **5.2** - DB coverage of species in target genus (only applies to targets
      at rank genus or species). This requires sending a request to NCBI/BOLD for
      each related species - this is where most threads are spawned.
    1. **5.3** - DB coverage of species in target genus, limited to the sample
      country of origin (declared in metadata.csv input)
1. Wait for all threads to complete, collect results and write to `db_coverage.json`

One of the main difficulties in this analysis is that we are sending lots of API
requests and some of them may fail for legitimate reasons. In these cases, we
handle the errors gracefully by using the
[errors module](#handling-errors)
module to write errors to file which can later be rendered in the workflow
report. This often results in a `None` result being
returned for the analysis, and so we also have to be careful to ensure that any
code which depends on these results can handle that (especially flags and report
generation). Inadequate handling of API errors has accounted for many of the
bugs been raised in the P5 module.


## P6 Report generation

This script reads in outputs generated throughout the workflow and generates a
final HTML report which aims to provide all the analytical results required
by the user. The report is a single HTML file rendered from many templates
(snippets and macros) using the Jinja2 templating engine.

```
$ python p6_report.py -h
usage: p6_report.py [-h] [--output-dir OUTPUT_DIR] [--bold]
                    [--params_json PARAMS_JSON] [--versions_yml VERSIONS_YML]
                    [--report-debug] [--database-name DATABASE_NAME]
                    [--facility-name FACILITY_NAME] [--analyst-name ANALYST_NAME]
                    [--flag-details-csv FLAG_DETAILS_CSV]
                    query_dir

Build the workflow report.

positional arguments:
  query_dir             Path to query output directory

options:
  -h, --help            show this help message and exit
  --output-dir OUTPUT_DIR
                        Path to output directory. Defaults to output.
  --bold                If set, will enable the 'bold' logic for rendering the report.
  --params_json PARAMS_JSON
                        Path to params JSON file.
  --versions_yml VERSIONS_YML
                        Path to versions YAML file.
  --report-debug        Enable debug mode for report generation
  --database-name DATABASE_NAME
                        Name of the reference database
  --facility-name FACILITY_NAME
                        Name of the analysis facility
  --analyst-name ANALYST_NAME
                        Name of the analyst
  --flag-details-csv FLAG_DETAILS_CSV
                        Path to CSV file containing flag definitions
```

The entrypoint for the
report module is
[report.py](https://github.com/qcif/taxodactyl/blob/main/scripts/src/report/report.py)
which includes compilation of report context from analysis output files, followed
by rendering the report. Given that we are rendering a standalone HTML file that
needs to be fully portable and robust, this process involves some tactics that
are not typical of web development:

- Content that would often be loaded over a CDN is included in the repository
  to ensure stability of the product over time.
- Static files (CSS, JavaScript, images) are embedded directly in the HTML file,
  with images encoded in base64. This results in a fairly large HTML file. All
  css/js files in the static directory get embedded in the HTML document, so
  be careful what you put in here (don't bloat the document)
- A "Save report" feature is included that allows the analyst to save any typed
  content and lock the document as read-only. This is a hack that involves a good
  dose of JavaScript (see
  [save-report.js](https://github.com/qcif/taxodactyl/blob/main/scripts/src/report/static/js/save-report.js))


# Building the docs

[Some documentation](../docs/) is written in markdown and rendered for display as a GitHub page. This adds a little more complexity than a GitHub Markdown page, but it allows us to render parameters directly into the HTML which helps to keep things up-to-date. If some parameters have changed, or been overridden with an [environment variable](https://qcif.github.io/taxodactyl/environment.html), you can re-render these docs and those values will be updated.

See [setup](#developer-setup) if you don't have a Python environment yet for this repo yet.

```
# Activate your python environment
source activate venv

python scripts/dev/render_docs.py

git commit -m "Update documentation"
git push
```

This will prompt the github.io docs pages to rebuild, which takes 2-3 minutes.


# Version release

There (annoyingly) are 4 places where the version must be updated:

```
# cloudgene.yml
version: 1.3.3

# conf/manifest.config
    version         = '1.3.3'

# scripts/VERSION
1.3.3

# scripts/pyproject.toml
version = "1.3.3"
```

Then you can create a branch like `release_1.3.3`, and create GitHub release v1.3.3 with `release_1.3.3` as the target.
The docker image (for python scripts) will be built on version release. If you need to make a pre-release to obtain a build, you should make a pre-release version like `1.3.3-dev` before releasing `1.3.3`.


# Application features


## Application configuration

The application uses a flexible YAML-based configuration system with Pydantic validation. Configuration is defined in [config_schema.py](./src/utils/config_schema.py) and loaded via the [config.py](./src/utils/config.py) module, which provides a singleton Config object for runtime access.

```py
from src.utils.config import Config

config = Config()  # Returns a singleton, shared across all modules
sample_id = config.get_sample_id(query_ix)
```

The configuration system supports cascading files and CLI argument overrides. For detailed configuration usage, examples, and the full schema documentation, see: **[./config/README.md](./config/README.md)**

### For developers: Maintaining configuration

When modifying the Pydantic configuration schema, you **must** regenerate the default configuration file:

```bash
python dev/generate_default_config.py
```

This ensures `config/default.yml` stays synchronized with the schema defined in `config_schema.py`. This step is critical for maintaining consistency between the code and configuration files.


## Handling errors

There are numerous locations in the workflow where non-fatal errors can occur.
At minimum, a log statement is written to record these, but typically the
[errors.py](https://github.com/qcif/taxodactyl/blob/main/scripts/src/utils/errors.py)
module is used to track these errors and render them at the appropriate place in
the HTML report:

```py
# An exception has been caught in P5 database coverage
errors.write(
    errors.LOCATIONS.DB_COVERAGE,
    'A really bad error has occured while analysing this taxon',
    exc=e,  # If an Exception was caught
    context={'target': 'Homo sapiens'},
)
```

The `LOCATION` provided corresponds to a named location where the error occurred
in the analysis, and this also maps to a specific location in the report. The
`context` dict provides additional context on what exactly was being analysed
(e.g. which target taxon) when the error occurred. So for the example above, we
know when rendering the report that this error should be shown at the
`DB_COVERAGE` location, for the target *Homo sapiens*.

In practice, the `errors` module has a neat filter that can be used for
rendering these in our Jinja2 templates:

```html
<!-- Filter to get a range of locations relevant to this report section -->
<!-- errors.LOCATIONS.DB_COVERAGE_NO_GBIF_RECORD = 5.01 -->
{% set p5_01_errors = errors.filter(location=5.01, context={'target': context.target_taxon}) %}

{% if p5_01_errors %}
{{ render_error_message(p5_01_errors) }}
{% endif %}
```

## Throttling API requests

The P5 script results in many threads across multiple independent processes
(one per-sample, as orchestrated by Nextflow) sending LOTS of API requests.
Without some kind of throttling mechanism, we would quickly get blocked by NCBI,
GBIF, BOLD, or other APIs that we access in the workflow. For this reason, ALL
requests to external APIs need to go through the Throttle. The example below
shows the Throttle being used via its `with_retry()` method to retry the
request several times before raising an exception.

```py
kwargs = {
    'species': 'Homo sapiens',
    'country': 'CA',
}
throttle = Throttle(ENDPOINTS.GBIF_FAST)
res = throttle.with_retry(
    pygbif.occurrences.search,
    kwargs=kwargs,
)
```

The throttle works by writing timestamps to a SQLite3 table which is stored
in the user's temp files and shared across instances. When a thread is being
throttled, the timestamps in the database are checked until they indicate
that less than 10 requests have been sent in the last second. At that point,
whichever thread is "lucky enough" to acquire the database lock is able to
write its timestamp to the table and then the throttle for that thread is
released. The database table used depends on the `ENDPOINT` that the throttle
was created with, as each endpoint is throttled independently:

https://github.com/qcif/taxodactyl/blob/main/scripts/src/utils/throttle.py#L14-L31


## Caching API responses

Many of the external API calls made during P4/P5 are expensive and idempotent
(e.g. GBIF species lookups, NCBI taxonomy, publication metadata). To avoid
repeating the same request across reruns - or across the many threads spawned
within a single run - responses are cached via the
[cache.py](./src/utils/cache.py) module.

Use the module-level `get`/`put` API, keying entries with `keyhash()` which
accepts any number of hashable items (strings, ints, callables, objects with
a `serialize()` method):

```py
from src.utils import cache

key = cache.keyhash('gbif.species_suggest', 'Homo sapiens')
result = cache.get(key)
if result is None:
    result = throttle.with_retry(pygbif.species.name_suggest, kwargs={...})
    cache.put(key, result)
```

The `get`/`put` calls delegate to a singleton `CacheBackend` selected by
`config.cache_backend`. Two backends are shipped:

- **`sqlite`** (default) - stores entries in a local SQLite database with
  WAL mode and `fcntl` file locks to coordinate concurrent access across
  threads and processes on the same host. This is what runs during
  development and on a single-node deployment.
- **`azure_blob`** - stores each entry as a single blob in an Azure Blob
  Storage container. Intended for deployment on Azure Batch where ephemeral
  compute nodes share a cache over the network. Azure Blob Storage provides
  last-writer-wins semantics on `PUT`, so no cross-node locking is required.
  See [docs/azure/01-initial-setup.md](../docs/azure/01-initial-setup.md)
  for provisioning instructions.

Backends subclass the abstract `CacheBackend` and must implement `get()` and
`put()`. A `lock()` context manager can optionally be overridden for
backends that need cross-process coordination around schema/setup (the
SQLite backend does this; the Azure backend does not). Both backends
honour `config.cache_timeout_hours` and best-effort delete expired entries
on read. For the Azure backend, the authoritative garbage collector is the
storage account lifecycle rule defined in
[deployment/azure/storage-policy.json](../deployment/azure/storage-policy.json).

The active backend is controlled by these config fields (also settable via
env vars - see [config/README.md](./config/README.md)):

```yaml
cache_backend: sqlite          # or 'azure_blob'
cache_timeout_hours: 168       # 7 days
cache_sqlite_path: /tmp/...    # sqlite backend only
cache_azure_container: cache   # azure_blob only
cache_azure_connection_string: ...  # azure_blob only (preferred)
cache_azure_account_url: ...        # azure_blob only (DefaultAzureCredential)
cache_azure_blob_prefix: ''         # azure_blob only, optional namespace
```

Cache entries are pickled, so values must be `pickle`-safe. Errors during
`get`/`put` (missing blob, corrupt pickle, transport errors, SDK exceptions)
are logged and swallowed - a cache failure should never break the analysis,
it just results in the upstream API call being repeated.


## Secrets vault

The [secrets.py](./src/utils/secrets.py) module provides persistent, encrypted
storage for user-supplied credentials — specifically the NCBI API key and
facility name — so that users do not need to pass them on the command line on
every run.

`Config` exposes a `vault` cached property that returns a `Vault` instance
backed by whichever backend is appropriate for the current environment:

```py
from src.utils.config import Config

config = Config()
config.vault.put('NCBI_API_KEY', config.USER_EMAIL, 'my-key')
value = config.vault.get('NCBI_API_KEY', config.USER_EMAIL)
```

Secrets are keyed as `"{secret_name}:{user_email}"` so that different users
sharing the same execution environment maintain independent stores.

### Vault integration in Config

`Config._resolve_ncbi_api_key()` is called during initialisation and
`Config._resolve_facility_name()` is called at the end of `update_from_args()`.
Both follow the same pattern: if a value was supplied by the user (via env var
or CLI), store it in the vault; otherwise, attempt to retrieve a previously
stored value from the vault.

### Backends

Two backends are shipped, selected automatically based on the execution
environment:

**Local (default)** — an AES-encrypted JSON file written to
`config.user_tempdir`. Enabled by setting the `SECRET_KEY` environment variable
to any non-empty passphrase. The key is hashed with SHA-256 to derive a
Fernet-compatible 256-bit key before use. If `SECRET_KEY` is not set, all
vault operations are no-ops (the workflow continues without persisting secrets).

**Azure Key Vault** — delegates to an
[Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/secrets/)
instance via `DefaultAzureCredential`. Enabled when `config.azure_key_vault_enabled`
is `True` (i.e. `AZURE_KEY_VAULT_URL` is set). Secret names are sanitised to
the alphanumeric-and-hyphens format required by Azure Key Vault.

Both backends subclass `VaultBackend` and implement `get()` and `put()`. The
`Vault` class selects the backend in its constructor:

```py
from src.utils.secrets import Vault

vault = Vault(config)        # backend selected from config.azure_key_vault_enabled
vault.put('MY_SECRET', user_email, 'value')
vault.get('MY_SECRET', user_email)  # returns None if not found
```

Errors during `get`/`put` are logged and swallowed — a vault failure should
never interrupt the analysis. If neither `AZURE_KEY_VAULT_URL` nor `SECRET_KEY`
is set the vault disables itself silently (`NullVaultBackend`).

The active backend is controlled by:

| Env var | Backend | Notes |
|---|---|---|
| `SECRET_KEY=<passphrase>` | Local encrypted file | Any string; used to derive the encryption key |
| `AZURE_KEY_VAULT_URL=<url>` | Azure Key Vault | Set in `.env.azure`; picked up automatically by `conf/azure.config` |
| *(neither set)* | Disabled (no-op) | `get` returns `None`, `put` is silently ignored |


## Flags

Flags are a way that we capture and report discrete analytical outcomes clearly
and concisely. For example, `Flag 1A` means that a positive species
identification was concluded from the analysis.

The `flags.csv` file describes the flags and their potential
values in detail - the content in this table is used directly to render the
HTML report, so any text updates here will propagate to the report generation.
Some of the criteria for calling flags is declared in `config.CRITERIA` - refer
the [config section](#application-configuration).

During the analysis (P3-P5) flag files are written in JSON format. These should
be collected by Nextflow and then all passed to p6 script for report generation
at the end. The flag files
can then all be read from the output directory to get a complete "flag set" for
the report. A complete set of flag files should look like this:

```
1.flag
2.flag
4.flag
5.1.flag
5.2.flag
5.3.flag
7.flag
```

Example flag file content:

```json
[
  {
    "flag_id": "5.1",
    "value": "A",
    "target": "Anneissia japonica",
    "target_type": "candidate"
  },
  {
    "flag_id": "5.1",
    "value": "A",
    "target": "Acanthaster planci",
    "target_type": "toi"
  },
  {
    "flag_id": "5.1",
    "value": "A",
    "target": "Asterias rubens",
    "target_type": "pmi"
  }
]
```

Flags have caused a few bugs because sometimes a non-fatal error (usually an
API call) results in a flag file not being written.


## Sample locus

The loci (genetic regions) permitted for query DNA sequences is listed in the
[loci.json](./config/loci.json) file. For each locus, ambiguous and non-ambiguous
synonyms are defined:

```json
  "16s": {
    "ambiguous_synonyms": [
      "16s"
    ],
    "non_ambiguous_synonyms": [
      "16s rrna",
      "16s mitochondrial rrna",
      "16s ribosomal rna"
    ]
  },
```

These are used to build dynamic genbank queries, when we are trying to request
a count of genbank records at a given locus. Non-ambiguous
synonyms are queried against all fields, whereas ambiguous synonyms are queried
against the `[Gene name]` and `[Title]` fields only, to avoid returning records
which are not the intended locus. For example, a query of "COI[ALL]" matches
all kinds of records that have nothing to do with the cytochrome oxidase gene.
All the logic for managing loci and rendering GB query strings is encapsulated
in [locus.py](./src/utils/locus.py).
