import json
import os
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import dagster as dg
import psycopg
from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets
from google.cloud import bigquery, storage

from rider360.constants import PROJECT_ROOT
from rider360.generator.engine import generate_dataset
from rider360.warehouse.bigquery import load_local_parquet
from rider360.warehouse.publisher import PUBLISH_ALLOWLIST, publish_marts

DBT_PROJECT = DbtProject(
    project_dir=PROJECT_ROOT,
    profiles_dir=PROJECT_ROOT,
    target_path=PROJECT_ROOT / "target",
)
DBT_PROJECT.prepare_if_dev()


def _dataset_dir() -> Path:
    configured = os.getenv("R360_DATASET_DIR")
    if configured:
        return Path(configured)
    profile = os.getenv("R360_GENERATION_PROFILE", "fixture")
    return PROJECT_ROOT / "data" / "generated" / profile


@dg.asset(
    name="synthetic_sources",
    group_name="ingestion",
    kinds={"python", "parquet"},
    description="Deterministic fictional source extracts and truth manifest.",
    automation_condition=dg.AutomationCondition.missing(),
)
def synthetic_sources(context: AssetExecutionContext) -> dg.MaterializeResult:
    destination = _dataset_dir()
    manifest_path = destination / "manifest.json"
    if not manifest_path.exists():
        profile = os.getenv("R360_GENERATION_PROFILE", "fixture")
        result = generate_dataset(profile, output_dir=destination)
        counts = result.counts
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        counts = {name: int(details["row_count"]) for name, details in manifest["tables"].items()}
        context.log.info("Reusing immutable source manifest at %s", manifest_path)
    return dg.MaterializeResult(
        metadata={
            "manifest_path": dg.MetadataValue.path(str(manifest_path)),
            "event_rows": counts.get("events", 0),
            "order_rows": counts.get("orders", 0),
            "table_count": len(counts),
        }
    )


@dg.asset_check(asset=synthetic_sources, name="manifest_contract")
def synthetic_manifest_contract() -> dg.AssetCheckResult:
    path = _dataset_dir() / "manifest.json"
    if not path.exists():
        return dg.AssetCheckResult(passed=False, metadata={"reason": "manifest missing"})
    manifest = json.loads(path.read_text(encoding="utf-8"))
    tables = manifest.get("tables", {})
    required = {
        "events",
        "orders",
        "order_items",
        "returns",
        "products",
        "inventory_daily",
        "marketing_spend",
        "exchange_rates",
    }
    missing = sorted(required - set(tables))
    session_starts = int(manifest.get("target_sessions", 0))
    passed = not missing and int(tables.get("events", {}).get("row_count", 0)) > session_starts
    return dg.AssetCheckResult(
        passed=passed,
        metadata={"missing_tables": missing, "target_sessions": session_starts},
    )


@dg.asset(
    deps=[synthetic_sources],
    group_name="ingestion",
    kinds={"bigquery", "parquet"},
    description="Manifest-verified raw tables in the isolated r360_raw dataset.",
)
def raw_bigquery(context: AssetExecutionContext) -> dg.MaterializeResult:
    project_id = os.environ["GCP_PROJECT_ID"]
    start_tag = context.run_tags.get("rider360/backfill_start")
    end_tag = context.run_tags.get("rider360/backfill_end")
    lookback_tag = context.run_tags.get("rider360/lookback_days")
    if bool(start_tag) != bool(end_tag):
        raise dg.Failure("backfill_start and backfill_end run tags must be supplied together")
    if start_tag and end_tag:
        partition_start = date.fromisoformat(start_tag)
        partition_end = date.fromisoformat(end_tag)
    elif lookback_tag:
        lookback_days = int(lookback_tag)
        if lookback_days < 1:
            raise dg.Failure("rider360/lookback_days must be at least 1")
        manifest = json.loads((_dataset_dir() / "manifest.json").read_text(encoding="utf-8"))
        partition_end = date.fromisoformat(manifest["end_date"])
        partition_start = partition_end - timedelta(days=lookback_days - 1)
    else:
        partition_start = None
        partition_end = None
    result = load_local_parquet(
        _dataset_dir(),
        project_id=project_id,
        bucket_name=os.getenv("R360_DATA_BUCKET"),
        partition_start=partition_start,
        partition_end=partition_end,
    )
    return dg.MaterializeResult(
        metadata={
            "project_id": result.project_id,
            "dataset_id": result.dataset_id,
            "table_count": len(result.table_rows),
            "total_rows": sum(result.table_rows.values()),
            "manifest_uri": result.gcs_manifest_uri or "local-only",
            "load_mode": result.load_mode,
            "partition_start": str(result.partition_start or "full-history"),
            "partition_end": str(result.partition_end or "full-history"),
        }
    )


@dg.asset_check(asset=raw_bigquery, name="manifest_row_counts_match")
def raw_manifest_row_counts_match() -> dg.AssetCheckResult:
    manifest = json.loads((_dataset_dir() / "manifest.json").read_text(encoding="utf-8"))
    client = bigquery.Client(project=os.environ["GCP_PROJECT_ID"])
    mismatches: dict[str, dict[str, int]] = {}
    for table_name, details in manifest["tables"].items():
        actual = int(client.get_table(f"{client.project}.r360_raw.{table_name}").num_rows)
        expected = int(details["row_count"])
        if actual != expected:
            mismatches[table_name] = {"expected": expected, "actual": actual}
    return dg.AssetCheckResult(passed=not mismatches, metadata={"mismatches": mismatches})


@dbt_assets(
    manifest=DBT_PROJECT.manifest_path,
    project=DBT_PROJECT,
    select="fqn:*",
    name="rider360_dbt_models",
    op_tags={"rider360/layer": "warehouse"},
)
def rider360_dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


rider360_dbt_models = rider360_dbt_models.map_asset_specs(
    lambda spec: spec.merge_attributes(deps=[dg.AssetKey("raw_bigquery")])
)


@dg.asset(
    deps=[dg.AssetKey(name) for name in PUBLISH_ALLOWLIST],
    group_name="serving",
    kinds={"postgres", "bigquery"},
    description="Atomic allowlisted aggregate-mart publication into r360_bi PostgreSQL.",
)
def postgres_bi_serving() -> dg.MaterializeResult:
    result = publish_marts(
        project_id=os.environ["GCP_PROJECT_ID"],
        pg_dsn=os.environ["R360_BI_PG_DSN"],
        reader_role=os.getenv("R360_BI_READER_ROLE", "r360_metabase"),
    )
    return dg.MaterializeResult(
        metadata={
            "publication_id": result.publication_id,
            "published_tables": len(result.row_counts),
            "published_rows": sum(result.row_counts.values()),
            "target_schema": result.target_schema,
        }
    )


@dg.asset_check(asset=postgres_bi_serving, name="bigquery_postgres_reconciliation")
def bigquery_postgres_reconciliation() -> dg.AssetCheckResult:
    project_id = os.environ["GCP_PROJECT_ID"]
    client = bigquery.Client(project=project_id)
    differences: dict[str, dict[str, int]] = {}
    with (
        psycopg.connect(os.environ["R360_BI_PG_DSN"]) as connection,
        connection.cursor() as cursor,
    ):
        for table_name in PUBLISH_ALLOWLIST:
            bq_count = int(client.get_table(f"{project_id}.r360_marts.{table_name}").num_rows)
            cursor.execute(
                psycopg.sql.SQL("select count(*) from {}.{}").format(
                    psycopg.sql.Identifier("r360_bi"), psycopg.sql.Identifier(table_name)
                )
            )
            pg_count = int(cursor.fetchone()[0])
            if bq_count != pg_count:
                differences[table_name] = {"bigquery": bq_count, "postgres": pg_count}
    return dg.AssetCheckResult(passed=not differences, metadata={"differences": differences})


all_assets = [synthetic_sources, raw_bigquery, rider360_dbt_models, postgres_bi_serving]
full_pipeline_job = dg.define_asset_job(
    name="rider360_full_pipeline",
    selection=dg.AssetSelection.assets(*all_assets).upstream(),
    description="Generate, load, transform, test, and publish Rider 360 analytics.",
)
publish_serving_job = dg.define_asset_job(
    name="rider360_publish_serving",
    selection=dg.AssetSelection.assets(postgres_bi_serving),
    description="Publish and reconcile only the allowlisted BigQuery aggregate marts.",
)
daily_schedule = dg.ScheduleDefinition(
    name="rider360_daily_refresh",
    job=full_pipeline_job,
    cron_schedule="30 3 * * *",
    execution_timezone="Europe/Vienna",
    tags={"rider360/lookback_days": "4"},
    default_status=dg.DefaultScheduleStatus.STOPPED,
)


@dg.sensor(
    name="rider360_marketing_arrival",
    job=full_pipeline_job,
    minimum_interval_seconds=60,
    default_status=dg.DefaultSensorStatus.STOPPED,
    description=(
        "Launch the governed pipeline once for each new generation of an explicitly configured "
        "Rider-namespaced GCS marketing-arrival marker."
    ),
)
def marketing_arrival_sensor(context: dg.SensorEvaluationContext):
    marker_uri = os.getenv("R360_MARKETING_ARRIVAL_URI", "").strip()
    if not marker_uri:
        return dg.SkipReason("R360_MARKETING_ARRIVAL_URI is not configured")

    parsed = urlsplit(marker_uri)
    bucket_name = parsed.netloc
    object_name = parsed.path.lstrip("/")
    if (
        parsed.scheme != "gs"
        or not bucket_name.startswith("r360-")
        or not object_name.startswith("arrivals/marketing/")
        or not object_name
    ):
        return dg.SkipReason("Arrival marker must use gs://r360-*/arrivals/marketing/<marker>")

    client = storage.Client(project=os.environ["GCP_PROJECT_ID"])
    marker = client.bucket(bucket_name).get_blob(object_name)
    if marker is None:
        return dg.SkipReason(f"Arrival marker does not exist: {marker_uri}")

    generation = str(marker.generation)
    if context.cursor == generation:
        return dg.SkipReason(f"Arrival generation {generation} was already requested")

    context.update_cursor(generation)
    return dg.RunRequest(
        run_key=f"marketing-arrival-{generation}",
        tags={
            "rider360/trigger": "marketing-arrival",
            "rider360/marker_uri": marker_uri,
            "rider360/marker_generation": generation,
            "rider360/lookback_days": "4",
        },
    )


defs = dg.Definitions(
    assets=all_assets,
    asset_checks=[
        synthetic_manifest_contract,
        raw_manifest_row_counts_match,
        bigquery_postgres_reconciliation,
    ],
    jobs=[full_pipeline_job, publish_serving_job],
    schedules=[daily_schedule],
    sensors=[marketing_arrival_sensor],
    resources={
        "dbt": DbtCliResource(
            project_dir=DBT_PROJECT,
            profiles_dir=PROJECT_ROOT,
        )
    },
)
