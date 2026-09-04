# Results export — "Arming the Body Politic – Semantics of Arms" capsule

Requester: Jonathan Obert, Amherst College. Capsule 03eb86bb-518c-4dcc-af1a-5f24880904a4.
Analysis code (public): https://github.com/jmobert/gunsem-capsule (commit <SHA>).

## What the files are
Aggregate n-gram COUNT tables around 34 fixed anchor terms (terms.txt: gun/rifle/
shotgun/firearm/pistol/revolver + singular/plural, comparison objects bicycle/
padlock/dynamite/automobile, and 15 firearm/padlock brand names). No running text,
no page text, no page-level data, no sequences longer than the counted trigram type.

| file | columns | grain |
|---|---|---|
| bigrams.csv | anchor, direction{pre,post}, other, [htid,] year, count | anchor + its immediate neighbour |
| trigrams.csv | w1, w2, w3, [htid,] year, count | anchor with both immediate neighbours |
| volumes.csv | htid, year, n_pages, n_tokens | per-volume denominators only |
| skipped.csv | htid, reason | volumes that could not be read (if any) |

Workset: <N> in-copyright volumes, 1929–1980 (sporting periodicals, sporting-goods
trade press, firearms monographs), the workset uploaded with this capsule.

## Reductions applied (if any — delete this section otherwise)
<none | aggregated from volume-year to year grain | rows with count < N dropped>,
to bring the request under the 67 MB release cap. Per-volume denominators are
retained in volumes.csv.

Total size: <X> MB. Plain-text CSV only; no binary, compressed or encrypted files.
