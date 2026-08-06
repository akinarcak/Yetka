#!/usr/bin/env bash
set -Eeuo pipefail

# Root-side half of the GUI "plan" control. The web process may only write a
# release tag into plan-request; this runner re-validates it and runs the
# read-only planner, so the privilege boundary carries a version string and
# never a command. Mirrors yetka-update-request-runner.sh, which does the same
# for apply.

REQUEST_DIR=${YETKA_UPDATE_REQUEST_DIR:-/run/yetka-update-requests}
REQUEST_FILE="$REQUEST_DIR/plan-request"
RESULT_FILE="$REQUEST_DIR/plan-result.json"
RESULT_GROUP=${YETKA_USER:-yetka}
# The planner prints the whole target installer preflight. Keep the tail the
# GUI renders bounded so a pathological run cannot fill the tmpfs or the page.
MAX_OUTPUT_BYTES=${YETKA_PLAN_OUTPUT_LIMIT:-65536}

die() {
  printf '[yetka-update-plan] ERROR: %s\n' "$*" >&2
  exit 1
}

write_result() {
  local version=$1 started=$2 finished=$3 exit_code=$4 output_file=$5
  local tmp
  tmp=$(mktemp "$RESULT_DIR_TMP_TEMPLATE")
  python3 - "$version" "$started" "$finished" "$exit_code" "$output_file" "$MAX_OUTPUT_BYTES" > "$tmp" <<'PY'
import json
import sys

version, started, finished, exit_code, output_file, limit = sys.argv[1:7]
limit = int(limit)
with open(output_file, 'rb') as stream:
    raw = stream.read()
truncated = len(raw) > limit
if truncated:
    raw = raw[-limit:]
json.dump(
    {
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
}

[[ -d "$REQUEST_DIR" && ! -L "$REQUEST_DIR" ]] || die "Unsafe request directory"
RESULT_DIR_TMP_TEMPLATE="$REQUEST_DIR/.plan-result.XXXXXX"

if [[ ! -f "$REQUEST_FILE" || -L "$REQUEST_FILE" ]]; then
  rm -f -- "$REQUEST_FILE"
  die "No safe plan request found"
fi
IFS= read -r version < "$REQUEST_FILE"
[[ "$version" =~ ^(yetka-|v)?[0-9]+\.[0-9]+\.[0-9]+([-+][A-Za-z0-9.-]+)?$ ]] || {
  rm -f -- "$REQUEST_FILE"
  die "Invalid release tag"
}

# Remove the trigger before the long-running plan so the path unit does not
# refire, exactly as the apply runner does.
rm -f -- "$REQUEST_FILE"

started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
output=$(mktemp)
trap 'rm -f -- "$output"' EXIT

set +e
/usr/local/sbin/yetka-update plan --version "$version" > "$output" 2>&1
exit_code=$?
set -e
finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)

write_result "$version" "$started" "$finished" "$exit_code" "$output"
exit "$exit_code"
