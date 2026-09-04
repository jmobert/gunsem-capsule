#!/usr/bin/env python3
"""Non-consumptive compound/collocation extraction for an HTRC Data Capsule.

Tabulates bigram and trigram COUNTS around a fixed list of anchor terms
(e.g. gun, rifle, shotgun) across a workset of HathiTrust volumes. The only
output is aggregate frequency tables at the volume-year level — no running
text, no page images, no token sequences beyond the counted n-gram types.

Input volumes may be either:
  - directories of page .txt files (as produced by `htrc download`), or
  - HathiTrust dataset .zip files (<id>.zip containing page .txt files).

Usage (inside the capsule, secure mode):
  python3 extract_compounds.py --volumes /path/to/volumes \
      --terms terms.txt --meta workset_meta.csv --out counts/

Outputs (CSV):
  counts/bigrams.csv   anchor, direction {pre,post}, other, htid, year, count
  counts/trigrams.csv  w1, w2, w3 (anchor in any slot), htid, year, count
  counts/volumes.csv   htid, year, n_pages, n_tokens  (denominators)
  counts/skipped.csv   htid, reason  (volumes that could not be read; only
                       written if any were skipped)

Only the Python 3 standard library is required.
"""

import argparse
import csv
import io
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

TOKEN_RE = re.compile(r"[a-z]+(?:[-'][a-z]+)*")

# `htrc download` (and pairtree tooling generally) writes volume names in the
# "clean" id form: ':' -> '+', '/' -> '=', '.' -> ','. Workset metadata uses
# raw htids. Un-clean so outputs and the year lookup carry the raw htid.
def unclean_htid(name: str) -> str:
    if name.endswith(".zip"):
        name = name[: -len(".zip")]
    return name.replace("+", ":").replace("=", "/").replace(",", ".")


def strip_namespace(htid: str) -> str:
    """'mdp.39015012345678' -> '39015012345678'; unchanged if no namespace."""
    return htid.split(".", 1)[1] if "." in htid else htid


def load_terms(path: Path) -> set:
    terms = set()
    for line in path.read_text().splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#"):
            terms.add(line)
    return terms


class YearLookup:
    """htid -> year, keyed on the raw htid with a fallback on the id with its
    namespace stripped. Some HTRC deliveries name volumes WITHOUT the
    namespace prefix (the 2018 capsule sample volumes are 'ark+=13960=...',
    not 'uc2.ark+=13960=...'); the fallback is only used when the stripped
    id is unique in the workset, so it can never mis-join."""

    def __init__(self, path: Path):
        self.full = {}
        stripped = Counter()
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self.full[row["htid"]] = row.get("year", "")
                stripped[strip_namespace(row["htid"])] += 1
        self.by_stripped = {
            strip_namespace(h): y for h, y in self.full.items()
            if stripped[strip_namespace(h)] == 1
        }
        self.misses = []

    def __len__(self):
        return len(self.full)

    def get(self, htid: str) -> str:
        if htid in self.full:
            return self.full[htid]
        # The volume name may already BE a namespace-less id (which can
        # itself contain dots, e.g. 'aaj6638.0001.001'), so try it as-is
        # before stripping.
        y = (self.by_stripped.get(htid, "")
             or self.by_stripped.get(strip_namespace(htid), ""))
        if not y:
            self.misses.append(htid)
        return y


def iter_volume_pages(vol: Path):
    """Yield page texts from a volume directory or dataset zip."""
    if vol.is_dir():
        for p in sorted(vol.glob("**/*.txt")):
            yield p.read_text(encoding="utf-8", errors="replace")
    elif vol.suffix == ".zip":
        with zipfile.ZipFile(vol) as z:
            for name in sorted(z.namelist()):
                if name.endswith(".txt"):
                    yield io.TextIOWrapper(z.open(name), encoding="utf-8",
                                           errors="replace").read()


def tokenize(text: str) -> list:
    return TOKEN_RE.findall(text.lower())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--volumes", required=True,
                    help="directory containing volume dirs and/or .zip files")
    ap.add_argument("--terms", required=True, help="anchor term list")
    ap.add_argument("--meta", required=True,
                    help="CSV with htid,year columns (workset metadata)")
    ap.add_argument("--out", required=True, help="output directory")
    args = ap.parse_args()

    anchors = load_terms(Path(args.terms))
    years = YearLookup(Path(args.meta))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    vols = sorted(p for p in Path(args.volumes).iterdir()
                  if p.is_dir() or p.suffix == ".zip")
    print(f"{len(vols)} volumes, {len(anchors)} anchor terms, "
          f"{len(years)} metadata rows", flush=True)

    bi = Counter()   # (anchor, direction, other, htid) -> n
    tri = Counter()  # (w1, w2, w3, htid) -> n
    vol_rows = []
    skipped = []

    for i, vol in enumerate(vols, 1):
        htid = unclean_htid(vol.name)
        n_pages = 0
        n_tokens = 0
        vol_bi = Counter()
        vol_tri = Counter()
        try:
            for page in iter_volume_pages(vol):
                toks = tokenize(page)
                n_pages += 1
                n_tokens += len(toks)
                for j, t in enumerate(toks):
                    if t not in anchors:
                        continue
                    if j > 0:
                        vol_bi[(t, "pre", toks[j - 1], htid)] += 1
                    if j + 1 < len(toks):
                        vol_bi[(t, "post", toks[j + 1], htid)] += 1
                    if 0 < j < len(toks) - 1:
                        vol_tri[(toks[j - 1], t, toks[j + 1], htid)] += 1
        except Exception as e:  # a bad volume must not kill the whole run
            reason = f"{type(e).__name__}: {e}"
            print(f"  SKIP {vol.name}: {reason}", file=sys.stderr, flush=True)
            skipped.append((htid, reason))
            continue
        bi.update(vol_bi)
        tri.update(vol_tri)
        vol_rows.append((htid, years.get(htid), n_pages, n_tokens))
        if i % 50 == 0:
            print(f"  {i}/{len(vols)}", flush=True)

    with open(out / "bigrams.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["anchor", "direction", "other", "htid", "year", "count"])
        for (a, d, o, h), n in sorted(bi.items()):
            w.writerow([a, d, o, h, years.get(h), n])
    with open(out / "trigrams.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["w1", "w2", "w3", "htid", "year", "count"])
        for (w1, w2, w3, h), n in sorted(tri.items()):
            w.writerow([w1, w2, w3, h, years.get(h), n])
    with open(out / "volumes.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["htid", "year", "n_pages", "n_tokens"])
        w.writerows(vol_rows)
    if skipped:
        with open(out / "skipped.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["htid", "reason"])
            w.writerows(skipped)

    n_no_year = sum(1 for r in vol_rows if not r[1])
    print(f"wrote {len(bi):,} bigram rows, {len(tri):,} trigram rows, "
          f"{len(vol_rows)} volumes -> {out}")
    if skipped:
        print(f"WARNING: {len(skipped)} volumes SKIPPED (unreadable) — see "
              f"{out / 'skipped.csv'}", file=sys.stderr)
    if n_no_year:
        print(f"WARNING: {n_no_year}/{len(vol_rows)} volumes have NO YEAR — "
              f"the htid<->metadata join is wrong; do not export. First "
              f"unmatched ids: {sorted(set(years.misses))[:5]}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
