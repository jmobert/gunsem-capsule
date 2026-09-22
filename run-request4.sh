#!/bin/bash
# Export request 4: (a) a PRECISION sample, the neighbours of every object term on one
# sampled page per volume (18,700 pages: 11 objects x 17 decades x 100); and (b) IDIOM
# anchors (arms, amendment, militia ...) over the SAME 816 volumes as requests 1-3.
# Both are counted by the SAME extract_compounds.py (e4c6e12) as requests 1-3; this
# request adds the page sample, select_pages.py, count_forms.py, two term lists and
# this driver.
#
# In SECURE mode, in the Remote Desktop terminal, type one line at a time:
#   cd /home/dcuser/gunsem-capsule
#   tmux new -d -s r4 bash run-request4.sh
# To watch it:   tmux attach -t r4      (leave again with Ctrl-b, then d)
# Progress:      cat /media/secure_volume/gunsem/r4-status.txt
# When it ends in READY, stage and submit:
#   bash release-request4.sh
#   releaseresults done        (only if the spool then shows exactly one new results zip)
# Type underscores by hand; do not rely on Tab completion for names that contain them.
#
# Disk. The secure volume (100 GB, ~6 M inodes) cannot hold the 18,700 sampled volumes
# whole: the first run filled it at 96% (75 GB, one file per page). So each page is now
# fetched on its own (`htrc download -pg`, lines `htid[seq]`), and any whole-volume
# chunks an earlier run left behind are used first, chunk by chunk, each deleted once
# its pages are out. The selected pages and the report live on the home disk during
# the run ($WORK) and are copied to the secure volume at the end.
set -u
export PATH=$HOME/.local/bin:$PATH
KIT=${KIT:-$(cd "$(dirname "$0")" && pwd)}
SV=${SV:-/media/secure_volume}
RUN=$SV/gunsem
VOLP=$RUN/volumes-precision
WORK=${WORK:-$HOME/r4-work}
PAGES=$WORK/pages-precision
REPORT=$WORK/precision-pages.csv
OUTP=$RUN/counts-precision
OUTI=$RUN/counts-idiom
REL=$RUN/request4-release
SAMPLE=${SAMPLE:-$KIT/workset/precision_sample.csv}
SAMPLE_SHA=${SAMPLE_SHA:-c70095188c7c689076be828f4f4bdbaee286410a02b1c257348a05b436ecf54e}
META=${META:-$KIT/workset/capsule_workset_v2.csv}
IDS816=${IDS816:-$KIT/workset/capsule_htids_v2.txt}
REQ1=${REQ1:-$KIT/volumes-request1.csv}  # volumes.csv exactly as released for request 1
REQ1_SHA=${REQ1_SHA:-da7d5953c2f840189a0029cef71fd421f541447035e429738e5a60c1469e8751}
KIT_SHA=31262b3902c71072da44b4dca5c9c06ebc1e0524a5ec99d6bc5f279cfa7d8473  # extract_compounds.py at e4c6e12
CAP=${CAP:-60000000}       # stay clear of HTRC's 67 MB per-request limit
CHUNK=${CHUNK:-2000}       # sample rows per `htrc download` call; each call gets a fresh token
MODE=${MODE:-pages}        # pages = one page per volume (`-pg`); volumes = whole volumes, streamed

sha() { python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }
stop() { echo "STOP: $*"; echo "STOP: $*" > "$RUN/r4-status.txt"; exit 1; }
status() { echo "=== $*"; echo "$(date +%H:%M) $*" > "$RUN/r4-status.txt"; }
rows() { echo $(( $(wc -l < "$1") - 1 )); }

mkdir -p "$RUN" 2>/dev/null && [ -w "$RUN" ] || stop "the secure volume is not mounted at $SV (are you in SECURE mode?)"
rm -f "$RUN/r4-ready"
rm -rf "$RUN/r4-chunks" "$RUN/pages-precision" "$RUN/precision-pages.csv"   # an earlier run's leftovers
LOG=$RUN/run-request4-$(date +%Y%m%d-%H%M%S).log
exec > >(tee -a "$LOG") 2>&1
echo "=== $(date)  request 4 run, log $LOG"
echo "python: $(python3 --version 2>&1); htrc: $(command -v htrc || echo MISSING)"
df -h "$SV" "$HOME" | sed 's/^/  /'
df -i "$SV" "$HOME" | sed 's/^/  /'

for f in "$KIT/extract_compounds.py" "$KIT/select_pages.py" "$KIT/count_forms.py" "$KIT/terms-precision.txt" \
         "$KIT/terms-idiom.txt" "$SAMPLE" "$META" "$IDS816" "$REQ1" "$KIT/export/README-request4.md"; do
  [ -s "$f" ] || stop "missing $f"
done
[ "$(sha "$KIT/extract_compounds.py")" = "$KIT_SHA" ] || stop "extract_compounds.py is not the e4c6e12 file"
[ "$(sha "$SAMPLE")" = "$SAMPLE_SHA" ] || stop "$SAMPLE is not the published precision sample"
[ "$(sha "$REQ1")" = "$REQ1_SHA" ] || stop "$REQ1 is not request 1's released volumes.csv"
command -v htrc >/dev/null || stop "the htrc toolkit is not on PATH"
mkdir -p "$WORK" "$VOLP" || stop "cannot create $WORK or $VOLP"
[ "$(df -Pk "$WORK" | awk 'NR == 2 {print $4}')" -gt 500000 ] || stop "less than 500 MB free on the home disk for $WORK"
echo "code: extract_compounds.py = e4c6e12; sample: $(rows "$SAMPLE") pages; anchors: $(grep -c -v -E '^[[:space:]]*(#|$)' "$KIT/terms-precision.txt") precision, $(grep -c -v -E '^[[:space:]]*(#|$)' "$KIT/terms-idiom.txt") idiom"
[ -s "$REPORT" ] && echo "resuming: $(rows "$REPORT") report lines already in $REPORT"

select_chunk() {  # $1 = a downloaded chunk dir: pull its sampled pages into $PAGES, log its not-available list
  cat "$1"/volumes_not_available.txt >> "$RUN/r4-not-available.txt" 2>/dev/null
  python3 "$KIT/select_pages.py" --volumes "$1" --sample "$SAMPLE" --out "$PAGES" --report "$REPORT" --append
}

missing() {  # sample rows with no OK report line -> r4-missing.txt (htids) + r4-missing-pages.txt (htid[seq]); prints the count
  python3 - "$SAMPLE" "$REPORT" "$RUN/r4-missing.txt" "$RUN/r4-missing-pages.txt" <<'PY'
import csv, os, sys
sample, report, out_ids, out_pages = sys.argv[1:5]
done = set()
if os.path.exists(report):
    for r in csv.DictReader(open(report, newline="", encoding="utf-8")):
        if r["status"] == "ok":
            done.add((r["htid"], int(r["seq"])))
ids, pages = [], []
for r in csv.DictReader(open(sample, newline="", encoding="utf-8")):
    if (r["htid"], int(r["seq"])) not in done:
        ids.append(r["htid"])
        pages.append("%s[%d]" % (r["htid"], int(r["seq"])))
open(out_ids, "w").write("".join(h + "\n" for h in ids))
open(out_pages, "w").write("".join(p + "\n" for p in pages))
print(len(ids))
PY
}

status "1/6 select pages from the chunks an earlier run left in $VOLP, deleting each afterwards"
for d in "$VOLP"/p*-ids-*; do
  [ -d "$d" ] || continue
  echo "--- $d: $(du -sh "$d" 2>/dev/null | cut -f1)"
  select_chunk "$d"
  rm -rf "$d"
  df -h "$SV" | tail -1 | sed 's/^/  /'
done

status "1/6 download the sampled pages that are not selected yet"
shown=
for pass in 1 2 3; do
  n=$(missing) || stop "could not list the missing pages"
  echo "pass $pass ($MODE): $n of $(rows "$SAMPLE") sampled pages still to fetch"
  [ "$n" -eq 0 ] && break
  rm -rf "$RUN/r4-chunks" && mkdir -p "$RUN/r4-chunks"
  if [ "$MODE" = pages ]; then src=$RUN/r4-missing-pages.txt; else src=$RUN/r4-missing.txt; fi
  split -l "$CHUNK" -a 3 "$src" "$RUN/r4-chunks/ids-"
  fallback=
  for f in "$RUN/r4-chunks"/ids-*; do
    k=$(basename "$f"); dir=$VOLP/p$pass-$k
    status "1/6 download pass $pass ($MODE), $k ($(wc -l < "$f") of $n)"
    rm -rf "$dir"
    if [ "$MODE" = pages ]; then
      htrc download -pg -o "$dir" --batch-size 100 "$f"
    else
      htrc download -o "$dir" --batch-size 100 "$f"
    fi
    echo "download $k exit=$?"
    if [ -z "$shown" ]; then echo "layout of the first download:"; find "$dir" -maxdepth 4 2>/dev/null | head -12 | sed 's/^/    /'; shown=1; fi
    select_chunk "$dir"
    rc=$?
    if [ "$rc" -eq 4 ] && [ "$MODE" = pages ] && [ "$pass" -eq 1 ]; then
      echo "the first page download produced no usable volume: switching to whole-volume downloads, streamed"
      MODE=volumes; fallback=1
    fi
    rm -rf "$dir"
    [ -n "$fallback" ] && break
  done
done
n=$(missing)
sort -u "$RUN/r4-not-available.txt" 2>/dev/null > "$RUN/r4-not-available-u.txt"; mv "$RUN/r4-not-available-u.txt" "$RUN/r4-not-available.txt"
echo "after the downloads: $n sampled pages not selected; the Data API listed $(wc -l < "$RUN/r4-not-available.txt") volumes as not available"

status "2/6 check the selected pages"
python3 "$KIT/select_pages.py" --sample "$SAMPLE" --report "$REPORT" --check
rc=$?
[ "$rc" -eq 0 ] || stop "page selection failed its checks (exit $rc); see the lines above"
cp "$REPORT" "$RUN/precision-pages.csv" || stop "could not copy the report to the secure volume"

status "3/6 extract: precision anchors on the selected pages"
rm -rf "$OUTP"
python3 "$KIT/extract_compounds.py" --volumes "$PAGES" --terms "$KIT/terms-precision.txt" --meta "$SAMPLE" --out "$OUTP"
rc=$?
[ "$rc" -eq 0 ] || stop "the precision extraction failed (exit $rc)"
[ ! -e "$OUTP/skipped.csv" ] || stop "some one-page volumes could not be read (see $OUTP/skipped.csv)"
multi=$(tail -n +2 "$OUTP/volumes.csv" | awk -F, '$3 != 1' | wc -l)
[ "$multi" -eq 0 ] || stop "$multi precision volumes do not hold exactly one page"
python3 "$KIT/count_forms.py" --volumes "$PAGES" --terms "$KIT/terms-precision.txt" --meta "$SAMPLE" --out "$OUTP/forms.csv" \
  || stop "the forms count failed"

status "4/6 extract: idiom anchors over the 816 volumes of requests 1-3"
nv=$(find "$RUN/volumes" -mindepth 1 -maxdepth 1 \( -type d -o -name '*.zip' \) 2>/dev/null | wc -l)
echo "volumes of requests 1-3 on the secure volume: $((nv))"
if [ "$nv" -eq 0 ]; then
  echo "none left: downloading the v2 list again"
  htrc download -o "$RUN/volumes" --batch-size 100 "$IDS816"
  echo "download exit=$?"
fi
rm -rf "$OUTI"
python3 "$KIT/extract_compounds.py" --volumes "$RUN/volumes" --terms "$KIT/terms-idiom.txt" --meta "$META" --out "$OUTI"
rc=$?
[ "$rc" -eq 0 ] || stop "the idiom extraction failed (exit $rc)"
[ ! -e "$OUTI/skipped.csv" ] || stop "some volumes could not be read (see $OUTI/skipped.csv)"
[ "$(sha "$OUTI/volumes.csv")" = "$REQ1_SHA" ] || stop "idiom volumes.csv differs from request 1's: not the same volumes, or not the same text"
echo "idiom volumes.csv is byte-identical to request 1's: the same volumes and the same text"

status "5/6 checks"
for f in "$OUTP/bigrams.csv" "$OUTP/trigrams.csv" "$OUTP/volumes.csv" "$OUTP/forms.csv" "$RUN/precision-pages.csv" \
         "$OUTI/bigrams.csv" "$OUTI/trigrams.csv"; do
  echo "$f: $(rows "$f") rows, $(wc -c < "$f") bytes"
done
echo "precision bigram rows per anchor (top 15):"
tail -n +2 "$OUTP/bigrams.csv" | cut -d, -f1 | sort | uniq -c | sort -rn | head -15
echo "idiom bigram rows per anchor:"
tail -n +2 "$OUTI/bigrams.csv" | cut -d, -f1 | sort | uniq -c | sort -rn
grep -q -E '^arms,' "$OUTI/bigrams.csv" || stop "no 'arms' rows in the idiom output"

status "6/6 stage request 4 in $REL"
rm -rf "$REL" && mkdir -p "$REL" || stop "could not create $REL"
cp "$OUTP/bigrams.csv" "$REL/precision-bigrams.csv" && cp "$OUTP/trigrams.csv" "$REL/precision-trigrams.csv" \
  && cp "$OUTP/volumes.csv" "$REL/precision-volumes.csv" && cp "$OUTP/forms.csv" "$REL/precision-forms.csv" \
  && cp "$RUN/precision-pages.csv" "$REL/precision-pages.csv" && cp "$OUTI/bigrams.csv" "$REL/idiom-bigrams.csv" \
  && cp "$OUTI/trigrams.csv" "$REL/idiom-trigrams.csv" && cp "$OUTI/volumes.csv" "$REL/idiom-volumes.csv" \
  || stop "could not stage the files"
python3 - "$KIT/export/README-request4.md" "$REL" <<'PY' || stop "the README could not be written"
import csv, re, sys
from pathlib import Path
tpl, rel = Path(sys.argv[1]).read_text(encoding="utf-8"), Path(sys.argv[2])
rows = lambda f: sum(1 for _ in open(str(rel / f), encoding="utf-8")) - 1
names = ["precision-bigrams.csv", "precision-trigrams.csv", "precision-volumes.csv", "precision-forms.csv",
         "precision-pages.csv", "idiom-bigrams.csv", "idiom-trigrams.csv", "idiom-volumes.csv"]
pages = list(csv.DictReader(open(str(rel / "precision-pages.csv"), encoding="utf-8")))
ok = sum(1 for r in pages if r["status"] == "ok")
fill = {"ROWS_" + n.replace("-", "_").replace(".csv", "").upper(): "{:,}".format(rows(n)) for n in names}
fill["N_SAMPLE"] = "{:,}".format(len(pages))
fill["N_OK"] = "{:,}".format(ok)
size = sum((rel / n).stat().st_size for n in names) + len(tpl.encode("utf-8"))
fill["TOTAL_MB"] = "%.1f" % (size / 1e6)
for k, v in fill.items():
    tpl = tpl.replace("{" + k + "}", v)
left = re.findall(r"\{[A-Z_]+\}|<CODE_COMMIT>", tpl)
if left:
    sys.exit("unfilled README placeholders: %s" % left)
(rel / "README.md").write_text(tpl, encoding="utf-8")
print("README filled; %s bytes staged in total" % "{:,}".format(size))
PY
total=$(( $(cat "$REL"/*.csv "$REL/README.md" | wc -c) ))
[ "$total" -lt "$CAP" ] || stop "the export is $total bytes, too close to the 67 MB cap"
echo
cat "$REL/README.md"
echo
ls -la "$REL"
touch "$RUN/r4-ready"
status "READY: request 4 is staged ($total bytes). Next: bash release-request4.sh"
echo "Next, in this terminal, one line at a time:"
echo "    bash release-request4.sh"
echo "    releaseresults done      (only if the spool then shows exactly one new results zip)"
echo "=== $(date) done"
