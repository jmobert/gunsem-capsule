#!/bin/bash
# Stage export request 4 for release, after run-request4.sh has ended in READY.
# In SECURE mode, in the Remote Desktop terminal:
#   bash release-request4.sh
# then, only if the spool shows exactly one new results zip:
#   releaseresults done
set -u
SV=${SV:-/media/secure_volume}
SPOOL=${SPOOL:-/media/release_spool}
RUN=$SV/gunsem
REL=$RUN/request4-release
stop() { echo "STOP: $*"; exit 1; }

[ -e "$RUN/r4-ready" ] || stop "run-request4.sh has not ended in READY; run it first"
command -v releaseresults >/dev/null || stop "releaseresults is not available (are you in SECURE mode?)"
echo "=== release spool before:"
ls -la "$SPOOL"
releaseresults add "$REL/README.md" "$REL/precision-bigrams.csv" "$REL/precision-trigrams.csv" \
  "$REL/precision-volumes.csv" "$REL/precision-forms.csv" "$REL/precision-pages.csv" \
  "$REL/idiom-bigrams.csv" "$REL/idiom-trigrams.csv" "$REL/idiom-volumes.csv"
echo "releaseresults add exit=$?"
echo "=== release spool after:"
ls -la "$SPOOL"
echo
echo "If the spool now holds exactly ONE results zip, made just now, submit it by typing:"
echo "    releaseresults done"
echo "If it holds anything else (an older package, stray files), stop and tell Claude."
