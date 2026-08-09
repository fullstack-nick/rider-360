# Executive recommendation memo

**Context:** fixed, fictional 2023-2025 Rider 360 history. Every number below is synthetic.

## Executive position

Do not lead with a SizePath rollout. First restore the broken French mobile payment step and stop
buying contribution-negative volume; then use the now-trusted instrumentation to randomize SizePath
prominence. In parallel, a small compatibility-aware merchandising test offers a bounded low-risk
win.

## 1. Recover French mobile checkout

**Evidence.** French mobile payment-to-purchase fell from 78.0% before the planted release to 53.0%
after it. DE/NL mobile changed from 81.4% to 76.0% over the same periods, leaving a -19.5 pp
difference-in-differences signal. French desktop remained broadly stable. The segment/release
pattern points to a checkout incident rather than broad demand deterioration.

**Action.** Checkout Product and Engineering should reproduce the mobile payment path, compare the
release diff and provider callbacks, roll back or hotfix, and monitor payment-to-purchase by
market/device/release. In the measured synthetic incident sample, returning from 53% toward the
78% pre-rate is roughly **57 recovered purchases per 230 payment sessions**; this is a diagnostic
range, not a forward forecast.

**Success.** French mobile returns within 3 pp of its pre-period rate for two full weeks without a
decline in authorization quality or increase in duplicate confirmations.

## 2. Put contribution guardrails on paid acquisition

**Evidence.** Total contribution after modeled marketing is -€27.85m. Paid Search alone contributes
-€13.64m after €16.04m spend, with €2,960 aggregate CAC proxy and 0.15 contribution ROAS. Paid
Social and Affiliate are also negative. Direct is the only positive channel after modeled spend.

**Action.** Growth and Finance should pause the weakest campaign cells, reconcile spend and
attribution, and re-open budgets only behind contribution-per-acquired-customer and mature cohort
guardrails. A **10-20% reallocation review of the €33.14m combined Paid Search/Social/Affiliate
spend (€3.31m-€6.63m)** is the useful decision envelope; it is spend placed under review, not claimed
profit uplift.

**Success.** No campaign scales with contribution ROAS below its approved threshold; spend/customer
and 365-day contribution are reviewed together, with incomplete cohorts visibly censored.

## 3. Test SizePath; pair it with a bounded attach intervention

**Evidence.** Observed SizePath starters convert 1.59 pp more often after cross-fitted adjustment
(95% CI 1.44-1.74 pp), but the synthetic structural truth is only 1.20 pp. The gap is residual latent
intent, despite strong propensity overlap and post-weighting balance. Mature size returns are 5.1%
for observed users versus 10.9% for non-users, but this is post-purchase descriptive evidence.

**Action.** Digital Product should run the pre-registered 50/50 CTA-prominence experiment in
[`experiment_spec.md`](experiment_spec.md), requiring 51,204 users for a 0.6 pp MDE. Do not treat
completion as randomized. Merchandising can concurrently test compatibility-aware placement for
Ridge 24 and Drift 20: reaching peer attach rates represents about **698 additional attach orders**
and an illustrative **€15.4k contribution** at €22/order.

**Success.** Roll out SizePath only on an acceptable ITT purchase effect with healthy mature fit
returns and complete assignment/exposure logging. Ship accessory placement only if incremental
compatible attach—not generic basket attachment—beats control.

## Data confidence

Operational orders are canonical; raw purchase duplicates are deduplicated and reconciled. All 48
dbt tests passed in the release build, and every one of the seven dashboard serving tables exactly
matched BigQuery row counts at publication. The public Trust tab exposes measurement coverage and
freshness. The inventory-stockout result is not used as a lost-sales claim because generator v1 does
not suppress demand when stock is unavailable.
