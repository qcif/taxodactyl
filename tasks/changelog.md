# Unreleased changes

One line per completed task, added by the task's PR. Used to write release
notes; clear the list below after each release.

- Azure docs and `.env.sample` now describe staging reference data from the public `daffstandard/refdata-wf2` container; the premium storage account and reference-data SAS token steps are removed (task 05_azure_refdata_docs, #338)
- The Selenium review page, pytest failures and `testkit.py promote` now name the target taxon on database coverage and publication drift rows, e.g. `database_coverage.min_bar_count (Homo sapiens)` (task 06_review_drift_species_label)
- Database coverage now reports flags 5.1-5.3 as NA, with an explanation, for kingdom- or domain-level targets such as 'Fungi', instead of failing with 'No GBIF record found'. For samples without a locus, targets that are not assessed (kingdom to family level) now show flag 5 as NA rather than a 'no locus' warning (task 07_kingdom_targets_not_assessed, #354)
