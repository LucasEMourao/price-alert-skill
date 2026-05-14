# Operations

This file is the quickest handoff for another agent or developer who needs to understand the current runtime behavior of `price-alert-skill` on Windows plus WSL/Ubuntu.

## Current layout

- `price_alert_skill/`
  Core application package, runtime detection, clean-architecture modules, adapters and entrypoints.
- `.agents/skills/price-alert-skill/scripts/`
  Thin compatibility wrappers used by the skill and the Linux cron jobs.
- `.agents/skills/price-alert-skill/data/`
  Runtime state, WhatsApp sessions, queue snapshots, sent history, affiliate cache and debug artifacts.
- `.agents/skills/price-alert-skill/logs/`
  Sender, supervisor, scan and diagnostics logs.

## Current profiles

- `tech`
  Preserved for future reuse and possible alternate WhatsApp routing.
- `beauty`
  Current scan/send profile used in Ubuntu/WSL.

Queue entries carry `product_profile`, which lets multiple product families coexist in the same queue/state files without mixing actual sends.

The current scan load guardrails are:

- explicit `PRICE_ALERT_SCAN_CATEGORIES` always wins and scans a fixed subset
- otherwise `beauty` rotates two categories per run by default
- other profiles stay full-profile unless `PRICE_ALERT_SCAN_CATEGORY_BATCH_SIZE` is set
- overlapping scan triggers are ignored while an earlier scan is still running

## Linux/WSL wrappers

Main scripts under `.agents/skills/price-alert-skill/`:

- `setup_ubuntu.sh`
- `run_scan.sh`
- `run_sender.sh`
- `ensure_sender.sh`
- `stop_sender.sh`
- `run_baileys_gateway.sh`
- `ensure_baileys_gateway.sh`
- `stop_baileys_gateway.sh`
- `boot_recover.sh`
- `diag_flow.sh`

The wrappers export `TZ=America/Sao_Paulo` so shell-level logs match Brazil time.

## Log time

User-facing flow logs are expected to be in `America/Sao_Paulo`.

Examples:

- `logs/scan-YYYY-MM-DD.log`
- `logs/sender-YYYY-MM-DD.log`
- `logs/sender-supervisor-YYYY-MM-DD.log`

Python log formatting is centralized in `price_alert_skill/log_time.py`.

## Cron shape

The current Ubuntu crontab pattern is:

- `ensure_sender.sh` every 5 minutes during the active window
- `run_scan.sh` every 15 minutes from 08:00 through 22:45
- final scans at 23:00 and 23:15
- `stop_sender.sh` at 23:30
- `run_scan.sh` now skips itself when a previous scan is still alive, preventing overlapping Chromium trees
- when `PRICE_ALERT_SCAN_PROFILE=beauty` and `PRICE_ALERT_SCAN_CATEGORIES` is empty, `run_scan.sh` rotates two categories per run by default; use `PRICE_ALERT_SCAN_CATEGORY_BATCH_SIZE` to override

Optional boot recovery hook:

- `boot_recover.sh` can be added as `@reboot` to re-enable the sender and run one recovery scan only when the instance starts inside the active window.
- The boot script checks scan health by looking for a live `scan_deals.py` process or a recent successful scan log before deciding whether to launch another scan.
- The recovery scan is skipped outside the `08:00-23:30` Sao Paulo window.

Important operational rule: cron only runs while the Ubuntu WSL instance is actually alive. If the distro is down, missed runs are not replayed automatically.

## Server/systemd target

The repository now carries the first production server deployment assets under `deploy/`:

- `deploy/install_systemd_units.sh`
- `deploy/verify_systemd_units.sh`
- `deploy/deploy_server.sh`
- `deploy/systemd/*.template`

Tracked unit model:

- `price-alert-runtime.target`
- `price-alert-baileys.service`
- `price-alert-sender.service`
- `price-alert-runtime-start.timer`
- `price-alert-runtime-stop.timer`
- `price-alert-scan.service`
- `price-alert-scan.timer`

Intended server behavior:

- runtime window opens at `08:00` Sao Paulo time
- sender + Baileys stop at `23:30`
- scans run every 15 minutes from `08:00` through `22:45`
- final scans run at `23:00` and `23:15`
- scan overlap protection still stays inside `run_scan.sh`

Server expectations:

- Ubuntu or another Linux distribution with `systemd`
- host timezone configured to `America/Sao_Paulo`
- repo cloned to a stable path that will become `DEPLOY_PATH`
- production `.env` stored only on the server
- deploy user can run `sudo -n` for `systemctl` and unit installation

Useful commands on the server:

```bash
bash deploy/verify_systemd_units.sh
sudo systemctl daemon-reload
sudo systemctl status price-alert-runtime.target
sudo systemctl list-timers --all | grep price-alert
sudo journalctl -u price-alert-baileys.service -n 100 --no-pager
sudo journalctl -u price-alert-sender.service -n 100 --no-pager
sudo journalctl -u price-alert-scan.service -n 100 --no-pager
```

## GitHub Actions deploy flow

The repo now uses two workflows:

- `CI`
  Runs on `push` and `pull_request`, executing Python tests, compile checks, shell syntax checks, rendered `systemd` verification, and the Baileys gateway build.
- `Deploy`
  Runs after `CI` succeeds for a `push` to `main`, connects by SSH, checks out the exact tested SHA on the server, then runs `deploy/deploy_server.sh`.

Required GitHub configuration:

- repository variable:
  - `DEPLOY_PATH`
- repository secrets:
  - `DEPLOY_HOST`
  - `DEPLOY_PORT`
  - `DEPLOY_USER`
  - `DEPLOY_SSH_KEY`
  - optional `DEPLOY_HOST_FINGERPRINT`

Rollback model:

- revert the offending commit on `main` or push a corrective commit
- let CI pass
- allow the next Deploy workflow run to apply the corrected SHA

## WhatsApp notes

- Windows and Linux can keep separate Chromium profile directories.
- The sender now retries by re-opening the target group if WhatsApp Web leaves the active chat view before a send retry.
- Debug artifacts for WhatsApp failures are stored under `.agents/skills/price-alert-skill/data/debug/`.

## Known host-level risk

Observed on `2026-05-10`:

- the Ubuntu instance received a full `systemd` shutdown around `22:20 -03`
- `cron.service` was stopped inside Ubuntu
- the active `22:15` scan was cut off mid-run
- later Hyper-V vSwitch detach/delete events appeared on the Windows host

Current interpretation:

- this was not a scan-code failure
- this was not a normal `23:30` sender stop
- the Ubuntu WSL instance itself was terminated by the host side before the end of the nightly window

What we did not find:

- no normal scan exception proving an application crash
- no host sleep event confirmed from the accessible event logs
- no matching scheduled task found from the accessible Windows task list query

Relevant host config at the time of investigation:

- WSL version `2.6.3.0`
- `.wslconfig` enabled:
  - `networkingMode=mirrored`
  - `dnsTunneling=true`

## Next mitigation candidates

If this host-level stop happens again, the next engineering options to consider are:

1. Add a catch-up scan on WSL boot or `@reboot`.
2. Move the schedule from cron-only assumptions toward `systemd` timers and recovery hooks.
3. Test whether `networkingMode=mirrored` is contributing to the instance teardown; compare with the default NAT mode on a controlled run.
4. Run the flow on a VPS or dedicated always-on Linux host if the local PC remains unreliable for overnight automation.

## Debug checklist

When the flow appears stuck:

1. Check `logs/sender-YYYY-MM-DD.log`.
2. Check `logs/scan-YYYY-MM-DD.log`.
3. Check `logs/sender-supervisor-YYYY-MM-DD.log`.
4. Verify `crontab -l` inside Ubuntu.
5. Verify the Ubuntu instance uptime and `systemctl status cron`.
6. Run `./diag_flow.sh` for RAM/CPU/GPU/process snapshots.
7. Confirm the reported scan profile, categories and batch mode match the intended pilot settings.

## Baileys migration operating plan

The WhatsApp sender migration is intentionally staged. The current Playwright sender remains the rollback path while the new Baileys gateway is introduced.

Target environment variables:

- `WHATSAPP_SENDER_BACKEND=playwright|baileys`
- `WHATSAPP_SEND_INTERVAL_SECONDS=<seconds>`; empty means `30` for Baileys and `0` for Playwright
- `WHATSAPP_GROUP_JID=<group-id>@g.us`
- `BAILEYS_PORT=3015`
- `BAILEYS_AUTH_DIR=.agents/skills/price-alert-skill/data/baileys_auth`
- `BAILEYS_LOG_LEVEL=info`
- `BAILEYS_NODE_BIN=/absolute/path/to/node` when cron cannot resolve `node`
- `BAILEYS_NPM_BIN=/absolute/path/to/npm` when cron cannot resolve `npm`

Expected operating order after the gateway exists:

1. Start the Baileys gateway with `./run_baileys_gateway.sh` for the first QR/pairing login, or `./ensure_baileys_gateway.sh` for supervised background operation.
2. Use the gateway group-list endpoint to find `WHATSAPP_GROUP_JID`.
3. Set `WHATSAPP_SENDER_BACKEND=baileys` only for the pilot window.
4. Start or restart the Python sender with `./ensure_sender.sh`.
5. Keep the Python sender serial; it still owns queue selection, sent history and cooldown.
6. Run `diag_flow.sh` before and after the pilot to compare the old Chromium sender against the gateway.

Stop order:

1. `./stop_sender.sh`
2. `./stop_baileys_gateway.sh`

Rollback is changing `WHATSAPP_SENDER_BACKEND` back to `playwright` and restarting the sender. No scan logic should depend on the Baileys gateway.

The Baileys gateway scripts use:

- PID file: `data/baileys_gateway.pid`
- Auth/session directory: `data/baileys_auth` by default
- Supervisor log: `logs/baileys-supervisor-YYYY-MM-DD.log`

If the gateway works in an interactive shell but not from cron, check the supervisor log first. A common cause is a reduced cron `PATH`; use `command -v node` and `command -v npm` from the target Linux account, then set `BAILEYS_NODE_BIN` and `BAILEYS_NPM_BIN` in `.env` if needed.

When the Baileys backend is down or disconnected, the Python sender now keeps the selected offer pending and reports it as deferred. This avoids burning queue retries during an infrastructure outage. In that situation, inspect both `logs/sender-YYYY-MM-DD.log` and `logs/baileys-supervisor-YYYY-MM-DD.log`.

Example `systemd` shape for a Linux server:

```ini
[Unit]
Description=Price Alert Baileys Gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/lukinha/projetos/agentSkills/price-alert-skill/.agents/skills/price-alert-skill
ExecStart=/home/lukinha/projetos/agentSkills/price-alert-skill/.agents/skills/price-alert-skill/run_baileys_gateway.sh
Restart=always
RestartSec=10
Environment=TZ=America/Sao_Paulo

[Install]
WantedBy=multi-user.target
```

Risks to monitor:

- Baileys is not an official Meta/WhatsApp Business API integration.
- WhatsApp Web protocol changes can break the gateway.
- Linked-device sessions can be invalidated and require a fresh login.
- Sending must remain serial and moderate to avoid duplicate or spam-like behavior.
