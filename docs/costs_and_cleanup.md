# Costs, credit safety, and cleanup

## Spend posture

The current host is verified as billing-enabled under the owner's Free Trial. The owner approved use
of the available trial credit without an artificial project budget ceiling; this does **not**
authorize a paid upgrade or post-trial charges. An alerts-only Rider 360 billing budget exists at
50%, 90%, and 100% thresholds. Because the host project is shared and not every Google charge is
guaranteed to inherit a user label, label-filtered analysis and project-total billing are both needed.

All supported Rider resources carry `application=rider-360`, `environment=demo`,
`managed_by=terraform`, and `data_classification=synthetic` labels where the service supports them.

## Cost drivers

| Driver | Current shape | Cost behavior / control |
|---|---|---|
| Cloud SQL PostgreSQL | Zonal Enterprise, 1 vCPU / 3.75 GiB, 20 GiB SSD, backups + PITR | Largest always-on fixed component; one instance hosts three isolated databases |
| Dagster Worker Pool | One 1 vCPU / 2 GiB daemon plus one 1 vCPU / 2 GiB code sidecar and proxy | Continuous while the pool has one instance; stop only as a deliberate demo-state change |
| Public Dagster Cloud Run | Min 1, max 1; web/code/proxy containers | Predictable demo response; lower min to zero when cold starts are acceptable |
| Metabase Cloud Run | Min 1, max 1; 1 vCPU / 2 GiB plus proxy | Predictable demo response; lower min to zero outside portfolio review windows |
| Private Dagster admin | Min 0, max 1 | Request-driven; IAM-protected |
| BigQuery | 450k-session load, physical dbt marts, EU | Storage plus query bytes; atomic bounded partition replacement, partition pruning, fixed history, and dbt model selection limit scans |
| Cloud Storage | Versioned Parquet/artifacts in EU; older objects transition after 90 days | Small for this release; versions/soft-delete can retain bytes |
| Artifact Registry | Rider image plus keep-10 cleanup policy | Bounded image storage |
| Secret Manager/logging | Two application secrets and normal demo logs | Low volume; avoid verbose payload logging |

Exact prices vary by region, currency, discounts, and product changes. Use the official Google Cloud
pricing pages/calculator and the billing report for the account rather than treating a static estimate
in this repository as an invoice.

The `audit_job_costs` model exposes Rider-attributed BigQuery job bytes for the latest 30-day
window. Review it after a full rebuild or backfill: bounded raw replacements reduce source-write
scope, while the current portfolio-scale dbt build still recomputes its physical marts in full.

## Low-cost operating mode

When a responsive live portfolio demo is not needed, set Metabase and public Dagster minimum
instances to zero and deliberately scale the Worker Pool to zero after disabling schedules. The
dashboard will be unavailable if the daemon is stopped only during a publication; wait for runs to
finish. Cloud SQL remains the main fixed cost unless the entire environment is retired.

## Expiry and cleanup runbook

Cleanup is intentionally not a one-line broad delete. The platform has `prevent_destroy` on Cloud
SQL, BigQuery datasets, and buckets so an accidental Terraform destroy fails closed.

1. Confirm the exact project/configuration and take a final machine-readable inventory.
2. Disable Dagster schedules/sensors, wait for active runs/publications, and capture final screenshots.
3. Export only the synthetic Metabase/Dagster application state if preserving the demo is desired.
4. Produce and review a Terraform destroy plan that contains Rider resources only. Verify every
   target is named `r360-`/`r360_`; the TraceGate VM, disk, default network, and firewall rules must
   not appear.
5. With fresh explicit approval, remove `prevent_destroy` only from the exact Rider resources being
   retired, apply in dependency order, and confirm deletions. Do not use wildcard CLI deletion.
6. Retain or delete the Rider state bucket last, through a separately reviewed bootstrap-state
   procedure. Enabled APIs use `disable_on_destroy=false` because disabling a shared-project API
   could affect unrelated workloads.
7. Run the inventory again and prove that the TraceGate baseline remains intact. Record whether the
   removed data is recoverable from bucket versioning/soft delete or Cloud SQL backups.

Migration to a dedicated billed Rider project uses fresh Terraform state and regeneration of the
synthetic warehouse. It never moves or imports unrelated TraceGate resources.
