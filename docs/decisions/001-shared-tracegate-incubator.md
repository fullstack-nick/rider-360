# ADR 001: Use TraceGate as a contained incubator

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

The intended dedicated Rider 360 project could not be attached to the active Free Trial billing
account because the billing-account project-link quota was already reached. Existing billed
projects contain live resources and were not safe to detach.

## Decision

Deploy Rider 360 temporarily inside `tracegate-r7m5o9ld` with Rider-only Terraform state,
`r360-`/`r360_` namespaces, synthetic-data labels, additive IAM, and an explicit pre/post inventory.
The host project and every pre-existing TraceGate resource are data sources or out of scope—not
Terraform resources.

## Consequences

The project-level billing, quota, IAM inheritance, and log perimeter are shared. Resource-level
naming, labels, identities, datasets, databases, services, storage, and state remain isolated. A
future dedicated-project migration uses fresh state and regenerated synthetic data; it never
repoints or imports TraceGate resources.
