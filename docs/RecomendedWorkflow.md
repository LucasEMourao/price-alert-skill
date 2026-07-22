 Recommended workflow

 1. Create feat/shopee-v2-api.
 2. Start a new conversation for each sprint.
 3. Begin each prompt by referencing:
     - docs/ShopeeV2_Implementation_Plan.md
     - current branch
     - sprint scope
 4. Require the agent to inspect current files before editing.
 5. Use mocked tests for Sprints 0–4.
 6. Never paste credentials or real Authorization headers.
 7. Commit only after all sprint tests pass.
 8. Start the next conversation from a clean working tree.

 Shared instructions

 Include this in every sprint prompt:

 ```text
   Act as a Senior Python Automation Developer and Technical Architect.

   Repository:
    /home/lucas/projetos/price-alert-skill

   Authoritative plan:
    docs/ShopeeV2_Implementation_Plan.md

   Work only within the requested sprint scope.
   Preserve the existing layered architecture:
   domain -> application -> ports -> adapters -> entrypoints.

   Before editing:
   1. Read the implementation plan completely.
   2. Inspect the relevant existing files and tests.
   3. Check the current git branch and working tree.
   4. Identify conflicts or missing prerequisites.

   Do not:
   - modify unrelated providers;
   - modify the WhatsApp gateway;
   - introduce unnecessary dependencies;
   - expose credentials or Authorization headers;
   - make live Shopee API calls unless explicitly authorized;
   - perform destructive actions.

   You are authorized to edit files within this sprint, run relevant tests and validation checks, and create the sprint commit only after all acceptance criteria pass.

   At the end, report:
   - files changed;
   - tests executed and results;
   - acceptance criteria status;
   - commit hash;
   - remaining risks or follow-up work.
 ```

 ────────────────────────────────────────────────────────────────────────────────

 Sprint 0 prompt

 ```text
   Execute Sprint 0 — Branch, contract freeze, and fixtures.

   Create or verify the branch:
   feat/shopee-v2-api

   Read all relevant Shopee documentation, especially:
   - docs/Authentication.md
   - docs/RequestAndResponse.md
   - docs/GetProductOfferList.md
   - docs/ShopeeV2_Implementation_Plan.md

   Freeze the confirmed contract:
   - productOfferV2;
   - page-based pagination;
   - priceMin primary, price fallback;
   - priceDiscountRate as the source discount;
   - no fabricated previous price or savings;
   - productLink as canonical URL;
   - offerLink as outbound URL;
   - feed ingestion out of initial scope.

   Add only redacted static fixtures and fixture tests for:
   - successful page;
   - second page;
   - final page;
   - empty result;
   - HTTP-200 GraphQL error;
   - price discrepancy;
   - ratingStar="0";
   - empty shopType.

   Do not implement the API client or scanner yet.

   Run the existing test suite and commit only after acceptance passes.

   Use commit message:
   chore(shopee): complete sprint 0 - freeze API contract and fixtures
 ```

 Sprint 1 prompt

 ```text
   Execute Sprint 1 — Signed Shopee GraphQL client.

   Read the plan and relevant authentication/request documentation.

   Implement only:
   - price_alert_skill/core/adapters/shopee_api.py
   - required configuration changes in price_alert_skill/config.py
   - .agents/skills/price-alert-skill/.env.example
   - client tests

   Implement:
   - exact JSON payload serialization;
   - SHA-256 signature;
   - Credential Authorization header;
   - timestamp generation;
   - HTTP and GraphQL error parsing;
   - bounded retry classification;
   - secret redaction.

   Do not implement product scanning or workflow integration.

   Use mocks only. Do not call the live API.

   Run the complete existing suite plus Sprint 1 tests.

   Commit after all acceptance criteria pass:
   feat(shopee): complete sprint 1 - add signed GraphQL client
 ```

 Sprint 2 prompt

 ```text
   Execute Sprint 2 — productOfferV2 scanner and normalization.

   Implement only the Shopee adapter/scanner layer.

   Create:
   - price_alert_skill/core/adapters/shopee_scanner.py

   Use the existing API client from Sprint 1.

   Implement:
   - productOfferV2 query construction;
   - project query-to-keyword mapping;
   - page/hasNextPage pagination;
   - page safety limit;
   - product deduplication;
   - priceMin primary and price fallback;
   - priceDiscountRate mapping;
   - productLink and offerLink separation;
   - period timestamp filtering;
   - raw metadata preservation;
   - safe handling of missing and invalid fields;
   - structured provider errors.

   Do not connect the scanner to queue or WhatsApp workflows yet.

   Add tests for:
   - first and second pages;
   - final page;
   - malformed nodes;
   - missing fields;
   - invalid numerics;
   - price discrepancy;
   - duplicate item IDs;
   - period filtering;
   - GraphQL errors.

   Run the complete suite and commit:
   feat(shopee): complete sprint 2 - add productOfferV2 scanner
 ```

 Sprint 3 prompt

 ```text
   Execute Sprint 3 — source-aware Shopee discount selection and messages.

   Read the existing:
   - price_alert_skill/core/domain/lane_rules.py
   - price_alert_skill/deal_selection.py
   - price_alert_skill/core/application/scan_use_case.py
   - price_alert_skill/utils.py
   - related tests

   Implement the approved policy:
   - priceDiscountRate is authoritative;
   - previous_price remains None;
   - savings_brl remains None;
   - no implied previous price;
   - Shopee messages show percentage and current price;
   - Shopee messages omit the Antes line;
   - Amazon and Mercado Livre behavior remains unchanged.

   Define and test explicit Shopee lane thresholds. Do not let unknown savings silently become valid savings.

   Add tests for:
   - qualification;
   - lane selection;
   - message formatting;
   - ranking;
   - deduplication;
   - cooldown;
   - regression coverage for Amazon and Mercado Livre.

   Commit:
   feat(shopee): complete sprint 3 - support source-aware discounts
 ```

 Sprint 4 prompt

 ```text
   Execute Sprint 4 — scan workflow integration and rollback controls.

   Integrate Shopee as an opt-in marketplace.

   Modify only the relevant:
   - application orchestration;
   - scan wiring;
   - CLI/configuration;
   - queue filtering;
   - sender marketplace filtering;
   - tests.

   Implement:
   - shopee_runner injection;
   - shopee_br dispatch;
   - PRICE_ALERT_MARKETPLACES;
   - PRICE_ALERT_SEND_MARKETPLACES;
   - canonical product identity;
   - affiliate outbound URL;
   - Shopee failure isolation;
   - rollback by configuration.

   Preserve the existing default:
   amazon_br,mercadolivre_br

   Do not modify the WhatsApp gateway.

   Test:
   - Shopee-only scan;
   - mixed marketplace scan;
   - Shopee outage;
   - default behavior;
   - queue insertion;
   - rollback filtering;
   - existing profiles and brand filtering.

   Commit:
   feat(shopee): complete sprint 4 - integrate scan and rollback controls
 ```

 Sprint 5 prompt

 ```text
   Execute Sprint 5 — observability, CI, documentation, and rollout validation.

   Update only the documentation, CI, and operational files required by the plan.

   Add or verify:
   - Shopee operational documentation;
   - configuration documentation;
   - redacted error logging;
   - request/page/product/deal counters;
   - rollback procedure;
   - CI coverage.

   Run:
   - complete Python test suite;
   - compile checks;
   - shell syntax checks;
   - deployment validation;
   - all Shopee tests.

   Do not make a live API call unless I explicitly authorize it in this conversation.

   If live validation is authorized:
   1. Use a dedicated non-production credential.
   2. Run one bounded query.
   3. Inspect normalized output, queue state, message JSON, and affiliate URL.
   4. Never print or persist secrets.
   5. Keep rollback available.

   Commit:
   chore(shopee): complete sprint 5 - validate and document rollout
 ```

 Important handoff rule

 At the end of each sprint, ask the agent to stop after committing. Start the next sprint in a new conversation using the next prompt and the previous commit as the baseline.