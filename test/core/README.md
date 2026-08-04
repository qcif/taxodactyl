### Core test scenario

version: 1.0
date: 2026-08-04
taxonkit: 2026-05-08
blastdb: 2026-07-29/subset_core_nt

This test scenario consists of a diverse set of samples as described by `metadata.csv`.

The nf-test snapshot and flags have been generated using reference data versions noted above. 

Follow the instructions in `${projectDir}/docs/nf-tests.md` to run this test, changing steps:

#### 3. Required databases

To run this test with the same versions as the snapshot, download and extract:
- Subset blast database from `https://daffstandard.blob.core.windows.net/test-data/taxodactyl/core/refdata/blastdb/2026-07-29.zip` to `${projectDir}/test/core/refdata/blastdb/2026-07-29/`
- Taxonkit from `https://daffstandard.blob.core.windows.net/test-data/taxodactyl/core/refdata/taxdump/2026-05-08.zip` to `${projectDir}/test/core/refdata/taxonkit/2026-05-08/`

In `${projectDir}$/test/core/nextflow.config`, set the following parameters:
```
params.blastdb = "${projectDir}/test/core/refdata/blastdb/2026-07-29/subset_core_nt"
params.taxdb = "${projectDir}/test/core/refdata/taxonkit/2026-05-08/"
```

#### Configuration

- Set `nf-test.config` scenario to `core1
- Set `params.mock_blast` to false to run blast using the subset database. 