#!/usr/bin/env bash
set -euo pipefail

export TZ="${TZ:-America/Sao_Paulo}"

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lock_file="$skill_root/data/sender_worker.lock"
stop_request_file="$skill_root/data/sender_stop.request"
supervisor_pattern="$skill_root/run_sender.sh"

deadline_seconds="${STOP_TIMEOUT_SECONDS:-180}"
mkdir -p "$skill_root/data"
printf 'requested_at=%s
' "$(date -Is)" > "$stop_request_file"

collect_supervisor_pids() {
    pgrep -f "$supervisor_pattern" || true
}

mapfile -t supervisor_pids < <(collect_supervisor_pids)

if [ ! -f "$lock_file" ] && [ "${#supervisor_pids[@]}" -eq 0 ]; then
    rm -f "$stop_request_file"
    exit 0
fi

pid=""
if grep -Eq 'pid=[0-9]+' "$lock_file"; then
    pid="$(grep -Eo 'pid=[0-9]+' "$lock_file" | head -n 1 | cut -d= -f2)"
fi

end_at=$((SECONDS + deadline_seconds))
while [ "$SECONDS" -lt "$end_at" ]; do
    mapfile -t supervisor_pids < <(collect_supervisor_pids)

    if [ ! -f "$lock_file" ] && [ "${#supervisor_pids[@]}" -eq 0 ]; then
        rm -f "$stop_request_file"
        exit 0
    fi

    if [ -n "$pid" ] && ! kill -0 "$pid" >/dev/null 2>&1; then
        rm -f "$lock_file"
        pid=""
    fi

    sleep 2
done

if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    sleep 5
    if kill -0 "$pid" >/dev/null 2>&1; then
        kill -9 "$pid" >/dev/null 2>&1 || true
    fi
fi

mapfile -t supervisor_pids < <(collect_supervisor_pids)
for supervisor_pid in "${supervisor_pids[@]}"; do
    kill "$supervisor_pid" >/dev/null 2>&1 || true
done

sleep 2

mapfile -t supervisor_pids < <(collect_supervisor_pids)
for supervisor_pid in "${supervisor_pids[@]}"; do
    if kill -0 "$supervisor_pid" >/dev/null 2>&1; then
        kill -9 "$supervisor_pid" >/dev/null 2>&1 || true
    fi
done

rm -f "$lock_file" "$stop_request_file"
