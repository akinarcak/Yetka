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
for name in NODE_NAME NODE_IP ETCD_INITIAL_CLUSTER ETCD_CLUSTER_TOKEN ETCD_VERSION ETCD_CA_FILE ETCD_CERT_FILE ETCD_KEY_FILE; do
  [[ -n ${!name:-} ]] || { echo "$name is missing" >&2; exit 1; }
done
if [[ "$DRY_RUN" == false ]]; then
  for file in "$ETCD_CA_FILE" "$ETCD_CERT_FILE" "$ETCD_KEY_FILE"; do [[ -f "$file" ]] || { echo "Certificate file not found: $file" >&2; exit 1; }; done
fi
run() { if [[ "$DRY_RUN" == true ]]; then printf '+ '; printf '%q ' "$@"; printf '\n'; else "$@"; fi; }
case "$(uname -m)" in
  x86_64|amd64) arch=amd64; default_sha=b05cb07f5686dab8f9cdab89986b44f0dd24aaf5c627176aff325e21fa56f9f0 ;;
  aarch64|arm64) arch=arm64; default_sha=e61a0954fe6a3003ee20f45e773e12e15c58323ea485deb8a55d065170cdafe8 ;;
  *) echo "Supported architectures are amd64 and arm64" >&2; exit 1 ;;
esac
ETCD_SHA256=${ETCD_SHA256:-$default_sha}
[[ "$ETCD_VERSION" == v3.7.0 || -n ${ETCD_SHA256_OVERRIDE:-} ]] || { echo "Set ETCD_SHA256_OVERRIDE for a non-default etcd version" >&2; exit 1; }
[[ -z ${ETCD_SHA256_OVERRIDE:-} ]] || ETCD_SHA256=$ETCD_SHA256_OVERRIDE
archive="etcd-${ETCD_VERSION}-linux-${arch}.tar.gz"
url="https://github.com/etcd-io/etcd/releases/download/${ETCD_VERSION}/${archive}"

if ! getent passwd etcd >/dev/null; then run useradd --system --home-dir /var/lib/etcd --shell "$(command -v nologin || echo /sbin/nologin)" etcd; fi
run install -d -o etcd -g etcd -m 0700 /var/lib/etcd
run install -d -o root -g etcd -m 0750 /etc/etcd/pki
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
run curl --fail --location --retry 3 --output "$tmp/$archive" "$url"
if [[ "$DRY_RUN" == false ]]; then
  printf '%s  %s\n' "$ETCD_SHA256" "$tmp/$archive" | sha256sum -c -
  tar -xzf "$tmp/$archive" -C "$tmp"
  install -m 0755 "$tmp/etcd-${ETCD_VERSION}-linux-${arch}/etcd" "$tmp/etcd-${ETCD_VERSION}-linux-${arch}/etcdctl" /usr/local/bin/
  install -m 0644 "$ETCD_CA_FILE" /etc/etcd/pki/ca.crt
  install -m 0640 -o root -g etcd "$ETCD_CERT_FILE" /etc/etcd/pki/node.crt
  install -m 0640 -o root -g etcd "$ETCD_KEY_FILE" /etc/etcd/pki/node.key
  cat > /etc/etcd/etcd.env <<EOF
ETCD_NAME=${NODE_NAME}
ETCD_DATA_DIR=/var/lib/etcd
ETCD_LISTEN_PEER_URLS=https://${NODE_IP}:2380
ETCD_INITIAL_ADVERTISE_PEER_URLS=https://${NODE_IP}:2380
ETCD_LISTEN_CLIENT_URLS=https://${NODE_IP}:2379,https://127.0.0.1:2379
ETCD_ADVERTISE_CLIENT_URLS=https://${NODE_IP}:2379
ETCD_INITIAL_CLUSTER=${ETCD_INITIAL_CLUSTER}
ETCD_INITIAL_CLUSTER_STATE=new
ETCD_INITIAL_CLUSTER_TOKEN=${ETCD_CLUSTER_TOKEN}
ETCD_CLIENT_CERT_AUTH=true
ETCD_TRUSTED_CA_FILE=/etc/etcd/pki/ca.crt
ETCD_CERT_FILE=/etc/etcd/pki/node.crt
ETCD_KEY_FILE=/etc/etcd/pki/node.key
ETCD_PEER_CLIENT_CERT_AUTH=true
ETCD_PEER_TRUSTED_CA_FILE=/etc/etcd/pki/ca.crt
ETCD_PEER_CERT_FILE=/etc/etcd/pki/node.crt
ETCD_PEER_KEY_FILE=/etc/etcd/pki/node.key
EOF
  chmod 0640 /etc/etcd/etcd.env
  cat > /etc/systemd/system/etcd.service <<'EOF'
[Unit]
Description=etcd quorum for Yetka PostgreSQL
After=network-online.target
Wants=network-online.target

[Service]
User=etcd
Group=etcd
EnvironmentFile=/etc/etcd/etcd.env
ExecStart=/usr/local/bin/etcd
Restart=on-failure
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now etcd
fi
echo "etcd node prepared. Start all initial members with the same ETCD_INITIAL_CLUSTER value."
