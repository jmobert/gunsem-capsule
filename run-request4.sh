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
# It downloads the sampled volumes first, so it runs for a while. To watch it:
#   tmux attach -t r4          (leave again with Ctrl-b, then d)
# When it ends in READY, stage and submit:
#   bash release-request4.sh
#   releaseresults done        (only if the spool then shows exactly one new results zip)
# Type underscores by hand; do not rely on Tab completion for names that contain them.
# Everything written goes to the secure volume, the only place that survives secure mode.
set -u
export PATH=$HOME/.local/bin:$PATH
KIT=${KIT:-$(cd "$(dirname "$0")" && pwd)}
SV=${SV:-/media/secure_volume}
RUN=$SV/gunsem
VOLP=$RUN/volumes-precision
PAGES=$RUN/pages-precision
OUTP=$RUN/counts-precision
OUTI=$RUN/counts-idiom
REL=$RUN/request4-release
SAMPLE=${SAMPLE:-$KIT/workset/precision_sample.csv}
SAMPLE_SHA=${SAMPLE_SHA:-c70095188c7c689076be828f4f4bdbaee286410a02b1c257348a05b436ecf54e}
IDS=${IDS:-$KIT/workset/precision_htids.txt}
META=${META:-$KIT/workset/capsule_workset_v2.csv}
IDS816=${IDS816:-$KIT/workset/capsule_htids_v2.txt}
REQ1=${REQ1:-$KIT/volumes-request1.csv}  # volumes.csv exactly as released for request 1
REQ1_SHA=${REQ1_SHA:-da7d5953c2f840189a0029cef71fd421f541447035e429738e5a60c1469e8751}
KIT_SHA=31262b3902c71072da44b4dca5c9c06ebc1e0524a5ec99d6bc5f279cfa7d8473  # extract_compounds.py at e4c6e12
CAP=${CAP:-60000000}       # stay clear of HTRC's 67 MB per-request limit
CHUNK=${CHUNK:-2000}       # htids per `htrc download` call; each call gets a fresh token

sha() { python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }
stop() { echo "STOP: $*"; echo "STOP: $*" > "$RUN/r4-status.txt"; exit 1; }
status() { echo "=== $*"; echo "$(date +%H:%M) $*" > "$RUN/r4-status.txt"; }
rows() { echo $(( $(wc -l < "$1") - 1 )); }

mkdir -p "$RUN" 2>/dev/null && [ -w "$RUN" ] || stop "the secure volume is not mounted at $SV (are you in SECURE mode?)"
rm -f "$RUN/r4-ready"
LOG=$RUN/run-request4-$(date +%Y%m%d-%H%M%S).log
exec > >(tee -a "$LOG") 2>&1
echo "=== $(date)  request 4 run, log $LOG"

for f in "$KIT/extract_compounds.py" "$KIT/select_pages.py" "$KIT/count_forms.py" "$KIT/terms-precision.txt" \
         "$KIT/terms-idiom.txt" "$SAMPLE" "$IDS" "$META" "$REQ1" "$KIT/export/README-request4.md"; do
  [ -s "$f" ] || stop "missing $f"
done
[ "$(sha "$KIT/extract_compounds.py")" = "$KIT_SHA" ] || stop "extract_compounds.py is not the e4c6e12 file"
[ "$(sha "$SAMPLE")" = "$SAMPLE_SHA" ] || stop "$SAMPLE is not the published precision sample"
[ "$(sha "$REQ1")" = "$REQ1_SHA" ] || stop "$REQ1 is not request 1's released volumes.csv"
command -v htrc >/dev/null || stop "the htrc toolkit is not on PATH"
echo "code: extract_compounds.py = e4c6e12; sample: $(rows "$SAMPLE") pages; anchors: $(grep -c -v -E '^[[:space:]]*(#|$)' "$KIT/terms-precision.txt") precision, $(grep -c -v -E '^[[:space:]]*(#|$)' "$KIT/terms-idiom.txt") idiom"

missing() {  # htids of the sample with no volume on disk yet -> $RUN/r4-missing.txt
  python3 - "$KIT" "$VOLP" "$IDS" "$RUN/r4-missing.txt" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from select_pages import index_volumes, strip_namespace
root = Path(sys.argv[2]); root.mkdir(parents=True, exist_ok=True)
found, stripped = index_volumes(root)
want = [h for h in Path(sys.argv[3]).read_text().split() if h]
miss = [h for h in want if h not in found and len(stripped.get(strip_namespace(h), [])) != 1]
Path(sys.argv[4]).write_text("".join(h + "\n" for h in miss))
print(len(miss))
PY
}

status "1/6 download the sampled volumes into $VOLP"
for pass in 1 2; do
  n=$(missing) || stop "could not list the volumes on disk"
  echo "pass $pass: $n of $(wc -l < "$IDS") sampled volumes still to download"
  [ "$n" -eq 0 ] && break
  rm -rf "$RUN/r4-chunks" && mkdir -p "$RUN/r4-chunks"
  split -l "$CHUNK" -a 3 "$RUN/r4-missing.txt" "$RUN/r4-chunks/ids-"
  for f in "$RUN/r4-chunks"/ids-*; do
    k=$(basename "$f")
    status "1/6 download pass $pass, $k ($(wc -l < "$f") volumes)"
    htrc download -o "$VOLP/p$pass-$k" --batch-size 100 "$f"
    echo "download $k exit=$?"
  done
done
n=$(missing)
echo "after download: $n sampled volumes not on disk (not available, or failed twice)"
cat "$VOLP"/*/volumes_not_available.txt 2>/dev/null | sort -u > "$RUN/r4-not-available.txt"
echo "the Data API reported $(wc -l < "$RUN/r4-not-available.txt") as not available"
du -sh "$VOLP"

status "2/6 select the sampled page of each volume"
rm -rf "$PAGES"
python3 "$KIT/select_pages.py" --volumes "$VOLP" --sample "$SAMPLE" --out "$PAGES" --report "$RUN/precision-pages.csv"
rc=$?
[ "$rc" -eq 0 ] || stop "page selection failed its checks (exit $rc); see the lines above"

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
python3 - "$KIT/export/README-request4.md" "$REL" "$SAMPLE" <<'PY' || stop "the README could not be written"
import csv, re, sys
from pathlib import Path
tpl, rel, sample = Path(sys.argv[1]).read_text(encoding="utf-8"), Path(sys.argv[2]), sys.argv[3]
rows = lambda f: sum(1 for _ in open(rel / f, encoding="utf-8")) - 1
names = ["precision-bigrams.csv", "precision-trigrams.csv", "precision-volumes.csv", "precision-forms.csv",
         "precision-pages.csv", "idiom-bigrams.csv", "idiom-trigrams.csv", "idiom-volumes.csv"]
pages = list(csv.DictReader(open(rel / "precision-pages.csv", encoding="utf-8")))
ok = sum(1 for r in pages if r["status"] == "ok")
fill = {f"ROWS_{n.replace('-', '_').replace('.csv', '').upper()}": f"{rows(n):,}" for n in names}
fill["N_SAMPLE"] = f"{len(pages):,}"
fill["N_OK"] = f"{ok:,}"
size = sum((rel / n).stat().st_size for n in names) + len(tpl.encode())
fill["TOTAL_MB"] = f"{size / 1e6:.1f}"
for k, v in fill.items():
    tpl = tpl.replace("{" + k + "}", v)
left = re.findall(r"\{[A-Z_]+\}|<CODE_COMMIT>", tpl)
if left:
    sys.exit(f"unfilled README placeholders: {left}")
(rel / "README.md").write_text(tpl, encoding="utf-8")
print(f"README filled; {size:,} bytes staged in total")
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
