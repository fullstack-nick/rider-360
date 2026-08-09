# Data contracts

All rows are fictional and generated from versioned rules. The fixed full profile covers
2023-01-01 through 2025-12-31; the fixture covers 2025-01-01 through 2025-01-30. A manifest records
the generator version, config hash, seed, row counts, file hashes, and profile.

## Source contracts

| Source table | Grain | Stable key | Partition/date | Authority |
|---|---|---|---|---|
| `events` | One emitted event instance | `event_id` | `event_date` | Behavioral sequence and feature exposure |
| `orders` | One operational order version | `order_id` | Local order date from `placed_at` | Order existence, status, customer, totals |
| `order_items` | One operational order line | `order_item_id` | Parent order date | Quantity, price, discounts, tax, COGS |
| `returns` | One returned order-line record | `return_id` | `received_at`/parent order date | Return outcome, reason, refund |
| `products` | One SKU validity interval | `sku`, `valid_from` | `valid_from` | Product attributes and cost basis |
| `product_market_prices` | One SKU/market validity interval | `sku`, `site_market`, `valid_from` | `valid_from` | Local list price and currency |
| `product_accessory_compatibility` | One parent/accessory rule | parent SKU, accessory SKU | Snapshot | Compatibility, not mere co-occurrence |
| `inventory_daily` | One SKU/market/day | `sku`, `site_market`, `inventory_date` | `inventory_date` | Availability and stockout exposure |
| `marketing_spend` | One campaign/market/channel/day | `campaign_id`, `site_market`, `spend_date` | `spend_date` | Spend and clicks |
| `exchange_rates` | One source/reporting-currency/day | currencies, `rate_date` | `rate_date` | EUR conversion |
| `customers` | One known synthetic purchaser | `customer_id` | `first_order_date` | First known acquisition and cohort |
| `source_delivery_log` | One source partition delivery | source, partition | partition date | Expected/actual delivery and checksum |

The raw event shape deliberately mirrors the subset of GA4 export used here: microsecond event
timestamp, event date, pseudo/user identity, stream/platform/device/browser, country, privacy state,
traffic-source fields, repeated key/value `event_params`, and repeated `items`. It is not presented
as an exact GA4 emulator.

## Canonical grain contracts

| Model | Grain | Contract |
|---|---|---|
| `stg_events` | Deduplicated `event_id` | Typed fields and governed parameter extraction; original arrays remain raw-only |
| `int_sessions` | `session_key` | Session attribution and milestone flags; `ga_session_id` alone is never unique |
| `int_purchase_events` | `transaction_id` | Duplicate purchase emissions collapse to one canonical transaction |
| `int_orders_enriched` | `order_id` | Operational order is authoritative; contribution, FX, returns, and channel are joined |
| `mart_executive_daily` | day × market × channel | Additive sessions/orders/revenue/cost/spend inputs plus display ratios |
| `mart_funnel_daily` | day × market × device × channel | Valid core-commerce stage counts |
| `mart_sizepath_daily` | day × market × device × observed-use flag | Descriptive conversion and mature size-return components |
| `mart_inventory_daily` | day × market × SKU | Availability, units, stockout minutes, and product attributes |
| `mart_accessory_attach_daily` | day × market × parent product | Compatibility-aware attach counts |
| `mart_customer_ltv` | cohort month × acquisition market × channel | Observed/90-day/365-day realized contribution components |
| `mart_data_quality_daily` | day × market | Public-safe event, parameter, lateness, and FX health |

Only the seven `mart_*` relations above are eligible for PostgreSQL publication. Raw events,
pseudonymous users, customer IDs, order IDs, and operational payloads are prohibited from the public
BI serving layer.

The mature SizePath mart exposes both `mature_size_return_sessions` and `mature_order_sessions` so
filtered return rates are recomputed from additive components rather than averaged percentages.

## Audit and operational contracts

| Model | Grain | Purpose |
|---|---|---|
| `audit_reconciliation` | warehouse snapshot | Canonical purchases versus operational orders and missing FX |
| `audit_source_freshness` | source | Latest delivered partition, row count, latency, data-through date, and status |
| `audit_check_results` | named check | Current pass/warning/fail outcome, observed value, threshold, and explanation |
| `audit_job_costs` | BigQuery job | Rider-labeled/commented 30-day bytes processed/billed, state, timing, and destination |

Audit tables stay in authoritative BigQuery and are never copied into the public BI schema. The
Trust tab exposes only reviewed aggregate health fields from `mart_data_quality_daily`.

## Money contract

- Source amounts are integer minor units in the transaction currency.
- BigQuery transformations convert to decimal EUR with the exchange rate for the relevant business
  date. Missing FX never silently becomes 1.0.
- Gross item sales exclude tax and shipping. Net item revenue is gross item sales minus item
  discounts and refunded/returned item amount. Contribution margin is net item revenue minus
  variable product/fulfilment cost. Contribution after marketing subtracts marketing spend.
- Booked operational views use order date. Return/CLV analyses restate mature returns to the order
  cohort; operational return activity may instead use the return date and must say so.

## Time and maturity contract

Event timestamps and ingestion timestamps are UTC instants. `event_date` and reporting dates use the
store market's local timezone; the synthetic property timezone is Europe/Vienna. Daily processing
rebuilds at least the recent four event-date partitions so late arrivals are included. Returns and
return-adjusted comparisons require 60 days of observation. A cohort is never ranked on a 365-day
metric until that horizon is observable.

## Identity and privacy contract

`session_key` is the canonical visit key. `user_pseudo_id` represents a fictional browser/device;
`customer_id` exists only when a synthetic known-purchaser link is present. Cross-device identity is
not inferred. New visitor and first-time purchaser are separate concepts. Hidden `latent_intent` and
counterfactual truth fields may exist only in the generator validation artifact and analysis extract;
they are excluded from analytical marts and public serving tables.

No source field may contain a real name, birthday, email, phone, address, precise location, or free
text. SizePath uses coarse bands in the instrumentation contract.
