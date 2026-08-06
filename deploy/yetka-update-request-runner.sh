#!/usr/bin/env bash
set -Eeuo pipefail

# Root-side half of the GUI maintenance controls. The web process may only
# write a release tag into a queue file; this runner re-validates it and picks
# the command itself, so the privilege boundary carries data and never a
# command.
#
# The action comes from the systemd unit, not from the queue file, and the
# only two units that exist pass "apply" and "plan". Called without an
# argument it applies, which is what the unit installed before plan existed
# does.

ACTION=${1:-apply}
case "$ACTION" in
  apply) REQUEST_NAME=request ;;
  plan) REQUEST_NAME=plan-request ;;
  *) printf '[yetka-update-request] ERROR: unknown action: %s\n' "$ACTION" >&2; exit 1 ;;
esac

REQUEST_DIR=${YETKA_UPDATE_REQUEST_DIR:-/run/yetka-update-requests}
REQUEST_FILE="$REQUEST_DIR/$REQUEST_NAME"
RESULT_FILE="$REQUEST_DIR/last-result.json"
RESULT_GROUP=${YETKA_USER:-yetka}
# Keep what the GUI renders bounded so a pathological run cannot fill the
# tmpfs or the page.
MAX_OUTPUT_BYTES=${YETKA_RESULT_OUTPUT_LIMIT:-65536}

die() {
  printf '[yetka-update-request] ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -d "$REQUEST_DIR" && ! -L "$REQUEST_DIR" ]] || die "Unsafe request directory"
if [[ ! -f "$REQUEST_FILE" || -L "$REQUEST_FILE" ]]; then
  rm -f -- "$REQUEST_FILE"
  die "No safe $ACTION request found"
fi
IFS= read -r version < "$REQUEST_FILE"
[[ "$version" =~ ^(yetka-|v)?[0-9]+\.[0-9]+\.[0-9]+([-+][A-Za-z0-9.-]+)?$ ]] || {
  rm -f -- "$REQUEST_FILE"
  die "Invalid release tag"
}

# Remove the trigger before the long-running step so the path unit does not
# refire. The updater has its own exclusive lock, checksum verification,
# backup, rollback and health checks.
rm -f -- "$REQUEST_FILE"

started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
output=$(mktemp)
trap 'rm -f -- "$output"' EXIT

set +e
if [[ "$ACTION" == plan ]]; then
  /usr/local/sbin/yetka-update plan --version "$version" > "$output" 2>&1
else
  /usr/local/sbin/yetka-update apply --version "$version" --yes > "$output" 2>&1
fi
exit_code=$?
set -e
finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Record what happened where the web process can read it, so the GUI can show
# the outcome of both actions instead of sending the operator to journald.
tmp=$(mktemp "$REQUEST_DIR/.last-result.XXXXXX")
python3 - "$ACTION" "$version" "$started" "$finished" "$exit_code" "$output" "$MAX_OUTPUT_BYTES" > "$tmp" <<'PY'
import json
import sys

action, version, started, finished, exit_code, output_file, limit = sys.argv[1:8]
limit = int(limit)
with open(output_file, 'rb') as stream:
    raw = stream.read()
truncated = len(raw) > limit
if truncated:
    raw = raw[-limit:]
json.dump(
    {
        'action': action,
        'version': version,
        'started_at': started,
        'finished_at': finished,
        'exit_code': int(exit_code),
        'truncated': truncated,
        'output': raw.decode('utf-8', 'replace'),
    },
    sys.stdout,
)
PY
chmod 0640 "$tmp"
chgrp "$RESULT_GROUP" "$tmp" 2>/dev/null || true
mv -f -- "$tmp" "$RESULT_FILE"

exit "$exit_code"
