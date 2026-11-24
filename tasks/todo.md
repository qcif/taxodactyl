# To-do items

Out-of-scope spin-offs found while planning or implementing a task, recorded
so a relevant or dedicated task can pick them up later. This is not a list of
planned tasks: planned briefs are tracked by their own `tasks/<NN>_*.md`
files. Remove an item once a task brief takes it on or it's done. The aim is
an empty list.

One bullet per item: what needs doing and why, its origin
(`task NN_short_name`, issue) and the date.

- Remove the now-unreachable `KINGDOM_TAXA` query rewrite in
  `RelatedTaxaGBIF._get_taxon_record` (`scripts/src/gbif/relatives.py`),
  and its description in P5-010: root names are stopped before any lookup
  (P5-015), so the rewrite no longer affects any target. `KINGDOM_TAXA`'s
  keys are still used by `is_root_taxon`; its `rank`/`canonical_name`
  values would become unused. Origin: task 07_kingdom_targets_not_assessed,
  #354, 2026-11-18.
- Pass rank `species` (not the target's rank) when counting each related
  species in BOLD mode (`get_related_coverage` →
  `_fetch_bold_records_for_species`, P5-043). For a genus-rank target, or a
  not-in-COL target using the NCBI genus fallback whose NCBI rank is genus or
  none, the per-species counts are looked up at the wrong rank (0) or
  rejected (`None`), so 5.2/5.3 are understated. Origin: task
  09_targets_missing_from_col, #353, 2026-11-18.
- Directory parameters with spaces break containerised processes:
  `containerOptions` binds `${file(params.outdir)}` (9 modules, e.g.
  `modules/validate/input/main.nf:7`), `${file(params.taxdb)}` and
  `${file(params.allowed_loci_file).parent}` unquoted, so singularity sees
  a truncated path (`FATAL: could not open image .../dir/out_cov`, seen in
  task 10's smoke run with `--outdir "<scratch>/smoke dir/out_cov"`).
  `docs/params.md:64` says "no spaces" only for `allowed_loci_file`, and
  none of these has a schema pattern. Either quote the binds or add
  patterns so they fail at parameter validation. Origin: task
  10_input_filenames_with_spaces, #358, 2026-11-19.
- Resolve the genus of COL species targets by name too, using the same-name
  genus with the most descendants (P5-011), instead of the record's own
  genusKey. COL has stray duplicate genera (e.g. *Vitivirus* 338017727 holds
  only "Grapevine virus A"), so a target in one gets 1 related species.
  Left out of scope by user decision. Origin: task
  11_inexact_col_match_genus, 2026-11-19.
- Coverage maps for two targets whose names differ only in case (e.g. PMI
  `Bulimulus Sporadicus` and TOI `Bulimulus sporadicus` in 512503_1_Andrew) are
  written as `map_Bulimulus_Sporadicus.png` and `map_Bulimulus_sporadicus.png`.
  They collide on case-insensitive filesystems and in some copy/archive routes; a
  retained copy lost one. Consider case-normalising targets or map filenames in
  `config.get_map_filename_for_target`. Origin: task 12_core_nf_test_assertions,
  2026-11-23.
- Fix `_write_pmi_match` in `scripts/p3_assign_taxonomy.py`: it writes
  `preliminary_id_match.csv` without a line break between header and row
  (P3-D-008). Task 12's core check `C.pmi` deliberately fails, labelled as a
  known defect, until this is fixed (user decision). Add a Python unit test.
  Origin: task 12_core_nf_test_assertions, 2026-11-23.
