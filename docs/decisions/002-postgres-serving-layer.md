# ADR 002: Serve Metabase from PostgreSQL

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

BigQuery is the authoritative warehouse, but a direct Metabase OSS BigQuery connection requires a
Google credential payload that conflicts with the no-long-lived-service-account-key rule.

## Decision

dbt builds canonical physical marts in BigQuery. Dagster copies only a reviewed seven-table
aggregate allowlist into PostgreSQL `r360_bi`, reconciles the copy, and promotes it atomically.
Metabase connects to PostgreSQL through Cloud SQL's automatic IAM database authentication.

## Consequences

There is a small, replaceable serving copy and one extra publication step. In return, Metabase has
no BigQuery access or Google key, dashboard queries are predictable, raw/pseudonymous rows stay out
of the BI surface, and KPI logic remains in one authoritative dbt layer.
