#!/usr/bin/env bash
set -Eeuo pipefail

COMMAND=check
ENV_FILE=""
TARGET_VERSION=""
ASSUME_YES=false
WORK_DIR=""
BACKUP_DIR=""
PREVIOUS_COMMIT=""
declare -a PREVIOUSLY_ENABLED=()

log() { printf '[yetka-update] %s\n' "$*"; }
die() { printf '[yetka-update] ERROR: %s\n' "$*" >&2; exit 1; }
cleanup() { [[ -z "$WORK_DIR" ]] || rm -rf -- "$WORK_DIR"; }
trap cleanup EXIT

usage() {
  cat <<'EOF'
Usage:
  yetka-update check
  sudo yetka-update plan [--env FILE] [--version vX.Y.Z]
  sudo yetka-update apply [--env FILE] [--version vX.Y.Z] [--yes]

check  Shows the latest installable Yetka release without changing the host.
plan   Downloads and verifies the signed release-channel checksum, then runs the
       target installer in dry-run mode.
apply  Takes configuration, database and (by default) data backups; updates one
       node; restarts its configured services; and verifies health.
EOF
}

if (($#)) && [[ $1 != --* ]]; then COMMAND=$1; shift; fi
while (($#)); do
  case "$1" in
    --env) ENV_FILE=${2:?--env requires a file}; shift 2 ;;
    --version) TARGET_VERSION=${2:?--version requires a tag}; shift 2 ;;
    --yes|-y) ASSUME_YES=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done
[[ "$COMMAND" =~ ^(check|plan|apply)$ ]] || die "Command must be check, plan or apply"

latest_release() {
  local json
  json=$(mktemp)
  curl --fail --silent --show-error --location --retry 3 \
    -H 'Accept: application/vnd.github+json' \
    -H 'User-Agent: Yetka-host-updater' \
    -o "$json" \
    https://api.github.com/repos/akinarcak/Yetka/releases/latest
  python3 - "$json" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding='utf-8') as stream:
    tag = json.load(stream).get('tag_name', '')
if not re.fullmatch(r'v?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?', tag):
    raise SystemExit('GitHub did not return a valid Yetka release tag')
print(tag)
PY
  rm -f -- "$json"
}

current_release() {
  local version_file=${YETKA_DATA_DIR:-/var/lib/yetka}/release-version
  if [[ -r "$version_file" ]]; then
    head -n 1 "$version_file"
  elif [[ -d ${YETKA_INSTALL_DIR:-/opt/yetka}/app/.git ]]; then
    git -c safe.directory="${YETKA_INSTALL_DIR:-/opt/yetka}/app" \
      -C "${YETKA_INSTALL_DIR:-/opt/yetka}/app" describe --tags --always 2>/dev/null || printf 'unknown\n'
  else
    printf 'unknown\n'
  fi
}

if [[ "$COMMAND" == check ]]; then
  latest=$(latest_release)
  printf 'Kurulu Yetka: %s\nSon yayın: %s\n' "$(current_release)" "$latest"
  printf 'Plan: sudo yetka-update plan --version %s\n' "$latest"
  printf 'Uygula: sudo yetka-update apply --version %s\n' "$latest"
  exit 0
fi

[[ $EUID -eq 0 ]] || die "plan and apply must run as root"
command -v flock >/dev/null || die "flock is required"
exec 9>/run/yetka-update.lock
flock -n 9 || die "Another Yetka update is already running"

if [[ -z "$ENV_FILE" && -r /etc/yetka/update.env.path ]]; then
  IFS= read -r ENV_FILE < /etc/yetka/update.env.path
fi
: "${ENV_FILE:=/etc/yetka-install.env}"
[[ -f "$ENV_FILE" ]] || die "Installation environment file not found: $ENV_FILE"
ENV_FILE=$(readlink -f "$ENV_FILE")

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
: "${YETKA_INSTALL_DIR:=/opt/yetka}"
: "${YETKA_DATA_DIR:=/var/lib/yetka}"
: "${YETKA_CONFIG_DIR:=/etc/yetka}"
: "${YETKA_USER:=yetka}"
: "${YETKA_HTTP_PORT:=8080}"
: "${YETKA_ENABLE_WEB:=true}"
: "${YETKA_ENABLE_WORKER:=true}"
: "${YETKA_ENABLE_SCHEDULER:=false}"
: "${YETKA_UPDATE_BACKUP_DATA:=true}"
: "${YETKA_BACKUP_ROOT:=/var/backups/yetka}"
: "${DB_ENGINE:=postgresql}"
: "${DB_PORT:=$([[ $DB_ENGINE == mysql ]] && echo 3306 || echo 5432)}"
: "${DB_NAME:=yetka}"
: "${DB_USER:=yetka}"
: "${DB_USE_SSL:=false}"

[[ -n "$TARGET_VERSION" ]] || TARGET_VERSION=$(latest_release)
[[ "$TARGET_VERSION" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+([-+][A-Za-z0-9.-]+)?$ ]] || die "Invalid release tag: $TARGET_VERSION"

WORK_DIR=$(mktemp -d /tmp/yetka-update.XXXXXX)
chmod 0700 "$WORK_DIR"
archive_name="yetka-installer-${TARGET_VERSION}.tar.gz"
archive="$WORK_DIR/$archive_name"
checksum="$archive.sha256"
release_base="https://github.com/akinarcak/Yetka/releases/download/${TARGET_VERSION}"
log "Downloading $TARGET_VERSION installer and checksum"
curl --fail --silent --show-error --location --retry 3 -o "$archive" "$release_base/$archive_name"
curl --fail --silent --show-error --location --retry 3 -o "$checksum" "$release_base/$archive_name.sha256"
read -r expected_hash listed_name < "$checksum" || die "Invalid checksum file"
[[ "$expected_hash" =~ ^[a-fA-F0-9]{64}$ && "$listed_name" == "$archive_name" ]] || die "Checksum file does not describe the expected archive"
(cd "$WORK_DIR" && printf '%s  %s\n' "$expected_hash" "$archive_name" | sha256sum -c -)
mkdir "$WORK_DIR/package"
tar -xzf "$archive" -C "$WORK_DIR/package"
installer="$WORK_DIR/package/deploy/install-baremetal.sh"
[[ -f "$installer" ]] || die "Release archive does not contain the bare-metal installer"
chmod 0700 "$installer"

target_env="$WORK_DIR/target.env"
cp -- "$ENV_FILE" "$target_env"
printf '\nYETKA_GIT_REF=%s\n' "$TARGET_VERSION" >> "$target_env"
chmod 0600 "$target_env"
log "Running the target installer preflight"
"$installer" --env "$target_env" --dry-run --yes
[[ "$COMMAND" == plan ]] && { log "Plan complete; no host changes were made"; exit 0; }

backup_database() {
  if [[ ${YETKA_DATA_MODE:-external} == standalone ]]; then
    command -v pg_dump >/dev/null || die "pg_dump is required for the database backup"
    runuser -u postgres -- pg_dump --format=custom "$DB_NAME" > "$BACKUP_DIR/database.pgcustom"
  elif [[ "$DB_ENGINE" == postgresql ]]; then
    command -v pg_dump >/dev/null || die "pg_dump is required for the database backup"
    PGPASSWORD=${DB_PASSWORD:?DB_PASSWORD is required} \
      PGSSLMODE=$([[ "$DB_USE_SSL" == true ]] && echo require || echo prefer) \
      pg_dump --host "$DB_HOST" --port "$DB_PORT" --username "$DB_USER" \
      --format=custom "$DB_NAME" > "$BACKUP_DIR/database.pgcustom"
  else
    command -v mysqldump >/dev/null || die "mysqldump is required for the database backup"
    MYSQL_PWD=${DB_PASSWORD:?DB_PASSWORD is required} \
      mysqldump --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" \
      --single-transaction --routines --events "$DB_NAME" > "$BACKUP_DIR/database.sql"
  fi
}

create_backups() {
  local stamp current
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  current=$(current_release | tr -cd 'A-Za-z0-9._-')
  BACKUP_DIR="$YETKA_BACKUP_ROOT/${stamp}-${current:-unknown}-to-${TARGET_VERSION}"
  install -d -o root -g root -m 0700 "$BACKUP_DIR"
  tar -czf "$BACKUP_DIR/host-config.tar.gz" "$ENV_FILE" "$YETKA_CONFIG_DIR" "$YETKA_INSTALL_DIR/app/config.yml"
  backup_database
  if [[ "$YETKA_UPDATE_BACKUP_DATA" == true ]]; then
    tar -czf "$BACKUP_DIR/data.tar.gz" "$YETKA_DATA_DIR"
  else
    log "Persistent data archive disabled by YETKA_UPDATE_BACKUP_DATA=false"
  fi
  chmod 0600 "$BACKUP_DIR"/*
  log "Backups completed: $BACKUP_DIR"
}

remember_and_stop_services() {
  local unit
  PREVIOUS_COMMIT=$(git -c safe.directory="$YETKA_INSTALL_DIR/app" -C "$YETKA_INSTALL_DIR/app" rev-parse HEAD)
  for unit in yetka-scheduler yetka-worker yetka-web yetka-koko; do
    if systemctl is-enabled --quiet "$unit" 2>/dev/null; then
      PREVIOUSLY_ENABLED+=("$unit")
      systemctl stop "$unit"
    fi
  done
}

restart_previous_services() {
  local unit
  for unit in "${PREVIOUSLY_ENABLED[@]}"; do systemctl restart "$unit" || true; done
}

rollback_application() {
  [[ -n "$PREVIOUS_COMMIT" ]] || return 0
  log "Health/update failure: restoring application commit $PREVIOUS_COMMIT"
  git -c safe.directory="$YETKA_INSTALL_DIR/app" -C "$YETKA_INSTALL_DIR/app" checkout --detach "$PREVIOUS_COMMIT" || true
  uv pip install --python "$YETKA_INSTALL_DIR/venv/bin/python" -r "$YETKA_INSTALL_DIR/app/pyproject.toml" || true
  chown -R "$YETKA_USER:$YETKA_USER" "$YETKA_INSTALL_DIR/app" "$YETKA_INSTALL_DIR/venv" || true
  restart_previous_services
  printf '[yetka-update] Database migrations were NOT automatically reversed. Restore from %s only after reviewing migration compatibility.\n' "$BACKUP_DIR" >&2
}

verify_node() {
  local unit
  for unit in "${PREVIOUSLY_ENABLED[@]}"; do
    systemctl is-active --quiet "$unit" || return 1
  done
  if [[ "$YETKA_ENABLE_WEB" == true ]]; then
    "$WORK_DIR/package/deploy/check-install.sh" "http://127.0.0.1:$YETKA_HTTP_PORT"
  fi
}

if [[ "$ASSUME_YES" != true ]]; then
  read -r -p "Back up and update this node to $TARGET_VERSION? [y/N] " answer
  [[ "$answer" =~ ^[Yy]$ ]] || exit 0
fi

create_backups
remember_and_stop_services
if ! "$installer" --env "$target_env" --yes; then
  rollback_application
  die "Installer failed; application rollback was attempted"
fi
if ! verify_node; then
  rollback_application
  die "Health verification failed; application rollback was attempted"
fi
printf '%s\n' "$TARGET_VERSION" > "$YETKA_DATA_DIR/release-version"
chown "$YETKA_USER:$YETKA_USER" "$YETKA_DATA_DIR/release-version"
chmod 0640 "$YETKA_DATA_DIR/release-version"
log "Update complete: $TARGET_VERSION"
log "Backup retained at: $BACKUP_DIR"
