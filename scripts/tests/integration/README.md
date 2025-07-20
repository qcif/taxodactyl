# Integration tests

These are thin tests, in that they run the entire Python-side workflow without
making any assertions - only ensuring that each test case runs without error.
The strength of these tests is that each test case covers a different scenario
that has raised errors in the past.

It's a long test that requires some internet bandwidth for API calls, so be
aware of that before running.

Requirements of running this suite:

- Virtual environment at $project_root/venv with requirements installed
- NCBI Taxdump data dir must be available (set in launch.json):
  ftp://ftp.ncbi.nih.gov/pub/taxonomy/taxdump.tar.gz
- taxonkit binary must be available in PATH
