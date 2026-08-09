# TraceGate before-state and containment baseline

Captured before the first Rider 360 cloud mutation on 2026-08-08.

The approved incubator is the billed, active GCP project `tracegate-r7m5o9ld` (project number `555370648578`). Rider 360 does not own the project itself and Terraform must never attempt to manage or destroy it.

Pre-existing resources that are explicitly outside Rider 360 scope:

- Compute Engine VM `tracegate-vm` (`e2-micro`, `us-west1-a`), its 30 GB persistent disk, and its dedicated service account.
- The default VPC, routes, subnets, and default firewall rules.
- Firewall rules `tracegate-v0-1-http` and `tracegate-v0-1-ssh`.
- Google-managed project service agents and the default Compute Engine service account.

At capture time, no BigQuery datasets, Cloud Storage buckets, Cloud Run services, Cloud SQL instances, Artifact Registry repositories, Pub/Sub topics, or Secret Manager secrets were detected. The corresponding APIs were disabled where noted during discovery.

Containment rules:

- Rider resource names use `r360-`; BigQuery datasets and PostgreSQL schemas use `r360_`.
- Rider services do not attach to or modify the default VPC.
- Every supported resource carries Rider 360 labels.
- Terraform states contain only Rider-specific resources and enabled APIs; the host project is a data source, never a resource.
- Pre- and post-deployment inventories are compared before handoff.
- A future move to the dedicated Rider project uses a new Terraform state and data migration; it never repoints the TraceGate state.

The machine-readable capture is generated locally with `scripts/gcp_inventory.ps1` and intentionally excluded from Git because full cloud metadata can contain account-specific fields.
