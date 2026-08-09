# Business brief

## Stakeholder request

The fictional general manager of Riderly Bikes needs a weekly decision view that connects digital
journey behavior to orders, contribution, product availability, returns, and customer value. The
initial question—whether SizePath works—cannot be answered responsibly without also resolving
funnel reliability, operational authority, maturity, and self-selection.

## Decisions this product supports

| Decision | Evidence | Owner | Decision cadence |
|---|---|---|---|
| Restore or roll back a checkout change | Payment-to-purchase by market/device/release period | Checkout Product + Engineering | Incident / daily |
| Change SizePath prominence | Eligible exposure/start conversion, adjusted association, experiment result, mature fit returns | Digital Product + Experimentation | Test readout |
| Reallocate acquisition spend | Contribution after marketing, CAC, contribution ROAS, mature 365-day contribution | Growth + Finance | Weekly/monthly |
| Fix assortment or merchandising | Views, stockout exposure, compatible attach gap, contribution assumptions | Merchandising + Operations | Weekly |
| Trust or quarantine a reporting slice | Freshness, duplicates, reconciliation, missing parameters, FX coverage | Analytics Engineering | Every run |

## Scope guardrails

Rider 360 is an analytics product, not a storefront, recommendation engine, streaming platform, or
predictive-CLV system. It uses no real tracking and no real personal data. The fixed release window
is 2023-01-01 through 2025-12-31 across AT, DE, FR, NL, GB, and US, normalized to EUR.

## Success criteria

Management should be able to identify the priority issue, understand the evidence and uncertainty,
assign an owner, and define a measurable next action without reading implementation code. An
engineer should be able to regenerate a deterministic fixture, inspect the contracts, run the test
suite, and understand how the cloud demo is deployed and retired.
