# Output Schema

The Amazon fetcher returns one JSON object:

```json
{
  "marketplace": "amazon_br",
  "query": "ssd 2tb",
  "search_url": "https://www.amazon.com.br/s?k=ssd+2tb",
  "captured_at": "2026-03-09T14:00:00Z",
  "products": [
    {
      "position": 1,
      "asin": "B0EXAMPLE",
      "title": "SSD NVMe 2TB Example",
      "url": "https://www.amazon.com.br/dp/B0EXAMPLE",
      "image_url": "https://...",
      "price_text": "R$ 899,90",
      "price": 899.9,
      "list_price_text": "R$ 1.099,90",
      "list_price": 1099.9,
      "rating_text": "4,8 de 5 estrelas",
      "rating": 4.8,
      "review_count": 321,
      "is_sponsored": false,
      "availability": "unknown",
      "extraction_confidence": 0.93
    }
  ],
  "errors": []
}
```

Rules:
- `price` and `list_price` are numbers in BRL, parsed from Brazilian currency strings when possible.
- `asin` should be read from the result card `data-asin` when present.
- `extraction_confidence` is a local heuristic based on whether title, URL, and price were extracted.
- `errors` should contain non-fatal issues such as timeouts, blocked pages, or selector drift.
