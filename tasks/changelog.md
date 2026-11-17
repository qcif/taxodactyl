# Unreleased changes

One line per completed task, added by the task's PR. Used to write release
notes; clear the list below after each release.

- Azure docs and `.env.sample` now describe staging reference data from the public `daffstandard/refdata-wf2` container; the premium storage account and reference-data SAS token steps are removed (task 05_azure_refdata_docs, #338)
- The Selenium review page, pytest failures and `testkit.py promote` now name the target taxon on database coverage and publication drift rows, e.g. `database_coverage.min_bar_count (Homo sapiens)` (task 06_review_drift_species_label)
