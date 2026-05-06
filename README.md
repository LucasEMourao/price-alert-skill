# price-alert-skill

Python package and skill wrappers for marketplace deal scanning and WhatsApp delivery.

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

## Ubuntu/WSL

From the skill directory:

```bash
cd .agents/skills/price-alert-skill
./setup_ubuntu.sh
./run_scan.sh --marketplaces amazon_br --max-results 1 --min-discount 999
./ensure_sender.sh
./stop_sender.sh
```

Use `./run_sender.sh --headed --group "$WHATSAPP_GROUP"` when you need the first visible WhatsApp Web login in WSLg. The sender opens WhatsApp only when there is a sendable deal in the queue, so run a normal scan first if the queue is empty.

The Linux scripts mirror the Windows `.ps1` wrappers and write logs to `.agents/skills/price-alert-skill/logs/`. Use `ensure_sender.sh` from cron to restart the sender if WSL, networking or the browser process drops during the active window.
