# Extraction Rules

## Primary result selector

Use Amazon search cards:

```text
div[data-component-type="s-search-result"][data-asin]
```

Ignore cards without a title or URL.

## Preferred field selectors

- Title: `h2 a span`
- URL: `h2 a`
- Image: `img.s-image`
- Current price: `.a-price .a-offscreen`
- List price: `.a-price.a-text-price .a-offscreen`
- Rating text: `span[aria-label*="de 5 estrelas"]`
- Review count: `a[href*="#customerReviews"], span[aria-label$="avaliações"]`

## Stability guidance

- Amazon often duplicates `.a-offscreen` values in a card, including installment amounts. In this skill version, only the first reliable current price is extracted; leave `list_price` null unless a later parser can prove it is a struck-through full price.
- Ads may still appear as normal result cards. Mark `is_sponsored` using any visible "Patrocinado" label in the card text.
- Do not assume product availability is visible on search results. Use `"unknown"` unless a reliable availability marker is present.
- If Amazon shows bot protection or an empty result shell, return an error and no fabricated products.
- When using Steel API extraction instead of a browser client, keep the extraction request focused on these card-level fields rather than trying to over-model the whole page.
