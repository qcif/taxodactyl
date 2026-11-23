# To-do items

Out-of-scope follow-ups discovered while implementing this branch's tasks.

- Fix the missing newline in `_write_pmi_match` (`scripts/p3_assign_taxonomy.py`),
  already catalogued as P3-D-008 in the source specification checkout. The new
  raw CSV contract exposes it for Scenario_04 and the Potyviridae sample;
  production fixes are outside task 12. Origin: task 12_core_nf_test_assertions,
  2026-11-23.
- Coverage maps for two targets whose names differ only in case (e.g. PMI
  `Bulimulus Sporadicus` and TOI `Bulimulus sporadicus` in 512503_1_Andrew) are
  written as `map_Bulimulus_Sporadicus.png` and `map_Bulimulus_sporadicus.png`.
  They collide on case-insensitive filesystems and in some copy/archive routes; a
  retained copy lost one. Consider case-normalising targets or map filenames in
  `config.get_map_filename_for_target`. Origin: task 12_core_nf_test_assertions,
  2026-11-23.
