# Unreleased changes

One line per completed task, added by the task's PR. Used to write release
notes; clear the list below after each release.

- Azure docs and `.env.sample` now describe staging reference data from the public `daffstandard/refdata-wf2` container; the premium storage account and reference-data SAS token steps are removed (task 05_azure_refdata_docs, #338)
- The Selenium review page, pytest failures and `testkit.py promote` now name the target taxon on database coverage and publication drift rows, e.g. `database_coverage.min_bar_count (Homo sapiens)` (task 06_review_drift_species_label)
- Database coverage now reports flags 5.1-5.3 as NA, with an explanation, for kingdom- or domain-level targets such as 'Fungi', instead of failing with 'No GBIF record found'. For samples without a locus, targets that are not assessed (kingdom to family level) now show flag 5 as NA rather than a 'no locus' warning (task 07_kingdom_targets_not_assessed, #354)
- Database coverage now picks the correct GBIF record when the Catalogue of Life has duplicate accepted records with the same name (e.g. *Drosophila*), avoiding intermittent 5.2 ERR flags, and notes the choice in the report (task 08_col_duplicate_name_tiebreak, #351)
- Database coverage now evaluates targets that aren't in the Catalogue of Life (e.g. unclassified viruses or virus common names) using their NCBI taxid, and checks related species through their NCBI genus when that genus is in the Catalogue of Life. The report explains which checks could be run, instead of dropping the target (task 09_targets_missing_from_col, #353)
- Input files (`--metadata`, `--sequences`, `--coverage_taxa`) may now have spaces in their file or folder names (task 10_input_filenames_with_spaces, #358)
