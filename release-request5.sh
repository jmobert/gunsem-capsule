#!/bin/bash
# Stage export request 5 for release, after run-request5.sh has ended in READY.
# In SECURE mode, in the Remote Desktop terminal:
#   bash release-request5.sh
# then, only if the spool shows exactly one new results zip:
#   releaseresults done
set -u
SV=${SV:-/media/secure_volume}
SPOOL=${SPOOL:-/media/release_spool}
RUN=$SV/gunsem
REL=$RUN/request5-release
stop() { echo "STOP: $*"; exit 1; }

[ -e "$RUN/r5-ready" ] || stop "run-request5.sh has not ended in READY; run it first"
command -v releaseresults >/dev/null || stop "releaseresults is not available (are you in SECURE mode?)"
echo "=== release spool before:"
ls -la "$SPOOL"
releaseresults add "$REL/README.md" "$REL"/*.csv
echo "releaseresults add exit=$?"
echo "=== release spool after:"
ls -la "$SPOOL"
echo
echo "If the spool now holds exactly ONE results zip, made just now, submit it by typing:"
echo "    releaseresults done"
echo "If it holds anything else (an older package, stray files), stop and tell Claude."
