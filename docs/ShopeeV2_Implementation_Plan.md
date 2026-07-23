# Shopee V2 API Integration — Final Implementation Plan

## 1. Status and decision summary

The project is **READY TO BEGIN IMPLEMENTATION** through small, independently tested sprints.

It is **not ready for production rollout** until the sprint acceptance criteria, API canary, and operational checks pass.

The initial scope is deliberately limited to the official Shopee Affiliate Open API `productOfferV2` operation. The following endpoints are explicitly out of scope for the first release:

- `shopOfferV2`
- `shopeeOfferV2`
- `conversionReport`
- `validatedReport`
- `listItemFeeds`
- `getItemFeedData`
- `generateShortLink`
- `generateBatchShortLink`

`productOfferV2` already returns `offerLink`, so short-link generation is not required for the initial integration.

The representative `getItemFeedData` response remains documented as a future feed-ingestion contract. It must not be silently treated as a `productOfferV2` response.

No implementation files, configuration files, tests, branches, or commits are created by this document update. The implementation branch and sprint commits must be created when implementation begins.

---

## 2. Confirmed Shopee contract

### 2.1 Endpoint and transport

```text
POST https://open-api.affiliate.shopee.com.br/graphql
Content-Type: application/json
```

The request body is JSON containing a GraphQL query. `operationName` and `variables` are optional when the query contains only one operation.

### 2.2 Authentication

The confirmed Authorization format is:

```text
Authorization: SHA256 Credential={AppID}, Timestamp={UnixTimestamp}, Signature={Signature}
```

The signature is:

```text
SHA256(AppID + Timestamp + ExactRequestPayload + AppSecret)
```

Requirements:

- use the singular `Credential` form shown in the working cURL examples;
- generate a fresh integer Unix timestamp for every request;
- serialize the JSON payload once;
- sign exactly the serialized bytes sent over HTTP;
- send the secret only as an input to signature calculation;
- never log the secret or complete Authorization header.

The supplied `10035` response was intentionally produced with incorrect credentials for validation. It is an application-level authorization failure, not a transport failure.

### 2.3 GraphQL errors

Shopee can return HTTP `200` with an `errors` array:

```json
{
  "errors": [
    {
      "message": "error [10035]: ...",
      "extensions": {
        "code": 10035,
        "message": "..."
      }
    }
  ]
}
```

The client must inspect both HTTP status and the GraphQL `errors` field.

Error classification:

- `10020` authentication/signature/timestamp failures: non-retryable except one fresh-timestamp retry for timestamp-related messages;
- `10030` rate limit: stop or defer according to the configured policy;
- `10031` through `10035`: non-retryable access/account failures;
- `11000` through `11002`: non-retryable business or parameter failures unless a specific message is explicitly classified otherwise;
- network timeout, connection reset, and temporary HTTP 5xx: bounded transient retries.

The client must retain the numeric code and message in a redacted structured error. HTTP `200` must not automatically be considered a successful provider result.

### 2.4 Product operation and pagination

The initial scanner uses `productOfferV2`.

The confirmed page request is:

```graphql
productOfferV2(page: 2) {
  nodes { ... }
  pageInfo {
    page
    limit
    hasNextPage
    scrollId
  }
}
```

Observed responses include:

```json
"pageInfo": {
  "page": 1,
  "limit": 20,
  "hasNextPage": true,
  "scrollId": null
}
```

and:

```json
"pageInfo": {
  "page": 5,
  "limit": 20,
  "hasNextPage": true,
  "scrollId": null
}
```

Initial pagination policy:

- use `page` and `hasNextPage` for `productOfferV2`;
- preserve `scrollId` in raw metadata;
- do not send `scrollId` for this operation unless a later official response proves it is required;
- stop when `hasNextPage` is false;
- enforce `SHOPEE_MAX_PAGES_PER_QUERY` as a safety bound;
- deduplicate products across pages by stable product identity;
- keep request and response page numbers in logs.

The query builder must support the project’s existing search terms through the documented `keyword`/sorting/filter arguments. The first implementation can use the confirmed operation fields and must validate the exact filtered query in the Sprint 2 canary.

### 2.5 Product field mapping

The normalized mapping is:

| Internal field | Shopee source | Policy |
|---|---|---|
| `marketplace` | constant | `shopee_br` |
| `title` | `productName` | required |
| `product_url` | `productLink` | canonical identity URL |
| outbound `url` | `offerLink` | affiliate URL |
| `current_price` | `priceMin` | primary current-price candidate |
| `current_price` fallback | `price` | use when `priceMin` is absent |
| `previous_price` | reconstructed from `priceMin`/`price` and `priceDiscountRate` | rounded reference price; marked as inferred |
| `discount_pct` | `priceDiscountRate` | API-reported percentage, 0–100 |
| `savings_brl` | reconstructed reference minus current price | rounded display/monitoring value; not a lane threshold input |
| `item_id` | `itemId` | raw metadata and identity input |
| `shop_id` | `shopId` | raw metadata |
| `shop_name` | `shopName` | raw metadata |
| `shop_type` | `shopType` | empty list means unknown |
| `image_url` | `imageUrl` | optional |
| `sales` | `sales` | raw metadata |
| `rating` | `ratingStar` | `"0"` means unavailable |
| category IDs | `productCatIds` | preserve zeros as missing levels |
| commission | commission fields | raw metadata only |
| offer period | `periodStartTime`, `periodEndTime` | epoch values, preserved raw |
| variation maximum | `priceMax` | metadata only; never previous price |

`price` and `priceMin` are equal in the supplied examples. The implementation must prefer `priceMin`, fall back to `price`, and record a diagnostic if both are present but differ.

The API does not expose a documented original/list price. The approved source-aware policy reconstructs a reference price only in the application layer:

```text
previous_price = round_half_up(current_price / (1 - priceDiscountRate / 100), 2)
savings_brl    = previous_price - current_price
```

The deal must persist `previous_price_source=shopee_inferred_from_price_discount_rate`.
This is a monitored inference, not an API-provided historical price. `priceMax`
must never be used as a previous price, and inferred savings must not change the
Shopee percentage-only lane thresholds.

### 2.6 Offer period handling

`periodStartTime` and `periodEndTime` are Unix timestamps and must be compared numerically with the current Unix timestamp. They do not need local-time conversion for filtering.

The observed value `32503651199` converts approximately to:

```text
2999-12-31 15:59:59 UTC
```

Because this exact far-future value appears across unrelated offers, it is likely a no-practical-expiration sentinel. Its semantic meaning is not documented, so the initial implementation must not hardcode a special meaning.

Safe policy:

```text
if periodStartTime > now:
    skip as not yet active

if periodEndTime < now:
    skip as expired
```

A far-future timestamp remains active naturally. Raw timestamps must be preserved for diagnostics. Queue freshness rules continue to control how long a discovered deal remains sendable.

### 2.7 Representative feed response boundary

The supplied `getItemFeedData` response has a different contract:

```text
data.getItemFeedData.rows[*].columns
```

where `columns` is a JSON-encoded string and `global_item_attributes` is another JSON-encoded string inside it.

Feed support is not part of the initial scanner. If it is added later, it requires a separate adapter and tests for:

- nested response validation;
- double JSON decoding;
- `updateType` values and `null`;
- missing fields;
- invalid numeric strings;
- malformed row JSON;
- exact preservation of `product_short link`, including its space;
- `offset`, `limit`, `totalCount`, and `hasMore` pagination.

The feed field `product_short link` must never be renamed or normalized silently.

---

## 3. Architecture and boundaries

The integration must preserve the current architecture.

```text
scan_cli
  -> scan_deals dependency wiring
  -> ShopeeMarketplaceScanner
  -> ShopeeGraphQLClient
  -> signed POST /graphql
  -> GraphQL/error validation
  -> normalized product records
  -> existing scan_use_case
  -> existing domain selection
  -> existing JSON queue
  -> existing serial WhatsApp sender
```

### 3.1 API client

Recommended file:

```text
price_alert_skill/core/adapters/shopee_api.py
```

Responsibilities:

- endpoint and timeout;
- App ID and secret loading;
- exact-payload serialization;
- timestamp generation;
- SHA-256 signature;
- Authorization header;
- HTTP transport;
- GraphQL error extraction;
- error classification;
- bounded retry policy;
- redacted logging.

The API client must not know about product profiles, lanes, queues, WhatsApp, or message formatting.

### 3.2 Product scanner

Recommended file:

```text
price_alert_skill/core/adapters/shopee_scanner.py
```

Responsibilities:

- build the confirmed `productOfferV2` query;
- map project search queries to Shopee keyword filters;
- iterate pages;
- enforce the page safety limit;
- normalize product fields;
- filter inactive offers;
- preserve raw metadata;
- return structured provider failures.

### 3.3 Application integration

Modify only the orchestration layer where necessary:

- add `shopee_runner` dependency to `scan_marketplace()`;
- add `shopee_br` dispatch;
- preserve current Amazon and Mercado Livre defaults;
- keep `product_url` canonical and `url` affiliate-oriented;
- keep scan-only behavior unchanged;
- never send directly from a scanner.

Shopee-specific JSON parsing, signature handling, and API terminology must not be added to the domain layer.

### 3.4 Domain and message policy

Shopee deals use:

```text
current_price = priceMin or price
previous_price = round_half_up(current_price / (1 - priceDiscountRate / 100), 2)
savings_brl = previous_price - current_price
previous_price_source = shopee_inferred_from_price_discount_rate
price_discount_source = shopee_price_discount_rate
```

The inferred values are explicitly source-aware and must be monitored against
marketplace pages. They must not change Amazon or Mercado Livre behavior.

Approved source-aware behavior:

- accept a Shopee deal when `priceDiscountRate` meets the approved source-specific threshold;
- display the percentage, reconstructed “Antes” value, and current price;
- retain the source marker so the value is not mistaken for an API list-price field;
- keep source-specific percentage lane thresholds; inferred savings do not qualify a lane;
- preserve percentage-based ranking and cooldown improvement behavior;
- never use `priceMax` as the previous price.

The exact thresholds must be approved before Sprint 3 is considered complete.

---

## 4. Configuration and secrets

Add the following variables to `.agents/skills/price-alert-skill/.env.example`:

```env
SHOPEE_ENABLED=0
SHOPEE_APP_ID=
SHOPEE_APP_SECRET=
SHOPEE_API_URL=https://open-api.affiliate.shopee.com.br/graphql
SHOPEE_REQUEST_TIMEOUT_SECONDS=30
SHOPEE_MAX_PAGES_PER_QUERY=5
PRICE_ALERT_MARKETPLACES=amazon_br,mercadolivre_br
PRICE_ALERT_SEND_MARKETPLACES=
```

Rules:

- `SHOPEE_ENABLED=0` keeps Shopee disabled during development and rollback;
- `PRICE_ALERT_MARKETPLACES` controls scanner activation;
- `PRICE_ALERT_SEND_MARKETPLACES` is empty by default and acts as an optional sender allowlist;
- the precedence between `SHOPEE_ENABLED` and marketplace lists must be documented in configuration code;
- production credentials remain only in the server `.env`;
- secrets must not appear in logs, fixtures, queue entries, messages, or commits;
- App ID may appear in a redacted diagnostic only if necessary; the secret must never appear.

No OAuth refresh flow is planned because the official documentation describes per-request signatures, not bearer-token refresh.

---

## 5. Sprint and branch methodology

Implementation must occur on a dedicated branch. Do not implement directly on `main`.

Recommended branch:

```text
feat/shopee-v2-api
```

Suggested start:

```bash
git switch main
git pull --ff-only
git switch -c feat/shopee-v2-api
```

The branch creation command is part of the implementation procedure and must be executed only when implementation is authorized.

### Sprint rules

Every sprint must:

1. have a narrow scope;
2. preserve existing behavior outside that scope;
3. include tests for all new behavior;
4. run the complete relevant test suite at the end;
5. run compile/static/shell checks affected by the sprint;
6. pass the sprint acceptance criteria;
7. be committed as one logical completed sprint;
8. stop before beginning the next sprint if any acceptance criterion fails.

Recommended commit format:

```text
feat(shopee): complete sprint N - short description
```

Do not combine unfinished work from multiple sprints in one commit. If a sprint exposes a design problem, update the plan before continuing.

---

## 6. Sprint plan

### Sprint 0 — Branch, contract freeze, and fixtures

#### Objective

Prepare the branch and freeze the confirmed initial contract without changing runtime behavior.

#### Scope

- create `feat/shopee-v2-api`;
- document the confirmed `productOfferV2` request and response;
- add redacted static fixtures for:
  - successful page 1;
  - successful page 2;
  - `hasNextPage=false`;
  - HTTP-200 GraphQL authentication error;
  - empty `nodes`;
  - price/priceMin discrepancy;
  - `ratingStar="0"`;
  - empty `shopType`;
- document the source-aware pricing decision;
- explicitly mark feed ingestion as future scope.

#### Tests

- fixture loading and JSON validity;
- no production imports or behavior changes;
- existing full test suite.

#### Acceptance

- branch exists;
- fixtures contain no credentials or Authorization headers;
- the plan and fixtures agree;
- all existing tests pass.

#### Commit

```text
chore(shopee): complete sprint 0 - freeze API contract and fixtures
```

---

### Sprint 1 — Signed Shopee GraphQL client

#### Objective

Implement and test transport/authentication independently of the scan workflow.

#### Files

Create:

```text
price_alert_skill/core/adapters/shopee_api.py
```

Modify:

- `price_alert_skill/config.py`
- `.agents/skills/price-alert-skill/.env.example`

#### Behavior

- load App ID and secret only when Shopee is enabled;
- serialize the request body once;
- sign the exact serialized payload;
- generate the Authorization header;
- send JSON to the documented endpoint;
- parse HTTP status and GraphQL errors separately;
- classify documented error codes;
- retry only bounded transient failures;
- retry timestamp errors once with a fresh timestamp;
- never retry invalid credentials/signatures indefinitely;
- redact secrets and Authorization values.

#### Tests

- known signature vector from `Authentication.md`;
- header formatting using singular `Credential`;
- exact body/signature consistency;
- missing credentials;
- timeout and connection error;
- HTTP 4xx/5xx;
- HTTP 200 with `errors`;
- code `10035` as non-retryable access failure;
- rate-limit classification;
- secret redaction.

#### Acceptance

- all client tests pass;
- existing marketplace tests pass;
- no real API call is required for this sprint.

#### Commit

```text
feat(shopee): complete sprint 1 - add signed GraphQL client
```

---

### Sprint 2 — `productOfferV2` scanner and normalization

#### Objective

Fetch and normalize Shopee product offers without connecting them to the queue.

#### Files

Create:

```text
price_alert_skill/core/adapters/shopee_scanner.py
```

Potentially create a small provider-specific model or parser module if it improves validation without leaking into the domain.

#### Behavior

- accept `query` and `max_results`;
- construct the confirmed `productOfferV2` operation;
- use keyword filtering compatible with project queries;
- request a bounded page size;
- follow `page`/`hasNextPage`;
- preserve `scrollId` but do not send it unless required;
- stop at `SHOPEE_MAX_PAGES_PER_QUERY`;
- deduplicate by `itemId` or canonical product identity;
- prefer `priceMin`, fallback to `price`;
- record price discrepancies;
- map `productLink` and `offerLink` separately;
- map `priceDiscountRate` and leave application-layer reference-price reconstruction to the source-aware policy;
- preserve raw commission, shop, rating, category, and period metadata;
- skip malformed product nodes safely;
- return structured errors.

#### Validation

- required title, canonical URL, outbound URL, and valid current price;
- `priceDiscountRate` must be numeric and within `0..100`;
- `ratingStar="0"` becomes unavailable;
- empty `shopType` is retained as unknown;
- invalid optional fields do not crash the full page;
- period timestamps are compared as Unix integers.

#### Tests

- page 1 and page 2;
- `hasNextPage` termination;
- page safety limit;
- empty results;
- malformed nodes;
- missing image/rating/shop type;
- invalid numeric values;
- `priceMin` fallback to `price`;
- price discrepancy diagnostics;
- canonical versus affiliate URLs;
- period start/end filtering;
- duplicate item IDs across pages;
- HTTP-200 GraphQL error response.

#### Acceptance

A mocked response becomes a normalized product list without any queue, sender, or WhatsApp dependency. Existing Amazon and Mercado Livre behavior is unchanged.

#### Commit

```text
feat(shopee): complete sprint 2 - add productOfferV2 scanner
```

---

### Sprint 3 — Source-aware deal selection and messages

#### Objective

Allow Shopee’s authoritative percentage discount and explicitly marked
reconstructed reference price to enter the existing deal flow without changing
Amazon or Mercado Livre behavior.

#### Files

Potentially modify:

- `price_alert_skill/core/application/scan_use_case.py`
- `price_alert_skill/deal_selection.py`
- `price_alert_skill/core/domain/lane_rules.py`
- `price_alert_skill/utils.py`
- `price_alert_skill/core/domain/models.py`

#### Behavior

- preserve existing Amazon and Mercado Livre price-pair behavior;
- reconstruct `previous_price` with
  `round_half_up(current_price / (1 - discount_pct / 100), 2)`;
- persist `previous_price_source=shopee_inferred_from_price_discount_rate`;
- preserve `discount_source=shopee_price_discount_rate`;
- keep normal/priority/urgent lanes on percentage-only thresholds;
- keep inferred savings visible for display and monitoring, but do not use them
  as lane qualification evidence;
- format Shopee messages as:
  - discount percentage;
  - reconstructed “Antes” value marked with `~`;
  - current price;
  - affiliate URL;
- maintain product and offer keys using canonical product identity and current price.

#### Tests

- Shopee percentage qualification;
- reconstructed previous price and savings with monetary rounding;
- zero, 100%, and invalid discount rejection;
- unmarked previous price sanitization;
- lane classification independent of inferred savings;
- percentage-based ranking and cooldown behavior;
- message with the reconstructed “Antes” line;
- unchanged Amazon and Mercado Livre formatting;
- cooldown and offer identity behavior.

#### Acceptance

The source-aware inference policy is explicit, tested, and approved. Every
reconstructed Shopee reference price carries its source marker, and no
Amazon/Mercado Livre price-pair behavior changes.

#### Commit

```text
feat(shopee): complete sprint 3 - support source-aware discounts
```

---

### Sprint 4 — Scan workflow integration and rollback controls

#### Objective

Add Shopee as an opt-in marketplace while preserving current defaults and enabling safe rollback.

#### Files

Modify:

- `price_alert_skill/core/application/scan_use_case.py`
- `price_alert_skill/scan_deals.py`
- `price_alert_skill/core/entrypoints/scan_cli.py`
- `price_alert_skill/config.py`
- `price_alert_skill/core/domain/queue_policy.py`
- `price_alert_skill/core/adapters/json_queue_repository.py`
- `price_alert_skill/core/ports/queue_repository.py`
- `price_alert_skill/deal_queue.py`
- `price_alert_skill/sender_worker.py`
- `.agents/skills/price-alert-skill/.env.example`

#### Behavior

- add a `shopee_runner` dependency;
- add `shopee_br` dispatch;
- preserve default `amazon_br,mercadolivre_br` behavior;
- enable Shopee through explicit marketplace configuration;
- preserve `product_url` for identity and `url` for outbound affiliate use;
- add optional `PRICE_ALERT_SEND_MARKETPLACES` filtering;
- allow Shopee to be disabled without editing queue JSON;
- continue scanning other providers if Shopee fails;
- report Shopee request/page/product/deal/error counts.

#### Tests

- Shopee-only scan;
- mixed Amazon/ML/Shopee scan;
- default marketplace regression;
- Shopee failure does not suppress other providers;
- queue insertion;
- sender marketplace rollback filter;
- existing profiles and beauty brand filtering;
- sender behavior when marketplace allowlist is empty.

#### Acceptance

Shopee can be enabled explicitly, reaches the existing queue, and can be disabled independently. Existing scheduled behavior remains unchanged when Shopee is disabled.

#### Commit

```text
feat(shopee): complete sprint 4 - integrate scan and rollback controls
```

---

### Sprint 5 — Observability, CI, documentation, and controlled rollout

#### Objective

Validate the integrated feature and prepare a controlled canary without changing the WhatsApp gateway.

#### Files

Modify documentation and CI only where required:

- `README.md`
- `OPERATIONS.md`
- `.agents/skills/price-alert-skill/PLANO.md`
- `.agents/skills/price-alert-skill/.env.example`
- `.github/workflows/ci.yml` if new test paths require explicit inclusion

Do not modify `whatsapp_gateway` for this feature.

#### Tests and checks

Run:

```bash
python -m pytest tests .agents/skills/price-alert-skill/scripts/tests
python -m compileall price_alert_skill
bash -n .agents/skills/price-alert-skill/run_scan.sh
bash -n .agents/skills/price-alert-skill/run_sender.sh
bash -n deploy/verify_systemd_units.sh
```

Also run the complete Shopee unit and workflow suite.

#### Canary sequence

1. Configure dedicated non-production Shopee credentials.
2. Confirm no credentials are printed.
3. Run one query with one bounded page.
4. Inspect normalized output and `data/messages/`.
5. Inspect queue identity, current price, discount source, and outbound URL.
6. Send only after queue validation.
7. Monitor authentication, rate-limit, and error logs.
8. Enable Shopee for one controlled operating window.
9. Keep rollback available through marketplace configuration.

Suggested command:

```bash
python3 scripts/scan_deals.py \
  "monitor gamer" \
  --marketplaces shopee_br \
  --max-results 1 \
  --min-discount 999 \
  --scan-only
```

The high minimum discount is intended for a safe connectivity check and may produce no queued deal. A separate controlled test must validate a real qualifying Shopee deal.

#### Acceptance

- all tests pass;
- CI passes;
- no existing provider regression exists;
- one controlled Shopee canary succeeds;
- rollback is documented and tested;
- no secret or Authorization header is present in logs or artifacts.

#### Commit

```text
chore(shopee): complete sprint 5 - validate and document rollout
```

After the sprint commit, merge only after review and successful canary evidence.

---

## 7. Error, retry, and resilience policy

### Retryable

- connection timeout;
- connection reset;
- temporary HTTP 5xx;
- request-expired or invalid-timestamp response, once with a fresh timestamp;
- rate-limit response only after an explicit wait/defer policy.

### Non-retryable

- invalid signature;
- invalid credential;
- invalid Authorization header;
- unsupported authentication type;
- disabled application;
- access denied;
- invalid affiliate ID;
- frozen account;
- blacklisted account;
- no API access;
- invalid parameters;
- malformed response schema.

### Partial responses

If a response contains both `data` and `errors`:

- retain valid normalized nodes only if the requested operation’s result is explicitly usable;
- record the errors;
- mark the scan as partial;
- never treat a partial response as a fully successful scan;
- never fabricate missing products.

If the response has no usable product data, return a provider failure and allow other marketplaces to continue.

---

## 8. Persistence and identity

Canonical identity must use `productLink` or a stable `itemId`-derived identity, not the affiliate short URL.

Recommended fields:

```text
source_product_key = stable identity from productLink/itemId
product_key        = source_product_key unless a documented variant-family rule applies
offer_key          = product_key + current_price
```

Persist raw Shopee fields as metadata where useful, but never persist:

- App secret;
- Authorization header;
- request signature;
- full signed payload when it contains sensitive values.

The existing JSON queue format remains compatible. Queue writes must continue to use the current repository and locking conventions.

---

## 9. Testing matrix

### API client

- signature vector;
- payload byte equality;
- header formatting;
- missing credentials;
- HTTP errors;
- HTTP-200 GraphQL errors;
- error-code classification;
- bounded retry;
- secret redaction.

### Product scanner

- valid page;
- multiple pages;
- final page;
- page safety limit;
- empty nodes;
- malformed node;
- missing optional fields;
- invalid numeric values;
- `priceMin` fallback;
- price discrepancy;
- invalid period;
- future start;
- expired end;
- far-future end timestamp;
- duplicate item IDs.

### Domain/application

- source-aware discount qualification;
- reconstructed previous price with an explicit source marker;
- reconstructed savings with monetary rounding;
- message rendering and inference disclosure;
- lane selection;
- deduplication;
- cooldown;
- canonical URL identity;
- affiliate outbound URL.

### Workflow and regression

- Shopee-only scan;
- mixed marketplace scan;
- Shopee outage with Amazon/ML success;
- default marketplace behavior;
- sender rollback allowlist;
- existing Amazon parser tests;
- existing Mercado Livre parser tests;
- queue and sender tests;
- shell locking tests;
- deployment validation.

---

## 10. Future endpoint backlog

These endpoints are intentionally deferred:

### `shopOfferV2`

Future shop/campaign discovery. It does not replace product-level price scanning.

### `shopeeOfferV2`

Future campaign or collection discovery. It does not provide the product price contract required by the initial flow.

### `listItemFeeds` and `getItemFeedData`

Future bulk catalog synchronization. Requires a dedicated feed adapter, double JSON parsing, DELTA semantics, and exact preservation of external field names such as `product_short link`.

### `generateShortLink` and `generateBatchShortLink`

Future fallback attribution flow only if `offerLink` is unavailable. Batch generation should be preferred for multiple URLs and must have idempotency and partial-failure tests before use.

### `conversionReport` and `validatedReport`

Future analytics use cases. Their cursor pagination and 30-second validity window must not be mixed into product discovery.

---

## 11. Final acceptance criteria

The initial integration is complete only when:

1. the dedicated branch contains only reviewed sprint commits;
2. the signed client uses the exact transmitted payload;
3. the `Credential` Authorization header is correct;
4. GraphQL errors are detected even on HTTP `200`;
5. product pagination follows `page` and `hasNextPage` safely;
6. `priceMin`/`price` mapping is deterministic;
7. `priceMax` is never treated as previous price;
8. `priceDiscountRate` is preserved as the source discount;
9. reconstructed Shopee prices and savings carry an explicit source marker;
10. source-aware lane and message behavior is tested;
11. `productLink` and `offerLink` remain separate;
12. Shopee logic is isolated under `core/adapters/`;
13. Amazon and Mercado Livre behavior is unchanged by default;
14. Shopee remains opt-in during rollout;
15. Shopee can be disabled without editing queue state;
16. malformed, missing, nullable, and invalid values are handled safely;
17. credentials and signatures never appear in logs or persisted state;
18. the complete test suite and CI checks pass;
19. a controlled live canary succeeds;
20. rollback and operational monitoring are documented.

---

## 12. Recommended execution order

1. Create `feat/shopee-v2-api`.
2. Complete Sprint 0 and commit it.
3. Complete Sprint 1 and commit it.
4. Complete Sprint 2 and commit it.
5. Approve and implement the source-aware discount policy in Sprint 3.
6. Complete Sprint 4 with Shopee still opt-in.
7. Complete Sprint 5 and run the controlled canary.
8. Review sprint commits and canary evidence.
9. Merge only after all acceptance criteria pass.
10. Keep Shopee rollback available through configuration after merge.
