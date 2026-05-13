# price-alert-skill

Python package and skill wrappers for marketplace deal scanning and WhatsApp delivery.

See [OPERATIONS.md](OPERATIONS.md) for the current WSL/cron/runtime operating notes and known host-level risks.

## Architecture

- `price_alert_skill/`
  Repo-level Python package with the real application code.
- `.agents/skills/price-alert-skill/scripts/`
  Thin compatibility wrappers used by the skill and Windows scheduler.
- `.agents/skills/price-alert-skill/data/`
  Runtime state such as queue, sent history, affiliate cache and scan snapshots.

The intent is to keep business logic, application flow and adapters in a normal Python package,
while the skill only exposes thin entrypoint scripts.


## Runtime and OS adapters

The project keeps one shared codebase for Windows and Ubuntu/WSL. Host-specific behavior is selected at runtime with `PRICE_ALERT_RUNTIME=auto` by default.

- Windows keeps the default WhatsApp profile under `%LOCALAPPDATA%\price-alert-skill\whatsapp_chrome_profile`.
- Linux/WSL reuses the legacy `data/whatsapp_session/chrome_profile` when it exists, preserving existing sessions; otherwise it creates `data/whatsapp_session/linux_chrome_profile`.
- `WHATSAPP_CHROME_PATH` and `WHATSAPP_PROFILE_DIR` always override auto-detection.
- Queue entries are tagged by `product_profile`, so `tech` and `beauty` can coexist in the same shared queue/state files without mixing sends.

## Ubuntu/WSL

From the skill directory:

```bash
cd .agents/skills/price-alert-skill
./setup_ubuntu.sh
./run_scan.sh --marketplaces amazon_br --max-results 1 --min-discount 999
./ensure_baileys_gateway.sh   # only when piloting WHATSAPP_SENDER_BACKEND=baileys
./ensure_sender.sh
./stop_sender.sh
./stop_baileys_gateway.sh
```

Use `./run_sender.sh --headed --group "$WHATSAPP_GROUP"` when you need the first visible WhatsApp Web login in WSLg. The sender opens WhatsApp only when there is a sendable deal in the queue, so run a normal scan first if the queue is empty.

The Linux scripts mirror the Windows `.ps1` wrappers and write logs to `.agents/skills/price-alert-skill/logs/`.

- Flow logs now render timestamps in `America/Sao_Paulo`.
- Use `ensure_sender.sh` from cron to restart the sender if WSL, networking or the browser process drops during the active window.
- The sender now re-opens the target WhatsApp group when Web leaves the active chat view before a retry.
- `boot_recover.sh` can be used from `@reboot` to relaunch the sender and run a recovery scan only inside the active window, while checking whether the scan is already healthy.
- `run_scan.sh` now skips overlapping triggers and rotates heavy profile categories in smaller batches before launching another browser-heavy scan.

Example `@reboot` entry:

```cron
@reboot cd /home/lukinha/projetos/agentSkills/price-alert-skill/.agents/skills/price-alert-skill && ./boot_recover.sh
```

## Profiles

The codebase currently supports at least these scan/send profiles:

- `tech`: preserved for future reuse and alternate groups.
- `beauty`: active Linux/WSL profile for the beauty/feminine product flow.

Useful environment variables:

- `PRICE_ALERT_SCAN_PROFILE`
- `PRICE_ALERT_SCAN_CATEGORIES`
- `PRICE_ALERT_SCAN_CATEGORY_BATCH_SIZE`
- `PRICE_ALERT_SEND_PROFILE`
- `WHATSAPP_GROUP`

When `PRICE_ALERT_SCAN_PROFILE=beauty` and `PRICE_ALERT_SCAN_CATEGORIES` is empty, `run_scan.sh` rotates two categories per run by default. Set `PRICE_ALERT_SCAN_CATEGORY_BATCH_SIZE` to override the batch size, or set `PRICE_ALERT_SCAN_CATEGORIES` to pin a fixed subset.

## Flow diagnostic

Use this when you want to share current resource usage with someone who is choosing a server:

```bash
cd .agents/skills/price-alert-skill
./diag_flow.sh
```

The report includes:

- repo version and branch
- WSL RAM and swap summary
- current GPU usage when `nvidia-smi` is available
- CPU and RSS for the sender, scan and browser trees
- active scan profile, explicit scan categories and effective scan batching mode

Send the generated file from `logs/diagnostics/flow-*.txt` together with the server specs.

## Baileys WhatsApp sender migration

A dedicated migration is being developed on `feat/baileys-whatsapp-sender` to replace the WhatsApp sender browser session with a Baileys-based gateway while keeping Playwright as the fallback backend.

Planned sender backends:

- `WHATSAPP_SENDER_BACKEND=playwright`: current default, opens WhatsApp Web through Playwright/Chromium.
- `WHATSAPP_SENDER_BACKEND=baileys`: experimental backend, sends through a local Baileys gateway without Chromium.

The Baileys flow will require `WHATSAPP_GROUP_JID`, because the gateway sends to a stable WhatsApp JID instead of searching the visible group name in the web UI. The group JID will be discovered through the gateway group-list endpoint after the first login.

Operational guardrails:

- keep exactly one sender consuming the queue;
- when using Baileys, start `./ensure_baileys_gateway.sh` before `./ensure_sender.sh`;
- stop in reverse order: `./stop_sender.sh`, then `./stop_baileys_gateway.sh`;
- keep a pause between consecutive sends; `WHATSAPP_SEND_INTERVAL_SECONDS` defaults to 30 seconds for Baileys and 0 for Playwright;
- keep Playwright installed and documented as rollback until Baileys passes a 24h soak test;
- treat Baileys as a non-official WhatsApp Web/Linked Devices integration, with risk of session loss or protocol breakage;
- validate every sprint with tests or targeted manual checks before committing.

Useful Baileys gateway commands from `.agents/skills/price-alert-skill`:

```bash
./run_baileys_gateway.sh      # foreground, useful for first QR login
./ensure_baileys_gateway.sh   # background/supervised start
./stop_baileys_gateway.sh
./diag_flow.sh
```
