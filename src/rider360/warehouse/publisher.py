from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import uuid4

import psycopg
from google.cloud import bigquery
from psycopg import sql

PUBLISH_ALLOWLIST: tuple[str, ...] = (
    "mart_executive_daily",
    "mart_funnel_daily",
    "mart_sizepath_daily",
    "mart_inventory_daily",
    "mart_accessory_attach_daily",
    "mart_customer_ltv",
    "mart_data_quality_daily",
)
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]+$")
ROLE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.@-]+$")
PG_TYPES = {
    "STRING": "text",
    "BYTES": "bytea",
    "INTEGER": "bigint",
    "INT64": "bigint",
    "FLOAT": "double precision",
    "FLOAT64": "double precision",
    "NUMERIC": "numeric",
    "BIGNUMERIC": "numeric",
    "BOOLEAN": "boolean",
    "BOOL": "boolean",
    "DATE": "date",
    "DATETIME": "timestamp",
    "TIMESTAMP": "timestamptz",
    "TIME": "time",
    "JSON": "jsonb",
}


@dataclass(frozen=True)
class PublishResult:
    publication_id: str
    row_counts: dict[str, int]
    source_project: str
    source_dataset: str
    target_schema: str


def _safe_identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe SQL identifier: {value}")
    return value


def _postgres_type(field: bigquery.SchemaField) -> str:
    if field.mode == "REPEATED" or field.field_type in {"RECORD", "STRUCT", "GEOGRAPHY"}:
        return "jsonb"
    try:
        return PG_TYPES[field.field_type]
    except KeyError as error:
        raise ValueError(
            f"unsupported BigQuery type for publication: {field.field_type}"
        ) from error


def _adapt(value: Any) -> Any:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (list, dict)):
        return psycopg.types.json.Jsonb(value)
    return value


def _chunks(
    rows: Iterable[Mapping[str, Any]], size: int = 2_000
) -> Iterable[list[Mapping[str, Any]]]:
    batch: list[Mapping[str, Any]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def publish_marts(
    *,
    project_id: str,
    pg_dsn: str,
    source_dataset: str = "r360_marts",
    target_schema: str = "r360_bi",
    allowlist: tuple[str, ...] = PUBLISH_ALLOWLIST,
    reader_role: str = "r360_metabase",
) -> PublishResult:
    if source_dataset != "r360_marts" or target_schema != "r360_bi":
        raise ValueError("publication is restricted to r360_marts -> r360_bi")
    if set(allowlist) - set(PUBLISH_ALLOWLIST):
        raise ValueError("publication request includes a table outside the reviewed allowlist")
    for table_name in allowlist:
        _safe_identifier(table_name)
    if not ROLE_IDENTIFIER.fullmatch(reader_role):
        raise ValueError(f"unsafe PostgreSQL reader role: {reader_role}")
    publication_id = uuid4().hex[:12]
    staging_schema = f"r360_bi_next_{publication_id}"
    backup_schema = f"r360_bi_previous_{publication_id}"
    client = bigquery.Client(project=project_id)
    row_counts: dict[str, int] = {}
    with psycopg.connect(pg_dsn, autocommit=False) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("create schema {}").format(sql.Identifier(staging_schema)))
            cursor.execute(
                sql.SQL("grant usage on schema {} to {}").format(
                    sql.Identifier(staging_schema), sql.Identifier(reader_role)
                )
            )
            for table_name in allowlist:
                table_ref = f"{project_id}.{source_dataset}.{table_name}"
                table = client.get_table(table_ref)
                columns = [
                    sql.SQL("{} {}").format(
                        sql.Identifier(field.name), sql.SQL(_postgres_type(field))
                    )
                    for field in table.schema
                ]
                cursor.execute(
                    sql.SQL("create table {}.{} ({})").format(
                        sql.Identifier(staging_schema),
                        sql.Identifier(table_name),
                        sql.SQL(", ").join(columns),
                    )
                )
                field_names = [field.name for field in table.schema]
                insert = sql.SQL("insert into {}.{} ({}) values ({})").format(
                    sql.Identifier(staging_schema),
                    sql.Identifier(table_name),
                    sql.SQL(", ").join(map(sql.Identifier, field_names)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in field_names),
                )
                count = 0
                for batch in _chunks(client.list_rows(table)):
                    values = [tuple(_adapt(row[name]) for name in field_names) for row in batch]
                    cursor.executemany(insert, values)
                    count += len(values)
                row_counts[table_name] = count
                cursor.execute(
                    sql.SQL("create index on {}.{} ({})").format(
                        sql.Identifier(staging_schema),
                        sql.Identifier(table_name),
                        sql.Identifier(
                            "metric_date" if "metric_date" in field_names else field_names[0]
                        ),
                    )
                )
                cursor.execute(
                    sql.SQL("analyze {}.{}").format(
                        sql.Identifier(staging_schema), sql.Identifier(table_name)
                    )
                )
                cursor.execute(
                    sql.SQL("grant select on {}.{} to {}").format(
                        sql.Identifier(staging_schema),
                        sql.Identifier(table_name),
                        sql.Identifier(reader_role),
                    )
                )
            cursor.execute(
                "select exists(select 1 from pg_namespace where nspname = %s)", (target_schema,)
            )
            if cursor.fetchone()[0]:
                cursor.execute(
                    sql.SQL("alter schema {} rename to {}").format(
                        sql.Identifier(target_schema), sql.Identifier(backup_schema)
                    )
                )
            cursor.execute(
                sql.SQL("alter schema {} rename to {}").format(
                    sql.Identifier(staging_schema), sql.Identifier(target_schema)
                )
            )
            cursor.execute(
                "select exists(select 1 from pg_namespace where nspname = %s)", (backup_schema,)
            )
            if cursor.fetchone()[0]:
                cursor.execute(
                    sql.SQL("drop schema {} cascade").format(sql.Identifier(backup_schema))
                )
        connection.commit()
    return PublishResult(
        publication_id=publication_id,
        row_counts=row_counts,
        source_project=project_id,
        source_dataset=source_dataset,
        target_schema=target_schema,
    )
