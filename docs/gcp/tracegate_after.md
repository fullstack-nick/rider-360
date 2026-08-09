# TraceGate post-deployment containment evidence

The post-deployment inventory was captured from `tracegate-r7m5o9ld` after the Rider 360 demo became
healthy. The machine-readable JSON remains local under `artifacts/gcp/` because raw cloud metadata
can contain operator details; this document retains the public-safe evidence.

## Preserved pre-existing baseline

- Compute VM and 30 GiB disk: `tracegate-vm`, still present and outside Rider Terraform state.
- Network: `default`, with no Rider VPC, subnet, route, or peering created.
- Firewall rules: `default-allow-icmp`, `default-allow-internal`, `default-allow-rdp`,
  `default-allow-ssh`, `tracegate-v0-1-http`, and `tracegate-v0-1-ssh`.
- TraceGate VM and default Compute Engine service accounts remain present and are not used by Rider.

`scripts/verify_containment.ps1` requires these exact compute/network/firewall names and fails if the
baseline changes.

## Rider resources added

| Type | Rider resources |
|---|---|
| BigQuery EU datasets | `r360_raw`, `r360_staging`, `r360_intermediate`, `r360_marts`, `r360_audit` |
| Cloud Storage EU | `r360-tfstate-555370648578`, `r360-data-555370648578` |
| Cloud SQL | `r360-pg-demo` with `r360_metabase`, `r360_dagster`, and `r360_bi` databases |
| Cloud Run services | `r360-metabase`, `r360-dagster-public`, `r360-dagster-admin` |
| Cloud Run Worker Pool | `r360-dagster-daemon` |
| Artifact Registry | `r360-containers` |
| Secret Manager | `r360-metabase-admin-password`, `r360-metabase-encryption-key` |
| Service accounts | `r360-metabase`, `r360-dagster`, `r360-deployer` |
| Custom IAM | `r360BigQueryJobReader` (`bigquery.jobs.list` only, bound to `r360-dagster`) |
| Keyless deployment | `r360-github` workload identity pool and `r360-github-oidc` provider |
| Cost control | `Rider 360 demo alerts only` billing budget |

The Terraform platform state lists only Rider resources plus a read-only host-project data source.
It does not contain the TraceGate VM, disk, VPC, firewall rules, or existing service accounts. Added
project IAM grants are scoped to the three Rider service accounts. Metabase has Cloud SQL roles and
no BigQuery role.

## Verification

```powershell
./scripts/gcp_inventory.ps1 -ProjectId tracegate-r7m5o9ld `
  -OutputPath artifacts/gcp/tracegate-after.json
./scripts/verify_containment.ps1 `
  -InventoryPath artifacts/gcp/tracegate-after.json
terraform -chdir=infra/terraform/platform state list
```

Expected result: the containment verifier reports the TraceGate baseline intact and every added
durable resource inside the Rider namespace. A separate zero-change Terraform plan proves there is
no unmanaged Rider drift at handoff.

## Final release verification

Verified on 2026-08-09 after the public GitHub deployment:

- immutable Rider image:
  `sha256:7ef35c25292d2deae3cafa8a3bec61e3bc4fa8d38e751ec7a449669df01a889d`;
- ready revisions: public `r360-dagster-public-00005-cxs`, admin
  `r360-dagster-admin-00005-ft6`, and worker `r360-dagster-daemon-00006-5cg`;
- the [deployment workflow](https://github.com/fullstack-nick/rider-360/actions/runs/31334812490)
  completed successfully using keyless federation;
- the corrected [clean-checkout CI run](https://github.com/fullstack-nick/rider-360/actions/runs/31335029140)
  passed both jobs; and
- the post-rollout containment check passed and Terraform reported `No changes` with zero additions,
  updates, or destroys.
