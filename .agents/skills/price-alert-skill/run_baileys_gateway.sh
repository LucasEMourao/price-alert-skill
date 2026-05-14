#!/usr/bin/env bash
set -euo pipefail

export TZ="${TZ:-America/Sao_Paulo}"

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$skill_root/../../.." && pwd)"
data_dir="$skill_root/data"
pid_file="$data_dir/baileys_gateway.pid"

read_env_value() {
    local key="$1"
    local env_file="$skill_root/.env"

    [ -f "$env_file" ] || return 0
    sed -n "s/^${key}=//p" "$env_file" | tail -n 1 | sed "s/^\"//; s/\"$//; s/^'//; s/'$//"
}

gateway_root="${BAILEYS_GATEWAY_ROOT:-$(read_env_value BAILEYS_GATEWAY_ROOT)}"
gateway_root="${gateway_root:-$repo_root/whatsapp_gateway}"
case "$gateway_root" in
    /*) ;;
    *) gateway_root="$repo_root/$gateway_root" ;;
esac

resolve_tool_bin() {
    local tool_name="$1"
    local explicit_path="$2"
    local candidate=""
    local -a candidates=()

    if [ -n "$explicit_path" ]; then
        if [ -x "$explicit_path" ]; then
            printf '%s\n' "$explicit_path"
            return 0
        fi
        echo "Configured ${tool_name} path is not executable: $explicit_path" >&2
        return 1
    fi

    local resolved_path
    resolved_path="$(command -v "$tool_name" 2>/dev/null || true)"
    if [ -n "$resolved_path" ]; then
        printf '%s\n' "$resolved_path"
        return 0
    fi

    candidates=(
        "/usr/local/bin/$tool_name"
        "/usr/bin/$tool_name"
        "/bin/$tool_name"
    )

    if [ -n "${HOME:-}" ]; then
        shopt -s nullglob
        candidates+=("$HOME"/.nvm/versions/node/*/bin/"$tool_name")
        candidates+=("$HOME"/.local/share/nvm/*/bin/"$tool_name")
        shopt -u nullglob
    fi

    for candidate in "${candidates[@]}"; do
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done

    return 1
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

npm_bin="$(resolve_tool_bin npm "${BAILEYS_NPM_BIN:-$(read_env_value BAILEYS_NPM_BIN)}" || true)"
node_bin="$(resolve_tool_bin node "${BAILEYS_NODE_BIN:-$(read_env_value BAILEYS_NODE_BIN)}" || true)"

if [ -z "$npm_bin" ] || [ -z "$node_bin" ]; then
    echo "node/npm not found. Set BAILEYS_NODE_BIN and BAILEYS_NPM_BIN or install Node.js/npm in a cron-visible path." >&2
    exit 1
fi

export PATH="$(dirname "$node_bin"):$(dirname "$npm_bin"):$PATH"

if [ ! -d "$gateway_root/node_modules" ]; then
    echo "Gateway dependencies not found at $gateway_root/node_modules." >&2
    echo "Run: cd $gateway_root && $npm_bin install" >&2
    exit 1
fi

cd "$gateway_root"
if [ ! -d "$gateway_root/dist" ]; then
    "$npm_bin" run build
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

"$npm_bin" start &
child_pid=$!
wait "$child_pid"
exit_code=$?
child_pid=""
rm -f "$pid_file"
exit "$exit_code"
