# Extraction Rules

## Search URL

Use Shopee Brasil search:

```text
https://shopee.com.br/search?keyword={query}
```

## Primary targets

Shopee frequently renders product listings as anchors linking to item pages and may embed structured state in scripts.

Preferred extraction order:

1. Structured JSON or script state if present
2. Anchor-based product cards
3. Fallback text scan for title and BRL price near item links

## Stability guidance

- Shopee markup changes often and may be partially obfuscated.
- Product URLs often contain `/product/` or `-i.` item patterns.
- If the Steel scrape redirects to `/buyer/login`, return an explicit authentication-required error and no fabricated products.
- In practice, Shopee may require a logged-in Steel session before search listings are accessible.
- When a `session_id` is provided, fetch the session context from Steel and pass it to the scrape request as `sessionContext`.
