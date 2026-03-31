# Extraction Rules

## Search URL

Use Mercado Livre Brasil search:

```text
https://lista.mercadolivre.com.br/{query}
```

with spaces normalized to hyphens.

## Primary result selector

Mercado Livre commonly uses result cards like:

```text
li.ui-search-layout__item
```

## Preferred fields

- Title: card heading/link text
- URL: product link pointing to `/MLB-...`
- Image: `img`
- Price: current integer and decimal fragments near `andes-money-amount`
- Review count and rating: optional, often absent in search cards

## Stability guidance

- Sponsored cards should still be captured, but labeled when visible.
- Mercado Livre HTML varies between list/grid layouts. Prefer broad class detection rather than exact nesting assumptions.
- If the scrape payload contains no expected list items, return a descriptive error instead of inventing products.
