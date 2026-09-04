#!/bin/bash
# Secure-mode run for the GUNSEM capsule. Run DETACHED:
#   tmux new -s gunsem -d 'bash ~/gunsem-capsule/run_secure.sh'
#   tmux attach -t gunsem        # watch;  Ctrl-b d  to detach
# Everything lands on the secure volume so it survives a mode switch.
set -u
export PATH=$HOME/.local/bin:$PATH
SV=/media/secure_volume
KIT=$HOME/gunsem-capsule
RUN=$SV/gunsem
LOG=$RUN/run_$(date +%Y%m%d_%H%M%S).log
IDS=${1:-$KIT/capsule_htids.txt}      # pass a smaller id file for a pilot

mkdir -p "$RUN" || { echo "secure volume not mounted at $SV — are you in SECURE mode?"; exit 1; }
exec > >(tee -a "$LOG") 2>&1
echo "=== $(date) start; ids=$IDS ($(wc -l < "$IDS") lines)"

echo "=== 1. download (skips if volumes/ already populated)"
if [ -d "$RUN/volumes" ] && [ "$(ls "$RUN/volumes" | wc -l)" -gt 0 ]; then
  echo "volumes/ exists with $(ls "$RUN/volumes" | wc -l) entries — not re-downloading (rm -rf $RUN/volumes to force)"
else
  htrc download -o "$RUN/volumes" --batch-size 100 "$IDS"
  echo "download exit=$?"
fi
echo "=== volumes present: $(find "$RUN/volumes" -mindepth 1 -maxdepth 1 -type d | wc -l) dirs; not-available: $(wc -l < "$RUN/volumes/volumes_not_available.txt" 2>/dev/null || echo 0); ERROR.err: $(test -f "$RUN/volumes/ERROR.err" && wc -l < "$RUN/volumes/ERROR.err" || echo none)"
echo "=== first 5 volume dir names (confirm naming convention):"; find "$RUN/volumes" -mindepth 1 -maxdepth 1 -type d | head -5
du -sh "$RUN/volumes"

echo "=== 2. extract"
python3 "$KIT/extract_compounds.py" --volumes "$RUN/volumes" --terms "$KIT/terms.txt" \
    --meta "$KIT/capsule_workset.csv" --out "$RUN/counts"
echo "extract exit=$?"

echo "=== 3. sanity"
for f in bigrams trigrams volumes; do echo "$f: $(($(wc -l < "$RUN/counts/$f.csv") - 1)) rows"; done
echo "volumes with year: $(tail -n +2 "$RUN/counts/volumes.csv" | awk -F, '$2!=""' | wc -l) / $(tail -n +2 "$RUN/counts/volumes.csv" | wc -l)"
echo "year range: $(tail -n +2 "$RUN/counts/volumes.csv" | cut -d, -f2 | grep . | sort -n | sed -n '1p;$p' | tr '\n' ' ')"
echo "anchors present in bigrams:"; tail -n +2 "$RUN/counts/bigrams.csv" | cut -d, -f1 | sort | uniq -c | sort -rn
echo "=== 4. export size (cap 67 MB; >1 MB = owner discussion)"; python3 "$KIT/shrink_counts.py" "$RUN/counts"
echo "=== $(date) done"
