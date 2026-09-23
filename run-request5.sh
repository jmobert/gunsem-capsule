#!/bin/bash
# Export request 5: general-corpus compounds, 1930-1979. The neighbours of the 74 anchors of
# requests 1, 3 and 4 (terms-request5.txt), counted by the SAME extract_compounds.py (e4c6e12)
# over a stratified sample of 7,500 in-copyright volumes (workset/general_sample.csv).
#
# In SECURE mode, in the Remote Desktop terminal, enter one line at a time:
#   cd /home/dcuser/gunsem-capsule
#   tmux new -d -s r5 bash run-request5.sh
# Progress:      cat /media/secure_volume/gunsem/r5-status.txt
# To watch it:   tmux attach -t r5      (leave again with Ctrl-b, then d)
# When the status says READY, stage and submit:
#   bash release-request5.sh
#   releaseresults done        (only if the spool then shows exactly one new results zip)
#
# Disk. The sample does not fit on the secure volume whole (one file per page, and a 100 GB
# volume has ~6 M inodes), so it is streamed: download 1,000 volumes, normalise their layout,
# count them in the background while the next 1,000 download, then delete them. Every volume
# lies in one chunk, so the chunks' rows together are the single-run output (merge_counts.py).
# The run is resumable: a finished chunk is never redone.
set -u
export PATH=$HOME/.local/bin:$PATH
KIT=${KIT:-$(cd "$(dirname "$0")" && pwd)}
SV=${SV:-/media/secure_volume}
RUN=$SV/gunsem
VOLG=$RUN/volumes-general
CNT=$RUN/counts-general
REL=$RUN/request5-release
SAMPLE=${SAMPLE:-$KIT/workset/general_sample.csv}
SAMPLE_SHA=${SAMPLE_SHA:-d2924fc9ca57bcc54a2c5fcf0136ecb7df8dd8a8a929d05253258a8fe63ca9d1}
IDS=${IDS:-$KIT/workset/general_htids.txt}
TERMS=$KIT/terms-request5.txt
TERMS_SHA=93199688949a301d1bd01fdb4a21b8ae5c186541fe5038eb675571755db4319e
KIT_SHA=31262b3902c71072da44b4dca5c9c06ebc1e0524a5ec99d6bc5f279cfa7d8473     # extract_compounds.py at e4c6e12
SHRINK_SHA=edaeb90bab14f2c3de2f869bd2dd017b2d7a1f57b9ba0e2ef6558884a32dd415  # shrink_counts.py
CAP=${CAP:-64000000}      # HTRC's limit is 67 MB per release request
CHUNK=${CHUNK:-1000}      # volumes per download

sha() { python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }
stop() { echo "STOP: $*"; echo "STOP: $*" > "$RUN/r5-status.txt"; exit 1; }
status() { echo "=== $*"; echo "$(date +%H:%M) $*" > "$RUN/r5-status.txt"; }
rows() { echo $(( $(wc -l < "$1") - 1 )); }

mkdir -p "$RUN" 2>/dev/null && [ -w "$RUN" ] || stop "the secure volume is not mounted at $SV (are you in SECURE mode?)"
rm -f "$RUN/r5-ready"
LOG=$RUN/run-request5-$(date +%Y%m%d-%H%M%S).log
exec > >(tee -a "$LOG") 2>&1
echo "=== $(date)  request 5 run, log $LOG"
echo "python: $(python3 --version 2>&1); htrc: $(command -v htrc || echo MISSING)"
df -h "$SV" | sed 's/^/  /'
df -i "$SV" | sed 's/^/  /'

for f in "$KIT/extract_compounds.py" "$KIT/shrink_counts.py" "$KIT/flatten_volumes.py" "$KIT/merge_counts.py" \
         "$KIT/stage_request5.py" "$TERMS" "$SAMPLE" "$IDS" "$KIT/export/README-request5.md"; do
  [ -s "$f" ] || stop "missing $f"
done
[ "$(sha "$KIT/extract_compounds.py")" = "$KIT_SHA" ] || stop "extract_compounds.py is not the e4c6e12 file"
[ "$(sha "$KIT/shrink_counts.py")" = "$SHRINK_SHA" ] || stop "shrink_counts.py is not the published file"
[ "$(sha "$SAMPLE")" = "$SAMPLE_SHA" ] || stop "$SAMPLE is not the published sample"
[ "$(sha "$TERMS")" = "$TERMS_SHA" ] || stop "$TERMS is not the published anchor list"
command -v htrc >/dev/null || stop "the htrc toolkit is not on PATH"
n_sample=$(rows "$SAMPLE")
echo "code: extract_compounds.py = e4c6e12; sample: $n_sample volumes; anchors: $(grep -c -v -E '^[[:space:]]*(#|$)' "$TERMS")"
mkdir -p "$VOLG" "$CNT" "$RUN/r5-chunks" || stop "cannot create the work directories"
# a finished chunk is only reusable if the chunks are cut the same way as before
if [ -e "$CNT/chunk-size" ] && [ "$(cat "$CNT/chunk-size")" != "$CHUNK" ]; then
  stop "an earlier run used CHUNK=$(cat "$CNT/chunk-size"); rerun with that, or delete $CNT to start over"
fi
echo "$CHUNK" > "$CNT/chunk-size"
rm -f "$RUN/r5-chunks"/ids-*
split -l "$CHUNK" -a 3 "$IDS" "$RUN/r5-chunks/ids-"

EXK=""; EXPID=""
fetch() {  # $1 = chunk name, $2 = id file: download, normalise, keep the not-available list
  local k=$1 ids=$2
  rm -rf "$VOLG/$k" "$VOLG/$k-quarantine" "$CNT/chunk-$k"
  mkdir -p "$CNT/chunk-$k"
  htrc download -o "$VOLG/$k" --batch-size 100 "$ids"
  echo "download $k exit=$?"
  mkdir -p "$VOLG/$k"
  cp "$VOLG/$k/volumes_not_available.txt" "$CNT/chunk-$k/not_available.txt" 2>/dev/null
  python3 "$KIT/flatten_volumes.py" --volumes "$VOLG/$k" --sample "$SAMPLE" \
      --quarantine "$VOLG/$k-quarantine" --report "$CNT/chunk-$k/flatten.csv"
  return $?
}
start_count() {  # count chunk $1 in the background
  EXK=$1
  python3 "$KIT/extract_compounds.py" --volumes "$VOLG/$EXK" --terms "$TERMS" --meta "$SAMPLE" \
      --out "$CNT/chunk-$EXK" > "$CNT/chunk-$EXK/extract.log" 2>&1 &
  EXPID=$!
}
finish_count() {  # wait for the background count, check it, delete that chunk's volumes
  [ -n "$EXK" ] || return 0
  wait "$EXPID"
  local rc=$?
  tail -n 2 "$CNT/chunk-$EXK/extract.log" | sed "s/^/  [$EXK] /"
  [ "$rc" -eq 0 ] || stop "counting chunk $EXK failed (exit $rc); see $CNT/chunk-$EXK/extract.log"
  rm -rf "$VOLG/$EXK" "$VOLG/$EXK-quarantine"
  touch "$CNT/chunk-$EXK/.done"
  EXK=""
}

status "1/4 download and count the sample, $CHUNK volumes at a time"
first=1
for f in "$RUN/r5-chunks"/ids-*; do
  k=${f##*/ids-}
  if [ -e "$CNT/chunk-$k/.done" ]; then echo "chunk $k: done in an earlier run"; first=; continue; fi
  status "1/4 chunk $k: download ($(wc -l < "$f") volumes)${EXK:+, counting $EXK}"
  fetch "$k" "$f"
  rc=$?
  if [ -n "$first" ]; then
    echo "layout of the first download:"; find "$VOLG/$k" -maxdepth 2 | head -8 | sed 's/^/    /'
    [ "$rc" -eq 0 ] || stop "the first chunk yielded no sampled volume (see $CNT/chunk-$k/flatten.csv)"
    first=
  fi
  finish_count
  start_count "$k"
done
finish_count

status "2/4 retry the sampled volumes that are neither counted nor reported unavailable"
python3 - "$SAMPLE" "$CNT" "$RUN/r5-chunks/retry-ids" <<'PY'
import csv, sys
from pathlib import Path
sample, cnt, out = sys.argv[1:4]
got, na = set(), set()
for c in Path(cnt).glob("chunk-*"):
    if (c / ".done").exists() and (c / "volumes.csv").exists():
        with open(str(c / "volumes.csv"), newline="", encoding="utf-8") as fh:
            got |= {r["htid"] for r in csv.DictReader(fh)}
    if (c / "not_available.txt").exists():
        na |= {l.strip() for l in (c / "not_available.txt").read_text().splitlines() if l.strip()}
with open(sample, newline="", encoding="utf-8") as fh:
    want = [r["htid"] for r in csv.DictReader(fh)]
miss = [h for h in want if h not in got and h not in na]
Path(out).write_text("".join(h + "\n" for h in miss))
print("%d counted, %d reported not available, %d to retry" % (len(got & set(want)), len(na & set(want)), len(miss)))
PY
if [ -s "$RUN/r5-chunks/retry-ids" ] && [ ! -e "$CNT/chunk-retry/.done" ]; then
  fetch retry "$RUN/r5-chunks/retry-ids"
  start_count retry
  finish_count
fi

status "3/4 merge the chunks and check them"
rm -rf "$CNT/merged"
python3 "$KIT/merge_counts.py" --counts "$CNT" --sample "$SAMPLE" --out "$CNT/merged" || stop "the merge failed its checks"
n_got=$(rows "$CNT/merged/volumes.csv")
echo "retrieved $n_got of $n_sample sampled volumes"
[ "$n_got" -ge $(( n_sample * 95 / 100 )) ] || stop "fewer than 95% of the sampled volumes were counted"
for f in bigrams trigrams volumes; do echo "$f.csv: $(rows "$CNT/merged/$f.csv") rows, $(wc -c < "$CNT/merged/$f.csv") bytes"; done
echo "bigram rows per anchor (top 20):"
tail -n +2 "$CNT/merged/bigrams.csv" | cut -d, -f1 | sort | uniq -c | sort -rn | head -20
grep -q -E '^gun,' "$CNT/merged/bigrams.csv" || stop "no 'gun' rows in the output"
grep -q -E '^arms,' "$CNT/merged/bigrams.csv" || stop "no 'arms' rows in the output"

status "4/4 stage request 5 in $REL"
python3 "$KIT/stage_request5.py" --merged "$CNT/merged" --work "$CNT" --shrink "$KIT/shrink_counts.py" \
    --template "$KIT/export/README-request5.md" --out "$REL" --cap "$CAP" || stop "staging failed (see the lines above)"
total=$(( $(cat "$REL"/*.csv "$REL/README.md" | wc -c) ))
[ "$total" -lt "$CAP" ] || stop "the export is $total bytes, over the cap"
echo
cat "$REL/README.md"
echo
ls -la "$REL"
touch "$RUN/r5-ready"
status "READY: request 5 is staged ($total bytes). Next: bash release-request5.sh"
echo "Next, in this terminal, one line at a time:"
echo "    bash release-request5.sh"
echo "    releaseresults done      (only if the spool then shows exactly one new results zip)"
echo "=== $(date) done"
