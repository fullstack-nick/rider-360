# Data quality runbook

## Service objective

Publish a new `r360_bi` snapshot only when the source manifest, critical dbt tests, operational
reconciliation, and cross-engine serving counts pass. Warnings may publish with a documented
degraded status; critical failures must leave the previous PostgreSQL snapshot readable.

## Responsibilities

| Layer | Primary checks | Owner |
|---|---|---|
| Generator | Config validity, deterministic IDs, source coherence, manifest hashes/counts | Data Product Engineering |
| Ingestion | Required files/partitions, schema compatibility, manifest-versus-BigQuery counts | Analytics Engineering |
| dbt | Unique/not-null/relationship tests, funnel monotonicity, non-negative economics, purchase/order reconciliation | Analytics Engineering |
| Dagster | Dependencies, asset/check state, run metadata, retry/backfill, publication gate | Data Platform |
| BI publication | Allowlist, staging load, row counts, atomic promotion, public-card queryability | Analytics Engineering |
| Business owner | Plausibility, release annotations, decision impact | Named metric owner |

## Severity policy

- **Critical:** missing required source partition, manifest/hash mismatch, schema break, duplicate
  canonical key, operational order mismatch outside accepted classification, missing FX on a
  published commercial row, failed dbt build, or BigQuery/PostgreSQL reconciliation difference.
  Block publication and page the analytics owner.
- **Warning:** late partition inside the allowed lookback, segment-level parameter coverage below
  threshold, unusual but plausible volume, or a non-critical freshness delay. Publish only when the
  warning is explicitly recorded and the affected interpretation remains safe.
- **Information:** expected duplicate raw purchase emission that is successfully deduplicated,
  planned backfill, or a threshold near miss with no consumer impact.

Thresholds must be segmented by market/device/release where a global average could conceal a total
failure. The French mobile SizePath parameter regression is the reference case.

## Routine checks

```powershell
uv run rider360 config validate
uv run rider360 verify-dataset data/generated/fixture
uv run dbt build --project-dir . --profiles-dir .
uv run pytest
uv run python scripts/verify_cloud.py `
  --project-id tracegate-r7m5o9ld `
  --metabase-url https://r360-metabase-e225melpjq-ew.a.run.app `
  --dashboard-url https://r360-metabase-e225melpjq-ew.a.run.app/public/dashboard/859cbfd1-f1a9-458b-b2a2-2d1ac7011e53 `
  --dagster-public-url https://r360-dagster-public-e225melpjq-ew.a.run.app `
  --dagster-admin-url https://r360-dagster-admin-e225melpjq-ew.a.run.app
```

For a hosted run, confirm the Dagster asset/check graph is green, compare the latest successful run
ID with the PostgreSQL publication evidence, and inspect the Metabase Trust tab. The current
acceptance verifier checks anonymous/public HTTP status, private-admin denial, public GraphQL
mutation denial, and exact BigQuery/PostgreSQL row counts for all seven serving marts.

Query `r360_audit.audit_check_results`, `audit_source_freshness`, `audit_reconciliation`, and
`audit_job_costs` for the current observed values, thresholds, latest partition, data-through date,
and bytes processed. A `warning` is visible but does not masquerade as a critical failure; the
planted recommendation-parameter regression is the reference example.

## Incident procedure

1. **Detect and contain.** Stop the schedule if a critical condition can repeat. Do not delete or
   overwrite the previous serving schema.
2. **Classify.** Record affected source, date/market/device/version, first bad partition, metric
   impact, severity, and whether the issue is source, transformation, publication, or display.
3. **Prove the boundary.** Compare manifest → raw → canonical → mart → PostgreSQL counts and a
   selected additive total. Operational orders win disputes about commerce facts.
4. **Correct at the owning layer.** Never patch a KPI in Metabase or the serving database.
5. **Backfill idempotently.** Re-run the same code/config over the smallest safe date range plus the
   recent four-day late-arrival lookback. Return and cohort changes may require the original order
   cohort range, not only the return date.
6. **Validate and publish.** Run critical dbt tests/checks, publish to a new staging schema, reconcile,
   and promote transactionally.
7. **Close.** Record root cause, affected decisions, permanent test/threshold, data-through time,
   and whether screenshots/public notes need refresh.

## Common cases

| Symptom | First checks | Safe response |
|---|---|---|
| Orders exceed canonical purchase events | `audit_reconciliation`, delayed/blocked events, consent | Keep orders canonical; classify rather than force equality |
| Raw purchases exceed orders | Duplicate transaction IDs, test traffic, missing order mapping | Deduplicate; quarantine unclassified gap |
| Revenue shifted after rerun | FX date, order-version selection, return restatement | Rebuild affected orders/cohorts and explain accounting date basis |
| Recommendation missing rate spikes | Version × market × device coverage | Mark affected SizePath slice degraded; fix instrumentation |
| Funnel stage increases downstream | Sessionization, event timestamps, duplicate milestones | Block the mart; do not “fix” by clipping counts |
| PostgreSQL count differs | Partial staging load, schema/type failure, source changed mid-copy | Roll back; previous `r360_bi` stays live; retry from a stable source |
| Public Dagster mutation succeeds | Read-only process args/revision/IAM | Treat as critical security incident; remove public invoker until fixed |

## Backfills

Use the same full-pipeline job and contracts as the daily run. Pin the config version and pass the
inclusive range as `rider360/backfill_start` and `rider360/backfill_end` run tags, or use the typed CLI
flags documented in `reproduction.md`. The loader uses an atomic partition-replacement transaction;
rebuild downstream dbt models and publish only after all checks pass. Never run two overlapping
publications. Schedule and sensor state are stopped by default in this portfolio demo; an operator
deliberately enables them after checking trial credit and runtime health.
