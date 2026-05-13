#!/usr/bin/env bash
set -euo pipefail

export TZ="${TZ:-America/Sao_Paulo}"

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python="${SCAN_RUN_PYTHON:-$skill_root/.venv/bin/python}"
script="${SCAN_RUN_SCRIPT:-$skill_root/scripts/scan_deals.py}"
log_dir="${SCAN_RUN_LOG_DIR:-$skill_root/logs}"
log_file="$log_dir/scan-$(date +%F).log"
data_dir="${SCAN_RUN_DATA_DIR:-$skill_root/data}"
lock_dir="${SCAN_RUN_LOCK_DIR:-$data_dir/scan.lock}"
lock_pid_file="$lock_dir/pid"
scan_profile="${PRICE_ALERT_SCAN_PROFILE:-}"
scan_categories="${PRICE_ALERT_SCAN_CATEGORIES:-}"

mkdir -p "$log_dir" "$data_dir"

if [ ! -x "$python" ]; then
    echo "Python venv not found at: $python" >&2
    echo "Run ./setup_ubuntu.sh first." >&2
    exit 1
fi

cd "$skill_root"
export PYTHONUTF8=1

release_scan_lock() {
    rm -rf "$lock_dir"
}

acquire_scan_lock() {
    if mkdir "$lock_dir" 2>/dev/null; then
        printf '%s\n' "$$" > "$lock_pid_file"
        trap release_scan_lock EXIT
        return 0
    fi

    if [ -f "$lock_pid_file" ]; then
        lock_pid="$(tr -d '[:space:]' < "$lock_pid_file" 2>/dev/null || true)"
        if [ -n "$lock_pid" ] && ! kill -0 "$lock_pid" 2>/dev/null; then
            rm -rf "$lock_dir"
            if mkdir "$lock_dir" 2>/dev/null; then
                printf '%s\n' "$$" > "$lock_pid_file"
                trap release_scan_lock EXIT
                return 0
            fi
        fi
    fi

    printf '[%s] Scan already running; skipping this trigger.\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$log_file"
    return 1
}

if ! acquire_scan_lock; then
    exit 0
fi

scan_args=(--all)
if [ -n "$scan_profile" ]; then
    scan_args+=(--profile "$scan_profile")
fi
if [ -n "$scan_categories" ]; then
    scan_args+=(--query-categories "$scan_categories")
fi
scan_args+=(--scan-only --min-discount 10 --max-results 8)

set +e
"$python" -u "$script" "${scan_args[@]}" "$@" >> "$log_file" 2>&1
exit_code=$?
set -e

if [ "$exit_code" -ne 0 ]; then
    printf '[%s] Scan process exited with code %s.\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$exit_code" >> "$log_file"
fi

exit "$exit_code"
