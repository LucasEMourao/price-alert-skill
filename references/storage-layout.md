# Storage Layout

SQLite tables:

## `products`

- `id` integer primary key
- `marketplace` text not null
- `external_id` text nullable
- `canonical_key` text not null unique
- `title` text not null
- `url` text not null
- `image_url` text nullable
- `first_seen_at` text not null
- `last_seen_at` text not null

`canonical_key` is currently:
- `amazon_br:{asin}` when ASIN is present
- `mercadolivre_br:{asin}` when a Mercado Livre item id is present
- `shopee_br:{asin}` when a Shopee item id is present
- otherwise `amazon_br:url:{url}`
- otherwise `{marketplace}:url:{url}`

## `price_snapshots`

- `id` integer primary key
- `product_id` integer not null
- `captured_at` text not null
- `query` text not null
- `position` integer nullable
- `price` real nullable
- `price_text` text nullable
- `list_price` real nullable
- `list_price_text` text nullable
- `rating` real nullable
- `rating_text` text nullable
- `review_count` integer nullable
- `is_sponsored` integer not null default 0
- `availability` text nullable
- foreign key to `products(id)`

## Alert heuristic v1

A product is an alert candidate when:
- current `price` is not null
- and it is the lowest stored price for that product
- and there is at least one previous non-null price snapshot

This is intentionally conservative for the first version.

## `external_price_history`

External enrichment snapshots, currently intended for Zoom:

- `product_id` integer nullable
- `source` text not null
- `source_product_id` text nullable
- `source_url` text not null
- `captured_at` text not null
- `current_best_price` real nullable
- `low_offer_price` real nullable
- `high_offer_price` real nullable
- `offer_count` integer nullable
- `median_price` real nullable
- `tip_description` text nullable
- `tip_window_start` text nullable
- `tip_window_end` text nullable
- `tip_text` text nullable

Use this table for external baselines only. Do not mix it with direct retailer snapshots.

## `product_external_links`

Persistent product-to-external-source matches:

- `product_id` integer not null
- `source` text not null
- `source_product_id` text nullable
- `source_url` text not null
- `matched_title` text nullable
- `score` real nullable

Use this for durable mappings like `products.id -> zoom.com.br URL`.

## `alert_events`

Deduped emitted alert records:

- `product_id` integer not null
- `marketplace` text not null
- `query` text not null
- `reason` text not null
- `fingerprint` text not null unique
- `current_price` real nullable
- `reference_price` real nullable
- `discount_pct` real nullable
- `payload_json` text not null
- `created_at` text not null

The fingerprint prevents the same alert payload from firing repeatedly across runs.

## `watchlists`

User-defined recurring monitoring groups:

- `id` integer primary key
- `name` text not null
- `category` text nullable
- `categories_json` text nullable
- `query` text not null
- `queries_json` text nullable
- `marketplaces_json` text nullable
- `target_price` real nullable
- `update_interval_minutes` integer not null
- `active` integer not null default `1`
- `notes` text nullable
- `created_at` text not null
- `updated_at` text not null
- `last_run_at` text nullable

Use this table for the onboarding state. Each row represents one recurring user intent.

## `watchlist_products`

Tracked source products or marketplace-specific entrypoints attached to a watchlist:

- `id` integer primary key
- `watchlist_id` integer not null
- `source_url` text not null
- `marketplace` text not null
- `category` text nullable
- `normalized_query` text nullable
- `product_id` integer nullable
- `zoom_url` text nullable
- `session_id` text nullable
- `created_at` text not null
- `updated_at` text not null

Use `product_id` once onboarding bootstrap can resolve the watched link back to a stored `products.id`.

## `watchlist_runs`

Execution log for scheduled refreshes:

- `id` integer primary key
- `watchlist_id` integer not null
- `started_at` text not null
- `finished_at` text nullable
- `status` text not null
- `details_json` text nullable

This table gives you a durable audit trail for each recurring update cycle.
