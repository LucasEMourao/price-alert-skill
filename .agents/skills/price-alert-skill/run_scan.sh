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
resolved_scan_profile="${scan_profile:-tech}"
category_state_file="${SCAN_RUN_CATEGORY_STATE_FILE:-$data_dir/scan_categories_${resolved_scan_profile}.state}"

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

resolve_category_batch_size() {
    local raw_batch_size="${PRICE_ALERT_SCAN_CATEGORY_BATCH_SIZE:-}"
    if [ -n "$raw_batch_size" ]; then
        if ! [[ "$raw_batch_size" =~ ^[0-9]+$ ]]; then
            echo "PRICE_ALERT_SCAN_CATEGORY_BATCH_SIZE must be an integer greater than or equal to zero." >&2
            exit 1
        fi
        printf '%s\n' "$raw_batch_size"
        return 0
    fi

    if [ -z "$scan_categories" ] && [ "$resolved_scan_profile" = "beauty" ]; then
        printf '2\n'
        return 0
    fi

    printf '0\n'
}

load_available_categories() {
    local configured_categories="${SCAN_RUN_AVAILABLE_CATEGORIES:-}"
    if [ -n "$configured_categories" ]; then
        printf '%s\n' "$configured_categories" | tr ',' '\n'
        return 0
    fi

    set +e
    local category_output
    category_output="$("$python" - "$resolved_scan_profile" <<'PY'
from __future__ import annotations

import sys

from price_alert_skill.deal_selection import get_query_categories

for value in get_query_categories(sys.argv[1]):
    print(value)
PY
)"
    local helper_exit=$?
    set -e
    if [ "$helper_exit" -ne 0 ]; then
        printf '[%s] Failed to resolve scan category batches for profile %s; falling back to full profile scan.\n' \
            "$(date '+%Y-%m-%d %H:%M:%S')" "$resolved_scan_profile" >> "$log_file"
        return 1
    fi

    printf '%s\n' "$category_output"
}

resolve_rotating_scan_categories() {
    if [ -n "$scan_categories" ]; then
        printf '%s\n' "$scan_categories"
        return 0
    fi

    local batch_size
    batch_size="$(resolve_category_batch_size)"
    if [ "$batch_size" -le 0 ]; then
        return 0
    fi

    local category_output
    if ! category_output="$(load_available_categories)"; then
        return 0
    fi

    local -a available_categories=()
    while IFS= read -r category; do
        if [ -n "$category" ]; then
            available_categories+=("$category")
        fi
    done <<< "$category_output"

    local category_count="${#available_categories[@]}"
    if [ "$category_count" -le "$batch_size" ]; then
        return 0
    fi

    local next_index=0
    if [ -f "$category_state_file" ]; then
        next_index="$(tr -d '[:space:]' < "$category_state_file" 2>/dev/null || printf '0')"
    fi
    if ! [[ "$next_index" =~ ^[0-9]+$ ]]; then
        next_index=0
    fi
    next_index=$((next_index % category_count))

    local -a selected_categories=()
    local offset=0
    while [ "$offset" -lt "$batch_size" ]; do
        local selected_index=$(((next_index + offset) % category_count))
        selected_categories+=("${available_categories[$selected_index]}")
        offset=$((offset + 1))
    done

    local following_index=$(((next_index + batch_size) % category_count))
    printf '%s\n' "$following_index" > "$category_state_file"

    local selected_csv
    selected_csv="$(IFS=,; printf '%s' "${selected_categories[*]}")"
    printf '[%s] Rotating scan categories for profile %s: %s\n' \
        "$(date '+%Y-%m-%d %H:%M:%S')" "$resolved_scan_profile" "$selected_csv" >> "$log_file"
    printf '%s\n' "$selected_csv"
}

resolved_scan_categories="$(resolve_rotating_scan_categories)"

scan_args=(--all)
if [ -n "$resolved_scan_profile" ]; then
    scan_args+=(--profile "$resolved_scan_profile")
fi
if [ -n "$resolved_scan_categories" ]; then
    scan_args+=(--query-categories "$resolved_scan_categories")
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
