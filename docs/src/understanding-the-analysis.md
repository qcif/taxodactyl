While the workflow report aims to be self-documenting, there are many analytical details which the user may wish to understand in further detail. The purpose of this document is to provide this enhanced understanding of what exactly happens during the analysis, and how outcomes are derived from the resulting data.

- To set up and run the workflow, visit the Nextflow workflow repository: [qcif/taxodactyl](https://github.com/qcif/taxodactyl).
- For analysis code (used in the above workflow), see the Python modules repository: [qcif/daff-biosecurity-wf2](https://github.com/qcif/taxodactyl/tree/main/scripts)
- For reference, an example workflow report is available [here](https://qcif.github.io/taxodactyl/example_report.html)

## Table of contents

1. [Interpretting the workflow report](#interpretting-the-workflow-report)
1. [Reference data](#reference-data)
    1. [BLAST](#blast)
    1. [BOLD](#bold)
1. [Input files](#input-files)
    1. [FASTA file](#fasta-file)
    1. [Metadata CSV file](#metadata-csv-file)
1. [BLAST - parsing the XML output](#blast-parsing-the-xml-output)
    1. [Extracted values](#extracted-values)
    1. [Calculated values](#calculated-values)
1. [BLAST - Extracting taxonomic metadata](#blast-extracting-taxonomic-metadata)
1. [BOLD - submitting sequences to ID Engine](#bold-submitting-sequences-to-id-engine)
    1. [Sequence orientation](#sequence-orientation)
    1. [Submitting to ID Engine](#submitting-to-id-engine)
    1. [Requesting additional metadata](#requesting-additional-metadata)
1. [Assigning taxonomic identity](#assigning-taxonomic-identity)
    1. [Checking preliminary morphology ID](#checking-preliminary-morphology-id)
    1. [Checking taxa of interest](#checking-taxa-of-interest)
1. [Phylogenetic analysis](#phylogenetic-analysis)
1. [Assessment of supporting publications](#assessment-of-supporting-publications)
1. [Assessment of database coverage](#assessment-of-database-coverage)
    1. [Obtaining related species](#obtaining-related-species)
    1. [Enumerating GenBank records](#enumerating-genbank-records)
    1. [Occurrence maps](#occurrence-maps)


## Interpretting the workflow report

The workflow report aims to deliver clear outcomes with supporting evidence. The taxonomic identity (or lack thereof) is the first thing to be reported. The remainder of the report serves to corroborate supporting evidence for that claim.

<p class="alert alert-warning">
    It is crucial that the reader pays attention to supporting evidence when evaluating the report. Even when a positive identity is reported, there are other aspects of the analysis that can subtract from the credibility of such an outcome. Most notably, it is possible that a positive species identification could be based on a single reference sequence with an incorrect taxonomic annotation. In this case the result would obviously be erroneous. The potential for this error would be raised in the section "Publications supporting taxonomic association", which would flag that there is only one independent publication source supporting the outcome.
</p>

### Results overview

1. Check the taxonomic outcome (the first item under "Result overview")
1. If positive, the [Preliminary ID](#metadata-csv-file) will be either confirmed or rejected
    1. If rejected, you may wish to check the database coverage (square button) to ensure that the taxon is represented in the reference database
1. If Taxa of Interest (TOIs) were provided, check whether they were detected.
    1. If not detected, you may wish to check the database coverage to ensure that the taxon is represented in the reference database. A brief overview of TOI coverage is provided beneath the TOI item; this shows the highest observed warning level from each of the provided TOIs. For the full database coverage reports, go to the "Taxa of interest" report section.

### Candidate species

1. First take a look at the hit classification table (top-right). This shows how many hits were returned, and how they have been classified for the purpose of the analysis. You will typically see a few candidate species and many that are classified as `NO MATCH`. The first row of `STRONG MATCH` and `MODERATE MATCH` with 1+ species determines the [identity threshold](#assigning-taxonomic-identity) for identifying candidates.
1. Check the "Candidate species" table. For each species, you should take note of:
    1. Number of hits - >5 hits gives more confidence in the taxonomic annotation of reference sequences
    1. Top identity - with multiple candidates, a stark drop in identity between species provides higher confidence
    1. Median identity - if >0.5% lower than the top identity, this indicates high intraspecific diversity or possibly misidentified reference sequences.
    1. Database coverage - if the identity is not 100% and there are species in the genus with no database representation, it's possible that the true identity of the sample could be one of the unrepresented species.
1. If there are multiple candidates, the report will prompt the analyst to make a genus-level assignment for the sample. To aid in this process the analyst should refer to:
    1. The identities (top and median) of each candidate
    1. The phylogenetic tree, to see how the query sequence relates to the reference sequences. We hope to see the query sequence clustering with a monophyletic clade of one species.


### Taxa of interest

See [Checking taxa of interest](#checking-taxa-of-interest)


## Reference data

### BLAST

The reference data used by the workflow depends entirely on the deployment - ask your platform administrator if you are unsure.
For the BLAST version of the workflow, the reference data will be a BLAST database of sequence records that is held on the analysis server - by default this is `{{ config.REPORT.DATABASE_NAME }}`, but it is possible to run with a different reference database. The workflow report specifies the database name in the database coverage report (admins can set this manually with `BLAST_DATABASE_NAME`).

### BOLD

By default this is set to `{{ config.BOLD_DATABASE }}` (admins can override this by setting `BOLD_DATABASE`).

## Input files

### FASTA file

A FASTA file containing sample sequences to be analysed. Multiple sequences per sample can be used, but the FASTA header for each sequence must be unique and match an entry in the `metadata.csv` input. The following constraints apply to this input:

- Seq IDs must be unique
- Seq IDs must match `metadata.csv` input
- Maximum query sequences: `{{ config.INPUTS.FASTA_MAX_SEQUENCES }}`
- Minimum seq length: `{{ config.INPUTS.FASTA_MIN_LENGTH_NT }}nt`
- Max length of any sequence: `{{ config.INPUTS.FASTA_MAX_LENGTH_NT }}nt`
- All residues must be valid nucleotide (ambiguous IUPAC DNA: `ATGCRYSWKMBDHVN`)

### Metadata CSV file

This file provides metadata for each query sequence, with the following fields:

| Field             | Required | Description                                                                                                         |
|-------------------|----------|---------------------------------------------------------------------------------------------------------------------|
| sample_id         | yes      | Must match the header of one FASTA sequence                                                                         |
| locus             | yes      | Must be in the [list of allowed loci](./allowed-loci.html) or `NA` for virus or BOLD queries (note that this can be modified by updating [this file](https://github.com/qcif/taxodactyl/blob/main/assets/loci.json)).
| preliminary_id    | yes      | A suggested taxonomic identity based on sample morphology                                                           |
| taxa_of_interest  | no       | A pipe-delimited list of taxa to be evaluated against the sample. Can be at rank species, genus, family, order, class, phylum, kingdom or domain. |
| country           | no       | The sample country of origin                                                                                        |
| host              | no       | The host or commodity that the sample was extracted from                                                            |

<p class="alert alert-info">
  From <code>v1.1</code> any additional fields in this file will be displayed in the workflow report
</p>

## BLAST - parsing the XML output

BLAST search is performed using a local (meaning run on the same machine as the workflow) BLASTN from the [NCBI BLAST+ toolkit](https://blast.ncbi.nlm.nih.gov/doc/blast-help/downloadblastdata.html); the version is specified in the workflow report. This command-line BLASTN process produces a series of alignments for each query sequence, with each alignment relating to a BLAST "hit" against a sequence in the reference database.

<p class="alert alert-info">
    This step forks a single BLAST result into a series of query directories. From here each query's results are analysed in parallel.
</p>

### Extracted values

The following values are extracted verbatim from BLAST XML fields:

- Hit identifier (GenBank ID)
- Hit definition (GenBank record title)
- Hit NCBI accession
- Hit subject length (nt)
- High-scoring pairs (HSPs; each represents a segment of the alignment):
    - bitscore
    - evalue
    - identity
    - query_start
    - query_end
    - subject_start
    - subject_end
    - alignment_length

### Calculated values

These values are not present in the BLAST XML and are calculated from the extracted values:

<table class="table table-striped">
    <thead>
        <th>Value</th>
        <th>Description</th>
        <th>Equation</th>
    </thead>
    <tbody>
        <tr>
            <td>
                Alignment length
            </td>
            <td>
                The total non-overlapping length of all HSPs.
            </td>
            <td>
            </td>
        </tr>
        <tr>
            <td>
                Hit bitscore
            </td>
            <td>
                A score which takes into account both alignment strength and length. Calculated as the sum of bitscores across all HSPs.
            </td>
            <td class="text-center p-3">
                \( \sum_{HSP \in \text{HSPs}} \text{bits}(HSP) \)
            </td>
        </tr>
        <tr>
            <td>
                Hit E-value
            </td>
            <td>
                An expression of probability that the alignment occurred due to random chance, often expressed as an exponent to distinguish between very low numbers. If there is only one HSP, the `hsp.evalue` will be used. Otherwise, a formula is used.
            </td>
            <td class="text-center p-3">
                \( \text{ess} \cdot 2^{-\sum_{HSP \in \text{hit.HSPs}} \text{bits}(HSP)} \)
                <br>
                <em>Where <code>ess</code> is the effective search space specified in the BLAST XML output.</em>
            </td>
        </tr>
        <tr>
            <td>
                Hit identity
            </td>
            <td>
                The proportion of nucleotides which match between query and subject in the alignment. This is calculated as the weighted identity of HSPs (high-scoring pairs), clipped to a maximum of 1.
            </td>
            <td class="text-center p-3">
                \(
                    \frac{\sum_{HSP \in \text{HSPs}} \text{identities}(HSP)}{\sum_{HSP \in \text{HSPs}} \text{alignment length}(HSP)}
                \)
            </td>
        </tr>
        <tr>
            <td>
                Query coverage
            </td>
            <td>
                The proportion of the query sequence that is covered by the alignment with the reference sequence.
            </td>
            <td class="text-center p-3">
                \(
                    \frac{\text{alignment length}}{\text{query length}}
                \)
            </td>
        </tr>
    </tbody>
</table>

## BLAST - Extracting taxonomic metadata

BLAST results do not include structured taxonomic information. This data is extracted for each BLAST hit subject using [taxonkit](https://bioinf.shenwei.me/taxonkit/), a command-line tool which can retrieve taxonomic records from NCBI's [taxdump](https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/) archive. Taxids for each hit are extracted from the local BLAST database using `blastdbcmd`, another tool in the BLAST+ suite. This results in the following fields being collected for each hit:

- Taxid
- Domain
- Superkingdom
- Kingdom
- Phylum
- Class
- Order
- Family
- Genus
- Species

## BOLD - submitting sequences to ID Engine

When the workflow is run in `--bold` mode, the search method changes to use the BOLD ID Engine through the BOLD API ([https://v4.boldsystems.org/resources/api](https://v4.boldsystems.org/resources/api)). Since BOLD requires query DNA sequences that are correctly orientated (i.e. not antisense), we attempt to orientate the query sequences before submission. Query sequences are then submitted to the ID Engine API on-by-one. BOLD then returns a set of match statistics similar to BLAST for each query.

<p class="alert alert-info">
    This step forks each BOLD into a series of query directories. From here each query's results are analysed in parallel.
</p>

### Sequence orientation

Each DNA sequence is translated all three translation frames in both the forward and reverse directions. This results in six translated amino acid sequences for each query in frames `1`, `2`, `3`, `-1`, `-2`, `-3`.

To orientate each query sequence, we then use the `hmmsearch` tool (part of the [HMMER suite](http://eddylab.org/software/hmmer/Userguide.pdf)) locally to determine whether any the translation frames contain any of the following HMM profiles:

- `pf00115.hmm` - [Cytochrome C and Quinol oxidase polypeptide I](https://www.ebi.ac.uk/interpro/entry/pfam/PF00115/)
- `pf00116.hmm` - [Cytochrome C oxidase subunit II, periplasmic domain](https://www.ebi.ac.uk/interpro/entry/pfam/PF00116/)
- `pf02790.hmm` - [Cytochrome C oxidase subunit II, transmembrane domain](https://www.ebi.ac.uk/interpro/entry/pfam/PF02790/)

A match is accepted when the E-value is below `{{ config.HMMSEARCH_MIN_EVALUE }}`. The first frame which is predicted to encode one of these domains dictates the orientation that will then be submitted to BOLD. For query sequences with no matches, both the forward and reverse orientations are submitted to BOLD and the one which returns hit(s) is assumed to be in the correct orientation (the other orientation's result is discarded).

### Submitting to ID Engine

Orientated query sequences are submitted to the ID Engine API sequentially, and the requests run in parallel to increase throughput.
The following data are parsed directly from the API response:

- Query title
- Query length
- Query frame
- Query sequence
- Hits:
    - Hit identifier (BOLD ID)
    - Hit sequence description
    - Hit taxonomic identification (species)
    - Hit similarity (used in place of identity)
    - Hit URL (a link to the record on [https://boldsystems.org](https://boldsystems.org))
    - Hit nucleotide sequence
    - Hit collectors (BOLD database submitter(s))

### Requesting additional metadata

For each hit subject, additional metadata are then requested from the "Full data retrieval" BOLD API endpoint:

- Accession (GenBank accession)
- Phylum
- Class
- Order
- Family
- Genus
- Species

The above fields are then used to fetch a kingdom classification (not included in BOLD response data) from the GBIF API.
The phylum given above is used to fetch a the associated phylum record from the [GBIF species search API](https://techdocs.gbif.org/en/openapi/v1/species#/Searching%20names/searchNames), and the kingdom field is extracted from the response data.

## Assigning taxonomic identity

This is a critical stage in the analysis. Hits returned from BLAST/BOLD are filtered and a list of candidate species is extracted from those hits. Filtering is applied as follows. For BOLD search, the process is identical, with similarity being used in place of identity.

- All hits which are below `{{ config.CRITERIA.ALIGNMENT_MIN_NT }}nt` AND `{{ config.CRITERIA.ALIGNMENT_MIN_Q_COVERAGE * 100 }}%` query coverage are excluded from the entire analysis. These are referred to as "filtered hits".
- The identity threshold for candidate hits is either:
    - `{{ config.CRITERIA.ALIGNMENT_MIN_IDENTITY_STRICT * 100 }}%` (if any filtered hits meet this threshold) - defined as a **STRONG MATCH**
    - OR `{{ config.CRITERIA.ALIGNMENT_MIN_IDENTITY * 100 }}%` - defined as a **MODERATE MATCH**
- Resulting candidate hits are then aggregated by species and the top hit per-species is identified. These species are what you see reported in the "Candidates" section of the workflow report.
- The "No. hits" shown for each candidate includes all filtered hits, not just the candidate hits.
- The "Median identity" shown in the "Candidate species" table is derived from the identity (%) of all filtered hits. If there is a wide distribution of hit identities, the median will be reduced. If the median drops below the candidate threshold, the badge will turn from green to yellow. If it drops to less than `{{ config.CRITERIA.MEDIAN_IDENTITY_WARNING_FACTOR * 100 }}%` of the threshold (i.e. `<{{ (config.CRITERIA.ALIGNMENT_MIN_IDENTITY_STRICT * 100 * config.CRITERIA.MEDIAN_IDENTITY_WARNING_FACTOR) | round(1) }}%` for a threshold of `{{ config.CRITERIA.ALIGNMENT_MIN_IDENTITY_STRICT * 100 }}%`), the badge will turn red.

The candidate species identified above are then cross-checked against the Preliminary Morphology ID and Taxa of Interest (if provided).

### Checking preliminary morphology ID

The PMI provided by the user is checked against each taxonomic rank from each candidate species. If the provided name matches any of the fields, this is regarded as a match. The user should be aware that in some edge-cases this can result in a mis-match due to the existence of taxonomic homonyms (*Morus*, for example, is both a plant and bird genus).

### Checking taxa of interest

This process is identical to that described above, except that a little more information is collected for display in the "Taxa of interest" section of the workflow report. For each taxon of interest, the best-scoring species that matches the taxonomy is reported. It is possible for a TOI to match multiple candidates, but only the top candidate will be shown.

### Boxplot of identity distribution

When the analysis identifies more than {{ config.MAX_CANDIDATES_FOR_ANALYSIS }} candidate species, the analyst is prompted to make a subjective genus-level taxonomic assignment. To assist in this, a boxplot which shows the distribution of hit identities per-species is included in the report.


## Phylogenetic analysis

Subject sequences are selected from filtered hits [extracted previously](#assigning-taxonomic-identity).
The selection process is a little complex, as it aims to strike a balance between reasonable coverage of the genetic diversity present in BLAST/BOLD hit subjects, while also trying to minimize the number of sequences that need to go through alignment and analysis. Building trees with 100+ sequences is SLOW and the resulting tree is often ugly, so we do our best to avoid that.

1. Hits are collected in order of descending identity until at least {{ config.CRITERIA.PHYLOGENY_MIN_HIT_SEQUENCES }} hits have been collected. This means that candidate hits are always collected for sampling, and filtered hits are included if there aren't enough to form a good tree.
2. Next, if there are more than {{ config.CRITERIA.PHYLOGENY_MAX_HITS_PER_SPECIES }} hits for a species, these hits are strategically sampled to ensure that sequence diversity is accurately represented:

- Hits are ordered by identity
- A systematic sample of n={{ config.CRITERIA.PHYLOGENY_MAX_HITS_PER_SPECIES }} hits is taken, which always includes the first and last hit

This sampling strategy is illustrated below for clarity, assuming a species where 45 hits have been collected and a sample size of `n=5`:

![systematic sampling of hits](https://github.com/qcif/taxodactyl/blob/main/docs/images/systematic-sample.png?raw=true)

<p class="alert alert-info">
    The workflow restricts the number of sequences to 30 per species by default, which strikes a balance between reasonable run time and representation of genetic diversity. Setting this sample size too low would result in poor quality trees that may give a false impression of genetic diversity to the user. Setting it too high would result in very long run times and large trees that are difficult to interpret. Please refer to the
    <a href="https://github.com/qcif/taxodactyl/blob/main/docs/params.md">
      Nextflow docs
    </a>
    for adjustment of workflow parameters.
</p>

A FASTA sequence is then written by extracting the nucleotide sequence from each of the selected hits, and adding the query sequence.
This FASTA file is then alignment with [MAFFT](https://mafft.cbrc.jp/alignment/server/index.html), and then a tree is computed from the alignment with [FastME](http://www.atgc-montpellier.fr/fastme/).

## Assessment of supporting publications

An important drawback of searching against the large Non-redundant (Nr) BLAST database is that this database contains many sequences which are not very reputable. Since anyone can submit sequences to GenBank there are many sequences with incorrect taxonomic annotation. This analysis presents a measure of confidence in the integrity of the reference sequences supporting the conclusions. Are the candidate reference sequences supported by numerous publications? Great, that means that the taxonomic annotation has been corroborated by multiple studies. Do we have 5 reference sequences that were all submitted to GenBank by the same author(s)? That casts some doubt over the integrity of the taxonomic annotation.

<p class="alert alert-warning">
    Even when the workflow report is "green" in all other sections of the report, caution is advised if there is only one independent publication corroborating the reference sequences. Further investigation may be required to confirm the credibility of the reference sequence source.
</p>

The analysis involves clusting of GenBank publication records based on the provided metadata (author, title, journal). An independent analysis is carried out per-candidate species:

1. For each [candidate hit](#assigning-taxonomic-identity), a list of publications is extracted from the corresponding GenBank record using the Entrez `efetch` API.
1. Each publication is annotated with:
    1. The NCBI accession number
    1. A `source tag`, which is a token derived (by stripping non-alphanumeric characters and converting to lowercase) from one of the following fields (the field with a value):
        1. Author list
        2. Publication title ("Direct submission" titles are ignored here as they are computed-generated and not a real publication)
        3. Journal
    1. Whether the record appears to have been automatically generated - determined by the presence of the string `##Genome-Annotation-Data-START##` in the GenBank record text.
1. Publications are then clustered into groups of "independent publications":
    1. If a publication `source tag` matches one in an existing group, it is added to that group
    1. Otherwise, it is added to a new group
    1. Records with no publications are allocated to a single group
1. The groups are shown as "independent sources" in the "Publications supporting reference sequences" section of the workflow report.

## Assessment of database coverage

An analysis of taxonomic coverage of the reference database is carried out for each of the following taxa:

- Candidate species (only when `n ≤ {{ config.CRITERIA.MAX_CANDIDATES_FOR_ANALYSIS }}`)
- Preliminary ID taxon (provided in [metadata.csv](#metadata-csv-file))
- Taxa of interest (provided in [metadata.csv](#metadata-csv-file); only when `n ≤ {{ config.DB_COVERAGE_TOI_LIMIT }}`)

Each of these is referred to as a "target taxon" or, more concisely, "target".
For each target, three analyses may be performed:

- `5.1`: number of GenBank records for target taxon at the [given locus](#metadata-csv-file) (if provided)
- `5.2`: number of species in target genus which have 1+ GenBank records at the [given locus](#metadata-csv-file) (if provided)
- `5.3`: as for `5.2`, but with species limited to those which occur in the country of origin (according to GBIF occurrence records)

<p class="alert alert-info">
    Analyses <code>5.2</code> and <code>5.3</code> are only run when the target is of rank genus or species. This is because there would be far too much data to analyse at higher ranks.
</p>

### Obtaining related species

To obtain "species in genus" in analyses `5.2` and `5.3`, we use the GBIF API:

1. A GBIF record is retrieved from the [/species/suggest](https://techdocs.gbif.org/en/openapi/v1/species#/Searching%20names) API using the target taxon as the search query. If the target matches our [list of canonical taxa](https://github.com/qcif/taxodactly/blob/main/scripts/src/gbif/relatives.py#L16), the taxonomic rank specified in that list is set as an API request parameter. This prevents the rather annoying issue of the query "Bacteria" matching the genus "Bacteria" of the Diapheromeridae (a family of Arthropoda).
1. The genus key from the target record is then used to fetch all matching records at rank "species" from the [/species/match](https://techdocs.gbif.org/en/openapi/v1/species#/Searching%20names) API endpoint.
1. Returned speces records are filtered to exclude extinct species, and include only those where status is one of `{{ config.GBIF_ACCEPTED_STATUS }}`.

### Enumerating GenBank records

For each species identified, the Entrez API is used to query GenBank records that match that species at the given locus. The query is dynamically generated to include all synonyms for the locus specified in the workflow's [loci.json](https://github.com/qcif/taxodactyl/blob/main/assets/loci.json) file. the taxid is extracted from NCBI taxonomies [using taxonkit](#blast-extracting-taxonomic-metadata).

For example, the following locus and taxon "Homo sapiens" (taxid `9606`):

```
# loci.json entry for "COI"
{
    "ambiguous_synonyms": [
        "coi",
        "co1",
        "cox",
        "cox1"
    ],
    "non_ambiguous_synonyms": [
        "cytochrome oxidase subunit 1"
    ]
}
```

...would result in this GenBank query being rendered:

```
txid9606[Organism] AND (coi[Title]) OR (coi[GENE]) OR (co1[Title]) OR (co1[GENE]) OR (cox[Title]) OR (cox[GENE]) OR (cox1[Title]) OR (cox1[GENE]) OR (cytochrome oxidase subunit 1)
```

The response returned from Entrez includes a `count` field - this is the data that we use to enumerate records for each species.

### Occurrence maps

In addition to the analyses above, a geographic distribution map is also generated based on occurrence records fetched from the GBIF occurrence API. The number of occurrence records fetched is limited to {{ config.GBIF_MAX_OCCURRENCE_RECORDS }}, because some taxa (e.g. "arthropoda") have far too many occurrence records to fetch in a reasonable length of time.
