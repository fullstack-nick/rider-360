from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from rider360.config import ProjectConfig
from rider360.constants import DEFAULT_CONFIG_DIR
from rider360.generator.engine import generate_dataset
from rider360.warehouse.bigquery import load_local_parquet, verify_manifest_files
from rider360.warehouse.local import publish_local_marts
from rider360.warehouse.publisher import publish_marts

app = typer.Typer(
    name="rider360",
    help="Build and operate the fictional Rider 360 analytics platform.",
    no_args_is_help=True,
)
config_app = typer.Typer(help="Validate and inspect versioned project configuration.")
app.add_typer(config_app, name="config")
console = Console()


@config_app.command("validate")
def validate_config(
    config_dir: Annotated[Path, typer.Option(exists=True, file_okay=False)] = DEFAULT_CONFIG_DIR,
) -> None:
    """Fail closed when any configuration contract is invalid."""
    config = ProjectConfig.load(config_dir)
    console.print(
        f"[green]Valid[/green]: {len(config.markets.markets)} markets, "
        f"{len(config.catalog.products)} products, "
        f"{len(config.scenarios.scenarios)} scenarios."
    )


@app.command("generate")
def generate(
    profile: Annotated[
        str, typer.Option(help="Generation profile from config/generator.yml.")
    ] = "fixture",
    config_dir: Annotated[Path, typer.Option(exists=True, file_okay=False)] = DEFAULT_CONFIG_DIR,
    output: Annotated[Path | None, typer.Option(file_okay=False)] = None,
) -> None:
    """Generate deterministic, fictional source data as partition-ready Parquet."""
    result = generate_dataset(profile, config_dir=config_dir, output_dir=output)
    table = Table(title=f"Rider 360 {result.profile} dataset")
    table.add_column("Table")
    table.add_column("Rows", justify="right")
    for name, count in sorted(result.counts.items()):
        table.add_row(name, f"{count:,}")
    console.print(table)
    console.print(f"Manifest: [cyan]{result.manifest_path}[/cyan]")


@app.command("manifest")
def show_manifest(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
) -> None:
    """Print a generated dataset manifest."""
    console.print_json(json=path.read_text(encoding="utf-8"))


@app.command("load-bigquery")
def load_bigquery(
    dataset_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    project_id: Annotated[str, typer.Option(envvar="GCP_PROJECT_ID")],
    bucket_name: Annotated[str | None, typer.Option(envvar="R360_DATA_BUCKET")] = None,
    start_date: Annotated[
        str | None,
        typer.Option(help="Inclusive source-partition start date for an atomic backfill."),
    ] = None,
    end_date: Annotated[
        str | None,
        typer.Option(help="Inclusive source-partition end date for an atomic backfill."),
    ] = None,
) -> None:
    """Load a generated manifest into isolated Rider 360 BigQuery datasets."""
    try:
        parsed_start = date.fromisoformat(start_date) if start_date else None
        parsed_end = date.fromisoformat(end_date) if end_date else None
    except ValueError as error:
        raise typer.BadParameter("backfill dates must use YYYY-MM-DD") from error
    result = load_local_parquet(
        dataset_dir,
        project_id=project_id,
        bucket_name=bucket_name,
        partition_start=parsed_start,
        partition_end=parsed_end,
    )
    console.print(
        f"[green]Loaded[/green] {len(result.table_rows)} tables into {result.dataset_id} "
        f"using {result.load_mode}."
    )
    for name, count in sorted(result.table_rows.items()):
        console.print(f"  {name}: {count:,}")


@app.command("verify-dataset")
def verify_dataset(
    dataset_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
) -> None:
    """Verify a source manifest, file hashes, Parquet metadata, and row counts."""
    counts = verify_manifest_files(dataset_dir)
    console.print(
        f"[green]Verified[/green] {len(counts)} tables and {sum(counts.values()):,} rows."
    )


@app.command("publish-bi")
def publish_bi(
    project_id: Annotated[str, typer.Option(envvar="GCP_PROJECT_ID")],
    pg_dsn: Annotated[str, typer.Option(envvar="R360_BI_PG_DSN")],
    reader_role: Annotated[str, typer.Option(envvar="R360_BI_READER_ROLE")] = "r360_metabase",
) -> None:
    """Atomically publish the reviewed BigQuery aggregate marts into PostgreSQL."""
    result = publish_marts(project_id=project_id, pg_dsn=pg_dsn, reader_role=reader_role)
    console.print(
        f"[green]Published[/green] {len(result.row_counts)} marts as {result.publication_id}."
    )


@app.command("publish-local-bi")
def publish_local_bi(
    dataset_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    pg_dsn: Annotated[str, typer.Option(envvar="R360_BI_PG_DSN")],
) -> None:
    """Build fixture-scale marts locally and publish the same BI contract to PostgreSQL."""
    counts = publish_local_marts(dataset_dir, pg_dsn)
    console.print(f"[green]Published[/green] {len(counts)} local BI marts.")
    for name, count in counts.items():
        console.print(f"  {name}: {count:,}")


if __name__ == "__main__":
    app()
