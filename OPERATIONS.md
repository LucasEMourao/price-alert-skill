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

Optional boot recovery hook:

- `boot_recover.sh` can be added as `@reboot` to re-enable the sender and run one recovery scan only when the instance starts inside the active window.
- The boot script checks scan health by looking for a live `scan_deals.py` process or a recent successful scan log before deciding whether to launch another scan.
- The recovery scan is skipped outside the `08:00-23:30` Sao Paulo window.

Important operational rule: cron only runs while the Ubuntu WSL instance is actually alive. If the distro is down, missed runs are not replayed automatically.

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

## Baileys migration operating plan

The WhatsApp sender migration is intentionally staged. The current Playwright sender remains the rollback path while the new Baileys gateway is introduced.

Target environment variables:

- `WHATSAPP_SENDER_BACKEND=playwright|baileys`
- `WHATSAPP_SEND_INTERVAL_SECONDS=<seconds>`; empty means `30` for Baileys and `0` for Playwright
- `WHATSAPP_GROUP_JID=<group-id>@g.us`
- `BAILEYS_PORT=3015`
- `BAILEYS_AUTH_DIR=.agents/skills/price-alert-skill/data/baileys_auth`
- `BAILEYS_LOG_LEVEL=info`

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
