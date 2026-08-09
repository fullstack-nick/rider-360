# Governed metric dictionary

Percentages are always recomputed from additive numerator/denominator columns after filtering.
Precomputed percentages must never be averaged. Unless stated otherwise, commercial reporting uses
market-local order date, EUR, tax-exclusive item economics, and all six markets.

| Metric | Definition | Grain / denominator | Exclusions and maturity | Owner |
|---|---|---|---|---|
| Eligible ecommerce sessions | Distinct canonical sessions with valid storefront activity | `session_key` | Invalid consent, bot/test/internal, malformed session key | Digital Analytics |
| Product-view sessions | Eligible sessions reaching `view_item` | Eligible sessions | Same eligibility policy | Digital Analytics |
| Add-to-cart rate | Sessions with `add_to_cart` / product-view sessions | Recomputed for selected slice | No event-row denominator | Ecommerce Product |
| Checkout-start rate | Sessions with `begin_checkout` / cart sessions | Canonical session flags | Same-session progression | Checkout Product |
| Payment-to-purchase rate | Sessions with canonical purchase / sessions with accepted payment info | Market/device/release period | Deduplicated transactions; operational order reconciliation | Checkout Product |
| Session conversion | Operational orders mapped to sessions / eligible sessions | Day × market × channel components | One order can exist only once; GA4 duplicates do not add orders | Commercial Analytics |
| Orders | Count of latest non-test operational `order_id` | Order date | Canceled/test excluded by staging policy | Commerce Operations |
| Gross item sales | Sum item unit price × quantity before item discount, excluding tax/shipping | Order/item | Operational lines only | Finance |
| Net item revenue | Gross item sales − item discounts − refunded item amount | EUR; order or return accounting date view must be named | Return maturity stated where cohort-restated | Finance |
| Average order value | Gross or net revenue basis explicitly named / operational orders | Filtered aggregate | Never average daily AOV | Finance |
| Contribution margin | Net item revenue − variable product/fulfilment cost | EUR | Tax excluded | Finance |
| Contribution after marketing | Contribution margin − attributed marketing spend | EUR, channel/date | Unmatched spend remains visible | Growth Finance |
| CAC proxy | Marketing spend / purchasing customers in the same governed acquisition slice | Channel and period | Dashboard aggregate is an observed proxy; cohort acquisition is preferred | Growth Finance |
| Contribution ROAS | Contribution margin / marketing spend | Channel and period | Null when spend is zero | Growth Finance |
| SizePath start rate | Sessions with start/open / eligible CTA-impressed sessions | Eligible session | Generator v1 uses product view as eligibility proxy | Digital Product |
| SizePath completion rate | Sessions completing required questions / started sessions | Started session | Requires complete versioned answer sequence | Digital Product |
| SizePath recommendation CTR | Sessions selecting a recommended item / recommendation impressions | Recommendation exposure | Controlled recommendation list/placement | Digital Product |
| SizePath observed conversion difference | Conversion among observed starters/users − non-starters among eligible sessions | Eligible product-view session | Association only; report adjustment, overlap, CI, and hidden truth separately | Experimentation |
| Mature size-return rate | Sessions/orders with a size-related returned line / mature purchased sessions/orders | Order cohort | At least 60 days observable; post-purchase comparison is descriptive | Product Quality |
| Compatible accessory attach | Bike orders with ≥1 compatible accessory / bike orders | Parent product/market | Compatibility registry, not any accessory | Merchandising |
| Stockout exposure | Sum stockout minutes / available product minutes | SKU × market × date | Operational evidence; generator v1 does not suppress sales from stock state | Inventory Operations |
| Realized contribution LTV 90d/365d | Cohort contribution within horizon / acquired customers | Cohort month × acquisition market/channel | Rank only cohorts old enough for the horizon | Lifecycle Analytics |
| Purchase reconciliation gap | Canonical purchase transactions without orders plus orders without purchase events | Run / partition | Classified; operational orders remain authoritative | Analytics Engineering |
| Recommendation parameter missing rate | Recommendation events missing product ID / recommendation events | Day × market × device × version | Empty denominator is null, not zero | Analytics Engineering |
| Data through | Maximum successfully published `metric_date` across approved serving marts | Publication | Must refer to latest successful publication | Analytics Engineering |

The Metabase card SQL lives in [`scripts/metabase_bootstrap.py`](../scripts/metabase_bootstrap.py);
the authoritative transformations live in [`models/`](../models/). Any display label that changes a
definition requires a matching update here and in model documentation.
