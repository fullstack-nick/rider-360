# Reproduction and deployment

## Deterministic local fixture

From a fresh checkout with Python 3.11, `uv`, Docker Desktop, and Node.js:

```powershell
uv sync --frozen --all-groups
uv run rider360 config validate
uv run rider360 generate --profile fixture
uv run rider360 verify-dataset data/generated/fixture
docker compose up -d --build
uv run rider360 publish-local-bi data/generated/fixture `
  --pg-dsn "postgresql://r360_publisher:r360_publisher_local@localhost:54320/r360_bi"
$env:METABASE_ADMIN_PASSWORD = "r360_admin_local_only"
uv run python scripts/metabase_bootstrap.py `
  --url http://localhost:3000 `
  --db-host r360-postgres `
  --db-user r360_metabase `
  --db-password r360_metabase_local
Remove-Item Env:METABASE_ADMIN_PASSWORD
```

The generator writes to `data/generated/fixture`, which is ignored by Git. `manifest.json` contains
the config hash, seed, generator version, file hashes, schemas, and row counts. Run the command twice
and compare the manifests to verify determinism. Stop local services with `docker compose down`; omit
`-v` unless you intentionally want to remove the local application databases.

## Full fixed history and analysis

```powershell
uv run rider360 generate --profile full
uv run rider360 verify-dataset data/generated/full
uv run python analyses/run_sizepath.py
uv run python analyses/run_business_analysis.py
uv run jupyter nbconvert --to notebook --execute analyses/size_path_impact.ipynb `
  --inplace --ExecutePreprocessor.timeout=900 --ExecutePreprocessor.kernel_name=python3
```

The committed CSV/JSON/PNG outputs make analytical claims reviewable without regenerating 450,000
sessions. The executed notebook reads those results and retains its outputs.

## Cloud preflight

Cloud writes are intentionally pinned to the approved incubator. Select the named configuration,
confirm account/project/billing, and capture an inventory before any apply:

```powershell
gcloud config configurations activate rider-360-incubator
gcloud config get-value account
gcloud config get-value project
gcloud billing projects describe tracegate-r7m5o9ld
./scripts/gcp_inventory.ps1 -ProjectId tracegate-r7m5o9ld `
  -OutputPath artifacts/gcp/tracegate-before.json
```

Stop if the project is not `tracegate-r7m5o9ld`, billing is not enabled under the approved Free Trial,
or the expected TraceGate VM/disk/network/firewall baseline differs. Application Default Credentials
must belong to the same approved operator context.

## Terraform foundation and platform

Bootstrap uses a local state only long enough to create the Rider-specific versioned state bucket:

```powershell
terraform -chdir=infra/terraform/bootstrap init
terraform -chdir=infra/terraform/bootstrap plan `
  -var project_id=tracegate-r7m5o9ld -out bootstrap.tfplan
terraform -chdir=infra/terraform/bootstrap apply bootstrap.tfplan
terraform -chdir=infra/terraform/platform init
```

Supply the billing account ID and operator IAM member outside Git. First apply with
`deploy_runtime=false`, bootstrap the three databases/IAM roles with
`scripts/bootstrap_cloud_sql.ps1`, then build and push the Rider image. Resolve its immutable digest
and apply again with `deploy_runtime=true` and that digest. Never deploy `latest`.

```powershell
gcloud auth configure-docker europe-west1-docker.pkg.dev --quiet
docker build -t europe-west1-docker.pkg.dev/tracegate-r7m5o9ld/r360-containers/rider-360:vX.Y.Z .
docker push europe-west1-docker.pkg.dev/tracegate-r7m5o9ld/r360-containers/rider-360:vX.Y.Z
gcloud artifacts docker images describe `
  europe-west1-docker.pkg.dev/tracegate-r7m5o9ld/r360-containers/rider-360:vX.Y.Z `
  --format="value(image_summary.digest)"
```

Terraform requires the full digest-pinned Artifact Registry reference. GitHub Actions builds the
commit SHA, resolves the registry digest, and rolls the same immutable image to both Dagster web
services and the daemon/code worker pool.

## Load, transform, publish

```powershell
uv run rider360 load-bigquery data/generated/full `
  --project-id tracegate-r7m5o9ld `
  --bucket-name r360-data-555370648578
$env:GCP_PROJECT_ID = "tracegate-r7m5o9ld"
uv run dbt build --project-dir . --profiles-dir .
Remove-Item Env:GCP_PROJECT_ID
```

The full Dagster job performs generation/reuse, manifest-verified loading, dbt build/tests, and atomic
BI publication. The narrower `rider360_publish_serving` job republishes only the allowlist after
upstream marts pass. Use the private admin UI for launches/backfills; the public UI cannot mutate.

### Atomic partition backfill

Provide both inclusive bounds to replace only matching physical raw partitions. The loader first
verifies the complete manifest, loads a short-lived Rider-namespaced table, and executes
delete/insert/row-count assertion/commit in one BigQuery transaction. Non-partitioned dimensions are
replaced from the same immutable manifest. Re-run dbt and publish only after the load succeeds:

```powershell
uv run rider360 load-bigquery data/generated/full `
  --project-id tracegate-r7m5o9ld `
  --start-date 2025-12-28 `
  --end-date 2026-01-01
$env:GCP_PROJECT_ID = "tracegate-r7m5o9ld"
uv run dbt build --project-dir . --profiles-dir .
Remove-Item Env:GCP_PROJECT_ID
```

The 2025-12-28 through 2026-01-01 window was executed twice against the hosted raw layer on
2026-08-09. Both runs ended with the same twelve whole-table counts, including 4,523,810 events and
26,565 orders; the subsequent dbt build passed 60/60 nodes and tests. For a Dagster backfill, launch
the full job privately with `rider360/backfill_start` and `rider360/backfill_end` run tags. The
stopped daily schedule and marketing-arrival sensor supply `rider360/lookback_days=4` automatically.

The real arrival contract watches
`gs://r360-data-555370648578/arrivals/marketing/latest.json`. A new GCS object generation requests
one full-pipeline run; the sensor cursor prevents duplicate requests for the same generation. Both
the schedule and sensor are stopped by default so enabling automation is an explicit operator act.

## Post-deployment acceptance

Re-run the inventory and containment verifier, Terraform plan, and cloud acceptance:

```powershell
./scripts/gcp_inventory.ps1 -ProjectId tracegate-r7m5o9ld `
  -OutputPath artifacts/gcp/tracegate-after.json
./scripts/verify_containment.ps1
terraform -chdir=infra/terraform/platform plan -detailed-exitcode <the same external vars>
```

Exit code `0` from the Terraform plan is required for no drift; exit code `2` means changes remain.
Use [`public_demo.md`](public_demo.md) for the endpoint/reconciliation verifier and dashboard rebuild.
