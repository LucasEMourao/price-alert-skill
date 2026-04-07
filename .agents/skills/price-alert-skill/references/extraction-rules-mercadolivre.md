# Extraction Rules

## Search URL

Use Mercado Livre Brasil search:

```text
https://lista.mercadolivre.com.br/{query}
```

with spaces normalized to hyphens (e.g., `mouse-gamer`).

## Primary result selector

Mercado Livre uses result cards:

```text
div.ui-search-result__wrapper
```

## Preferred fields

- Title: `poly-component__title` link text
- URL: construct from MLB ID → `https://produto.mercadolivre.com.br/{MLB-ID}`
- Image: `poly-component__picture` src
- Current price: `aria-label="Agora: X reais com Y centavos"`
- List price: `aria-label="Antes: X reais"`
- MLB ID: extracted from card content via `(MLB[A-Z]?\d+)`

## Stability guidance

- Sponsored cards should still be captured, but labeled when visible (`is_advertising=true` or `type=pad`).
- ML HTML structure changed from `li.ui-search-layout__item` to `div.ui-search-result__wrapper`. Always use the wrapper class.
- Price values are parsed from aria-labels in Portuguese (e.g., "206 reais com 64 centavos").
- If the scrape payload contains no expected wrappers, return a descriptive error instead of inventing products.
