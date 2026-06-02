#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
skill_root="$repo_root/.agents/skills/price-alert-skill"
gateway_root="$repo_root/whatsapp_gateway"
node_bin="${BAILEYS_NODE_BIN:-/home/leocanela/.local/node/bin/node}"
npm_bin="${BAILEYS_NPM_BIN:-/home/leocanela/.local/node/bin/npm}"

cd "$repo_root"

echo "==> Updating executable permissions"
chmod +x deploy/*.sh "$skill_root"/*.sh

echo "==> Reapplying production schedule: 07:00-23:00 Sao Paulo (10:00-02:00 UTC)"
python3 - <<'PY'
from pathlib import Path

Path('deploy/systemd/price-alert-runtime-start.timer.template').write_text('''[Unit]
Description=Start the Price Alert runtime window at 10:00 UTC / 07:00 Sao Paulo

[Timer]
OnCalendar=*-*-* 10:00:00
Persistent=false
Unit=price-alert-runtime-start.service

[Install]
WantedBy=timers.target
''')

Path('deploy/systemd/price-alert-runtime-stop.timer.template').write_text('''[Unit]
Description=Stop the Price Alert runtime window at 02:00 UTC / 23:00 Sao Paulo

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=false
Unit=price-alert-runtime-stop.service

[Install]
WantedBy=timers.target
''')

Path('deploy/systemd/price-alert-scan.timer.template').write_text('''[Unit]
Description=Price Alert marketplace scan schedule

[Timer]
OnCalendar=*-*-* 10..23:00/15:00
OnCalendar=*-*-* 00..01:00/15:00
Persistent=false
Unit=price-alert-scan.service

[Install]
WantedBy=timers.target
''')

deploy_path = Path('deploy/deploy_server.sh')
deploy_text = deploy_path.read_text()
deploy_text = deploy_text.replace('[ "$current_hm" -ge 800 ] && [ "$current_hm" -lt 2330 ]', '[ "$current_hm" -ge 1000 ] || [ "$current_hm" -lt 200 ]')
deploy_path.write_text(deploy_text)

boot_path = Path('.agents/skills/price-alert-skill/boot_recover.sh')
if boot_path.exists():
    boot_text = boot_path.read_text()
    boot_text = boot_text.replace('window_start="${BOOT_RECOVERY_WINDOW_START:-0800}"', 'window_start="${BOOT_RECOVERY_WINDOW_START:-1000}"')
    boot_text = boot_text.replace('window_end="${BOOT_RECOVERY_WINDOW_END:-2330}"', 'window_end="${BOOT_RECOVERY_WINDOW_END:-0200}"')
    old_func = '''within_window() {
    local hhmm
    hhmm="$(current_hhmm)"
    [ "$hhmm" -ge "$window_start" ] && [ "$hhmm" -le "$window_end" ]
}
'''
    new_func = '''within_window() {
    local hhmm
    hhmm="$(current_hhmm)"
    if [ "$window_start" -le "$window_end" ]; then
        [ "$hhmm" -ge "$window_start" ] && [ "$hhmm" -lt "$window_end" ]
        return $?
    fi
    [ "$hhmm" -ge "$window_start" ] || [ "$hhmm" -lt "$window_end" ]
}
'''
    if old_func in boot_text:
        boot_text = boot_text.replace(old_func, new_func)
    boot_path.write_text(boot_text)
PY

echo "==> Refreshing Python runtime"
bash "$skill_root/setup_ubuntu.sh"

echo "==> Refreshing Baileys gateway runtime"
if [ ! -x "$npm_bin" ]; then
    echo "Expected npm not found at $npm_bin" >&2
    echo "Set BAILEYS_NPM_BIN or install Node 20+ before running this script." >&2
    exit 1
fi
cd "$gateway_root"
"$npm_bin" ci
"$npm_bin" run build

cd "$repo_root"
echo "==> Verifying systemd units"
"$repo_root/deploy/verify_systemd_units.sh"

if sudo -n true 2>/dev/null; then
    echo "==> Installing systemd units and restarting timers/services"
    sudo "$repo_root/deploy/install_systemd_units.sh"
    sudo systemctl restart price-alert-runtime-start.timer price-alert-runtime-stop.timer price-alert-scan.timer
    sudo systemctl restart price-alert-baileys.service price-alert-sender.service
    echo "==> Current timers"
    systemctl list-timers --all | grep price-alert || true
else
    cat <<MSG
==> Sudo requires an interactive password. Run these commands now:

cd $repo_root
sudo deploy/install_systemd_units.sh
sudo systemctl restart price-alert-runtime-start.timer price-alert-runtime-stop.timer price-alert-scan.timer
sudo systemctl restart price-alert-baileys.service price-alert-sender.service
systemctl list-timers --all | grep price-alert

MSG
fi

echo "==> Update preparation complete"
