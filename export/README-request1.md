# Results export, request 1 of 2 — "Arming the Body Politic – Semantics of Arms"

Requester: Jonathan Obert, Amherst College.
Capsule: 03eb86bb-518c-4dcc-af1a-5f24880904a4.
Analysis code (public): https://github.com/jmobert/gunsem-capsule, commit e4c6e12
(extract_compounds.py, terms.txt, run_secure.sh — the exact code that produced these files).

## Why two requests
The complete output of the approved analysis is 110.9 MB of plain-text CSV, above the
67 MB per-request release limit. Rather than aggregate away the per-volume grain the
proposal describes, or drop low-count rows, the output is filed as two requests that
are each under the limit and together contain every row produced:

- request 1 (this one): bigrams.csv + volumes.csv + this README  (57.0 MB)
- request 2:            trigrams.csv + README                     (53.9 MB)

Nothing has been aggregated, thresholded or otherwise reduced. If HTRC would prefer a
single smaller release, the same tables can be re-issued at year grain or with a
minimum-count floor; please say which.

## What the files are
Aggregate n-gram COUNT tables around 34 fixed anchor terms (terms.txt in the repository:
gun / rifle / shotgun / firearm / pistol / revolver, singular and plural; the comparison
objects bicycle, padlock, dynamite, automobile; and 15 firearm and padlock brand names).
No running text, no page text, no page-level data, and no token sequence longer than the
counted n-gram type. Tokens are lower-cased alphabetic word tokens.

| file | columns | one row per | rows |
|---|---|---|---|
| bigrams.csv | anchor, direction (pre/post), other, htid, year, count | anchor term x adjacent token x volume | 1,293,402 |
| volumes.csv | htid, year, n_pages, n_tokens | volume (denominators only) | 816 |

## Workset
816 in-copyright volumes, 1931–1980: American sporting periodicals (Field & Stream,
American Rifleman, Sports Afield, Outdoor Life, Hunting and Fishing, Gun Digest), the
sporting-goods trade press (The Sporting Goods Directory), and firearms-related monographs.
These are a subset of the volume list uploaded with this capsule: after a 40-volume pilot,
the uploaded list was cleaned of title-keyword false positives (for example works on the
poet Robert Browning matched by the brand name "Browning") and off-topic serials, leaving
820 volumes, all of them from the uploaded list. The HTRC Data API reported 4 of the 820 as
not available (uiug.30112101465059, uc1.31175013347748, coo.31924030705671,
nyp.33433044118085); they are simply absent from volumes.csv. The cleaned volume list will be published alongside the code.

## Reductions applied
None.

Total size of this request: 57.0 MB. Plain-text CSV and Markdown only; no binary,
compressed or encrypted files.
