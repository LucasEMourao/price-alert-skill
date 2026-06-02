#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
render_dir="$(mktemp -d)"
trap 'rm -rf "$render_dir"' EXIT

"$script_dir/install_systemd_units.sh" --render-only --output-dir "$render_dir" >/dev/null

if command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify "$render_dir"/*
fi

rendered_count="$(find "$render_dir" -maxdepth 1 -type f | wc -l | tr -d '[:space:]')"
echo "Verified $rendered_count rendered unit file(s)."
