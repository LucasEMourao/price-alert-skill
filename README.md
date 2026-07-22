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
- `PRICE_ALERT_ALLOWED_BEAUTY_BRANDS`: optional comma- or semicolon-separated override for the beauty brand allowlist; leave empty to use the versioned full list.
- `WHATSAPP_GROUP`
- `PRICE_ALERT_IMAGEMAGICK_BIN`: optional path to the ImageMagick `magick` or `convert` binary used to normalize Baileys image sends.

Baileys image sends are normalized through ImageMagick before delivery: product images are converted to centered `800x800` JPEGs on a white background to avoid stretched WhatsApp previews. To generate local visual stubs instead of sending to WhatsApp, run:

```bash
PRICE_ALERT_WRITE_IMAGE_STUBS=1 python -m pytest tests/test_baileys_image_stub.py
```

The generated images and manifest are written to `.pytest-tmp/whatsapp-image-stub/`.

When `PRICE_ALERT_SCAN_PROFILE=beauty` and `PRICE_ALERT_SCAN_CATEGORIES` is empty, `run_scan.sh` rotates two categories per run by default. Set `PRICE_ALERT_SCAN_CATEGORY_BATCH_SIZE` to override the batch size, or set `PRICE_ALERT_SCAN_CATEGORIES` to pin a fixed subset.

The `beauty` profile also applies a versioned brand allowlist before affiliate-link generation and queue insertion. Matching is accent-insensitive and alias-based, so marketplace titles such as `loreal paris`, `boticario`, or `la roche posay` can match the canonical brands. Set `PRICE_ALERT_ALLOWED_BEAUTY_BRANDS` only when you need a temporary pilot subset.

## Shopee Affiliate Open API (controlled rollout)

Shopee V2 is an opt-in provider. The initial integration uses only the official
`productOfferV2` operation and keeps `productLink` (canonical identity) separate
from `offerLink` (affiliate outbound URL). It does not use feed ingestion or
short-link generation.

Enable it only in a controlled environment with dedicated non-production
credentials:

```env
SHOPEE_ENABLED=1
SHOPEE_APP_ID=<non-production-app-id>
SHOPEE_APP_SECRET=<non-production-app-secret>
PRICE_ALERT_MARKETPLACES=shopee_br
SHOPEE_MAX_PAGES_PER_QUERY=1
```

Configuration precedence is deliberate:

1. `SHOPEE_ENABLED=0` is the hard provider-off switch and takes precedence over
   every marketplace list.
2. `PRICE_ALERT_MARKETPLACES` controls which providers are scanned; it must
   contain `shopee_br` for Shopee to run.
3. `PRICE_ALERT_SEND_MARKETPLACES`, when non-empty, is an independent sender
   allowlist. An empty value preserves the existing behavior for queued deals.

The normal legacy default remains `amazon_br,mercadolivre_br`. Credentials are
read only while Shopee is enabled and must exist only in the server `.env`; do
not place them in fixtures, queue files, message JSON, or logs.

### Shopee observability

A Shopee scan emits a structured summary in the scan log:

```text
Shopee summary: requests=1, pages=1, products=1, deals=0, errors=0
```

The counters mean:

- `requests`: provider requests reported by the scanner; when absent, one
  request is counted per recorded page;
- `pages`: pages received and recorded from `pageInfo`;
- `products`: normalized products returned by the provider adapter;
- `deals`: products that passed the source-aware percentage and lane rules;
- `errors`: structured provider/normalization errors returned by the adapter.

Shopee API and GraphQL failures are redacted before they reach operational
logs. Authorization values, signatures, App Secrets, and credential-shaped
values must never be printed or persisted. HTTP 200 responses containing a
GraphQL `errors` array are failures, not successful provider results.

### Controlled canary procedure

Repository tests and deployment validation use mocked responses and never call
Shopee. A live canary requires explicit approval, a dedicated non-production
credential, and one bounded page:

```bash
cd .agents/skills/price-alert-skill
SHOPEE_ENABLED=1 SHOPEE_MAX_PAGES_PER_QUERY=1 \\
python3 scripts/scan_deals.py \\
  "monitor gamer" --marketplaces shopee_br --max-results 1 \\
  --min-discount 999 --scan-only
```

This connectivity check should not qualify a deal. Before any qualifying test,
inspect the normalized product, `data/deal_queue.json`, `data/messages/`, the
canonical product identity, discount source, and affiliate URL. Do not pass
`--send-whatsapp` during the canary. A real send is a separate, manually
approved step after queue validation.

### Shopee rollback

To stop new Shopee scans without editing persisted queue state, remove
`shopee_br` from `PRICE_ALERT_MARKETPLACES` and set `SHOPEE_ENABLED=0`, then
restart the scan/sender supervisors. To prevent already queued Shopee entries
from being sent, temporarily set:

```env
PRICE_ALERT_SEND_MARKETPLACES=amazon_br,mercadolivre_br
```

Restore an empty sender allowlist only after the Shopee canary and logs are
healthy. Keep the rollback configuration available for the whole pilot window.

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
- if cron cannot find Node.js/npm, set `BAILEYS_NODE_BIN` and `BAILEYS_NPM_BIN` to absolute binary paths in `.env`;
- when the Baileys gateway is unavailable, the sender now keeps queue items pending and reports them as deferred instead of spending retries immediately;
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

## GitHub Actions and server deployment

The repository now includes a production-oriented deployment path for an always-on Ubuntu server:

- `.github/workflows/ci.yml`
  Validates Python tests, compile checks, shell wrappers, rendered `systemd` units, and the Baileys gateway build.
- `.github/workflows/deploy.yml`
  Triggers after the CI workflow succeeds for a `push` to `main`, then deploys the exact tested SHA over SSH.
- `deploy/install_systemd_units.sh`
  Renders and installs the tracked `systemd` unit templates.
- `deploy/verify_systemd_units.sh`
  Renders the unit templates in a temp directory and runs `systemd-analyze verify` when it is available.
- `deploy/deploy_server.sh`
  Fetches the target ref, installs Python and Node dependencies, installs the `systemd` units, aligns the runtime window, and verifies the resulting services/timers.

Expected server model:

- Ubuntu/Linux host with `systemd`
- server timezone set to `America/Sao_Paulo`
- repo cloned once to a stable path
- deploy user allowed to run `sudo -n systemctl ...` and install unit files under `/etc/systemd/system`
- production `.env` kept only on the server under `.agents/skills/price-alert-skill/.env`

GitHub configuration required for automatic deploy:

- repository variable: `DEPLOY_PATH`
- repository secrets:
  - `DEPLOY_HOST`
  - `DEPLOY_PORT`
  - `DEPLOY_USER`
  - `DEPLOY_SSH_KEY`
  - optional `DEPLOY_HOST_FINGERPRINT`

The server-side `systemd` model matches the current operating window:

- `price-alert-runtime-start.timer` starts the runtime target at `08:00`
- `price-alert-runtime-stop.timer` stops sender + Baileys at `23:30`
- `price-alert-scan.timer` runs scans every 15 minutes from `08:00` through `22:45`, then once at `23:00` and `23:15`

Useful server commands after the first install:

```bash
sudo systemctl status price-alert-runtime.target
sudo systemctl status price-alert-baileys.service
sudo systemctl status price-alert-sender.service
sudo systemctl status price-alert-scan.timer
sudo journalctl -u price-alert-baileys.service -n 100 --no-pager
sudo journalctl -u price-alert-sender.service -n 100 --no-pager
sudo journalctl -u price-alert-scan.service -n 100 --no-pager
```
