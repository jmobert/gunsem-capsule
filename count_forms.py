#!/usr/bin/env python3
"""Export request 4, step 4: hyphenated / possessive FORMS of the anchor terms.

extract_compounds.py keeps 'gun-boat', 'rifle-bullet' and "clock's" as single tokens,
so their neighbours are not counted for the anchor. EF splits many such forms, so they
are hits in the EF measure this sample checks, and a 'gun-boat' is not a gun. (Not all:
EF keeps "o'clock" whole, so it is never a `clock` hit; the analysis decides which forms
EF counted.) This counts, on the one-page volumes, every token that is not itself an
anchor but has an anchor as a component when split on '-' or "'".

Output: forms.csv  anchor, form, htid, year, count  (single tokens only; no text).
Standard library only.
"""
import argparse
import csv
import re
from collections import Counter
from pathlib import Path

TOKEN_RE = re.compile(r"[a-z]+(?:[-'][a-z]+)*")  # = extract_compounds.py


def unclean_htid(name):  # = extract_compounds.py
    if name.endswith(".zip"):
        name = name[: -len(".zip")]
    return name.replace("+", ":").replace("=", "/").replace(",", ".")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--volumes", required=True, help="the one-page volumes")
    ap.add_argument("--terms", required=True)
    ap.add_argument("--meta", required=True, help="CSV with htid, year")
    ap.add_argument("--out", required=True, help="forms.csv")
    args = ap.parse_args()
    anchors = {l.strip().lower() for l in open(args.terms, encoding="utf-8")
               if l.strip() and not l.strip().startswith("#")}
    years = {r["htid"]: r["year"] for r in csv.DictReader(open(args.meta, newline="", encoding="utf-8"))}
    # volumes named without their namespace (a known HTRC delivery quirk) join on the rest
    bare = {}
    for h, y in years.items():
        bare.setdefault(h.split(".", 1)[1] if "." in h else h, []).append(y)
    for k, ys in bare.items():
        if len(ys) == 1 and k not in years:
            years[k] = ys[0]
    c = Counter()
    for vol in sorted(p for p in Path(args.volumes).iterdir() if p.is_dir()):
        htid = unclean_htid(vol.name)
        for page in sorted(vol.glob("**/*.txt")):
            for w in TOKEN_RE.findall(page.read_text(encoding="utf-8", errors="replace").lower()):
                if ("-" in w or "'" in w) and w not in anchors:
                    for part in set(re.split(r"[-']", w)) & anchors:
                        c[(part, w, htid)] += 1
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["anchor", "form", "htid", "year", "count"])
        for (a, f, h), n in sorted(c.items()):
            wr.writerow([a, f, h, years.get(h, ""), n])
    print(f"wrote {len(c):,} form rows -> {args.out}")


if __name__ == "__main__":
    main()
