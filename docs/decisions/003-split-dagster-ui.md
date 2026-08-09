# ADR 003: Split public and operator Dagster surfaces

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

An anonymous Dagster OSS webserver normally exposes mutation controls. The portfolio needs a public
orchestration view without granting run launch, termination, schedule, sensor, or backfill control.

## Decision

Run two Cloud Run webservers from the same pinned application image and shared Cloud SQL state. The
public service starts with `--read-only` and permits unauthenticated invocation. The admin service
runs normally but requires Cloud Run IAM. Exactly one daemon/code-location pair runs in a private
Cloud Run Worker Pool.

## Consequences

The public UI can demonstrate asset lineage and run evidence while mutations fail. Operators retain
the normal UI through an identity-aware endpoint. The topology has extra containers, so daemon
heartbeat, queued execution, restart recovery, and anonymous mutation denial are acceptance tests.
