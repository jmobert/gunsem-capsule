#!/usr/bin/env python3
"""Export request 5: normalise one downloaded chunk so that extract_compounds.py sees one
top-level directory (or .zip) per sampled volume, named so that it un-cleans to the volume's
raw htid.

The Data API writes volumes under their raw htids. An ark id ('uc2.ark:/13960/t0000vq11')
contains '/', so it may arrive as nested directories, and extract_compounds.py would then read
the namespace directory ('uc2.ark:') as ONE volume holding every ark of that namespace. So:
  1. every directory that directly holds page files (.txt) and sits below an ark namespace
     directory (a first path component ending in ':') is a volume; its htid is its path below
     the chunk joined with '/';
  2. every top-level directory or .zip is a volume under its own name;
  3. each volume whose name does not already un-clean to its raw sampled htid is moved to the
     top level under the pairtree-cleaned raw htid (':' -> '+', '/' -> '=', '.' -> ',');
     a name matches a sampled htid exactly, or, as in extract_compounds.py's year lookup, by
     the id without its namespace when that is unique in the sample;
  4. anything else is moved to --quarantine (never extracted) and listed in the report, so an
     unexpected layout costs those volumes, not the run; emptied directories are removed.
Loose files (volumes_not_available.txt, ERROR.err) stay; the extractor ignores them.

Report CSV (--report): name, action (kept / renamed / quarantined), htid. Exit 4 if the chunk
holds no sampled volume at all. Python 3.6, standard library only.
"""
import argparse
import csv
import os
import shutil
import sys
from pathlib import Path


def unclean_htid(name):  # = extract_compounds.py
    if name.endswith(".zip"):
        name = name[: -len(".zip")]
    return name.replace("+", ":").replace("=", "/").replace(",", ".")


def clean_htid(htid):
    return htid.replace(":", "+").replace("/", "=").replace(".", ",")


def strip_namespace(htid):
    return htid.split(".", 1)[1] if "." in htid else htid


def has_pages(d):
    try:
        return any(e.is_file() and e.name.endswith(".txt") for e in os.scandir(str(d)))
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--volumes", required=True, help="one downloaded chunk")
    ap.add_argument("--sample", required=True, help="CSV with an htid column")
    ap.add_argument("--quarantine", required=True, help="where non-sample directories are moved")
    ap.add_argument("--report", required=True)
    args = ap.parse_args()
    root = Path(args.volumes)
    sample = set()
    with open(args.sample, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            sample.add(r["htid"])
    by_stripped = {}
    for h in sample:
        by_stripped.setdefault(strip_namespace(h), []).append(h)

    def resolve(raw):
        if raw in sample:
            return raw
        for k in (raw, strip_namespace(raw)):
            hits = by_stripped.get(k, [])
            if len(hits) == 1:
                return hits[0]
        return None

    if not root.is_dir():
        print("%s: not a directory" % root)
        return 4
    # 1. nested ark volumes
    nested = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        d = Path(dirpath)
        rel = d.relative_to(root).parts
        if len(rel) >= 2 and rel[0].endswith(":") and any(f.endswith(".txt") for f in filenames):
            nested.append((d, "/".join(rel)))
            dirnames[:] = []  # a volume's own subdirectories are its pages' business
    # 2. top-level entries
    top = [(p, p.name) for p in sorted(root.iterdir()) if p.is_dir() or p.suffix == ".zip"]
    report, quarantine = [], Path(args.quarantine)
    moves = []
    for p, name in nested + top:
        if not p.exists():
            continue
        if p.is_dir() and p.parent == root and name.endswith(":") and not has_pages(p):
            continue  # an ark namespace directory: its volumes are in `nested`
        raw = unclean_htid(name) if p.parent == root else name
        htid = resolve(raw)
        if htid is None:
            moves.append((p, quarantine / clean_htid(name), "quarantined", ""))
        elif p.parent == root and unclean_htid(p.name) == htid:
            report.append((name, "kept", htid))
        else:
            target = root / (clean_htid(htid) + (".zip" if p.suffix == ".zip" and p.is_file() else ""))
            if target.exists():
                moves.append((p, quarantine / clean_htid(name), "quarantined", htid))
            else:
                moves.append((p, target, "renamed", htid))
    for src, dst, action, htid in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        report.append((str(src.relative_to(root)), action, htid))
    for dirpath, dirnames, filenames in os.walk(str(root), topdown=False):
        d = Path(dirpath)
        if d != root and not any(d.iterdir()):
            d.rmdir()
    kept = sum(1 for r in report if r[1] in ("kept", "renamed"))
    with open(args.report, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "action", "htid"])
        w.writerows(report)
    tally = {}
    for r in report:
        tally[r[1]] = tally.get(r[1], 0) + 1
    print("%s: %d sampled volumes ready; %s" % (root, kept, tally), flush=True)
    return 0 if kept else 4


if __name__ == "__main__":
    sys.exit(main())
