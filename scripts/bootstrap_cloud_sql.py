from __future__ import annotations

import argparse
import os
import time

import psycopg
from psycopg import sql


def _connect(*, host: str, port: int, database: str, password: str) -> psycopg.Connection:
    last_error: psycopg.OperationalError | None = None
    for attempt in range(20):
        try:
            return psycopg.connect(
                host=host,
                port=port,
                dbname=database,
                user="postgres",
                password=password,
                sslmode="disable",
                autocommit=True,
            )
        except psycopg.OperationalError as error:
            last_error = error
            if attempt == 19:
                break
            time.sleep(0.5)
    raise RuntimeError("Cloud SQL backend did not become ready") from last_error


def _require_roles(connection: psycopg.Connection, roles: tuple[str, ...]) -> None:
    with connection.cursor() as cursor:
        cursor.execute("select rolname from pg_roles where rolname = any(%s)", (list(roles),))
        found = {row[0] for row in cursor.fetchall()}
    missing = set(roles) - found
    if missing:
        raise RuntimeError(f"Cloud SQL IAM database roles are missing: {sorted(missing)}")


def bootstrap(
    *, host: str, port: int, dagster_role: str, metabase_role: str, password: str
) -> None:
    with _connect(host=host, port=port, database="postgres", password=password) as connection:
        _require_roles(connection, (dagster_role, metabase_role))
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("grant connect, create, temporary on database r360_metabase to {}").format(
                    sql.Identifier(metabase_role)
                )
            )
            cursor.execute(
                sql.SQL("grant connect, create, temporary on database r360_dagster to {}").format(
                    sql.Identifier(dagster_role)
                )
            )
            cursor.execute(
                sql.SQL("grant connect, create, temporary on database r360_bi to {}").format(
                    sql.Identifier(dagster_role)
                )
            )
            cursor.execute("revoke all on database r360_bi from public")
            cursor.execute(
                sql.SQL("grant connect on database r360_bi to {}").format(
                    sql.Identifier(metabase_role)
                )
            )

    for database, owner in (
        ("r360_metabase", metabase_role),
        ("r360_dagster", dagster_role),
    ):
        with (
            _connect(host=host, port=port, database=database, password=password) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                sql.SQL("grant usage, create on schema public to {}").format(sql.Identifier(owner))
            )

    with (
        _connect(host=host, port=port, database="r360_bi", password=password) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("revoke create on schema public from public")
        cursor.execute("select nspowner::regrole::text from pg_namespace where nspname = 'r360_bi'")
        existing = cursor.fetchone()
        if existing:
            owner = existing[0]
            if owner != dagster_role:
                raise RuntimeError(f"Unexpected existing r360_bi schema owner: {owner}")
            cursor.execute(
                sql.SQL("grant usage on schema r360_bi to {}").format(sql.Identifier(metabase_role))
            )
            cursor.execute(
                sql.SQL("grant select on all tables in schema r360_bi to {}").format(
                    sql.Identifier(metabase_role)
                )
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap Cloud SQL ownership and grants.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--dagster-role", required=True)
    parser.add_argument("--metabase-role", required=True)
    args = parser.parse_args()
    password = os.environ.get("R360_BOOTSTRAP_PASSWORD")
    if not password:
        raise RuntimeError("R360_BOOTSTRAP_PASSWORD must be supplied through the environment")
    bootstrap(
        host=args.host,
        port=args.port,
        dagster_role=args.dagster_role,
        metabase_role=args.metabase_role,
        password=password,
    )
    print("Cloud SQL database ownership and least-privilege grants verified.")


if __name__ == "__main__":
    main()
