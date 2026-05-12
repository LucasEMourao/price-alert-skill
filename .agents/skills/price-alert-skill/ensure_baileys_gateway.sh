#!/usr/bin/env bash
set -euo pipefail

export TZ="${TZ:-America/Sao_Paulo}"

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$skill_root/../../.." && pwd)"
data_dir="$skill_root/data"
log_dir="$skill_root/logs"
pid_file="$data_dir/baileys_gateway.pid"
supervisor_log="$log_dir/baileys-supervisor-$(date +%F).log"
gateway_pattern="$repo_root/whatsapp_gateway"

mkdir -p "$data_dir" "$log_dir"

read_pid_file() {
    [ -f "$pid_file" ] || return 0
    grep -Eo 'pid=[0-9]+' "$pid_file" | head -n 1 | cut -d= -f2
}

pid="$(read_pid_file)"
if [ -n "${pid:-}" ] && kill -0 "$pid" >/dev/null 2>&1; then
    exit 0
fi

if [ -f "$pid_file" ]; then
    printf '[%s] Removing stale Baileys gateway pid file: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$pid_file" >> "$supervisor_log"
    rm -f "$pid_file"
fi

if pgrep -f "$gateway_pattern" >/dev/null 2>&1; then
    exit 0
fi

printf '[%s] Starting Baileys gateway supervisor.\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$supervisor_log"
cd "$skill_root"
nohup ./run_baileys_gateway.sh >> "$supervisor_log" 2>&1 &
