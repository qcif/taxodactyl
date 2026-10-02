# Contract: shared filenames (Nextflow ↔ Python)

Single source: `scripts/config/default.yml`. Nextflow reads it in
`conf/filenames.config` and exposes it as `task.ext.*`; Python reads it
via `Config`. Values and the schema-default discrepancies are tabulated in
[../python/shared/config.md §3.5](../python/shared/config.md).

| `task.ext.*` key | `default.yml` key | Value | Used in Nextflow by |
|---|---|---|---|
| `accessions_filename` | `accessions_filename` | `accessions.txt` | EXTRACT_HITS output |
| `blast_xml_filename` | — (Nextflow constant) | `blast_result.xml` | BLAST_BLASTN, MOCK_BLASTN, publish |
| `hits_fasta` | `hits_fasta` | `all_hits.fasta` | EXTRACT_HITS output + publish |
| `hits_json` | `hits_json` | `all_hits.json` | EXTRACT_HITS output |
| `query_title_file` | `query_title_file` | `query_title.txt` | EXTRACT_HITS output |
| `taxonomy_file` | `taxonomy_file` | `taxonomy.csv` | EXTRACT_TAXONOMY output |
| `bold_taxonomy_json` | `bold_taxonomy_json` | `bold_taxonomy.json` | BOLD_SEARCH output (never written, P1B-D-003) |
| `candidates_count_file` | | `candidates_count.txt` | EXTRACT_CANDIDATES |
| `candidates_phylogeny_fasta` | `phylogeny_fasta` | `candidates_phylogeny.fasta` | EXTRACT_CANDIDATES, MAFFT |
| `candidates_fasta` / `_csv` / `_json` | | `candidates.fasta` / `.csv` / `.json` | EXTRACT_CANDIDATES |
| `boxplot_img` | `boxplot_img_filename` | `candidates_identity_boxplot.png` | EXTRACT_CANDIDATES |
| `taxonomy_id_csv` | | `assigned_taxonomy.csv` | EXTRACT_CANDIDATES |
| `pmi_match_csv` | | `preliminary_id_match.csv` | EXTRACT_CANDIDATES |
| `toi_detected_csv` | | `taxa_of_concern_detected.csv` | EXTRACT_CANDIDATES |
| `independent_sources_json` | | `aggregated_sources.json` | EVALUATE_SOURCE_DIVERSITY |
| `candidates_sources_json` | | `candidates_sources.json` | (unused) |
| `candidates_msa` | — (Nextflow constant) | `candidates_phylogeny.msa` | MAFFT_ALIGN |
| `tree_nwk` | `tree_nwk_filename` | `candidates_phylogeny.nwk` | FASTME, REPORT |
| `log_filename` | `log_filename` | `run.log` | all Python processes |
| `versions_yml` | — (Nextflow constant) | `versions.yml` | tool processes |

## Hard-coded on the Nextflow side (not from config)

`sequences.fasta`, `metadata.csv`, `taxids.csv`, `id_mapping.tsv`,
`4.flag`, `db_coverage.json` (Python default equals it), `5*flag`,
`map*png` (Python template `map_<taxon>.png`), `errors/*`, `*_stat.txt`,
`*.matrix.phy`, `query_*`, `timestamp.txt`.

| ID | Requirement |
|---|---|
| FN-001 | Changing any value above requires the same change in `default.yml`, this table, every consumer in both layers, and the nf-test/flag fixtures. |
| FN-002 | The hard-coded names above SHOULD be moved to `default.yml` so this contract has one source (currently a defect-in-waiting, see CFG-D-001). |
