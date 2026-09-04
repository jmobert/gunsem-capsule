#!/usr/bin/env python3
"""Size report + reduction options for the counts/ export (stdlib only).

HTRC results release: hard cap 67 MB per request; >1 MB total is held for
discussion with the capsule owner; text files only (no binary/compressed).
The approved proposal describes per-volume-year counts; if counts/ exceeds
the cap, produce a reduced export here and DECLARE the reduction in the
export request README rather than trimming silently.

  python3 shrink_counts.py counts/                      # size report only
  python3 shrink_counts.py counts/ --out counts_year/ --grain year
  python3 shrink_counts.py counts/ --out counts_min2/ --min-count 2
  (options combine)

--grain year : sum counts over volumes within a year (drops htid; volumes.csv
               is kept per volume as the denominator table — it is small).
--min-count N: drop n-gram rows with count < N AFTER aggregation.
"""
import argparse, csv, os, sys
from collections import Counter
from pathlib import Path

def size_report(d: Path):
    tot = 0
    for f in sorted(d.iterdir()):
        if f.is_file():
            n = f.stat().st_size; tot += n
            rows = sum(1 for _ in open(f, encoding="utf-8")) - 1 if f.suffix == ".csv" else ""
            print(f"  {f.name:14s} {n/1e6:8.2f} MB  {rows} rows")
    print(f"  TOTAL          {tot/1e6:8.2f} MB   (cap 67 MB; >1 MB needs owner discussion)")
    return tot

def reduce(src: Path, dst: Path, grain: str, min_count: int):
    dst.mkdir(parents=True, exist_ok=True)
    for name, keycols in (("bigrams.csv", ["anchor", "direction", "other"]),
                          ("trigrams.csv", ["w1", "w2", "w3"])):
        agg = Counter()
        with open(src / name, newline="", encoding="utf-8") as fh:
            r = csv.DictReader(fh)
            for row in r:
                k = tuple(row[c] for c in keycols)
                k += (row["year"],) if grain == "year" else (row["htid"], row["year"])
                agg[k] += int(row["count"])
        with open(dst / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(keycols + (["year"] if grain == "year" else ["htid", "year"]) + ["count"])
            kept = 0
            for k, n in sorted(agg.items()):
                if n >= min_count:
                    w.writerow(list(k) + [n]); kept += 1
        print(f"  {name}: {len(agg):,} rows -> {kept:,} kept")
    # volumes.csv (denominators) and skipped.csv pass through unchanged
    for extra in ("volumes.csv", "skipped.csv"):
        if (src / extra).exists():
            (dst / extra).write_bytes((src / extra).read_bytes())

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("counts"); ap.add_argument("--out"); ap.add_argument("--grain", choices=["volume", "year"], default="volume")
    ap.add_argument("--min-count", type=int, default=1)
    a = ap.parse_args()
    src = Path(a.counts)
    print(f"{src}:"); size_report(src)
    if a.out:
        reduce(src, Path(a.out), a.grain, a.min_count)
        print(f"{a.out}:"); size_report(Path(a.out))

if __name__ == "__main__":
    main()
