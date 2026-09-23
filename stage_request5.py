#!/usr/bin/env python3
"""Export request 5: choose the package that fits, stage it, and fill the README.

HTRC's limit is 67 MB per release request. The finest grain that fits under --cap is staged,
trying in this order (the reductions are the kit's shrink_counts.py, and the README states
which one was applied):
  L0   bigrams.csv + trigrams.csv, both per volume (no reduction)
  L1   bigrams.csv per volume + trigrams-by-year.csv (shrink_counts.py --grain year)
  L1b  bigrams.csv per volume only (trigrams left out)
  L2   bigrams-by-year.csv + trigrams-by-year.csv (shrink_counts.py --grain year)
  L3   the same with --min-count 2 (rows with a count below 2 after aggregation dropped),
       staged as bigrams-by-year-min2.csv + trigrams-by-year-min2.csv
volumes.csv and sample-status.csv are staged at every level. Per-volume bigrams are kept as
long as possible because they carry what the year tables cannot: each volume's genre stratum
and decade (from the published sample), the unit a bootstrap resamples.

  python3 stage_request5.py --merged M --work W --shrink shrink_counts.py \\
      --template export/README-request5.md --out REL --cap 64000000
Exit 5 if not even L3 fits. `fill()` is also what the landing script uses to re-derive the
README from the released files. Python 3.6, standard library only.
"""
import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path

LEVELS = [
    ("L0", [("bigrams.csv", "merged", "bigrams.csv"), ("trigrams.csv", "merged", "trigrams.csv")], "None."),
    ("L1", [("bigrams.csv", "merged", "bigrams.csv"), ("trigrams-by-year.csv", "year", "trigrams.csv")],
     "Trigrams are aggregated to year grain: counts summed over the sampled volumes of each year "
     "(shrink_counts.py --grain year), because the per-volume trigram table would take the request "
     "over the size limit. Bigrams, volumes and the sample status are unreduced."),
    ("L1b", [("bigrams.csv", "merged", "bigrams.csv")],
     "Trigrams are left out: even at year grain they would take the request over the size limit. "
     "Bigrams, volumes and the sample status are unreduced."),
    ("L2", [("bigrams-by-year.csv", "year", "bigrams.csv"), ("trigrams-by-year.csv", "year", "trigrams.csv")],
     "Bigrams and trigrams are aggregated to year grain: counts summed over the sampled volumes of each "
     "year (shrink_counts.py --grain year). Volumes and the sample status are unreduced."),
    ("L3", [("bigrams-by-year-min2.csv", "year-min2", "bigrams.csv"), ("trigrams-by-year-min2.csv", "year-min2", "trigrams.csv")],
     "Bigrams and trigrams are aggregated to year grain, and rows whose count is below 2 after "
     "aggregation are dropped (shrink_counts.py --grain year --min-count 2). Volumes and the sample "
     "status are unreduced."),
]
ALWAYS = [("volumes.csv", "merged", "volumes.csv"), ("sample-status.csv", "merged", "sample-status.csv")]
DESCRIBE = {
    "bigrams.csv": ("anchor, direction (pre/post), other, htid, year, count", "anchor term x adjacent token x volume"),
    "trigrams.csv": ("w1, w2, w3, htid, year, count", "anchor term with both adjacent tokens x volume"),
    "bigrams-by-year.csv": ("anchor, direction (pre/post), other, year, count", "anchor term x adjacent token x year"),
    "trigrams-by-year.csv": ("w1, w2, w3, year, count", "anchor term with both adjacent tokens x year"),
    "bigrams-by-year-min2.csv": ("anchor, direction (pre/post), other, year, count", "anchor term x adjacent token x year, count at least 2"),
    "trigrams-by-year-min2.csv": ("w1, w2, w3, year, count", "anchor term with both adjacent tokens x year, count at least 2"),
    "volumes.csv": ("htid, year, n_pages, n_tokens", "retrieved volume (denominators only)"),
    "sample-status.csv": ("htid, status", "sampled volume: retrieved, not_available, unreadable or missing"),
}
ORDER = ["bigrams.csv", "bigrams-by-year.csv", "bigrams-by-year-min2.csv", "trigrams.csv", "trigrams-by-year.csv",
         "trigrams-by-year-min2.csv", "volumes.csv", "sample-status.csv"]
STATUS_ORDER = ["retrieved", "not_available", "unreadable", "missing"]


def rows(path):
    with open(str(path), encoding="utf-8") as fh:
        return sum(1 for _ in fh) - 1


def fill(template, rel):
    """README text for the files staged in `rel` (the level is read off the file names)."""
    rel = Path(rel)
    names = [n for n in ORDER if (rel / n).exists()]
    level = next(lv for lv, files, _ in LEVELS if sorted(f[0] for f in files) == sorted(n for n in names if n not in ("volumes.csv", "sample-status.csv")))
    reduction = next(text for lv, _, text in LEVELS if lv == level)
    table = "\n".join("| %s | %s | %s | %s |" % (n, DESCRIBE[n][0], DESCRIBE[n][1], "{:,}".format(rows(rel / n))) for n in names)
    tally = {}
    with open(str(rel / "sample-status.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            tally[r["status"]] = tally.get(r["status"], 0) + 1
    status = ", ".join("{:,} {}".format(tally[s], s.replace("_", " ")) for s in STATUS_ORDER if tally.get(s))
    size = sum((rel / n).stat().st_size for n in names) + len(template.encode("utf-8"))
    fills = {"FILES_TABLE": table, "REDUCTION": reduction, "N_SAMPLE": "{:,}".format(sum(tally.values())),
             "N_RETRIEVED": "{:,}".format(tally.get("retrieved", 0)), "STATUS": status, "TOTAL_MB": "%.1f" % (size / 1e6)}
    text = template
    for k, v in fills.items():
        text = text.replace("{" + k + "}", v)
    return level, text


def staged_size(paths, template_bytes):
    return sum(p.stat().st_size for p in paths) + template_bytes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--merged", required=True)
    ap.add_argument("--work", required=True, help="where the year-grain reductions are written")
    ap.add_argument("--shrink", required=True, help="the kit's shrink_counts.py")
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cap", type=int, default=64000000)
    args = ap.parse_args()
    template = Path(args.template).read_text(encoding="utf-8")
    dirs = {"merged": Path(args.merged), "year": Path(args.work) / "year", "year-min2": Path(args.work) / "year-min2"}
    made = set()

    def ensure(d):
        if d in made or d == "merged":
            return
        cmd = [sys.executable, args.shrink, str(dirs["merged"]), "--out", str(dirs[d]), "--grain", "year"]
        if d == "year-min2":
            cmd += ["--min-count", "2"]
        print("$ " + " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True)
        made.add(d)

    chosen = None
    for level, files, _ in LEVELS:
        for _, d, _ in files:
            ensure(d)
        paths = [dirs[d] / src for _, d, src in files + ALWAYS]
        size = staged_size(paths, len(template.encode("utf-8")))
        print("%-4s %s: %s bytes%s" % (level, " + ".join(f[0] for f in files), "{:,}".format(size),
                                       "" if size < args.cap else "  (over the %s-byte cap)" % "{:,}".format(args.cap)), flush=True)
        if size < args.cap:
            chosen = (level, files)
            break
    if chosen is None:
        print("STOP-CHECK: no level fits under the cap")
        return 5
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(str(out))
    out.mkdir(parents=True)
    for name, d, src in chosen[1] + ALWAYS:
        shutil.copyfile(str(dirs[d] / src), str(out / name))
    level, text = fill(template, out)
    left = [t for t in ("{FILES_TABLE}", "{REDUCTION}", "{N_SAMPLE}", "{N_RETRIEVED}", "{STATUS}", "{TOTAL_MB}", "<CODE_COMMIT>") if t in text]
    if left or level != chosen[0]:
        print("STOP-CHECK: README placeholders left %s, or level %s != %s" % (left, level, chosen[0]))
        return 5
    (out / "README.md").write_text(text, encoding="utf-8")
    print("staged level %s in %s" % (level, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
