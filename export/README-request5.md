# Results export, request 5 — "Arming the Body Politic – Semantics of Arms"

Requester: Jonathan Obert, Amherst College.
Capsule: 03eb86bb-518c-4dcc-af1a-5f24880904a4.
Analysis code (public): https://github.com/jmobert/gunsem-capsule, commit fbfdf4d.
extract_compounds.py is unchanged from commit e4c6e12, which produced requests 1–4. This
request adds a volume sample (workset/general_sample.csv), the combined anchor list
terms-request5.txt, three helper scripts (flatten_volumes.py, merge_counts.py,
stage_request5.py) and the driver run-request5.sh.

## Why a fifth request
Requests 1–4 counted n-grams in a gun press: 816 gun-titled books and gun serials, 1931–1980.
The project's public-domain tables, made with the same code, cover the general corpus up to
1928. This request counts the same 74 anchor terms in a stratified random sample of general
in-copyright volumes from 1930 to 1979, so that the twentieth-century decades can be measured
in the same kind of corpus as the earlier ones. It is the last request from this capsule.

## The sample
1,500 volumes per decade for the 1930s–1970s, drawn from the in-copyright English-language
books and serials with a US or UK imprint: one copy per bibliographic item, in proportion to
format × country × genre stratum within each decade, and excluding the 820 volumes of
requests 1–4. The list, with the metadata used to draw it, is public in the repository
(workset/general_sample.csv). {N_RETRIEVED} of the {N_SAMPLE} sampled volumes were retrieved
and counted ({STATUS}); sample-status.csv gives each sampled volume's status.

## What the files are
Aggregate n-gram COUNT tables around 74 fixed anchor terms (terms-request5.txt in the
repository: the 34 terms of requests 1–2, the 31 of request 3 and the 9 of request 4). No
running text, no page text, no page-level data, and no token sequence longer than the counted
n-gram type. Tokens are lower-cased alphabetic word tokens.

| file | columns | one row per | rows |
|---|---|---|---|
{FILES_TABLE}

The volumes were processed in chunks of 1,000, since the secure volume cannot hold the whole
sample at once; every volume lies in exactly one chunk, so the chunks' rows together are the
single-run output (merge_counts.py).

## Reductions applied
{REDUCTION}

Total size of this request: {TOTAL_MB} MB. Plain-text CSV and Markdown only; no binary,
compressed or encrypted files.
