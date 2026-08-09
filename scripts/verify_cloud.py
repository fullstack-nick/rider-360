"""Run non-destructive acceptance checks against the deployed Rider 360 demo."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests
from google.cloud import bigquery

from rider360.warehouse.publisher import PUBLISH_ALLOWLIST


@dataclass(frozen=True)
class EndpointResult:
    name: str
    status_code: int
    passed: bool


def _request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    expected: int | tuple[int, ...] = 200,
    **kwargs: Any,
) -> dict[str, Any]:
    response = session.request(method, url, timeout=60, **kwargs)
    expected_codes = (expected,) if isinstance(expected, int) else expected
    if response.status_code not in expected_codes:
        raise RuntimeError(
            f"{method} {url} returned {response.status_code}, expected {expected_codes}: "
            f"{response.text[:300]}"
        )
    return response.json()


def _metabase_rows(
    session: requests.Session,
    base_url: str,
    database_id: int,
    query: str,
) -> list[list[Any]]:
    payload = {
        "database": database_id,
        "type": "native",
        "native": {"query": query, "template-tags": {}},
        "parameters": [],
    }
    body = _request_json(
        session,
        "POST",
        f"{base_url}/api/dataset",
        expected=(200, 202),
        json=payload,
    )
    if body.get("status") == "failed" or "error" in body:
        raise RuntimeError(f"Metabase query failed: {body.get('error', body)}")
    return body["data"]["rows"]


def _endpoint(
    session: requests.Session,
    name: str,
    url: str,
    expected_status: int,
) -> EndpointResult:
    response = session.get(url, timeout=60, allow_redirects=False)
    return EndpointResult(
        name=name,
        status_code=response.status_code,
        passed=response.status_code == expected_status,
    )


def verify(args: argparse.Namespace) -> dict[str, Any]:
    metabase_url = args.metabase_url.rstrip("/")
    dagster_public_url = args.dagster_public_url.rstrip("/")
    dagster_admin_url = args.dagster_admin_url.rstrip("/")

    public_session = requests.Session()
    endpoints = [
        _endpoint(public_session, "metabase_application", metabase_url, 200),
        _endpoint(public_session, "metabase_public_dashboard", args.dashboard_url, 200),
        _endpoint(public_session, "dagster_public", dagster_public_url, 200),
        _endpoint(public_session, "dagster_admin_anonymous", dagster_admin_url, 403),
    ]

    version_query = _request_json(
        public_session,
        "POST",
        f"{dagster_public_url}/graphql",
        json={"query": "query { version }"},
    )
    if version_query.get("data", {}).get("version") != args.dagster_version:
        raise RuntimeError(f"Unexpected Dagster version response: {version_query}")

    denied_mutation = _request_json(
        public_session,
        "POST",
        f"{dagster_public_url}/graphql",
        json={"query": "mutation { reloadWorkspace { __typename } }"},
    )
    mutation_type = denied_mutation.get("data", {}).get("reloadWorkspace", {}).get("__typename")
    if mutation_type != "UnauthorizedError":
        raise RuntimeError(f"Public Dagster mutation was not denied: {denied_mutation}")

    metabase_session = requests.Session()
    _request_json(
        metabase_session,
        "POST",
        f"{metabase_url}/api/session",
        json={"username": args.admin_email, "password": args.admin_password},
    )
    databases = _request_json(metabase_session, "GET", f"{metabase_url}/api/database")
    records = databases.get("data", databases)
    database = next(
        (item for item in records if item.get("name") == args.database_name),
        None,
    )
    if database is None:
        raise RuntimeError(f"Metabase database {args.database_name!r} was not found")
    database_id = int(database["id"])

    table_rows = _metabase_rows(
        metabase_session,
        metabase_url,
        database_id,
        """
        select table_name
        from information_schema.tables
        where table_schema = 'r360_bi' and table_type = 'BASE TABLE'
        order by table_name
        """,
    )
    postgres_tables = [str(row[0]) for row in table_rows]
    expected_tables = sorted(PUBLISH_ALLOWLIST)
    if postgres_tables != expected_tables:
        raise RuntimeError(
            f"PostgreSQL serving allowlist mismatch: {postgres_tables} != {expected_tables}"
        )

    count_parts = [
        f"select '{table}' as table_name, count(*)::bigint as row_count from r360_bi.{table}"
        for table in PUBLISH_ALLOWLIST
    ]
    pg_rows = _metabase_rows(
        metabase_session,
        metabase_url,
        database_id,
        " union all ".join(count_parts) + " order by table_name",
    )
    postgres_counts = {str(row[0]): int(row[1]) for row in pg_rows}

    bq_client = bigquery.Client(project=args.project_id)
    bigquery_counts = {
        table: int(bq_client.get_table(f"{args.project_id}.r360_marts.{table}").num_rows)
        for table in PUBLISH_ALLOWLIST
    }
    if postgres_counts != dict(sorted(bigquery_counts.items())):
        raise RuntimeError(
            f"BigQuery/PostgreSQL reconciliation failed: {bigquery_counts} != {postgres_counts}"
        )

    failures = [asdict(item) for item in endpoints if not item.passed]
    if failures:
        raise RuntimeError(f"Endpoint checks failed: {failures}")

    result = {
        "project_id": args.project_id,
        "endpoints": [asdict(item) for item in endpoints],
        "dagster": {
            "version": version_query["data"]["version"],
            "public_mutation_result": mutation_type,
        },
        "serving_layer": {
            "schema": "r360_bi",
            "tables": expected_tables,
            "bigquery_row_counts": dict(sorted(bigquery_counts.items())),
            "postgres_row_counts": postgres_counts,
            "reconciled": True,
        },
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", default="tracegate-r7m5o9ld")
    parser.add_argument("--metabase-url", required=True)
    parser.add_argument("--dashboard-url", required=True)
    parser.add_argument("--dagster-public-url", required=True)
    parser.add_argument("--dagster-admin-url", required=True)
    parser.add_argument("--admin-email", default="admin@rider360.example")
    parser.add_argument("--admin-password", default=os.getenv("METABASE_ADMIN_PASSWORD"))
    parser.add_argument("--database-name", default="Rider 360 Analytics")
    parser.add_argument("--dagster-version", default="1.13.17")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.admin_password:
        parser.error("set METABASE_ADMIN_PASSWORD or provide --admin-password")
    return args


if __name__ == "__main__":
    print(json.dumps(verify(parse_args()), indent=2))
