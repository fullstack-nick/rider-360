# Rider 360

[![CI](https://github.com/fullstack-nick/rider-360/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/fullstack-nick/rider-360/actions/workflows/ci.yml)

Rider 360 is a fictional, fully synthetic end-to-end analytics product for a global
children's cycling retailer. It connects coherent GA4-shaped journeys and operational commerce
facts to BigQuery, dbt, Dagster, an atomic PostgreSQL serving layer, and a public Metabase review.

> Every brand, product, person, event, order, and commercial result in this repository is invented.
> No real customer or company data is used, modeled, or implied.

The management question is concrete: **does the fictional SizePath recommendation journey improve
conversion and product fit, where is the broader funnel leaking, and which product or acquisition
actions deserve priority?** The answer is deliberately evidence-led: trust the data first, separate
association from causality, quantify decisions, and leave a reproducible operating path.

## Live public demo

- [Five-tab Metabase weekly review](https://r360-metabase-e225melpjq-ew.a.run.app/public/dashboard/859cbfd1-f1a9-458b-b2a2-2d1ac7011e53)
- [Read-only Dagster asset catalog](https://r360-dagster-public-e225melpjq-ew.a.run.app)
- The Dagster operator UI is intentionally private and returns `403` to anonymous visitors.

![Hosted Rider 360 dashboard](docs/screenshots/metabase-hosted.png)

## What the evidence says

- The French mobile payment-to-purchase rate fell from **78.0% to 53.0%**; a DE/NL mobile control
  gives a synthetic difference-in-differences estimate of **-19.5 percentage points**.
- Paid Search is the largest modeled profitability problem: **-€13.64m contribution after
  marketing** in the fixed three-year history. This is a deliberately planted synthetic scenario.
- Starting SizePath is associated with **+1.59 pp conversion** after observed adjustment, while the
  generator's hidden structural truth is **+1.20 pp**. The remaining gap demonstrates residual
  confounding; it is evidence to run a randomized test, not a causal launch claim.
- Ridge 24 and Drift 20 together show about **698 incremental compatible accessory orders** at
  their peer attachment rates, worth an illustrative **€15.4k** at €22 contribution per order.

The methods and outputs are in [`analyses/`](analyses/); the concise management narrative is in
[`docs/executive_recommendations.md`](docs/executive_recommendations.md) and the seven-slide deck is
[`docs/executive/Rider_360_Executive_Decision_Deck.pptx`](docs/executive/Rider_360_Executive_Decision_Deck.pptx).

## Architecture

```mermaid
flowchart LR
    C["Versioned synthetic contracts"] --> G["Deterministic Python generator"]
    G --> P["Manifest-verified Parquet"]
    P --> D["Dagster assets, schedule, arrival sensor, and checks"]
    D --> BQ["BigQuery partitioned raw → staging → core → marts + audit"]
    BQ --> PG["Atomic allowlisted PostgreSQL snapshot"]
    PG --> MB["Public five-tab Metabase review"]
    BQ --> A["SQL + SizePath notebook"]
    A --> E["Executive decisions"]
```

BigQuery is authoritative. Metabase has no BigQuery permission or service-account key; Dagster
publishes only seven approved aggregate marts to PostgreSQL and reconciles their row counts. The
public Dagster process is read-only, while the admin service requires Google Cloud IAM. See
[`docs/architecture.md`](docs/architecture.md) for the deployment and trust boundaries.

## Reproduce the fixture locally

Prerequisites: Python 3.11, [`uv`](https://docs.astral.sh/uv/), Docker Desktop, and Node.js.

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
```

Open Metabase at <http://localhost:3000>, Dagster admin at <http://localhost:3001>, and the local
read-only Dagster UI at <http://localhost:3002>. The fixture contains 10,000 deterministic sessions
and can be regenerated without changing its manifest hashes. Full cloud reproduction and backfill
commands are in [`docs/reproduction.md`](docs/reproduction.md).

## Explore the instrumentation contract

```powershell
python -m http.server 8088 --bind 127.0.0.1 --directory demo/data-layer
node scripts/validate_demo.mjs
```

Visit <http://127.0.0.1:8088>. The page writes validated fictional events only to
`window.dataLayer`, rejects PII-like fields, and never loads a tracking endpoint.

![Rider 360 dataLayer lab](docs/screenshots/data-layer-demo.png)

## Repository guide

| Path | Purpose |
|---|---|
| [`PROJECT_PLAN.md`](PROJECT_PLAN.md) | Discovery, accepted decisions, roadmap, and definition of done |
| [`config/`](config/) | Generator, market, catalog, channel, and scenario contracts |
| [`src/rider360/generator/`](src/rider360/generator/) | Deterministic coherent source generator |
| [`models/`](models/) | dbt staging, intermediate, marts, and audit models |
| [`src/rider360/orchestration/`](src/rider360/orchestration/) | Dagster assets, checks, jobs, four-day schedule, and GCS arrival sensor |
| [`src/rider360/warehouse/publisher.py`](src/rider360/warehouse/publisher.py) | Atomic BigQuery-to-PostgreSQL publication |
| [`scripts/metabase_bootstrap.py`](scripts/metabase_bootstrap.py) | Idempotent OSS dashboard creation and validation |
| [`analyses/`](analyses/) | Versioned SQL, executed notebook, and reviewable results |
| [`demo/data-layer/`](demo/data-layer/) | Zero-network instrumentation prototype |
| [`infra/terraform/`](infra/terraform/) | Rider-scoped GCP foundation and runtime |
| [`docs/`](docs/) | Contracts, runbooks, decisions, screenshots, and management artifacts |

## Development checks

```powershell
uv run ruff check .
uv run dbt parse --project-dir . --profiles-dir .
uv run pytest
node scripts/validate_demo.mjs
uv run python scripts/verify_public_release.py
terraform -chdir=infra/terraform/bootstrap fmt -check
terraform -chdir=infra/terraform/platform fmt -check
docker build -t rider-360:verify .
```

Cloud writes require an explicit project/configuration preflight; no pull request receives cloud
credentials. See [`docs/public_demo.md`](docs/public_demo.md),
[`docs/costs_and_cleanup.md`](docs/costs_and_cleanup.md), and
[`docs/known_limitations.md`](docs/known_limitations.md) before operating the hosted demo.

## License

Project-authored code and documentation are MIT licensed. Third-party runtimes retain their own
licenses. The public-release review uses only project-authored visual assets and synthetic content.
