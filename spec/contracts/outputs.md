# Contract: what a run publishes (`--outdir`)

**Producer:** every Nextflow `publishDir` directive, across every
process ([processes.md](../nextflow/processes.md)). **Consumer:** the
analyst, and any downstream system reading the output tree (none exist
today for the machine-readable files — see `OUT-D-001`).

**Only these files reach the output directory**; everything else stays
in the Nextflow work directory.

```
<outdir>/
├── blast_result.xml                  BLAST XML, all queries (BLAST mode; mocked copy under mock_blast)
├── run.log                           concatenated process logs (arrival order)
├── pipeline_info/
│   ├── execution_report_<ts>.html
│   ├── execution_timeline_<ts>.html
│   ├── execution_trace_<ts>.txt      includes `workdir` column (NF-CF-030)
│   ├── pipeline_dag_<ts>.html
│   └── params_<ts>.json              ALL params, incl. secrets given on CLI (P6-D-001)
├── errors/<PROCESS>/<tag>.{out,err,log}     only if a task failed/aborted (NF-WF-004)
└── query_<NNN>_<sample_id>/
    ├── all_hits.fasta                (see contracts/hits.md; last-HSP fragments, P1-D-001)
    ├── candidates.fasta
    ├── candidates.csv
    ├── candidates_identity_boxplot.png     only if selected species > max_candidates_for_analysis
    ├── candidates_phylogeny.fasta
    ├── candidates_phylogeny.msa
    ├── candidates_phylogeny.nwk
    └── report_[BOLD_]<sample_id>_<timestamp>.html
```

| ID | Requirement |
|---|---|
| OUT-001 | A query directory exists in `<outdir>` iff at least one of its listed files was produced (created lazily by `publishDir`). A query that failed early has **no** directory. |
| OUT-002 | The HTML report is the only place flags, source diversity, database coverage, maps and non-fatal errors are presented. |
| OUT-003 | Report file name uses the sample id with `.` replaced by `_` and every character outside `[\w\-_.]` replaced by `_`; the timestamp is the workflow start (`YYYY-MM-DD_HH:MM:SS` sanitised) or `DEBUG`. |
| OUT-004 | The output directory MUST NOT contain secrets. **Violated** by `params_<ts>.json` and the report (P6-D-001). |

## Gaps

| ID | Gap |
|---|---|
| OUT-D-001 | Medium: **no machine-readable per-query result** is published. Flags (`*.flag`), `candidates.json`, `db_coverage.json`, `aggregated_sources.json` and `errors/*.json` stay in the work directory, so downstream systems must parse the HTML. (The nf-test flag baseline works from the work directory for this reason.) |
| OUT-D-002 | Low: `docs/output.md` and README list `all_hits.fasta` etc. but not the absence of run-level status; there is no file saying which queries were skipped, failed or produced no report (NF-D-003). |
| OUT-D-003 | Low: `blast_result.xml` is published even for mocked runs, and `mode: 'copy'` is hard-coded (the `publish_dir_mode` parameter is inert), so outputs are duplicated from the work directory. |

---

## Provenance

**Initially derived from:** every `publishDir` directive (all `mode: 'copy'`), `conf/misc.config`, `main.nf`. v1.5.0.

This spec is the source of truth from this point on: when the code and
this document disagree, change the code to match the spec — not the
other way around.
