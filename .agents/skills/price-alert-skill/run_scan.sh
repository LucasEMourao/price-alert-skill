#!/usr/bin/env bash
set -euo pipefail

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python="$skill_root/.venv/bin/python"
script="$skill_root/scripts/scan_deals.py"
log_dir="$skill_root/logs"
log_file="$log_dir/scan-$(date +%F).log"
scan_profile="${PRICE_ALERT_SCAN_PROFILE:-tech}"
scan_categories="${PRICE_ALERT_SCAN_CATEGORIES:-}"

mkdir -p "$log_dir"

if [ ! -x "$python" ]; then
    echo "Python venv not found at: $python" >&2
    echo "Run ./setup_ubuntu.sh first." >&2
    exit 1
fi

cd "$skill_root"
export PYTHONUTF8=1

scan_args=(--all --profile "$scan_profile")
if [ -n "$scan_categories" ]; then
    scan_args+=(--query-categories "$scan_categories")
fi
scan_args+=(--scan-only --min-discount 10 --max-results 8)

set +e
"$python" -u "$script" "${scan_args[@]}" "$@" >> "$log_file" 2>&1
exit_code=$?
set -e

if [ "$exit_code" -ne 0 ]; then
    printf '[%s] Scan process exited with code %s.
' "$(date '+%Y-%m-%d %H:%M:%S')" "$exit_code" >> "$log_file"
fi

exit "$exit_code"
