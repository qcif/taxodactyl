### Output Files and Folders

#### Top-level files and folders

- **blast_result.xml**  
  The raw BLAST XML output for all queries (only present for BLAST runs).

- **pipeline_info/**  
  Contains pipeline execution metadata and reports:
  - `execution_report_<timestamp>.html` – Interactive summary of the pipeline run.
  - `execution_timeline_<timestamp>.html` – Timeline view of process execution.
  - `execution_trace_<timestamp>.txt` – Detailed trace of all executed processes (time, CPU, memory used, etc.).
  - `params_<timestamp>.json` – JSON file with all pipeline parameters used for the run.
  - `pipeline_dag_<timestamp>.html` – Visual representation of the workflow as a directed acyclic graph.

#### Per-query folders

Each query sequence gets its folder `query_<NUM>_<SAMPLE_ID>`. Inside each folder:

- **all_hits.fasta**  
  FASTA file containing all database hits for the query sequence.

- **candidates.csv**  
  Table listing candidate hits for the query, with relevant statistics.

- **candidates.fasta**  
  FASTA file of candidate sequences selected for further analysis.

- **candidates_identity_boxplot.png**  
  Boxplot image visualising identity values of candidate hits (generated only when the number of candidate species is higher than `params.max_candidates_for_analysis`).

- **candidates_phylogeny.fasta**  
  FASTA file of sequences used for generation of phylogenetic tree.

- **candidates_phylogeny.msa**  
  Multiple sequence alignment (MSA) file of candidate and query sequences.

- **candidates_phylogeny.nwk**  
  Newick-format phylogenetic tree file for the candidate and query sequences.

- **report_<...>.html**  
  Detailed HTML report for the query, summarising results, supporting evidence, and visualisations.  
  - For BLAST runs: `report_<SAMPLE_ID>_<timestamp>.html`
  - For BOLD runs:  `report_BOLD_<SAMPLE_ID>_<timestamp>.html`
  
  See [this document](https://qcif.github.io/daff-biosecurity-wf2/understanding-the-analysis.html) for tips on understanding the analysis and interpreting the final HTML report.
