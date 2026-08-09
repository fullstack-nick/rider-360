# Public demo operations

## Endpoints

| Surface | URL | Anonymous expectation |
|---|---|---|
| Metabase dashboard | <https://r360-metabase-e225melpjq-ew.a.run.app/public/dashboard/859cbfd1-f1a9-458b-b2a2-2d1ac7011e53> | `200`; view-only synthetic aggregate cards |
| Dagster asset catalog | <https://r360-dagster-public-e225melpjq-ew.a.run.app> | `200`; webserver runs in read-only mode |
| Dagster operator UI | <https://r360-dagster-admin-e225melpjq-ew.a.run.app> | `403`; Google Cloud IAM required |

The Metabase dashboard has five tabs and 18 validated cards: Executive, Funnel & SizePath, Product
& Inventory, Customers & Growth, and Trust. The Trust tab visibly reports data through 2026-01-01,
critical status `PASS`, and the planted French recommendation-parameter warning. Its public UUID is
stable in the current Metabase application database; the
idempotent bootstrap script recreates the cards, parameters, tab placement, and public link if the
application state is rebuilt.

## Signed-out acceptance evidence

The release acceptance check verifies:

- Metabase application and public-dashboard HTTP `200`;
- public Dagster HTTP `200` and expected Dagster version;
- anonymous Dagster-admin HTTP `403`;
- a public Dagster GraphQL mutation returns `UnauthorizedError`;
- PostgreSQL exposes exactly the seven allowlisted aggregate marts; and
- each PostgreSQL table count exactly equals its authoritative BigQuery table count.

The final post-backfill serving publication is Dagster run
`aa5bb9a7-0801-4daf-8865-d7fb36d18a6c` (`SUCCESS`).

Run it without placing the admin secret on the command line:

```powershell
$env:METABASE_ADMIN_PASSWORD = gcloud secrets versions access latest `
  --secret r360-metabase-admin-password `
  --project tracegate-r7m5o9ld
uv run python scripts/verify_cloud.py `
  --project-id tracegate-r7m5o9ld `
  --metabase-url https://r360-metabase-e225melpjq-ew.a.run.app `
  --dashboard-url https://r360-metabase-e225melpjq-ew.a.run.app/public/dashboard/859cbfd1-f1a9-458b-b2a2-2d1ac7011e53 `
  --dagster-public-url https://r360-dagster-public-e225melpjq-ew.a.run.app `
  --dagster-admin-url https://r360-dagster-admin-e225melpjq-ew.a.run.app `
  --output artifacts/gcp/cloud-acceptance.json
Remove-Item Env:METABASE_ADMIN_PASSWORD
```

To prove authorized admin access, obtain an identity token from the approved operator account and
send it in `Authorization: Bearer …`; never commit or screenshot the token.

## Dashboard rebuild

The bootstrap updates existing cards by name, validates every query, creates or reuses the five tabs,
assigns each card to its expected tab, and verifies the public link:

```powershell
$env:METABASE_ADMIN_PASSWORD = gcloud secrets versions access latest `
  --secret r360-metabase-admin-password --project tracegate-r7m5o9ld
uv run python scripts/metabase_bootstrap.py `
  --url https://r360-metabase-e225melpjq-ew.a.run.app `
  --admin-email admin@rider360.example `
  --db-host 127.0.0.1 `
  --db-name r360_bi `
  --db-user r360-metabase@tracegate-r7m5o9ld.iam `
  --db-iam-auth `
  --output artifacts/gcp/metabase.json
Remove-Item Env:METABASE_ADMIN_PASSWORD
```

This hosted command updates connection metadata that expects the service's Cloud SQL proxy; it does
not connect from the local machine to `127.0.0.1`.

## Outage fallback

Current browser-verified captures are retained in [`docs/screenshots/`](screenshots/). If a public
URL is unavailable, use the screenshot, confirm Cloud Run/Worker Pool and Cloud SQL readiness, then
run the acceptance verifier. Do not weaken the admin IAM boundary or expose the normal Dagster
webserver to recover a demo. A cold start or trial-credit retirement is an availability issue, not
permission to bypass controls.
