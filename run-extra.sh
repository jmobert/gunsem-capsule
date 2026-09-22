#!/bin/bash
# Export request 3 (supplementary): the 31 comparison-object anchors in terms-extra.txt,
# counted by the SAME extract_compounds.py (e4c6e12) over the SAME volumes already on
# the secure volume.
#
# In SECURE mode, in the Remote Desktop terminal, type one line at a time:
#   cd /home/dcuser/gunsem-capsule
#   bash run-extra.sh
# If it ends in READY, stage and submit:
#   bash release-extra.sh
#   releaseresults done
# Type underscores by hand; do not rely on Tab completion for names that contain them.
# Everything written goes to the secure volume, the only place that survives secure mode.
set -u
export PATH=$HOME/.local/bin:$PATH
KIT=${KIT:-$(cd "$(dirname "$0")" && pwd)}
SV=${SV:-/media/secure_volume}
RUN=$SV/gunsem
OUT=$RUN/counts-extra
REL=$RUN/extra-release
META=${META:-$KIT/workset/capsule_workset_v2.csv}
IDS=${IDS:-$KIT/workset/capsule_htids_v2.txt}
REQ1=${REQ1:-$KIT/volumes-request1.csv}  # volumes.csv exactly as released for request 1
REQ1_SHA=${REQ1_SHA:-da7d5953c2f840189a0029cef71fd421f541447035e429738e5a60c1469e8751}
KIT_SHA=31262b3902c71072da44b4dca5c9c06ebc1e0524a5ec99d6bc5f279cfa7d8473  # extract_compounds.py at e4c6e12

sha() { python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }
stop() { echo "STOP: $*"; exit 1; }

mkdir -p "$RUN" 2>/dev/null && [ -w "$RUN" ] || stop "the secure volume is not mounted at $SV (are you in SECURE mode?)"
rm -f "$RUN/extra-ready"
LOG=$RUN/run-extra-$(date +%Y%m%d-%H%M%S).log
exec > >(tee -a "$LOG") 2>&1
echo "=== $(date)  request 3 run, log $LOG"

for f in "$KIT/extract_compounds.py" "$KIT/terms-extra.txt" "$KIT/shrink_counts.py" "$META" "$REQ1" "$KIT/export/README-request3.md"; do
  [ -s "$f" ] || stop "missing $f"
done
[ "$(sha "$KIT/extract_compounds.py")" = "$KIT_SHA" ] || stop "extract_compounds.py is not the e4c6e12 file"
[ "$(sha "$REQ1")" = "$REQ1_SHA" ] || stop "$REQ1 is not request 1's released volumes.csv"
echo "code: extract_compounds.py = e4c6e12; terms: $(grep -c -v -E '^[[:space:]]*(#|$)' "$KIT/terms-extra.txt") in terms-extra.txt"

n=$(find "$RUN/volumes" -mindepth 1 -maxdepth 1 \( -type d -o -name '*.zip' \) 2>/dev/null | wc -l)
echo "=== 1. volumes on the secure volume: $((n))"
if [ "$n" -eq 0 ]; then
  echo "none left from 4 September: downloading the v2 list again"
  htrc download -o "$RUN/volumes" --batch-size 100 "$IDS"
  echo "download exit=$?"
fi

echo "=== 2. extract"
rm -rf "$OUT"
python3 "$KIT/extract_compounds.py" --volumes "$RUN/volumes" --terms "$KIT/terms-extra.txt" \
    --meta "$META" --out "$OUT"
rc=$?
echo "extract exit=$rc"
[ "$rc" -eq 0 ] || stop "the extraction failed (exit $rc)"

echo "=== 3. checks"
for f in bigrams trigrams volumes; do
  echo "$f.csv: $(( $(wc -l < "$OUT/$f.csv") - 1 )) rows, $(( $(wc -c < "$OUT/$f.csv") )) bytes"
done
[ ! -e "$OUT/skipped.csv" ] || stop "some volumes could not be read (see $OUT/skipped.csv)"
[ "$(sha "$OUT/volumes.csv")" = "$REQ1_SHA" ] || stop "volumes.csv differs from request 1's: not the same volumes, or not the same text"
echo "volumes.csv is byte-identical to request 1's: the same volumes and the same text"
echo "bigram rows per anchor:"
tail -n +2 "$OUT/bigrams.csv" | cut -d, -f1 | sort | uniq -c | sort -rn
grep -q -E '^(whiskey|whisky|liquor),' "$OUT/bigrams.csv" || stop "no liquor anchor in the output"
python3 "$KIT/shrink_counts.py" "$OUT"
total=$(( $(cat "$OUT/bigrams.csv" "$OUT/trigrams.csv" "$OUT/volumes.csv" | wc -c) ))
[ "$total" -lt 60000000 ] || stop "the export is $total bytes, too close to the 67 MB cap"

echo "=== 4. stage request 3 in $REL"
rm -rf "$REL" && mkdir -p "$REL" && cp "$OUT/bigrams.csv" "$OUT/trigrams.csv" "$OUT/volumes.csv" "$REL/" \
  || stop "could not stage the files"
python3 - "$KIT/export/README-request3.md" "$REL" <<'PY' || stop "the README could not be written"
import re, sys
from pathlib import Path
tpl, rel = Path(sys.argv[1]).read_text(encoding="utf-8"), Path(sys.argv[2])
rows = lambda f: sum(1 for _ in open(rel / f, encoding="utf-8")) - 1
size = sum((rel / f).stat().st_size for f in ("bigrams.csv", "trigrams.csv", "volumes.csv")) + len(tpl.encode())
for key, val in {"BIGRAM_ROWS": f"{rows('bigrams.csv'):,}", "TRIGRAM_ROWS": f"{rows('trigrams.csv'):,}",
                 "VOLUME_ROWS": f"{rows('volumes.csv'):,}", "TOTAL_MB": f"{size / 1e6:.1f}"}.items():
    tpl = tpl.replace("{" + key + "}", val)
left = re.findall(r"\{[A-Z_]+\}|<CODE_COMMIT>", tpl)
if left:
    sys.exit(f"unfilled README placeholders: {left}")
(rel / "README.md").write_text(tpl, encoding="utf-8")
PY
echo
cat "$REL/README.md"
echo
ls -la "$REL"
touch "$RUN/extra-ready"
echo "=== READY. Next, in this terminal, one line at a time:"
echo "    bash release-extra.sh"
echo "    releaseresults done      (only if the spool then shows exactly one new results zip)"
echo "=== $(date) done"
