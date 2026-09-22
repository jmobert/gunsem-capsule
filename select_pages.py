#!/usr/bin/env python3
"""Export request 4, step 2: pull the ONE sampled page out of each downloaded volume.

For every row of the sample (htid, seq, ...), find the volume `htrc download` wrote,
take its seq-th page file, and write that single page to OUT/<volume name>/<seq>.txt,
so `extract_compounds.py` (unchanged) sees a one-page volume with the same htid.

Page mapping. EF numbers pages 1..pageCount. Page FILE names are not trusted: the
HathiTrust dataset zips number them from 00000000, other layouts from 00000001. So a
page is chosen by POSITION in the order extract_compounds.py itself reads files
(sorted), and only when the volume has exactly ef_page_count page files. If the
counts differ and the names are numeric, the name is used with the volume's own base
(0 or 1); otherwise the row is reported and skipped.

Check. EF says every sampled page carries one of its object terms. The selected page
is tokenized with the kit's tokenizer; the term counts as present if it is a token or
a component of a hyphenated or possessive token ('gun-boat', "clock's"), which EF
splits and the kit does not. Measured on 600 local public-domain pages: present on
the positionally mapped page for 93.5% as a whole token and on the neighbouring page
for ~19%, so a wrong mapping cannot pass. Exit 3 if fewer than
90% of mapped pages carry their term or fewer than 95% of rows could be mapped.

Writes REPORT (CSV, no text): htid, seq, object, decade, status, mapping, n_files,
ef_page_count, term_token, term_component. Standard library only.
"""
import argparse
import csv
import re
import sys
import zipfile
from pathlib import Path

TOKEN_RE = re.compile(r"[a-z]+(?:[-'][a-z]+)*")  # = extract_compounds.py
NUM_RE = re.compile(r"(\d+)\.txt$")
CHUNK_RE = re.compile(r"^p\d+-ids-")  # run-request4.sh downloads into p<pass>-ids-<chunk>/


def unclean_htid(name):  # = extract_compounds.py
    if name.endswith(".zip"):
        name = name[: -len(".zip")]
    return name.replace("+", ":").replace("=", "/").replace(",", ".")


def strip_namespace(htid):
    return htid.split(".", 1)[1] if "." in htid else htid


def index_volumes(root):
    """htid -> volume path. A volume is a dir or .zip, either directly under root or
    inside one of the driver's chunk dirs; loose files (volumes_not_available.txt,
    ERROR.err) are not volumes."""
    found = {}

    def add(v):
        if v.suffix == ".zip" or v.is_dir():
            found.setdefault(unclean_htid(v.name), v)

    for p in sorted(root.iterdir()):
        if p.is_dir() and CHUNK_RE.match(p.name):
            for v in sorted(p.iterdir()):
                add(v)
        else:
            add(p)
    stripped = {}
    for h in found:
        stripped.setdefault(strip_namespace(h), []).append(h)
    return found, stripped


def page_list(vol):
    """Page files: all .txt in the order extract_compounds.py reads them, and the
    numerically named ones in numeric order (a non-page .txt is never a page)."""
    if vol.is_dir():
        allp = [("dir", p) for p in sorted(vol.glob("**/*.txt"))]
    else:
        with zipfile.ZipFile(vol) as z:
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
    with zipfile.ZipFile(vol) as z:
        return z.read(ref).decode("utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--volumes", required=True, help="where htrc download wrote the volumes")
    ap.add_argument("--sample", required=True, help="precision_sample.csv")
    ap.add_argument("--out", required=True, help="output dir of one-page volumes")
    ap.add_argument("--report", required=True, help="per-row report CSV (no text)")
    args = ap.parse_args()

    found, stripped = index_volumes(Path(args.volumes))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(args.sample, newline="", encoding="utf-8")))
    print(f"{len(rows)} sampled pages; {len(found)} volumes on disk", flush=True)
    tally = {}
    rep = []
    for i, r in enumerate(rows, 1):
        htid, seq, n_ef = r["htid"], int(r["seq"]), int(r["ef_page_count"])
        vol = found.get(htid)
        if vol is None and len(stripped.get(strip_namespace(htid), [])) == 1:
            vol = found[stripped[strip_namespace(htid)][0]]
        status, mapping, n_files, tok_hit, comp_hit = "missing_volume", "", 0, "", ""
        if vol is not None:
            try:
                allp, num = page_list(vol)
                n_files = len(num) or len(allp)
                entry = None
                if len(num) == n_ef and 1 <= seq <= n_ef:
                    entry, mapping = num[seq - 1][1], "position"
                elif not num and len(allp) == n_ef and 1 <= seq <= n_ef:
                    entry, mapping = allp[seq - 1], "position"
                elif num:
                    base = num[0][0]
                    entry = dict(num).get(seq - 1 + base)
                    mapping = f"name_base{base}"
                if entry is None:
                    status = "count_mismatch"
                else:
                    text = read_page(vol, entry)
                    name = vol.name[: -len(".zip")] if vol.name.endswith(".zip") else vol.name
                    d = out / name
                    d.mkdir(parents=True, exist_ok=True)
                    (d / f"{seq:08d}.txt").write_text(text, encoding="utf-8")
                    toks = set(TOKEN_RE.findall(text.lower()))
                    terms = [t for t in r["terms_matched"].split("|") if t]
                    tok_hit = any(t in toks for t in terms)
                    comp_hit = tok_hit or any(t in re.split(r"[-']", w) for w in toks if ("-" in w or "'" in w) for t in terms)
                    status = "ok"
            except Exception as e:  # an unreadable volume must not stop the others
                status = f"unreadable:{type(e).__name__}"
        tally[status] = tally.get(status, 0) + 1
        rep.append([htid, r["seq"], r["object"], r["decade"], status, mapping, n_files, n_ef,
                    int(tok_hit) if tok_hit != "" else "", int(comp_hit) if comp_hit != "" else ""])
        if i % 2000 == 0:
            print(f"  {i}/{len(rows)}", flush=True)
    with open(args.report, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["htid", "seq", "object", "decade", "status", "mapping", "n_files",
                    "ef_page_count", "term_token", "term_component"])
        w.writerows(rep)
    ok = [x for x in rep if x[4] == "ok"]
    maps = {}
    for x in ok:
        maps[x[5]] = maps.get(x[5], 0) + 1
    tok_rate = sum(x[8] for x in ok) / max(1, len(ok))
    comp_rate = sum(x[9] for x in ok) / max(1, len(ok))
    print(f"status: {tally}; mapping: {maps}")
    print(f"object term on the selected page: {tok_rate:.1%} as a token, {comp_rate:.1%} with components")
    if len(ok) < 0.95 * len(rows):
        print(f"STOP-CHECK: only {len(ok)}/{len(rows)} sampled pages could be selected")
        sys.exit(3)
    if comp_rate < 0.90:
        print("STOP-CHECK: too few selected pages carry their object term: the page mapping is wrong")
        sys.exit(3)


if __name__ == "__main__":
    main()
