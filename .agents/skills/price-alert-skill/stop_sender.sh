#!/usr/bin/env bash
set -euo pipefail

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lock_file="$skill_root/data/sender_worker.lock"
stop_request_file="$skill_root/data/sender_stop.request"

deadline_seconds="${STOP_TIMEOUT_SECONDS:-180}"
mkdir -p "$skill_root/data"
printf 'requested_at=%s
' "$(date -Is)" > "$stop_request_file"

if [ ! -f "$lock_file" ]; then
    rm -f "$stop_request_file"
    exit 0
fi

pid=""
if grep -Eq 'pid=[0-9]+' "$lock_file"; then
    pid="$(grep -Eo 'pid=[0-9]+' "$lock_file" | head -n 1 | cut -d= -f2)"
fi

end_at=$((SECONDS + deadline_seconds))
while [ "$SECONDS" -lt "$end_at" ]; do
    if [ ! -f "$lock_file" ]; then
        rm -f "$stop_request_file"
        exit 0
    fi

    if [ -n "$pid" ] && ! kill -0 "$pid" >/dev/null 2>&1; then
        rm -f "$lock_file" "$stop_request_file"
        exit 0
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

rm -f "$lock_file" "$stop_request_file"
