# Results export, request 4 — "Arming the Body Politic – Semantics of Arms"

Requester: Jonathan Obert, Amherst College.
Capsule: 03eb86bb-518c-4dcc-af1a-5f24880904a4.
Analysis code (public): https://github.com/jmobert/gunsem-capsule, commit 3ee744e.
extract_compounds.py is unchanged from commit e4c6e12, which produced requests 1–3. This
request adds a page sample (workset/precision_sample.csv), two term lists
(terms-precision.txt, terms-idiom.txt), select_pages.py, count_forms.py and the driver
run-request4.sh.

## Why a fourth request
1. **Precision check.** The project measures eleven objects (guns, liquor, clocks,
   bicycles, typewriters and others) by the pages on which HathiTrust Extracted Features
   records one of their terms. Its design requires checking, decade by decade, how often
   such a term is a true reference to the object and not, say, a "spray gun" or "Yale
   University". That needs the words next to each term, which Extracted Features does not
   carry. This request counts those neighbouring words on a fixed random sample of pages.
   Nothing is read: the judgement is made afterwards, from the counts.
2. **Idiom anchors.** The same counting, over the same 816 volumes as requests 1–3, for
   nine gun-rights idiom terms (arms, amendment, militia, defense, defence, self-defense,
   self-defence, law-abiding, constitutional), so that phrases such as "bear arms" and
   "second amendment" can be dated in the gun press of 1931–1980.

## What the files are
Aggregate COUNT tables. Tokens are lower-cased alphabetic word tokens.

| file | columns | one row per | rows |
|---|---|---|---|
| precision-bigrams.csv | anchor, direction (pre/post), other, htid, year, count | anchor term x adjacent token x sampled page | {ROWS_PRECISION_BIGRAMS} |
| precision-trigrams.csv | w1, w2, w3, htid, year, count | anchor term with both adjacent tokens x sampled page | {ROWS_PRECISION_TRIGRAMS} |
| precision-volumes.csv | htid, year, n_pages, n_tokens | sampled page (n_pages is always 1) | {ROWS_PRECISION_VOLUMES} |
| precision-forms.csv | anchor, form, htid, year, count | hyphenated or possessive single token containing an anchor (e.g. gun-boat) x sampled page | {ROWS_PRECISION_FORMS} |
| precision-pages.csv | htid, seq, object, decade, status, mapping, n_files, ef_page_count, term_token, term_component | sampled page: processing report (how the page was located, whether its term is on it), no text | {ROWS_PRECISION_PAGES} |
| idiom-bigrams.csv | anchor, direction (pre/post), other, htid, year, count | anchor term x adjacent token x volume | {ROWS_IDIOM_BIGRAMS} |
| idiom-trigrams.csv | w1, w2, w3, htid, year, count | anchor term with both adjacent tokens x volume | {ROWS_IDIOM_TRIGRAMS} |
| idiom-volumes.csv | htid, year, n_pages, n_tokens | volume (denominators only) | {ROWS_IDIOM_VOLUMES} |

## The page sample
{N_SAMPLE} pages, drawn at random from the pages on which Extracted Features records one of
the eleven objects' terms: 11 objects x 17 decades (1820–1980) x 100 pages, one page per
volume and each volume used once. The full list, with page numbers, is public in the
repository (workset/precision_sample.csv). Public-domain volumes are included alongside
in-copyright ones, so the same measure runs across the whole period; the public-domain
pages can also be checked against their open text. Each sampled page was retrieved on
its own from the Data API (`htrc download -pg`), or taken from the volume where a first
run had already downloaded it whole; the page's presence was checked in either case
(select_pages.py). {N_OK} of the {N_SAMPLE} pages were processed; the others (volume not
available, or page not matched) are listed in precision-pages.csv.

## Non-consumptive character
Each sampled volume contributes exactly one page, so each precision row records the
immediate neighbours of an object term on one page. No running text, no page text and no
token sequence longer than three words leaves the capsule; the forms table holds single
tokens only. HathiTrust already publishes the complete page-level word counts for these
same pages in Extracted Features; these tables carry only the words adjacent to about a
hundred fixed terms.

## Workset for the idiom tables
The same 816 in-copyright volumes, 1931–1980, as requests 1–3. The run checked that it read
exactly the text request 1 read: idiom-volumes.csv is byte-identical to request 1's
volumes.csv.

## Reductions applied
None.

Total size of this request: {TOTAL_MB} MB. Plain-text CSV and Markdown only; no binary,
compressed or encrypted files.
