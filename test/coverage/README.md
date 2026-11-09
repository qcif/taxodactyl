### Database coverage mode test scenario

Runs the database coverage mode (`--coverage_taxa`) on `coverage.csv`, which has five rows:
a species, a genus, a family, an unresolvable name (a deliberate typo, to exercise the
"no GBIF record" error path), and a duplicate of the genus row (with a locus synonym, a
country code and different casing) that is dropped at validation. Four taxa are analysed.

No BLAST database is needed, because no BLAST search is run in this mode. The test needs
network access to the GBIF and NCBI APIs, so it asserts output counts only: record counts
drift with live data, so the outputs are not snapshotted.

Follow the instructions in `${projectDir}/docs/nf-tests.md` to run this test, changing steps:

- Set `nf-test.config` scenario to `coverage`.
- Set the `CUSTOMISE` values in `test/coverage/nextflow.config` (`params.taxdb`,
  `params.temp_root_dir`, `singularity.cacheDir` and the NCBI credentials).
- Run `nf-test test test/coverage/taxodactyl_coverage.workflow.nf.test`.

This scenario is not part of the CI workflows, which run `test/core` only.
