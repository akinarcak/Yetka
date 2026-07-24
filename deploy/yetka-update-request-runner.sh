#!/usr/bin/env bash
set -Eeuo pipefail

REQUEST_DIR=${YETKA_UPDATE_REQUEST_DIR:-/run/yetka-update-requests}
REQUEST_FILE="$REQUEST_DIR/request"

die() {
  printf '[yetka-update-request] ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -d "$REQUEST_DIR" && ! -L "$REQUEST_DIR" ]] || die "Unsafe request directory"
if [[ ! -f "$REQUEST_FILE" || -L "$REQUEST_FILE" ]]; then
  rm -f -- "$REQUEST_FILE"
  die "No safe update request found"
fi
IFS= read -r version < "$REQUEST_FILE"
[[ "$version" =~ ^(yetka-|v)?[0-9]+\.[0-9]+\.[0-9]+([-+][A-Za-z0-9.-]+)?$ ]] || {
  rm -f -- "$REQUEST_FILE"
  die "Invalid release tag"
}

# Remove the trigger before the long-running update. The updater has its own
# exclusive lock, checksum verification, backup, rollback and health checks.
rm -f -- "$REQUEST_FILE"
exec /usr/local/sbin/yetka-update apply --version "$version" --yes
