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
