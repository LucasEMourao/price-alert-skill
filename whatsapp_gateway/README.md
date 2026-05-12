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

From the skill directory, use the operational wrappers:

```bash
cd ../.agents/skills/price-alert-skill
./run_baileys_gateway.sh      # foreground, best for QR login
./ensure_baileys_gateway.sh   # background/supervised start
./stop_baileys_gateway.sh
```

## Current endpoints

- `GET /health`: connection and session status.
- `GET /groups`: list participating groups. Add `?include_participants=true` only when participant IDs are needed.
- `POST /send-text`: send `{ "group_jid": "...@g.us", "message": "..." }`.
- `POST /send-image`: send `{ "group_jid": "...@g.us", "image_url": "https://...", "caption": "..." }`.


## Group discovery

After the linked-device login is connected, call:

```bash
curl http://127.0.0.1:3015/groups
```

Copy the target `jid` into the skill `.env` as `WHATSAPP_GROUP_JID`. Group JIDs normally end in `@g.us`.


## Sending smoke checks

After the gateway is connected and `WHATSAPP_GROUP_JID` is known:

```bash
curl -X POST http://127.0.0.1:3015/send-text \
  -H 'Content-Type: application/json' \
  -d '{"group_jid":"120363000000000000@g.us","message":"Baileys smoke test"}'
```

```bash
curl -X POST http://127.0.0.1:3015/send-image \
  -H 'Content-Type: application/json' \
  -d '{"group_jid":"120363000000000000@g.us","image_url":"https://example.com/image.jpg","caption":"Oferta teste"}'
```
