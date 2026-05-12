# WhatsApp Gateway

Local Baileys gateway for the `price-alert-skill` sender migration.

This service is intentionally isolated from the Python package. During the migration, Python keeps owning queue selection, cooldown, deduplication and scan flow; the gateway only owns WhatsApp connectivity.

## Environment

- `BAILEYS_HOST`: bind host, default `127.0.0.1`
- `BAILEYS_PORT`: bind port, default `3015`
- `BAILEYS_AUTH_DIR`: persisted Baileys auth directory, default `../.agents/skills/price-alert-skill/data/baileys_auth`
- `BAILEYS_LOG_LEVEL`: pino log level, default `info`

## Commands

```bash
npm install
npm run build
npm run dev
```

The first successful run prints a QR code in the terminal. Scan it as a linked device, then restart the process to confirm that the session persists.

## Current endpoints

- `GET /health`: connection and session status.
