# Event tracking specification

This is a design contract for a fictional implementation. The static
[`dataLayer` lab](../demo/data-layer/) demonstrates the payloads without loading a tag manager or
sending data anywhere.

## Measurement topology

Use one logical web stream per storefront market with a shared naming/parameter registry and a
single warehouse property boundary. Market is explicit on every event; reporting date derives from
the storefront timezone. Consent state is captured with the event, and denied/internal/test traffic
is excluded by a visible eligibility rule rather than by dashboard filters.

## Standard ecommerce events

| Event | Trigger | Required item/transaction fields |
|---|---|---|
| `view_item_list` | A product list is rendered | list ID/name and impression items |
| `select_item` | A product is selected from a list | item ID/name/category/variant/price |
| `view_item` | Product detail becomes visible | one item plus currency/value where applicable |
| `add_to_cart` | Cart state confirms addition | currency, value, item quantity |
| `view_cart` | Cart is rendered | current currency/value/items |
| `begin_checkout` | First checkout step is reached | currency, value, items |
| `add_shipping_info` | Shipping selection is accepted | shipping tier, currency/value/items |
| `add_payment_info` | Payment method is accepted | coarse payment type, currency/value/items |
| `purchase` | Confirmation is rendered once | transaction ID, currency, value, item/tax/shipping/discount fields |
| `refund` | Refund is confirmed | transaction ID, currency, value, affected items |

Operational commerce remains authoritative. A `purchase` event is measurement evidence and must
reconcile to an order; duplicates are classified and deduplicated by transaction ID.

## SizePath events

| Event | Trigger | Required parameters |
|---|---|---|
| `size_path_cta_impression` | Eligible CTA is actually visible | `placement`, `size_path_version`, eligible product context |
| `size_path_start` | User intentionally opens the flow | `placement`, `size_path_version` |
| `size_path_answer` | A bounded answer is accepted | `question_id`, `answer_band`, `step_number`, `size_path_version` |
| `size_path_complete` | Required questions complete | `recommended_product_id`, `size_path_version` |
| `size_path_recommendation` | Recommendation is rendered | product ID, rank, version, item context |
| `select_item` | Recommended item is clicked | recommendation placement/list and item fields |

Generator version 1.0 predates the final exposure contract: it emits `size_path_open`, three
`size_path_answer` events, and `size_path_recommendation`; product-view sessions are the documented
eligibility proxy. The prototype shows the target `cta_impression`/`start` contract. This limitation
is why the observational study estimates start/use among eligible product views and why a future
experiment must log assignment and exposure explicitly.

## Common parameter registry

| Parameter | Type | Rule |
|---|---|---|
| `event_id` | string | Stable unique event instance; required for duplicate handling |
| `synthetic_session_id` / warehouse `session_key` | string | Canonical session key; never use `ga_session_id` alone |
| `site_market` | enum | AT, DE, FR, NL, GB, or US |
| `page_type` | enum | Controlled page taxonomy |
| `device_category` | enum | mobile, desktop, tablet |
| `placement` | enum | Controlled CTA/list placement |
| `size_path_version` | string | Release identifier used in coverage checks |
| `question_id` | enum | Versioned question identifier, not copied UI text |
| `answer_band` | enum | Coarse controlled response; no exact measurement |
| `recommended_product_id` | string | Fictional catalog ID; required on successful recommendation |
| `transaction_id` | string | Synthetic operational reconciliation key |
| `currency` | ISO 4217 | Transaction currency; never infer from market alone |
| `value` | number | Event-specific documented monetary basis |
| `consent_state` | enum | Captured at collection time |

## Rules and QA

1. Initialize with `window.dataLayer = window.dataLayer || []` before pushing.
2. Push one immutable object per state change; do not read UI text later to reconstruct it.
3. Outcomes such as purchase, return, or satisfaction are not parameters on a feature-start event.
4. Never collect names, birthday, exact child measurements, addresses, precise location, or free
   text. The demo validator rejects these keys recursively.
5. Validate required fields, types, enum values, item arrays, currency, and non-negative value in
   development and monitor coverage by market/device/version after release.
6. Test navigation, reload, duplicate confirmation rendering, consent denial, and delayed events.
7. Derive abandonment from absence of a later milestone within a defined session window; do not
   create fragile `*_exit` events.
