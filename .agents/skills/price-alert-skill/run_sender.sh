#!/usr/bin/env bash
set -euo pipefail

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python="$skill_root/.venv/bin/python"
script="$skill_root/scripts/sender_worker.py"
log_dir="$skill_root/logs"
log_file="$log_dir/sender-$(date +%F).log"
stop_request_file="$skill_root/data/sender_stop.request"
restart_delay_seconds="${RESTART_DELAY_SECONDS:-60}"

mkdir -p "$log_dir" "$skill_root/data"

if [ ! -x "$python" ]; then
    echo "Python venv not found at: $python" >&2
    echo "Run ./setup_ubuntu.sh first." >&2
    exit 1
fi

cd "$skill_root"
export PYTHONUTF8=1

while true; do
    if [ -f "$stop_request_file" ]; then
        rm -f "$stop_request_file"
        exit 0
    fi

    set +e
    "$python" -u "$script" --continuous "$@" >> "$log_file" 2>&1
    exit_code=$?
    set -e

    if [ -f "$stop_request_file" ]; then
        rm -f "$stop_request_file"
        exit 0
    fi

    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    if [ "$exit_code" -eq 0 ]; then
        printf '[%s] Sender worker exited cleanly. Restarting in %s seconds...
' "$timestamp" "$restart_delay_seconds" >> "$log_file"
    else
        printf '[%s] Sender worker exited with code %s. Retrying in %s seconds...
' "$timestamp" "$exit_code" "$restart_delay_seconds" >> "$log_file"
    fi

    sleep "$restart_delay_seconds"
done
