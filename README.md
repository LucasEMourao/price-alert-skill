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
