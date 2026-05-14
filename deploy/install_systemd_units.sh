#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
skill_root="${PRICE_ALERT_SKILL_ROOT:-$repo_root/.agents/skills/price-alert-skill}"
templates_dir="$script_dir/systemd"
timezone="${PRICE_ALERT_TIMEZONE:-America/Sao_Paulo}"
env_file="${PRICE_ALERT_ENV_FILE:-$skill_root/.env}"
service_user="${PRICE_ALERT_SERVICE_USER:-${SUDO_USER:-${USER:-$(id -un)}}}"
install_dir="${SYSTEMD_UNIT_DIR:-/etc/systemd/system}"
output_dir=""
render_only=0

usage() {
    cat <<'EOF'
Usage: install_systemd_units.sh [--render-only] [--output-dir DIR] [--install-dir DIR]

Options:
  --render-only       Render unit files without installing them.
  --output-dir DIR    Directory that receives the rendered unit files.
  --install-dir DIR   Override the systemd unit install directory.
EOF
}

as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
        return 0
    fi

    if command -v sudo >/dev/null 2>&1; then
        sudo -n "$@"
        return 0
    fi

    echo "Root privileges are required to install systemd unit files." >&2
    exit 1
}

resolve_service_group() {
    local detected_group=""

    if [ -n "${PRICE_ALERT_SERVICE_GROUP:-}" ]; then
        printf '%s' "$PRICE_ALERT_SERVICE_GROUP"
        return 0
    fi

    if detected_group="$(id -gn "$service_user" 2>/dev/null)"; then
        printf '%s' "$detected_group"
        return 0
    fi

    if detected_group="$(id -gn 2>/dev/null)"; then
        printf '%s' "$detected_group"
        return 0
    fi

    printf '%s' "$service_user"
}

render_unit() {
    local template_path="$1"
    local destination_path="$2"
    local escaped_service_user
    local escaped_service_group
    local escaped_repo_root
    local escaped_skill_root
    local escaped_env_file
    local escaped_timezone

    escape_sed_replacement() {
        printf '%s' "$1" | sed -e 's/[&|\\]/\\&/g'
    }

    escaped_service_user="$(escape_sed_replacement "$service_user")"
    escaped_service_group="$(escape_sed_replacement "$service_group")"
    escaped_repo_root="$(escape_sed_replacement "$repo_root")"
    escaped_skill_root="$(escape_sed_replacement "$skill_root")"
    escaped_env_file="$(escape_sed_replacement "$env_file")"
    escaped_timezone="$(escape_sed_replacement "$timezone")"

    sed \
        -e "s|__SERVICE_USER__|$escaped_service_user|g" \
        -e "s|__SERVICE_GROUP__|$escaped_service_group|g" \
        -e "s|__REPO_ROOT__|$escaped_repo_root|g" \
        -e "s|__SKILL_ROOT__|$escaped_skill_root|g" \
        -e "s|__ENV_FILE__|$escaped_env_file|g" \
        -e "s|__TIMEZONE__|$escaped_timezone|g" \
        "$template_path" > "$destination_path"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --render-only)
            render_only=1
            shift
            ;;
        --output-dir)
            output_dir="${2:-}"
            if [ -z "$output_dir" ]; then
                echo "--output-dir requires a path." >&2
                exit 1
            fi
            shift 2
            ;;
        --install-dir)
            install_dir="${2:-}"
            if [ -z "$install_dir" ]; then
                echo "--install-dir requires a path." >&2
                exit 1
            fi
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [ ! -d "$templates_dir" ]; then
    echo "Systemd template directory not found: $templates_dir" >&2
    exit 1
fi

service_group="$(resolve_service_group)"

cleanup_dir=""
if [ -z "$output_dir" ]; then
    output_dir="$(mktemp -d)"
    cleanup_dir="$output_dir"
fi

mkdir -p "$output_dir"

rendered_count=0
for template_path in "$templates_dir"/*.template; do
    unit_name="$(basename "${template_path%.template}")"
    destination_path="$output_dir/$unit_name"
    render_unit "$template_path" "$destination_path"
    rendered_count=$((rendered_count + 1))
done

if grep -R -n '__[A-Z0-9_]\+__' "$output_dir" >/dev/null 2>&1; then
    echo "Found unresolved placeholders in rendered systemd units." >&2
    grep -R -n '__[A-Z0-9_]\+__' "$output_dir" >&2 || true
    exit 1
fi

if [ "$render_only" -eq 1 ]; then
    echo "Rendered $rendered_count unit file(s) into: $output_dir"
    exit 0
fi

for rendered_path in "$output_dir"/*; do
    unit_name="$(basename "$rendered_path")"
    as_root install -D -m 0644 "$rendered_path" "$install_dir/$unit_name"
done

as_root systemctl daemon-reload

echo "Installed $rendered_count unit file(s) into: $install_dir"

if [ -n "$cleanup_dir" ]; then
    rm -rf "$cleanup_dir"
fi
