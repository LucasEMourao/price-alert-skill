#!/usr/bin/env bash
set -euo pipefail

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lock_file="$skill_root/data/sender_worker.lock"
stop_request_file="$skill_root/data/sender_stop.request"
log_dir="$skill_root/logs"
supervisor_log="$log_dir/sender-supervisor-$(date +%F).log"

mkdir -p "$log_dir" "$skill_root/data"

if pgrep -f "$skill_root/run_sender.sh" >/dev/null 2>&1; then
    exit 0
fi

if pgrep -f "$skill_root/scripts/sender_worker.py" >/dev/null 2>&1; then
    exit 0
fi

if [ -f "$lock_file" ]; then
    pid=""
    if grep -Eq 'pid=[0-9]+' "$lock_file"; then
        pid="$(grep -Eo 'pid=[0-9]+' "$lock_file" | head -n 1 | cut -d= -f2)"
    fi

    if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
        exit 0
    fi

    printf '[%s] Removing stale sender lock: %s
' "$(date '+%Y-%m-%d %H:%M:%S')" "$lock_file" >> "$supervisor_log"
    rm -f "$lock_file"
fi

rm -f "$stop_request_file"
printf '[%s] Starting sender supervisor.
' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$supervisor_log"
cd "$skill_root"
nohup ./run_sender.sh >> "$supervisor_log" 2>&1 &
