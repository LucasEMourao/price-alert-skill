#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
skill_root="${PRICE_ALERT_SKILL_ROOT:-$repo_root/.agents/skills/price-alert-skill}"
gateway_root="${BAILEYS_GATEWAY_ROOT:-$repo_root/whatsapp_gateway}"
deploy_remote="${DEPLOY_REMOTE:-origin}"
deploy_branch="${DEPLOY_BRANCH:-main}"
deploy_ref="${DEPLOY_REF:-$deploy_remote/$deploy_branch}"
timezone="${PRICE_ALERT_TIMEZONE:-America/Sao_Paulo}"
env_file="${PRICE_ALERT_ENV_FILE:-$skill_root/.env}"
runtime_timers=(
    price-alert-runtime-start.timer
    price-alert-runtime-stop.timer
)
scan_timers=(
    price-alert-scan.timer
)
runtime_services=(
    price-alert-baileys.service
    price-alert-sender.service
)

as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
        return 0
    fi

    if command -v sudo >/dev/null 2>&1; then
        sudo -n "$@"
        return 0
    fi

    echo "Root privileges are required for systemd installation and control." >&2
    exit 1
}

read_env_value() {
    local key="$1"

    [ -f "$env_file" ] || return 0
    sed -n "s/^${key}=//p" "$env_file" | tail -n 1 | sed "s/^\"//; s/\"$//; s/^'//; s/'$//"
}

is_runtime_window() {
    local current_hm
    current_hm="$(TZ="$timezone" date '+%H%M')"
    [ "$current_hm" -ge 1000 ] || [ "$current_hm" -lt 200 ]
}

resolve_gateway_url() {
    local configured_url="${BAILEYS_GATEWAY_URL:-$(read_env_value BAILEYS_GATEWAY_URL)}"
    if [ -n "$configured_url" ]; then
        printf '%s\n' "$configured_url"
        return 0
    fi

    local host="${BAILEYS_HOST:-$(read_env_value BAILEYS_HOST)}"
    local port="${BAILEYS_PORT:-$(read_env_value BAILEYS_PORT)}"
    host="${host:-127.0.0.1}"
    port="${port:-3015}"
    printf 'http://%s:%s\n' "$host" "$port"
}

wait_for_gateway_health() {
    local gateway_url="$1"
    local attempt

    if ! command -v curl >/dev/null 2>&1; then
        echo "curl not found; skipping Baileys gateway health check."
        return 0
    fi

    for attempt in $(seq 1 12); do
        if curl -fsS --max-time 5 "$gateway_url/health" >/dev/null; then
            echo "Baileys gateway health check passed."
            return 0
        fi
        sleep 5
    done

    echo "Baileys gateway health check failed at $gateway_url/health" >&2
    return 1
}

prepare_system_packages() {
    if command -v magick >/dev/null 2>&1 || command -v convert >/dev/null 2>&1; then
        return 0
    fi

    if ! command -v apt-get >/dev/null 2>&1; then
        echo "ImageMagick not found and apt-get is unavailable." >&2
        exit 1
    fi

    as_root apt-get update
    as_root apt-get install -y imagemagick
}

enable_timers() {
    as_root systemctl enable "${runtime_timers[@]}" "${scan_timers[@]}"
    as_root systemctl restart "${runtime_timers[@]}" "${scan_timers[@]}"
}

sync_repository() {
    cd "$repo_root"
    git fetch --prune "$deploy_remote"
    git checkout -B "$deploy_branch" "$deploy_ref"
    git reset --hard "$deploy_ref"
}

prepare_python_runtime() {
    cd "$skill_root"
    "$skill_root/setup_ubuntu.sh"
}

prepare_gateway_runtime() {
    cd "$gateway_root"
    npm ci
    npm run build
}

install_units() {
    cd "$repo_root"
    "$repo_root/deploy/install_systemd_units.sh"
}

align_runtime_state() {
    local gateway_url="$1"

    if is_runtime_window; then
        as_root systemctl start price-alert-runtime.target
        as_root systemctl restart "${runtime_services[@]}"
        wait_for_gateway_health "$gateway_url"
    else
        as_root systemctl stop price-alert-runtime.target || true
    fi
}

verify_systemd_state() {
    as_root systemctl is-enabled "${runtime_timers[@]}" "${scan_timers[@]}" >/dev/null
    as_root systemctl is-active "${runtime_timers[@]}" "${scan_timers[@]}" >/dev/null

    if is_runtime_window; then
        as_root systemctl is-active "${runtime_services[@]}" >/dev/null
    fi
}

main() {
    local gateway_url

    sync_repository
    prepare_system_packages
    prepare_python_runtime
    prepare_gateway_runtime
    install_units

    gateway_url="$(resolve_gateway_url)"
    enable_timers
    align_runtime_state "$gateway_url"
    verify_systemd_state

    printf 'Deploy complete at %s for %s\n' "$(date -Is)" "$deploy_ref"
}

main "$@"
