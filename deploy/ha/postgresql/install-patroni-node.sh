#!/usr/bin/env bash
set -Eeuo pipefail

ENV_FILE=""
DRY_RUN=false
while (($#)); do
  case "$1" in
    --env) ENV_FILE=${2:?}; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) echo "Usage: sudo $0 --env FILE [--dry-run]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ $EUID -eq 0 ]] || { echo "Run as root" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "Missing --env FILE" >&2; exit 1; }
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
for name in NODE_NAME NODE_IP CLUSTER_NAME ETCD_ENDPOINTS ETCD_CA_FILE ETCD_CERT_FILE ETCD_KEY_FILE POSTGRES_PASSWORD REPLICATION_PASSWORD PATRONI_API_PASSWORD YETKA_DB_NAME YETKA_DB_USER YETKA_DB_PASSWORD PG_ALLOWED_CIDR; do
  [[ -n ${!name:-} && ${!name} != CHANGE_LOCALLY ]] || { echo "$name is missing" >&2; exit 1; }
done
for secret in "$POSTGRES_PASSWORD" "$REPLICATION_PASSWORD" "$PATRONI_API_PASSWORD" "$YETKA_DB_PASSWORD"; do
  [[ "$secret" != *"'"* && "$secret" != *$'\n'* ]] || { echo "Passwords may not contain single quotes or newlines" >&2; exit 1; }
done
if [[ "$DRY_RUN" == false ]]; then
  for file in "$ETCD_CA_FILE" "$ETCD_CERT_FILE" "$ETCD_KEY_FILE"; do [[ -f "$file" ]] || { echo "Certificate file not found: $file" >&2; exit 1; }; done
fi
: "${PG_DATA_DIR:=/var/lib/pgsql/yetka}"
run() { if [[ "$DRY_RUN" == true ]]; then printf '+ '; printf '%q ' "$@"; printf '\n'; else "$@"; fi; }

if command -v apt-get >/dev/null; then
  run apt-get update
  run env DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql postgresql-contrib python3-venv python3-pip haproxy curl
elif command -v dnf >/dev/null || command -v yum >/dev/null; then
  pm=dnf; command -v dnf >/dev/null || pm=yum
  run "$pm" install -y postgresql-server postgresql-contrib python3-pip haproxy curl
else
  echo "Patroni bootstrap supports apt and dnf/yum" >&2; exit 1
fi
run python3 -m venv /opt/patroni-venv
run /opt/patroni-venv/bin/pip install --upgrade 'patroni[etcd3]' psycopg2-binary
run install -d -o postgres -g postgres -m 0700 "$PG_DATA_DIR"
run install -d -o root -g postgres -m 0750 /etc/patroni

if [[ "$DRY_RUN" == false ]]; then
  install -d -o root -g postgres -m 0750 /etc/patroni/pki
  install -m 0644 "$ETCD_CA_FILE" /etc/patroni/pki/ca.crt
  install -m 0640 -o root -g postgres "$ETCD_CERT_FILE" /etc/patroni/pki/patroni.crt
  install -m 0640 -o root -g postgres "$ETCD_KEY_FILE" /etc/patroni/pki/patroni.key
  cat > /etc/patroni/patroni.yml <<EOF
scope: ${CLUSTER_NAME}
namespace: /yetka/postgresql/
name: ${NODE_NAME}
restapi:
  listen: ${NODE_IP}:8008
  connect_address: ${NODE_IP}:8008
  authentication:
    username: patroni
    password: '${PATRONI_API_PASSWORD}'
etcd3:
  hosts: ${ETCD_ENDPOINTS}
  protocol: https
  cacert: /etc/patroni/pki/ca.crt
  cert: /etc/patroni/pki/patroni.crt
  key: /etc/patroni/pki/patroni.key
bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576
    postgresql:
      use_pg_rewind: true
      use_slots: true
      parameters:
        wal_level: replica
        hot_standby: 'on'
        wal_log_hints: 'on'
        max_wal_senders: 10
        max_replication_slots: 10
  initdb:
    - encoding: UTF8
    - data-checksums
  pg_hba:
    - host replication replicator ${PG_ALLOWED_CIDR} scram-sha-256
    - host all all ${PG_ALLOWED_CIDR} scram-sha-256
  users:
    ${YETKA_DB_USER}:
      password: '${YETKA_DB_PASSWORD}'
      options: [createdb]
postgresql:
  listen: ${NODE_IP}:5432
  connect_address: ${NODE_IP}:5432
  data_dir: ${PG_DATA_DIR}
  authentication:
    superuser: {username: postgres, password: '${POSTGRES_PASSWORD}'}
    replication: {username: replicator, password: '${REPLICATION_PASSWORD}'}
  parameters:
    password_encryption: scram-sha-256
tags:
  nofailover: false
  noloadbalance: false
  clonefrom: false
  nosync: false
EOF
  chmod 0640 /etc/patroni/patroni.yml
  cat > /etc/systemd/system/patroni.service <<'EOF'
[Unit]
Description=Patroni PostgreSQL HA
After=network-online.target
Wants=network-online.target

[Service]
User=postgres
Group=postgres
ExecStart=/opt/patroni-venv/bin/patroni /etc/patroni/patroni.yml
Restart=on-failure
RestartSec=5
LimitNOFILE=262144

[Install]
WantedBy=multi-user.target
EOF
  systemctl disable --now postgresql 2>/dev/null || true
  systemctl daemon-reload
  systemctl enable --now patroni
fi
echo "Patroni node prepared. Deploy a 3/5 member etcd quorum separately, then configure HAProxy from haproxy-postgresql.cfg.example."
