# To-do items

Out-of-scope spin-offs found while planning or implementing a task, recorded
so a relevant or dedicated task can pick them up later. This is not a list of
planned tasks: planned briefs are tracked by their own `tasks/<NN>_*.md`
files. Remove an item once a task brief takes it on or it's done. The aim is
an empty list.

One bullet per item: what needs doing and why, its origin
(`task NN_short_name`, issue) and the date.

- Remove the now-unreachable `KINGDOM_TAXA` query rewrite in
  `RelatedTaxaGBIF._get_taxon_record` (`scripts/src/gbif/relatives.py`):
  root names are stopped before any lookup, so the rewrite, and the
  "protozoa → protista" half of P5-D-009, no longer affect any target.
  Update P5-D-009 and P5-010 to match. Origin: task 07_kingdom_targets_not_assessed,
  #354, 2026-11-18.
