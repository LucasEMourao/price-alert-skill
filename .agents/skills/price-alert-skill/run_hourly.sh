#!/usr/bin/env bash
set -euo pipefail

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python="$skill_root/.venv/bin/python"
script="$skill_root/scripts/scan_deals.py"
log_dir="$skill_root/logs"
log_file="$log_dir/hourly-$(date +%F).log"

mkdir -p "$log_dir"

if [ ! -x "$python" ]; then
    echo "Python venv not found at: $python" >&2
    echo "Run ./setup_ubuntu.sh first." >&2
    exit 1
fi

cd "$skill_root"
export PYTHONUTF8=1

set +e
"$python" -u "$script" --all --min-discount 10 --max-results 8 --send-whatsapp "$@" >> "$log_file" 2>&1
exit_code=$?
set -e

if [ "$exit_code" -ne 0 ]; then
    printf '[%s] Hourly process exited with code %s.
' "$(date '+%Y-%m-%d %H:%M:%S')" "$exit_code" >> "$log_file"
fi

exit "$exit_code"
