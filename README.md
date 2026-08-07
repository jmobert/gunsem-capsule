# gunsem-capsule — non-consumptive compound extraction for an HTRC Data Capsule

Companion code for a research project on the changing meanings of firearms
in American print culture (Jonathan Obert, Amherst College). This is the
complete analysis code that runs inside an HTRC Data Capsule against a
defined workset of ~1,800 in-copyright volumes (sporting periodicals, the
sporting-goods trade press, and firearms monographs, 1929–1980), posted
publicly to facilitate HTRC's review of data-export requests.

## What it does

`extract_compounds.py` tokenizes volume page text and tabulates bigram and
trigram **counts** around a fixed anchor-term list (`terms.txt`): for every
anchor occurrence, the immediately preceding and following token (bigrams)
and the surrounding token pair (trigrams), aggregated per volume.

## What leaves the capsule

Three CSV count tables only — `bigrams.csv`, `trigrams.csv`, `volumes.csv`
(the last holds per-volume page/token totals as denominators). No running
text, no page images, no token sequences longer than the counted trigram
types, no per-page data. All exports go through HTRC results review.

## Workflow

1. **Maintenance mode** (network on, corpus off): copy this repo into the
   capsule; Python 3 stdlib only, nothing to install.
2. **Secure mode** (network off, corpus on): retrieve the workset volumes
   with the [HTRC Workset Toolkit](https://htrc.github.io/HTRC-WorksetToolkit/),
   then:

   ```
   python3 extract_compounds.py --volumes volumes/ --terms terms.txt \
       --meta workset_meta.csv --out counts/
   ```

3. File a results-export request for the `counts/` directory.

`workset_meta.csv` is the workset's own metadata (htid, year), uploaded
alongside the volume-ID list that defines the workset.
