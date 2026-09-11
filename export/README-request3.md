# Results export, request 3 (supplementary) — "Arming the Body Politic – Semantics of Arms"

Requester: Jonathan Obert, Amherst College.
Capsule: 03eb86bb-518c-4dcc-af1a-5f24880904a4.
Analysis code (public): https://github.com/jmobert/gunsem-capsule, commit 1fab4b3
(extract_compounds.py is unchanged from commit e4c6e12, which produced requests 1 and 2;
this request adds only terms-extra.txt and the run-extra.sh driver).

## Why a third request
Requests 1 and 2, released on 11 September 2026, hold n-gram counts around 34 anchor
terms. The project measures its comparison objects in public-domain volumes with 31
further terms. This request applies the same code, with those 31 terms, to the same 816
volumes, so the in-copyright tables can be compared with the public-domain ones object
by object. Liquor matters most: it is a principal comparison object in the project's
design, and none of the 34 original terms covers it.

## What the files are
Aggregate n-gram COUNT tables around 31 fixed anchor terms (terms-extra.txt in the
repository): whiskey, whisky, brandy, rum, liquor, liquors; clock, clocks, timepiece,
timepieces; typewriter, typewriters, type-writer, type-writers; cartridge, cartridges,
gunpowder; dirk, dirks, slungshot, slung-shot; motorcar, motorcars; tricycle,
tricycles; vault, vaults, strongbox; nitroglycerin, nitro-glycerine, nitroglycerine.
No running text, no page text, no page-level data, and no token sequence longer than
the counted n-gram type. Tokens are lower-cased alphabetic word tokens.

| file | columns | one row per | rows |
|---|---|---|---|
| bigrams.csv | anchor, direction (pre/post), other, htid, year, count | anchor term x adjacent token x volume | {BIGRAM_ROWS} |
| trigrams.csv | w1, w2, w3, htid, year, count | anchor term with both adjacent tokens x volume | {TRIGRAM_ROWS} |
| volumes.csv | htid, year, n_pages, n_tokens | volume (denominators only) | {VOLUME_ROWS} |

## Workset
The same 816 in-copyright volumes, 1931–1980, as requests 1 and 2: the cleaned
820-volume list less the 4 the HTRC Data API reported as not available. Nothing was
added or removed, and the run checked that it read exactly the text request 1 read:
this volumes.csv is byte-identical to request 1's.

## Reductions applied
None.

Total size of this request: {TOTAL_MB} MB. Plain-text CSV and Markdown only; no binary,
compressed or encrypted files.
