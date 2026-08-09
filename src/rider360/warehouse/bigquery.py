from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from google.api_core.exceptions import NotFound
from google.cloud import bigquery, storage

R360_NAME = re.compile(r"^r360_[a-z0-9_]+$")
MAX_PARQUET_ROW_GROUPS = 32_767
DATASET_LOCATIONS = {
    "raw": "EU",
    "staging": "EU",
    "intermediate": "EU",
    "marts": "EU",
    "audit": "EU",
}
PARTITION_FIELDS = {
    "events": "event_date",
    "orders": "placed_at",
    "order_items": "source_updated_at",
    "returns": "requested_at",
    "inventory_daily": "inventory_date",
    "marketing_spend": "spend_date",
    "exchange_rates": "rate_date",
    "source_delivery_log": "partition_date",
}
PARTITION_FILTER_SQL = {
    "events": "event_date",
    "orders": "date(placed_at)",
    "order_items": "date(source_updated_at)",
    "returns": "date(requested_at)",
    "inventory_daily": "inventory_date",
    "marketing_spend": "spend_date",
    "exchange_rates": "rate_date",
    "source_delivery_log": "partition_date",
}
CLUSTER_FIELDS = {
    "events": ["event_name", "geo_country"],
    "orders": ["site_market", "status"],
    "order_items": ["order_id", "sku"],
    "returns": ["reason"],
    "inventory_daily": ["site_market", "sku"],
    "marketing_spend": ["site_market", "channel"],
}


@dataclass(frozen=True)
class LoadResult:
    project_id: str
    dataset_id: str
    table_rows: dict[str, int]
    gcs_manifest_uri: str | None
    load_mode: str
    partition_start: date | None
    partition_end: date | None


def dataset_name(layer: str) -> str:
    try:
        location = DATASET_LOCATIONS[layer]
    except KeyError as error:
        raise ValueError(f"unsupported Rider 360 layer: {layer}") from error
    del location
    name = f"r360_{layer}"
    if not R360_NAME.fullmatch(name):
        raise ValueError(f"unsafe dataset name: {name}")
    return name


def ensure_datasets(client: bigquery.Client) -> list[str]:
    created: list[str] = []
    for layer, location in DATASET_LOCATIONS.items():
        name = dataset_name(layer)
        reference = bigquery.Dataset(f"{client.project}.{name}")
        reference.location = location
        reference.description = f"Rider 360 {layer} layer; fictional synthetic demo data only."
        reference.labels = {
            "app": "rider-360",
            "managed-by": "rider-360",
            "layer": layer,
        }
        client.create_dataset(reference, exists_ok=True)
        created.append(name)
    return created


def _load_job_config(
    table_name: str, *, configure_partitioning: bool = True
) -> bigquery.LoadJobConfig:
    config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        labels={"app": "rider-360", "operation": "source-load"},
    )
    parquet_options = bigquery.ParquetOptions()
    parquet_options.enable_list_inference = True
    config.parquet_options = parquet_options
    if configure_partitioning and table_name in PARTITION_FIELDS:
        config.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=PARTITION_FIELDS[table_name],
        )
    cluster = CLUSTER_FIELDS.get(table_name)
    if cluster:
        config.clustering_fields = cluster
    return config


def _validate_partition_range(
    partition_start: date | None, partition_end: date | None
) -> tuple[date | None, date | None]:
    if (partition_start is None) != (partition_end is None):
        raise ValueError("partition-start and partition-end must be supplied together")
    if (
        partition_start is not None
        and partition_end is not None
        and partition_start > partition_end
    ):
        raise ValueError("partition-start must be on or before partition-end")
    return partition_start, partition_end


def _partition_replace_sql(*, destination: str, temporary: str, table_name: str) -> str:
    if table_name not in PARTITION_FILTER_SQL:
        raise ValueError(f"table is not partition-replaceable: {table_name}")
    for identifier in (destination, temporary):
        if not re.fullmatch(r"[a-z0-9-]+\.r360_raw\.[A-Za-z0-9_]+", identifier):
            raise ValueError(f"unsafe BigQuery table identifier: {identifier}")
    partition_expression = PARTITION_FILTER_SQL[table_name]
    return f"""
    begin transaction;
    delete from `{destination}`
    where {partition_expression} between @partition_start and @partition_end;
    insert into `{destination}`
    select * from `{temporary}`
    where {partition_expression} between @partition_start and @partition_end;
    assert (
      select count(*) from `{destination}`
      where {partition_expression} between @partition_start and @partition_end
    ) = (
      select count(*) from `{temporary}`
      where {partition_expression} between @partition_start and @partition_end
    ) as 'Rider 360 partition replacement row-count mismatch';
    commit transaction;
    """


def _replace_partitions_from_file(
    client: bigquery.Client,
    *,
    source_path: Path,
    destination: str,
    table_name: str,
    partition_start: date,
    partition_end: date,
) -> None:
    try:
        client.get_table(destination)
    except NotFound as error:
        raise RuntimeError(
            f"partition backfill requires an existing destination table: {destination}"
        ) from error

    temporary = f"{client.project}.r360_raw._r360_load_{table_name}_{uuid.uuid4().hex[:12]}"
    try:
        with source_path.open("rb") as source:
            job = client.load_table_from_file(
                source,
                temporary,
                job_config=_load_job_config(table_name, configure_partitioning=False),
                rewind=True,
                location="EU",
            )
            job.result()
        temporary_table = client.get_table(temporary)
        temporary_table.expires = datetime.now(UTC) + timedelta(hours=2)
        client.update_table(temporary_table, ["expires"])
        query_config = bigquery.QueryJobConfig(
            labels={"app": "rider-360", "operation": "partition-backfill"},
            query_parameters=[
                bigquery.ScalarQueryParameter("partition_start", "DATE", partition_start),
                bigquery.ScalarQueryParameter("partition_end", "DATE", partition_end),
            ],
        )
        client.query(
            _partition_replace_sql(
                destination=destination,
                temporary=temporary,
                table_name=table_name,
            ),
            job_config=query_config,
            location="EU",
        ).result()
    finally:
        client.delete_table(temporary, not_found_ok=True)


def _read_manifest(dataset_dir: Path) -> dict[str, Any]:
    path = dataset_dir / "manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("project") != "Rider 360" or not isinstance(value.get("tables"), dict):
        raise ValueError(f"invalid Rider 360 manifest: {path}")
    return value


def verify_manifest_files(dataset_dir: Path) -> dict[str, int]:
    """Verify path containment, size, SHA-256, and Parquet row counts before loading."""
    root = dataset_dir.resolve()
    manifest = _read_manifest(root)
    verified_rows: dict[str, int] = {}
    for table_name, details in sorted(manifest["tables"].items()):
        if not re.fullmatch(r"[a-z][a-z0-9_]+", table_name):
            raise ValueError(f"unsafe table name in manifest: {table_name}")
        source_path = (root / str(details["path"])).resolve()
        if not source_path.is_relative_to(root) or not source_path.is_file():
            raise ValueError(f"manifest path is missing or escapes the dataset root: {table_name}")
        actual_size = source_path.stat().st_size
        expected_size = int(details["size_bytes"])
        if actual_size != expected_size:
            raise ValueError(
                f"size mismatch for {table_name}: expected {expected_size}, got {actual_size}"
            )
        with source_path.open("rb") as source:
            actual_digest = hashlib.file_digest(source, "sha256").hexdigest()
        expected_digest = str(details["sha256"])
        if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            raise ValueError(f"invalid SHA-256 in manifest for {table_name}")
        if actual_digest != expected_digest:
            raise ValueError(f"SHA-256 mismatch for {table_name}")
        metadata = pq.ParquetFile(source_path).metadata
        if metadata.num_row_groups > MAX_PARQUET_ROW_GROUPS:
            raise ValueError(
                f"Parquet row-group count for {table_name} exceeds BigQuery's "
                f"{MAX_PARQUET_ROW_GROUPS:,} limit: {metadata.num_row_groups:,}"
            )
        actual_rows = int(metadata.num_rows)
        expected_rows = int(details["row_count"])
        if actual_rows != expected_rows:
            raise ValueError(
                f"Parquet row-count mismatch for {table_name}: "
                f"expected {expected_rows}, got {actual_rows}"
            )
        verified_rows[table_name] = actual_rows
    return verified_rows


def load_local_parquet(
    dataset_dir: Path,
    *,
    project_id: str,
    raw_dataset: str = "r360_raw",
    bucket_name: str | None = None,
    partition_start: date | None = None,
    partition_end: date | None = None,
) -> LoadResult:
    if raw_dataset != dataset_name("raw"):
        raise ValueError("raw dataset must be the isolated r360_raw namespace")
    partition_start, partition_end = _validate_partition_range(partition_start, partition_end)
    manifest = _read_manifest(dataset_dir)
    verified_rows = verify_manifest_files(dataset_dir)
    client = bigquery.Client(project=project_id)
    ensure_datasets(client)
    table_rows: dict[str, int] = {}
    for table_name, details in sorted(manifest["tables"].items()):
        if not re.fullmatch(r"[a-z][a-z0-9_]+", table_name):
            raise ValueError(f"unsafe table name in manifest: {table_name}")
        source_path = dataset_dir / details["path"]
        destination = f"{project_id}.{raw_dataset}.{table_name}"
        if (
            partition_start is not None
            and partition_end is not None
            and table_name in PARTITION_FIELDS
        ):
            _replace_partitions_from_file(
                client,
                source_path=source_path,
                destination=destination,
                table_name=table_name,
                partition_start=partition_start,
                partition_end=partition_end,
            )
        else:
            with source_path.open("rb") as source:
                job = client.load_table_from_file(
                    source,
                    destination,
                    job_config=_load_job_config(table_name),
                    rewind=True,
                    location="EU",
                )
                job.result()
        table = client.get_table(destination)
        table_rows[table_name] = int(table.num_rows)
        expected = verified_rows[table_name]
        if table_rows[table_name] != expected:
            raise RuntimeError(
                f"row-count mismatch for {destination}: expected {expected}, got {table_rows[table_name]}"
            )
    manifest_uri: str | None = None
    if bucket_name:
        if not bucket_name.startswith("r360-"):
            raise ValueError("Rider 360 bucket names must start with r360-")
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(f"manifests/{manifest['profile']}/manifest.json")
        blob.upload_from_filename(
            str(dataset_dir / "manifest.json"), content_type="application/json"
        )
        manifest_uri = f"gs://{bucket_name}/{blob.name}"
    return LoadResult(
        project_id=project_id,
        dataset_id=raw_dataset,
        table_rows=table_rows,
        gcs_manifest_uri=manifest_uri,
        load_mode="partition_backfill" if partition_start is not None else "full_replace",
        partition_start=partition_start,
        partition_end=partition_end,
    )
