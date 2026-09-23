#!/usr/bin/env python3
"""Export request 5: merge the per-chunk outputs of extract_compounds.py into one set of tables.

The driver runs the unchanged extractor once per downloaded chunk (the secure volume cannot
hold the whole sample at once). Every volume lies in exactly one chunk and every row carries
its htid, so the union of the chunks' rows IS the single-run output; this writes it sorted
the way extract_compounds.py sorts (bigrams by anchor, direction, other, htid; trigrams by
w1, w2, w3, htid; volumes by htid), and refuses a volume that appears in two chunks, a row
whose htid is not a volume of its chunk, or a header that differs.

It also writes sample-status.csv: one row per sampled htid with its status
  retrieved      in volumes.csv
  unreadable     listed in a chunk's skipped.csv and never retrieved
  not_available  listed by the Data API as not available and never retrieved
  missing        none of the above (a download failure, or a layout the driver could not use)

  python3 merge_counts.py --counts CNT --sample SAMPLE.csv --out CNT/merged
Python 3.6, standard library only.
"""
import argparse
import csv
import sys
from pathlib import Path

HEAD = {"bigrams.csv": ["anchor", "direction", "other", "htid", "year", "count"],
        "trigrams.csv": ["w1", "w2", "w3", "htid", "year", "count"],
        "volumes.csv": ["htid", "year", "n_pages", "n_tokens"]}
HTID_COL = {"bigrams.csv": 3, "trigrams.csv": 3, "volumes.csv": 0}


def read(path):
    with open(str(path), newline="", encoding="utf-8") as fh:
        r = csv.reader(fh)
        head = next(r)
        return head, list(r)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--counts", required=True, help="dir holding chunk-*/ outputs")
    ap.add_argument("--sample", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    chunks = sorted(p for p in Path(args.counts).glob("chunk-*") if (p / ".done").exists())
    if not chunks:
        print("no finished chunks under %s" % args.counts)
        return 1
    sample = []
    with open(args.sample, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            sample.append(r["htid"])
    sset = set(sample)
    rows = {k: [] for k in HEAD}
    owner, skipped, unavailable = {}, set(), set()
    for c in chunks:
        vols = set()
        for name, want in HEAD.items():
            head, body = read(c / name)
            if head != want:
                print("STOP: %s has header %s" % (c / name, head))
                return 2
            if name == "volumes.csv":
                for r in body:
                    if r[0] in owner:
                        print("STOP: volume %s is in %s and %s" % (r[0], owner[r[0]], c.name))
                        return 2
                    if r[0] not in sset:
                        print("STOP: volume %s in %s is not in the sample" % (r[0], c.name))
                        return 2
                    owner[r[0]] = c.name
                    vols.add(r[0])
            rows[name].append((body, c))
        for name in ("bigrams.csv", "trigrams.csv"):
            body = rows[name][-1][0]
            stray = sum(1 for r in body if r[HTID_COL[name]] not in vols)
            if stray:
                print("STOP: %d rows of %s are for volumes not in its volumes.csv" % (stray, c / name))
                return 2
        if (c / "skipped.csv").exists():
            skipped |= {r[0] for r in read(c / "skipped.csv")[1]}
        if (c / "not_available.txt").exists():
            unavailable |= {l.strip() for l in (c / "not_available.txt").read_text().splitlines() if l.strip()}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    keys = {"bigrams.csv": lambda r: (r[0], r[1], r[2], r[3]), "trigrams.csv": lambda r: (r[0], r[1], r[2], r[3]),
            "volumes.csv": lambda r: r[0]}
    for name, want in HEAD.items():
        allrows = [r for body, _ in rows[name] for r in body]
        allrows.sort(key=keys[name])
        with open(str(out / name), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(want)
            w.writerows(allrows)
        print("%s: %d rows from %d chunks" % (name, len(allrows), len(chunks)))
    status, tally = [], {}
    for h in sample:
        if h in owner:
            s = "retrieved"
        elif h in skipped:
            s = "unreadable"
        elif h in unavailable:
            s = "not_available"
        else:
            s = "missing"
        status.append((h, s))
        tally[s] = tally.get(s, 0) + 1
    with open(str(out / "sample-status.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["htid", "status"])
        w.writerows(status)
    print("sample status: %s" % tally)
    return 0


if __name__ == "__main__":
    sys.exit(main())
