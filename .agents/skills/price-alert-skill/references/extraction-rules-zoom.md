# Extraction Rules

## Preferred sources

Use this order:

1. `__NEXT_DATA__` embedded JSON
2. JSON-LD product/offer data
3. Rendered history section text

## Useful fields observed on Zoom product pages

- Product id
- Product name
- Brand/model
- Offer low/high/current data
- Offer count
- `priceTip` summary with:
  - `price`
  - `median_price`
  - `description`
  - `date_range.start`
  - `date_range.end`
- Visible history windows in the rendered page:
  - `40 dias`
  - `3 meses`
  - `6 meses`
  - `1 ano`

## Limitations

- The full chart series may not be present in the initial HTML payload.
- Store summary baselines first; only add chart-series extraction if a reliable serialized source is found later.
