#!/usr/bin/env bash
set -euo pipefail

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$skill_root/../../.." && pwd)"
python_bin="${PYTHON:-python3}"
venv_dir="$skill_root/.venv"
venv_python="$venv_dir/bin/python"

as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
        return 0
    fi

    if command -v sudo >/dev/null 2>&1; then
        sudo -n "$@"
        return 0
    fi

    echo "Root privileges are required to install ImageMagick." >&2
    exit 1
}

ensure_imagemagick() {
    if command -v magick >/dev/null 2>&1 || command -v convert >/dev/null 2>&1; then
        return 0
    fi

    if ! command -v apt-get >/dev/null 2>&1; then
        echo "ImageMagick not found and apt-get is unavailable." >&2
        exit 1
    fi

    echo "Installing ImageMagick..."
    as_root apt-get update
    as_root apt-get install -y imagemagick
}

cd "$skill_root"

if ! command -v "$python_bin" >/dev/null 2>&1; then
    echo "Python not found: $python_bin" >&2
    exit 1
fi

ensure_imagemagick

if [ ! -x "$venv_python" ] || ! "$venv_python" -m pip --version >/dev/null 2>&1; then
    rm -rf "$venv_dir"
    venv_error_log="$(mktemp)"
    if ! "$python_bin" -m venv "$venv_dir" 2>"$venv_error_log"; then
        echo "python venv ensurepip is unavailable; bootstrapping pip with the global pip."
        "$python_bin" -m venv --without-pip "$venv_dir"
        "$python_bin" -m pip --python "$venv_python" install --upgrade pip
    fi
    rm -f "$venv_error_log"
fi

"$venv_python" -m pip install --upgrade pip
"$venv_python" -m pip install -e "$repo_root"
"$venv_python" -m playwright install chromium

mkdir -p "$skill_root/data/messages" "$skill_root/logs"
echo "Ubuntu/WSL setup complete. Python: $venv_python"
