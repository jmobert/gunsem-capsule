#!/usr/bin/env python3
"""Export request 4, step 2: the ONE sampled page of each volume.

Reads the sample (htid, seq, ef_page_count, terms_matched, ...) and a directory the
driver filled with `htrc download`, and writes each sampled page as a one-page volume
under OUT/<pairtree-cleaned htid>/<seq>.txt, so extract_compounds.py (unchanged) sees
one-page volumes whose names un-clean to the raw htids of the sample.

Two kinds of download are handled:
  whole volumes  (`htrc download`): the page is chosen by POSITION among the volume's
                 numerically named page files, only when their count equals EF's
                 pageCount; if the counts differ, the file whose number is seq (with the
                 volume's own numbering base, 0 or 1) is used. EF numbers pages 1..N;
                 the HathiTrust dataset zips number page files from 00000000.
  single pages   (`htrc download -pg`, input lines `htid[seq]`): the volume directory
                 holds one page file, and that file is the page.
A volume is a .zip, or a directory that directly holds page (.txt) files, at any depth:
the Data API writes raw htids, so an ark id (`uc2.ark:/13960/...`) becomes nested
directories.

Check: EF says every sampled page carries one of its object terms. The selected page
is tokenized with the kit's tokenizer; the term counts as present if it is a token or
a component of a hyphenated / possessive token ('gun-boat', "clock's"). On 600 local
public-domain pages the term was on the positionally mapped page for 98% (with
components) and on a neighbouring page for ~20%, so a wrong mapping cannot pass.

  --append   process the sample rows whose volume is under --volumes, append their
             report lines, skip the other rows silently (the driver calls this once
             per downloaded chunk); exit 4 if no volume at all is found there
  --check    no volumes: read the report, add `missing_volume` rows for sample rows
             without a line, keep the best line per page, rewrite the report in sample
             order, and exit 3 if fewer than 95% of the pages were selected or fewer
             than 90% of the selected pages carry their term

Report columns (no text): htid, seq, object, decade, status, mapping, n_files,
ef_page_count, term_token, term_component. Python 3.6, standard library only.
"""
import argparse
import csv
import os
import re
import sys
import zipfile
from pathlib import Path

TOKEN_RE = re.compile(r"[a-z]+(?:[-'][a-z]+)*")  # = extract_compounds.py
NUM_RE = re.compile(r"(\d+)\.txt$")
CHUNK_RE = re.compile(r"^p\d+-ids-")  # the driver's chunk dirs, if --volumes is their parent
COLS = ["htid", "seq", "object", "decade", "status", "mapping", "n_files", "ef_page_count",
        "term_token", "term_component"]
MIN_SELECTED = 0.95
MIN_TERM = 0.90


def unclean_htid(name):  # = extract_compounds.py
    if name.endswith(".zip"):
        name = name[: -len(".zip")]
    return name.replace("+", ":").replace("=", "/").replace(",", ".")


def clean_htid(htid):
    """Raw htid -> a single directory name that unclean_htid() maps back."""
    return htid.replace(":", "+").replace("/", "=").replace(".", ",")


def strip_namespace(htid):
    return htid.split(".", 1)[1] if "." in htid else htid


def index_volumes(root):
    """htid -> volume path. A volume is a .zip, or a directory that directly holds .txt
    files, anywhere below root; its htid is its path below root (a driver chunk dir
    is skipped), nested parts joined with '/', un-cleaned. Loose files in root
    (volumes_not_available.txt, ERROR.err) are not volumes."""
    found = {}
    root = Path(root)
    if not root.is_dir():
        return found, {}
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        rel = d.relative_to(root).parts
        if rel and CHUNK_RE.match(rel[0]):
            rel = rel[1:]
        for f in filenames:
            if f.endswith(".zip"):
                found.setdefault(unclean_htid("/".join(rel + (f,))), d / f)
        if rel and any(f.endswith(".txt") for f in filenames):
            found.setdefault(unclean_htid("/".join(rel)), d)
    stripped = {}
    for h in found:
        stripped.setdefault(strip_namespace(h), []).append(h)
    return found, stripped


def page_list(vol):
    """All page files of a volume in the order extract_compounds.py reads them, and the
    numerically named ones in numeric order."""
    if vol.is_dir():
        allp = [("dir", p) for p in sorted(vol.iterdir()) if p.suffix == ".txt" and p.is_file()]
    else:
        with zipfile.ZipFile(str(vol)) as z:
            allp = [("zip", n) for n in sorted(z.namelist()) if n.endswith(".txt")]
    num = []
    for e in allp:
        m = NUM_RE.search(Path(str(e[1])).name)
        if m:
            num.append((int(m.group(1)), e))
    num.sort(key=lambda x: x[0])
    return allp, num


def read_page(vol, entry):
    kind, ref = entry
    if kind == "dir":
        return ref.read_text(encoding="utf-8", errors="replace")
    with zipfile.ZipFile(str(vol)) as z:
        return z.read(ref).decode("utf-8", errors="replace")


def choose(allp, num, seq, n_ef):
    """-> (entry, mapping) or (None, '')."""
    if len(allp) == 1:
        if num and num[0][0] != seq:
            return allp[0], "single_other"
        return allp[0], "single"
    if len(num) == n_ef and 1 <= seq <= n_ef:
        return num[seq - 1][1], "position"
    if not num and len(allp) == n_ef and 1 <= seq <= n_ef:
        return allp[seq - 1], "position"
    if num:
        base = num[0][0]
        entry = dict(num).get(seq - 1 + base)
        if entry is not None:
            return entry, "name_base%d" % base
    return None, ""


def term_hits(text, terms):
    toks = set(TOKEN_RE.findall(text.lower()))
    tok = any(t in toks for t in terms)
    comp = tok or any(t in re.split(r"[-']", w) for w in toks if ("-" in w or "'" in w) for t in terms)
    return int(tok), int(comp)


def read_sample(path):
    return list(csv.DictReader(open(path, newline="", encoding="utf-8")))


def stage_append(args):
    found, stripped = index_volumes(args.volumes)
    if not found:
        print("%s: no volume found. What is there:" % args.volumes)
        n = 0
        for dirpath, dirnames, filenames in os.walk(args.volumes):
            for f in dirnames + filenames:
                print("   ", os.path.join(dirpath, f))
                n += 1
                if n >= 20:
                    break
            if n >= 20:
                break
        return 4
    rows = read_sample(args.sample)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    new = not (os.path.exists(args.report) and os.path.getsize(args.report) > 0)
    tally, maps, n_rows = {}, {}, 0
    with open(args.report, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(COLS)
        for r in rows:
            htid, seq, n_ef = r["htid"], int(r["seq"]), int(r["ef_page_count"])
            vol = found.get(htid)
            if vol is None and len(stripped.get(strip_namespace(htid), [])) == 1:
                vol = found[stripped[strip_namespace(htid)][0]]
            if vol is None:
                continue
            n_rows += 1
            status, mapping, n_files, tok, comp = "count_mismatch", "", 0, "", ""
            try:
                allp, num = page_list(vol)
                n_files = len(allp)
                entry, mapping = choose(allp, num, seq, n_ef)
                if entry is not None:
                    text = read_page(vol, entry)
                    d = out / clean_htid(htid)
                    d.mkdir(parents=True, exist_ok=True)
                    (d / ("%08d.txt" % seq)).write_text(text, encoding="utf-8")
                    terms = [t for t in r["terms_matched"].split("|") if t]
                    tok, comp = term_hits(text, terms)
                    status = "ok"
            except Exception as e:  # an unreadable volume must not stop the others
                status = "unreadable:" + type(e).__name__
            tally[status] = tally.get(status, 0) + 1
            if status == "ok":
                maps[mapping] = maps.get(mapping, 0) + 1
            w.writerow([htid, r["seq"], r["object"], r["decade"], status, mapping, n_files, n_ef, tok, comp])
    print("%s: %d volumes on disk, %d sample rows matched; status: %s; mapping: %s"
          % (args.volumes, len(found), n_rows, tally, maps), flush=True)
    return 0


def stage_check(args):
    rows = read_sample(args.sample)
    best = {}
    if os.path.exists(args.report):
        for r in csv.DictReader(open(args.report, newline="", encoding="utf-8")):
            key = (r["htid"], int(r["seq"]))
            if key not in best or r["status"] == "ok" or best[key]["status"] != "ok":
                best[key] = r
    final = []
    for r in rows:
        key = (r["htid"], int(r["seq"]))
        line = best.get(key)
        if line is None:
            line = {"htid": r["htid"], "seq": r["seq"], "object": r["object"], "decade": r["decade"],
                    "status": "missing_volume", "mapping": "", "n_files": 0,
                    "ef_page_count": r["ef_page_count"], "term_token": "", "term_component": ""}
        final.append(line)
    with open(args.report, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for line in final:
            w.writerow({k: line.get(k, "") for k in COLS})
    tally, maps = {}, {}
    for line in final:
        tally[line["status"]] = tally.get(line["status"], 0) + 1
        if line["status"] == "ok":
            maps[line["mapping"]] = maps.get(line["mapping"], 0) + 1
    ok = [l for l in final if l["status"] == "ok"]
    tok_rate = sum(int(l["term_token"] or 0) for l in ok) / max(1, len(ok))
    comp_rate = sum(int(l["term_component"] or 0) for l in ok) / max(1, len(ok))
    print("%d sampled pages: %d selected; status: %s; mapping: %s" % (len(final), len(ok), tally, maps))
    print("object term on the selected page: %.1f%% as a token, %.1f%% with components"
          % (100 * tok_rate, 100 * comp_rate))
    if len(ok) < MIN_SELECTED * len(final):
        print("STOP-CHECK: only %d/%d sampled pages could be selected" % (len(ok), len(final)))
        return 3
    if comp_rate < MIN_TERM:
        print("STOP-CHECK: too few selected pages carry their object term: the page mapping is wrong")
        return 3
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", required=True, help="precision_sample.csv")
    ap.add_argument("--report", required=True, help="per-page report CSV (no text)")
    ap.add_argument("--volumes", help="append: where htrc download wrote this chunk")
    ap.add_argument("--out", help="append: output dir of one-page volumes")
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.append == args.check:
        ap.error("give exactly one of --append or --check")
    if args.append and not (args.volumes and args.out):
        ap.error("--append needs --volumes and --out")
    return stage_append(args) if args.append else stage_check(args)


if __name__ == "__main__":
    sys.exit(main())
