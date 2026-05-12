#!/usr/bin/env bash
set -euo pipefail

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$skill_root/../../.." && pwd)"
report_dir="$skill_root/logs/diagnostics"
stamp="$(date +%F_%H%M%S)"
report_file="$report_dir/flow-${stamp}.txt"

mkdir -p "$report_dir"
: > "$report_file"

say() {
    printf '%s\n' "$*" | tee -a "$report_file" >/dev/null
}

section() {
    say ""
    say "== $1 =="
}

collect_descendants() {
    local root_pid="$1"
    local -a queue=("$root_pid")
    local -A seen=()
    local pid child

    while [ "${#queue[@]}" -gt 0 ]; do
        pid="${queue[0]}"
        queue=("${queue[@]:1}")

        if [ -n "${seen[$pid]:-}" ]; then
            continue
        fi
        seen["$pid"]=1

        while IFS= read -r child; do
            [ -n "$child" ] && queue+=("$child")
        done < <(pgrep -P "$pid" || true)
    done

    printf '%s\n' "${!seen[@]}" | sort -n
}

summarize_group() {
    local label="$1"
    local pattern="$2"
    local -a roots=()
    local -a all_pids=()
    local -a group_pids=()
    local ps_output cpu_total rss_total_kib rss_total_mib

    mapfile -t roots < <(pgrep -f "$pattern" || true)
    if [ "${#roots[@]}" -eq 0 ]; then
        say "$label: not running"
        return
    fi

    for root_pid in "${roots[@]}"; do
        mapfile -t group_pids < <(collect_descendants "$root_pid")
        all_pids+=("${group_pids[@]}")
    done

    mapfile -t all_pids < <(printf '%s\n' "${all_pids[@]}" | sort -n | uniq)
    ps_output="$(ps -o pid=,ppid=,pcpu=,pmem=,rss=,comm= -p "$(IFS=,; echo "${all_pids[*]}")" 2>/dev/null || true)"

    if [ -z "$ps_output" ]; then
        say "$label: process tree vanished before sampling"
        return
    fi

    cpu_total="$(printf '%s\n' "$ps_output" | awk '{sum += $3} END {printf "%.1f", sum + 0}')"
    rss_total_kib="$(printf '%s\n' "$ps_output" | awk '{sum += $5} END {printf "%.0f", sum + 0}')"
    rss_total_mib="$(awk -v kib="$rss_total_kib" 'BEGIN { printf "%.1f", kib / 1024 }')"

    say "$label total: CPU ${cpu_total}% | RSS ${rss_total_mib} MiB | procs ${#all_pids[@]}"
    printf '%s\n' "$ps_output" | awk '{printf "  %6s  %5.1f%%  %7.1f MiB  %s\n", $1, $3, $5 / 1024, $6}' | tee -a "$report_file" >/dev/null

    if command -v pstree >/dev/null 2>&1; then
        for root_pid in "${roots[@]}"; do
            say "  tree root $root_pid:"
            pstree -ap "$root_pid" | sed 's/^/    /' | tee -a "$report_file" >/dev/null || true
        done
    fi
}

section "Repo"
say "Repo root: $repo_root"
say "Branch: $(git -C "$repo_root" branch --show-current 2>/dev/null || echo unknown)"
say "Commit: $(git -C "$repo_root" rev-parse --short HEAD 2>/dev/null || echo unknown)"
say "Dirty: $(git -C "$repo_root" status --short 2>/dev/null | wc -l | tr -d ' ') file(s)"

section "Host"
say "Date: $(date '+%Y-%m-%d %H:%M:%S %z')"
say "Host: $(hostname 2>/dev/null || echo unknown)"
say "Kernel: $(uname -srmo)"
say "CPU cores: $(nproc 2>/dev/null || echo unknown)"
say "Uptime: $(uptime -p 2>/dev/null || echo unknown)"

section "Memory"
free -m | awk '
    /^Mem:/ {
        printf "RAM summary: used %d MiB / %d MiB total (available %d MiB)\n", $3, $2, $7
    }
    /^Swap:/ {
        printf "Swap summary: used %d MiB / %d MiB total\n", $3, $2
    }
' | tee -a "$report_file" >/dev/null
free -h | tee -a "$report_file" >/dev/null

section "GPU"
if command -v nvidia-smi >/dev/null 2>&1; then
    if ! nvidia-smi --query-gpu=name,utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader,nounits | tee -a "$report_file" >/dev/null; then
        say "nvidia-smi is available but could not read the GPU snapshot"
    fi
else
    say "nvidia-smi not available on this host"
fi

baileys_gateway_url="${BAILEYS_GATEWAY_URL:-}"
if [ -z "$baileys_gateway_url" ] && [ -f "$skill_root/.env" ]; then
    baileys_gateway_url="$(sed -n 's/^BAILEYS_GATEWAY_URL=//p' "$skill_root/.env" | tail -n 1)"
fi
baileys_gateway_url="${baileys_gateway_url:-http://127.0.0.1:${BAILEYS_PORT:-3015}}"
baileys_gateway_url="${baileys_gateway_url%/}"

section "Flow"
summarize_group "Sender" '[s]cripts/sender_worker.py|[r]un_sender.sh'
summarize_group "Baileys gateway" '[w]hatsapp_gateway|[b]aileys|[n]ode .*dist/index.js|[t]sx .*src/index.ts'
summarize_group "Scan" '[s]cripts/scan_deals.py|[r]un_scan.sh'
summarize_group "Playwright" '[p]laywright/driver/node|[c]hrome-headless-shell|[c]hromium'

section "Baileys Gateway Health"
say "Health URL: ${baileys_gateway_url}/health"
if command -v curl >/dev/null 2>&1; then
    if curl -fsS --max-time 3 "${baileys_gateway_url}/health" 2>>"$report_file" | tee -a "$report_file" >/dev/null; then
        say "Baileys gateway health: reachable"
    else
        say "Baileys gateway health: unavailable"
    fi
else
    say "curl not available; skipped Baileys gateway HTTP health check"
fi

section "How to share"
say "Report file: $report_file"
say "Send this file together with the server specs your friend has."
say "For a quick paste, the current report already includes repo version, WSL memory, GPU and per-flow CPU/RSS."

echo "$report_file"
