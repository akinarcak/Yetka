#!/usr/bin/env bash
set -Eeuo pipefail

ENV_FILE=""
DRY_RUN=false
ASSUME_YES=false

log() { printf '[yetka] %s\n' "$*"; }
die() { printf '[yetka] ERROR: %s\n' "$*" >&2; exit 1; }
run() {
  if [[ "$DRY_RUN" == true ]]; then printf '+ '; printf '%q ' "$@"; printf '\n'; else "$@"; fi
}
usage() {
  cat <<'EOF'
Usage: sudo ./deploy/install-baremetal.sh --env FILE [--dry-run] [--yes]

Installs the Yetka control plane directly on a systemd Linux host. Supported
package families: Debian/Ubuntu (apt), RHEL/Rocky/Alma/Fedora (dnf/yum),
openSUSE/SLES (zypper). Docker or another container runtime is not used.
EOF
}
while (($#)); do
  case "$1" in
    --env) ENV_FILE=${2:?--env requires a file}; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --yes|-y) ASSUME_YES=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done
[[ $EUID -eq 0 ]] || die "Run as root"
[[ -n "$ENV_FILE" && -f "$ENV_FILE" ]] || die "Pass an existing --env file"
ENV_FILE=$(readlink -f "$ENV_FILE")

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${YETKA_GIT_URL:=https://github.com/akinarcak/Yetka.git}"
: "${YETKA_GIT_REF:=dev}"
: "${YETKA_INSTALL_DIR:=/opt/yetka}"
: "${YETKA_DATA_DIR:=/var/lib/yetka}"
: "${YETKA_CONFIG_DIR:=/etc/yetka}"
: "${YETKA_USER:=yetka}"
: "${YETKA_DOMAIN:=_}"
: "${YETKA_HTTP_PORT:=8080}"
: "${YETKA_DATA_MODE:=external}"
: "${DB_ENGINE:=postgresql}"
: "${DB_PORT:=$([[ ${DB_ENGINE} == mysql ]] && echo 3306 || echo 5432)}"
: "${DB_NAME:=yetka}"
: "${DB_USER:=yetka}"
: "${DB_USE_SSL:=false}"
: "${REDIS_PORT:=6379}"
: "${YETKA_ENABLE_WEB:=true}"
: "${YETKA_ENABLE_WORKER:=true}"
: "${YETKA_ENABLE_SCHEDULER:=false}"
: "${YETKA_MAINTENANCE_CHECK_ENABLED:=true}"
: "${YETKA_UPSTREAM_BASE_VERSION:=v4.10.16}"

[[ "$DB_ENGINE" =~ ^(postgresql|mysql)$ ]] || die "DB_ENGINE must be postgresql or mysql"
[[ "$YETKA_DATA_MODE" != standalone || "$DB_ENGINE" == postgresql ]] || die "Standalone mode uses PostgreSQL; MySQL is supported in external mode"
[[ "$YETKA_DATA_MODE" =~ ^(standalone|external)$ ]] || die "YETKA_DATA_MODE must be standalone or external"
[[ "$YETKA_HTTP_PORT" =~ ^[0-9]+$ ]] || die "YETKA_HTTP_PORT must be numeric"
[[ "$DRY_RUN" == true || -d /run/systemd/system ]] || die "systemd is required"
[[ "$DB_USER" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "DB_USER is not a safe SQL identifier"
[[ "$DB_NAME" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "DB_NAME is not a safe SQL identifier"
for path_value in "$YETKA_INSTALL_DIR" "$YETKA_DATA_DIR" "$YETKA_CONFIG_DIR"; do
  [[ "$path_value" == /* && "$path_value" != / && "$path_value" != /opt && "$path_value" != /var && "$path_value" != /etc ]] || die "Unsafe installation path: $path_value"
  [[ "$path_value" != *[[:space:]]* ]] || die "Installation paths may not contain whitespace"
done
if [[ "$YETKA_DATA_MODE" == external ]]; then
  [[ -n ${DB_HOST:-} && -n ${DB_PASSWORD:-} ]] || die "External mode requires DB_HOST and DB_PASSWORD"
  if [[ -z ${REDIS_SENTINEL_HOSTS:-} ]]; then
    [[ -n ${REDIS_HOST:-} ]] || die "Set REDIS_HOST or REDIS_SENTINEL_HOSTS"
  fi
fi
if [[ "$YETKA_DATA_MODE" == standalone ]]; then
  DB_HOST=127.0.0.1
  REDIS_HOST=127.0.0.1
  [[ ${DB_PASSWORD:-} == CHANGE_LOCALLY ]] && DB_PASSWORD=
  [[ ${REDIS_PASSWORD:-} == CHANGE_LOCALLY ]] && REDIS_PASSWORD=
elif [[ ${DB_PASSWORD:-} == CHANGE_LOCALLY || ${REDIS_PASSWORD:-} == CHANGE_LOCALLY ]]; then
  die "Replace every CHANGE_LOCALLY value before installation"
fi

case "$(uname -m)" in
  x86_64|amd64|aarch64|arm64) ;;
  *) die "Supported architectures are amd64 and arm64" ;;
esac

install_packages() {
  if command -v apt-get >/dev/null; then
    run apt-get update
    run env DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git nginx gcc g++ make gettext libldap2-dev libsasl2-dev libssl-dev libxml2-dev libxmlsec1-dev libffi-dev libmariadb-dev pkg-config openssh-client sshpass postgresql-client default-mysql-client util-linux
    [[ "$YETKA_DATA_MODE" == standalone ]] && run env DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql redis-server
  elif command -v dnf >/dev/null || command -v yum >/dev/null; then
    local pm=dnf; command -v dnf >/dev/null || pm=yum
    run "$pm" install -y ca-certificates curl git nginx gcc gcc-c++ make gettext openldap-devel cyrus-sasl-devel openssl-devel libxml2-devel xmlsec1-devel libffi-devel mariadb-connector-c-devel pkgconf-pkg-config openssh-clients sshpass postgresql mariadb util-linux
    [[ "$YETKA_DATA_MODE" == standalone ]] && run "$pm" install -y postgresql-server postgresql-contrib redis
  elif command -v zypper >/dev/null; then
    run zypper --non-interactive install ca-certificates curl git nginx gcc gcc-c++ make gettext-tools openldap2-devel cyrus-sasl-devel libopenssl-devel libxml2-devel xmlsec1-devel libffi-devel libmariadb-devel pkg-config openssh-clients postgresql mariadb-client util-linux
    [[ "$YETKA_DATA_MODE" == standalone ]] && run zypper --non-interactive install postgresql-server redis
  else
    die "Unsupported package manager; use apt, dnf/yum or zypper"
  fi
  return 0
}

random_secret() {
  local length=$1 bytes value
  bytes=$(( (length + 1) / 2 ))
  value=$(od -An -N "$bytes" -tx1 /dev/urandom | tr -d ' \n')
  printf '%s\n' "${value:0:length}"
}
quote_yaml() { printf "'%s'" "${1//\'/\'\'}"; }

create_identity() {
  local nologin_shell
  nologin_shell=$(command -v nologin || printf '/sbin/nologin')
  getent passwd "$YETKA_USER" >/dev/null || run useradd --system --home-dir "$YETKA_INSTALL_DIR" --shell "$nologin_shell" "$YETKA_USER"
  run install -d -o "$YETKA_USER" -g "$YETKA_USER" -m 0750 "$YETKA_INSTALL_DIR" "$YETKA_DATA_DIR" "$YETKA_DATA_DIR/core" "$YETKA_CONFIG_DIR"
}

install_uv_python() {
  if ! command -v uv >/dev/null; then
    if [[ "$DRY_RUN" == true ]]; then log "Would install uv from astral.sh"; else
      curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
    fi
  fi
  run env UV_PYTHON_INSTALL_DIR="$YETKA_INSTALL_DIR/python" uv python install 3.14
}

install_source() {
  if [[ -d "$YETKA_INSTALL_DIR/app/.git" ]]; then
    run git -c safe.directory="$YETKA_INSTALL_DIR/app" -C "$YETKA_INSTALL_DIR/app" fetch --tags origin
    if git -c safe.directory="$YETKA_INSTALL_DIR/app" -C "$YETKA_INSTALL_DIR/app" show-ref --verify --quiet "refs/remotes/origin/$YETKA_GIT_REF"; then
      run git -c safe.directory="$YETKA_INSTALL_DIR/app" -C "$YETKA_INSTALL_DIR/app" checkout -B "$YETKA_GIT_REF" "origin/$YETKA_GIT_REF"
    elif git -c safe.directory="$YETKA_INSTALL_DIR/app" -C "$YETKA_INSTALL_DIR/app" show-ref --verify --quiet "refs/tags/$YETKA_GIT_REF"; then
      run git -c safe.directory="$YETKA_INSTALL_DIR/app" -C "$YETKA_INSTALL_DIR/app" checkout --detach "refs/tags/$YETKA_GIT_REF"
    else
      run git -c safe.directory="$YETKA_INSTALL_DIR/app" -C "$YETKA_INSTALL_DIR/app" checkout --detach "$YETKA_GIT_REF"
    fi
  else
    [[ ! -e "$YETKA_INSTALL_DIR/app" ]] || die "$YETKA_INSTALL_DIR/app exists but is not a git checkout"
    run git clone --branch "$YETKA_GIT_REF" --depth 1 "$YETKA_GIT_URL" "$YETKA_INSTALL_DIR/app"
  fi
  run env UV_PYTHON_INSTALL_DIR="$YETKA_INSTALL_DIR/python" uv venv --clear --python 3.14 "$YETKA_INSTALL_DIR/venv"
  run uv pip install --python "$YETKA_INSTALL_DIR/venv/bin/python" -r "$YETKA_INSTALL_DIR/app/pyproject.toml"
  run chown -R "$YETKA_USER:$YETKA_USER" "$YETKA_INSTALL_DIR/app" "$YETKA_INSTALL_DIR/venv" "$YETKA_INSTALL_DIR/python"
}

install_management_tools() {
  run install -o root -g root -m 0750 "$YETKA_INSTALL_DIR/app/deploy/yetka-update.sh" /usr/local/sbin/yetka-update
  if [[ "$DRY_RUN" == false ]]; then
    printf '%s\n' "$ENV_FILE" > "$YETKA_CONFIG_DIR/update.env.path"
    chown root:root "$YETKA_CONFIG_DIR/update.env.path"
    chmod 0600 "$YETKA_CONFIG_DIR/update.env.path"
  fi
}

prepare_data_mount() {
  local source_dir="$YETKA_DATA_DIR/core" target_dir="$YETKA_INSTALL_DIR/app/data" fstab_line
  fstab_line="$source_dir $target_dir none bind 0 0"
  if [[ "$DRY_RUN" == true ]]; then
    log "Would bind-mount $source_dir at $target_dir and persist it in /etc/fstab"
    return
  fi
  if [[ ! -f "$source_dir/.yetka-data-initialized" ]]; then
    cp -a "$target_dir/." "$source_dir/"
    touch "$source_dir/.yetka-data-initialized"
  fi
  mountpoint -q "$target_dir" || mount --bind "$source_dir" "$target_dir"
  grep -Fqx "$fstab_line" /etc/fstab || printf '%s\n' "$fstab_line" >> /etc/fstab
  chown -R "$YETKA_USER:$YETKA_USER" "$source_dir"
}

configure_standalone() {
  [[ "$YETKA_DATA_MODE" == standalone ]] || return 0
  local standalone_secrets="$YETKA_CONFIG_DIR/standalone-secrets.env"
  : "${DB_HOST:=127.0.0.1}"
  : "${REDIS_HOST:=127.0.0.1}"
  if [[ -f "$standalone_secrets" ]]; then
    # shellcheck disable=SC1090
    source "$standalone_secrets"
  else
    : "${DB_PASSWORD:=$(random_secret 32)}"
    : "${REDIS_PASSWORD:=$(random_secret 32)}"
    if [[ "$DRY_RUN" == false ]]; then
      umask 077
      printf 'DB_PASSWORD=%q\nREDIS_PASSWORD=%q\n' "$DB_PASSWORD" "$REDIS_PASSWORD" > "$standalone_secrets"
    fi
  fi
  if command -v pg_createcluster >/dev/null && ! pg_lsclusters --no-header 2>/dev/null | grep -q .; then
    run pg_createcluster "$(find /usr/lib/postgresql -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort -V | tail -1)" main --start
  fi
  run systemctl enable --now postgresql
  run systemctl enable --now redis-server 2>/dev/null || run systemctl enable --now redis
  if [[ "$DRY_RUN" == false ]]; then
    local sql_password=${DB_PASSWORD//\'/\'\'}
    if runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
      runuser -u postgres -- psql -v ON_ERROR_STOP=1 -c "ALTER USER \"$DB_USER\" WITH PASSWORD '$sql_password'"
    else
      runuser -u postgres -- psql -v ON_ERROR_STOP=1 -c "CREATE USER \"$DB_USER\" WITH PASSWORD '$sql_password'"
    fi
    runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || runuser -u postgres -- createdb -O "$DB_USER" "$DB_NAME"
    local redis_conf=/etc/redis/redis.conf
    [[ -f $redis_conf ]] || redis_conf=/etc/redis.conf
    sed -i -E "s/^[# ]*requirepass .*/requirepass $REDIS_PASSWORD/" "$redis_conf"
    grep -q '^requirepass ' "$redis_conf" || printf '\nrequirepass %s\n' "$REDIS_PASSWORD" >> "$redis_conf"
    systemctl restart redis-server 2>/dev/null || systemctl restart redis
  fi
}

write_config() {
  local secrets="$YETKA_CONFIG_DIR/cluster-secrets.env"
  if [[ -f "$secrets" ]]; then
    # shellcheck disable=SC1090
    source "$secrets"
  else
    : "${SECRET_KEY:=$(random_secret 64)}"
    : "${BOOTSTRAP_TOKEN:=$(random_secret 48)}"
    if [[ "$DRY_RUN" == false ]]; then
      umask 077
      printf 'SECRET_KEY=%q\nBOOTSTRAP_TOKEN=%q\n' "$SECRET_KEY" "$BOOTSTRAP_TOKEN" > "$secrets"
    fi
  fi
  [[ -n ${SECRET_KEY:-} && -n ${BOOTSTRAP_TOKEN:-} ]] || die "Cluster secrets may not be empty"
  if [[ "$DRY_RUN" == false ]]; then
    umask 027
    {
      printf 'SECRET_KEY: '; quote_yaml "$SECRET_KEY"; printf '\n'
      printf 'BOOTSTRAP_TOKEN: '; quote_yaml "$BOOTSTRAP_TOKEN"; printf '\n'
      printf 'DB_ENGINE: %s\nDB_HOST: ' "$DB_ENGINE"; quote_yaml "$DB_HOST"; printf '\nDB_PORT: %s\nDB_NAME: ' "$DB_PORT"; quote_yaml "$DB_NAME"; printf '\nDB_USER: '; quote_yaml "$DB_USER"; printf '\nDB_PASSWORD: '; quote_yaml "$DB_PASSWORD"; printf '\nDB_USE_SSL: %s\n' "$DB_USE_SSL"
      if [[ -n ${REDIS_SENTINEL_HOSTS:-} ]]; then
        printf 'REDIS_SENTINEL_HOSTS: '; quote_yaml "$REDIS_SENTINEL_HOSTS"; printf '\nREDIS_SENTINEL_PASSWORD: '; quote_yaml "${REDIS_SENTINEL_PASSWORD:-}"; printf '\n'
      else
        printf 'REDIS_HOST: '; quote_yaml "$REDIS_HOST"; printf '\nREDIS_PORT: %s\n' "$REDIS_PORT"
      fi
      printf 'REDIS_PASSWORD: '; quote_yaml "${REDIS_PASSWORD:-}"; printf '\nHTTP_BIND_HOST: 127.0.0.1\nHTTP_LISTEN_PORT: %s\nDOMAINS: ' "$YETKA_HTTP_PORT"; quote_yaml "$YETKA_DOMAIN"; printf '\n'
    } > "$YETKA_INSTALL_DIR/app/config.yml"
    chown "$YETKA_USER:$YETKA_USER" "$YETKA_INSTALL_DIR/app/config.yml"
    chmod 0640 "$YETKA_INSTALL_DIR/app/config.yml"
  fi
}

download_archive() {
  local name=$1 url=$2 checksum=$3 destination=$4 tmp
  [[ -n "$url" ]] || return 1
  [[ -n "$checksum" ]] || die "$name URL is set but its SHA-256 is empty"
  tmp=$(mktemp)
  run curl --fail --location --retry 3 --output "$tmp" "$url"
  if [[ "$DRY_RUN" == false ]]; then
    printf '%s  %s\n' "$checksum" "$tmp" | sha256sum -c -
    install -d "$destination"
    tar -xzf "$tmp" -C "$destination" --strip-components=1
    rm -f "$tmp"
    chown -R "$YETKA_USER:$YETKA_USER" "$destination"
  fi
}

install_optional_assets() {
  download_archive Lina "${YETKA_LINA_URL:-}" "${YETKA_LINA_SHA256:-}" "$YETKA_INSTALL_DIR/lina" || true
  download_archive Luna "${YETKA_LUNA_URL:-}" "${YETKA_LUNA_SHA256:-}" "$YETKA_INSTALL_DIR/luna" || true
  if download_archive Koko "${YETKA_KOKO_URL:-}" "${YETKA_KOKO_SHA256:-}" "$YETKA_INSTALL_DIR/koko"; then
    log "Koko archive installed; systemd passes its token without writing it to command arguments"
  fi
  if [[ -f "$YETKA_INSTALL_DIR/lina/index.html" && "$DRY_RUN" == false ]]; then
    "$YETKA_INSTALL_DIR/venv/bin/python" "$YETKA_INSTALL_DIR/app/tools/inject_yetka_maintenance_alert.py" --index "$YETKA_INSTALL_DIR/lina/index.html"
  fi
}

write_units() {
  [[ "$DRY_RUN" == false ]] || { log "Would write systemd and nginx configuration"; return; }
  local common ui_locations luna_location koko_location
  common="User=$YETKA_USER
Group=$YETKA_USER
WorkingDirectory=$YETKA_INSTALL_DIR/app
Environment=PATH=$YETKA_INSTALL_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
Environment=CELERY_COMBINE_QUEUES=1
Environment=YETKA_MAINTENANCE_CHECK_ENABLED=$YETKA_MAINTENANCE_CHECK_ENABLED
Environment=YETKA_UPSTREAM_BASE_VERSION=$YETKA_UPSTREAM_BASE_VERSION
Restart=on-failure
RestartSec=5
TimeoutStopSec=45
KillSignal=SIGQUIT"
  for spec in "web:gunicorn" "worker:celery_combine" "scheduler:beat"; do
    local unit=${spec%%:*} service=${spec##*:}
    printf '[Unit]\nDescription=Yetka %s\nAfter=network-online.target\nWants=network-online.target\n\n[Service]\n%s\nExecStart=%s/venv/bin/python apps/manage.py start %s\n\n[Install]\nWantedBy=multi-user.target\n' "$unit" "$common" "$YETKA_INSTALL_DIR" "$service" > "/etc/systemd/system/yetka-$unit.service"
  done
  if [[ -x "$YETKA_INSTALL_DIR/koko/koko" ]]; then
    printf '[Unit]\nDescription=Yetka Koko connector\nAfter=yetka-web.service\n\n[Service]\nUser=%s\nGroup=%s\nWorkingDirectory=%s/koko\nEnvironmentFile=%s/cluster-secrets.env\nEnvironment=CORE_HOST=http://127.0.0.1:%s\nExecStart=%s/koko/koko\nRestart=always\nRestartSec=5\n\n[Install]\nWantedBy=multi-user.target\n' "$YETKA_USER" "$YETKA_USER" "$YETKA_INSTALL_DIR" "$YETKA_CONFIG_DIR" "$YETKA_HTTP_PORT" "$YETKA_INSTALL_DIR" > /etc/systemd/system/yetka-koko.service
  fi
  if [[ -f "$YETKA_INSTALL_DIR/lina/index.html" ]]; then
    ui_locations="location /ui/ { alias ${YETKA_INSTALL_DIR}/lina/; try_files \$uri / /index.html; }
  location / { rewrite ^/(.*)\$ /ui/\$1 last; }"
  else
    ui_locations="location /ui/ { return 503; }
  location / { return 503; }"
  fi
  if [[ -f "$YETKA_INSTALL_DIR/luna/index.html" ]]; then
    luna_location="location /luna/ { alias ${YETKA_INSTALL_DIR}/luna/; try_files \$uri / /index.html; }"
  else
    luna_location="location /luna/ { return 503; }"
  fi
  if [[ -x "$YETKA_INSTALL_DIR/koko/koko" ]]; then
    koko_location="location /koko/ { proxy_pass http://127.0.0.1:5000; proxy_buffering off; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection \"upgrade\"; }"
  else
    koko_location="location /koko/ { return 503; }"
  fi
  cat > /etc/nginx/conf.d/yetka.conf <<EOF
upstream yetka_core { server 127.0.0.1:${YETKA_HTTP_PORT}; keepalive 32; }
server {
  listen 80;
  server_name ${YETKA_DOMAIN};
  client_max_body_size 5g;
  proxy_read_timeout 3600s;
  location ~ ^/(core|api|media)/ { proxy_pass http://yetka_core; proxy_set_header Host \$http_host; proxy_set_header X-Real-IP \$remote_addr; proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto \$scheme; }
  location /ws/ { proxy_pass http://yetka_core; proxy_buffering off; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host \$host; }
  location /static/ { alias ${YETKA_DATA_DIR}/core/static/; }
  location /private-media/ { internal; alias ${YETKA_DATA_DIR}/core/media/; }
  ${koko_location}
  ${luna_location}
  ${ui_locations}
}
EOF
  systemctl daemon-reload
}

enable_services() {
  [[ "$DRY_RUN" == true ]] && return
  local enabled unit
  runuser -u "$YETKA_USER" -- "$YETKA_INSTALL_DIR/venv/bin/python" "$YETKA_INSTALL_DIR/app/jms" upgrade_db
  runuser -u "$YETKA_USER" -- "$YETKA_INSTALL_DIR/venv/bin/python" "$YETKA_INSTALL_DIR/app/jms" collect_static
  for enabled in "$YETKA_ENABLE_WEB" "$YETKA_ENABLE_WORKER" "$YETKA_ENABLE_SCHEDULER"; do
    case "$enabled" in true|false) ;; *) die "Service enable flags must be true or false" ;; esac
  done
  for unit in web worker scheduler; do
    case "$unit" in
      web) enabled=$YETKA_ENABLE_WEB ;;
      worker) enabled=$YETKA_ENABLE_WORKER ;;
      scheduler) enabled=$YETKA_ENABLE_SCHEDULER ;;
    esac
    if [[ "$enabled" == true ]]; then
      systemctl enable "yetka-$unit"
      systemctl restart "yetka-$unit"
    else
      systemctl disable --now "yetka-$unit" 2>/dev/null || true
    fi
  done
  if [[ -f /etc/systemd/system/yetka-koko.service ]]; then
    systemctl enable yetka-koko
    systemctl restart yetka-koko
  fi
  nginx -t
  systemctl enable nginx
  systemctl restart nginx
}

if [[ "$ASSUME_YES" != true && "$DRY_RUN" != true ]]; then
  read -r -p "Install/update Yetka on this host? [y/N] " answer
  [[ "$answer" =~ ^[Yy]$ ]] || exit 0
fi
install_packages
create_identity
install_uv_python
configure_standalone
install_source
install_management_tools
prepare_data_mount
write_config
install_optional_assets
write_units
enable_services
if [[ "$DRY_RUN" == false ]]; then
  printf '%s\n' "$YETKA_GIT_REF" > "$YETKA_DATA_DIR/release-version"
  chown "$YETKA_USER:$YETKA_USER" "$YETKA_DATA_DIR/release-version"
  chmod 0640 "$YETKA_DATA_DIR/release-version"
fi
log "Installation complete. Clean databases initially use admin / ChangeMe. Change it immediately."
[[ -z ${YETKA_LINA_URL:-} ]] && log "No Lina archive was configured; API is installed but the browser UI intentionally returns 503."
