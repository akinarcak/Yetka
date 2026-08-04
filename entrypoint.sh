#!/bin/bash

# Keep cleanup: child processes would otherwise become zombies.
function cleanup()
{
    local pids=()
    mapfile -t pids < <(jobs -p)
    if (( ${#pids[@]} )); then
        kill "${pids[@]}" >/dev/null 2>/dev/null
    fi
}

action="${1-start}"
service="${2-all}"

trap cleanup EXIT

# /opt/jumpserver/tmp is a symlink to /tmp/yetka, created when the image was
# built. Running with --tmpfs /tmp masks the image's /tmp, so the target
# disappears and the symlink dangles. Neither mkdir -p nor Python's
# os.makedirs(exist_ok=True) repairs that -- both see the link itself and fail
# with EEXIST -- so hands.py raised FileExistsError at import and no service
# could start under a read-only, tmpfs-mounted runtime.
#
# Create the target rather than the link. readlink -m resolves without
# requiring existence, and leaves a plain directory untouched, so this is
# correct whether or not the path is a symlink.
mkdir -p "$(readlink -m /opt/jumpserver/tmp)"

rm -f /opt/jumpserver/tmp/*.pid

if [[ "$action" == "bash" || "$action" == "sh" ]];then
    bash
elif [[ "$action" == "sleep" ]];then
    echo "Sleep 365 days"
    sleep 365d
else
    which cron &>/dev/null && [[ ! -f /var/run/crond.pid ]] && cron || echo ""
    python jms "${action}" "${service}"
fi
