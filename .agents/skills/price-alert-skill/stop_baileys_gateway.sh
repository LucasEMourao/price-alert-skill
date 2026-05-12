#!/usr/bin/env bash
set -euo pipefail

export TZ="${TZ:-America/Sao_Paulo}"

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$skill_root/../../.." && pwd)"
data_dir="$skill_root/data"
pid_file="$data_dir/baileys_gateway.pid"
gateway_pattern="$repo_root/whatsapp_gateway"
deadline_seconds="${STOP_TIMEOUT_SECONDS:-60}"

mkdir -p "$data_dir"

collect_descendants() {
    local root_pid="$1"
    local -a queue=("$root_pid")
    local -A seen=()
    local pid child

    while [ "${#queue[@]}" -gt 0 ]; do
        pid="${queue[0]}"
        queue=("${queue[@]:1}")

        if [ -n "${seen[$pid]:-}" ]; then
            continue
        fi
        seen["$pid"]=1

        while IFS= read -r child; do
            [ -n "$child" ] && queue+=("$child")
        done < <(pgrep -P "$pid" || true)
    done

    printf '%s\n' "${!seen[@]}" | sort -rn
}

read_pid_file() {
    [ -f "$pid_file" ] || return 0
    grep -Eo 'pid=[0-9]+' "$pid_file" | head -n 1 | cut -d= -f2
}

mapfile -t root_pids < <(
    {
        read_pid_file
        pgrep -f "$gateway_pattern" || true
    } | awk 'NF' | sort -n | uniq
)

if [ "${#root_pids[@]}" -eq 0 ]; then
    rm -f "$pid_file"
    exit 0
fi

mapfile -t all_pids < <(
    for root_pid in "${root_pids[@]}"; do
        collect_descendants "$root_pid"
    done | awk 'NF' | sort -rn | uniq
)

for pid in "${all_pids[@]}"; do
    kill "$pid" >/dev/null 2>&1 || true
done

end_at=$((SECONDS + deadline_seconds))
while [ "$SECONDS" -lt "$end_at" ]; do
    still_running=0
    for pid in "${all_pids[@]}"; do
        if kill -0 "$pid" >/dev/null 2>&1; then
            still_running=1
            break
        fi
    done

    if [ "$still_running" -eq 0 ]; then
        rm -f "$pid_file"
        exit 0
    fi

    sleep 2
done

for pid in "${all_pids[@]}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
        kill -9 "$pid" >/dev/null 2>&1 || true
    fi
done

rm -f "$pid_file"
