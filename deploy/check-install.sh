#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL=${1:-http://127.0.0.1}
fail=0
check() { local name=$1 expected=$2 url=$3 code; code=$(curl -ksS -o /dev/null -w '%{http_code}' "$url" || true); if [[ $code == "$expected" ]]; then printf 'PASS %-24s %s\n' "$name" "$code"; else printf 'FAIL %-24s got=%s expected=%s\n' "$name" "$code" "$expected"; fail=1; fi; }

check "health" 200 "$BASE_URL/api/health/"
check "unauthenticated API" 401 "$BASE_URL/api/v1/users/users/"
if systemctl is-active --quiet yetka-web; then echo "PASS yetka-web service"; else echo "FAIL yetka-web service"; fail=1; fi
if systemctl is-enabled --quiet yetka-scheduler 2>/dev/null; then echo "INFO scheduler enabled on this node"; else echo "INFO scheduler disabled on this node"; fi
exit "$fail"
