#!/usr/bin/env bash
set -euo pipefail

export TZ="${TZ:-America/Sao_Paulo}"

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log_dir="${BOOT_RECOVERY_LOG_DIR:-$skill_root/logs}"
data_dir="${BOOT_RECOVERY_DATA_DIR:-$skill_root/data}"
sender_command="${BOOT_RECOVERY_ENSURE_SENDER_CMD:-$skill_root/ensure_sender.sh}"
scan_command="${BOOT_RECOVERY_RUN_SCAN_CMD:-$skill_root/run_scan.sh}"
window_start="${BOOT_RECOVERY_WINDOW_START:-1000}"
window_end="${BOOT_RECOVERY_WINDOW_END:-0200}"
scan_recent_seconds="${BOOT_RECOVERY_SCAN_RECENT_SECONDS:-1800}"
scan_max_runtime_seconds="${BOOT_RECOVERY_SCAN_MAX_RUNTIME_SECONDS:-3600}"
scan_process_pattern="${BOOT_RECOVERY_SCAN_PROCESS_PATTERN:-[s]can_deals\.py([[:space:]]|$)}"
now_override="${BOOT_RECOVERY_NOW:-}"

mkdir -p "$log_dir" "$data_dir"

boot_log="$log_dir/boot-recovery-$(date +%F).log"

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$boot_log"
}

current_hhmm() {
    if [ -n "$now_override" ]; then
        date -d "$now_override" +%H%M
    else
        date +%H%M
    fi
}

current_epoch() {
    if [ -n "$now_override" ]; then
        date -d "$now_override" +%s
    else
        date +%s
    fi
}

within_window() {
    local hhmm
    hhmm="$(current_hhmm)"
    if [ "$window_start" -le "$window_end" ]; then
        [ "$hhmm" -ge "$window_start" ] && [ "$hhmm" -lt "$window_end" ]
        return $?
    fi
    [ "$hhmm" -ge "$window_start" ] || [ "$hhmm" -lt "$window_end" ]
}

latest_scan_log() {
    ls -1t "$log_dir"/scan-*.log 2>/dev/null | head -n 1 || true
}

scan_pids() {
    pgrep -f "$scan_process_pattern" || true
}

scan_is_healthy() {
    local pids=()
    mapfile -t pids < <(scan_pids)

    if [ "${#pids[@]}" -gt 0 ]; then
        local pid="${pids[0]}"
        local elapsed
        elapsed="$(ps -o etimes= -p "$pid" 2>/dev/null | tr -d '[:space:]' || true)"
        if [ -n "$elapsed" ] && [ "$elapsed" -le "$scan_max_runtime_seconds" ]; then
            return 0
        fi
        return 1
    fi

    local log_file
    log_file="$(latest_scan_log)"
    if [ -z "$log_file" ] || [ ! -f "$log_file" ]; then
        return 1
    fi

    local mtime age
    mtime="$(stat -c %Y "$log_file")"
    age="$(( $(current_epoch) - mtime ))"
    if [ "$age" -gt "$scan_recent_seconds" ]; then
        return 1
    fi

    if grep -Eq 'Traceback|Scan process exited with code|ERROR:' "$log_file"; then
        return 1
    fi

    grep -Eq 'Cadence scan summary:|Saved to:' "$log_file"
}

ensure_sender_now() {
    log "Ensuring sender is running."
    "$sender_command"
}

run_scan_now() {
    log "Starting recovery scan."
    "$scan_command"
}

if ! within_window; then
    log "Outside active window ($window_start-$window_end). Skipping recovery actions."
    exit 0
fi

ensure_sender_now

if scan_is_healthy; then
    log "Scan is healthy. No recovery scan needed."
    exit 0
fi

log "Scan is not healthy. Running recovery scan."
run_scan_now
