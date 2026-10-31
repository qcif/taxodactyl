# To-do items

- 02_test_profile_small_core — Add a quick supported BLAST smoke check using
  `test/smoke/`, then switch the routine check to captured XML replay;
  paused pending Task 01 merge. On resume, review whether a dedicated
  `test_bold_guard.sh` is needed against Task 01's merged validation coverage.
- 04_expand_blast_hit_context — Address #160: use the existing hit cap
  (default 2000) for BLAST, parsing and reporting,
  and retain 500-hit blocks until the last aggregate identity is <=93.5%
  or hits run out; keep the entire final block for downstream screening.
