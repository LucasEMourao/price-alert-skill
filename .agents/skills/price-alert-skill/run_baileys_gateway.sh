#!/usr/bin/env bash
set -euo pipefail

export TZ="${TZ:-America/Sao_Paulo}"

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$skill_root/../../.." && pwd)"
gateway_root="$repo_root/whatsapp_gateway"
data_dir="$skill_root/data"
pid_file="$data_dir/baileys_gateway.pid"

read_env_value() {
    local key="$1"
    local env_file="$skill_root/.env"

    [ -f "$env_file" ] || return 0
    sed -n "s/^${key}=//p" "$env_file" | tail -n 1 | sed "s/^\"//; s/\"$//; s/^'//; s/'$//"
}

mkdir -p "$data_dir" "$skill_root/logs"

export BAILEYS_HOST="${BAILEYS_HOST:-$(read_env_value BAILEYS_HOST)}"
export BAILEYS_HOST="${BAILEYS_HOST:-127.0.0.1}"
export BAILEYS_PORT="${BAILEYS_PORT:-$(read_env_value BAILEYS_PORT)}"
export BAILEYS_PORT="${BAILEYS_PORT:-3015}"
export BAILEYS_LOG_LEVEL="${BAILEYS_LOG_LEVEL:-$(read_env_value BAILEYS_LOG_LEVEL)}"
export BAILEYS_LOG_LEVEL="${BAILEYS_LOG_LEVEL:-info}"
export BAILEYS_AUTH_DIR="${BAILEYS_AUTH_DIR:-$(read_env_value BAILEYS_AUTH_DIR)}"
export BAILEYS_AUTH_DIR="${BAILEYS_AUTH_DIR:-$data_dir/baileys_auth}"
case "$BAILEYS_AUTH_DIR" in
    /*) ;;
    *) export BAILEYS_AUTH_DIR="$repo_root/$BAILEYS_AUTH_DIR" ;;
esac

mkdir -p "$BAILEYS_AUTH_DIR"

if [ ! -d "$gateway_root" ]; then
    echo "Baileys gateway directory not found at: $gateway_root" >&2
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "npm not found. Install Node.js/npm before starting the Baileys gateway." >&2
    exit 1
fi

if [ ! -d "$gateway_root/node_modules" ]; then
    echo "Gateway dependencies not found at $gateway_root/node_modules." >&2
    echo "Run: cd $gateway_root && npm install" >&2
    exit 1
fi

cd "$gateway_root"
if [ ! -d "$gateway_root/dist" ]; then
    npm run build
fi

printf 'pid=%s started_at=%s port=%s auth_dir=%s\n' "$$" "$(date -Is)" "$BAILEYS_PORT" "$BAILEYS_AUTH_DIR" > "$pid_file"
printf '[%s] Starting Baileys gateway on %s:%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$BAILEYS_HOST" "$BAILEYS_PORT"

child_pid=""
cleanup() {
    if [ -n "$child_pid" ] && kill -0 "$child_pid" >/dev/null 2>&1; then
        kill "$child_pid" >/dev/null 2>&1 || true
    fi
    rm -f "$pid_file"
}
trap cleanup INT TERM

npm start &
child_pid=$!
wait "$child_pid"
exit_code=$?
child_pid=""
rm -f "$pid_file"
exit "$exit_code"
