from pathlib import Path

import pyarrow.parquet as pq
import pytest

from rider360.generator.engine import generate_dataset
from rider360.warehouse.bigquery import verify_manifest_files


def test_fixture_is_deterministic_and_reconciles(tmp_path: Path) -> None:
    first = generate_dataset("fixture", output_dir=tmp_path / "first")
    second = generate_dataset("fixture", output_dir=tmp_path / "second")

    assert first.counts == second.counts
    assert first.counts["events"] > 70_000
    assert 350 <= first.counts["orders"] <= 900
    assert first.counts["order_items"] >= first.counts["orders"]
    first_events = pq.read_table(first.output_dir / "events").column("event_id")
    second_events = pq.read_table(second.output_dir / "events").column("event_id")
    assert first_events.equals(second_events)
    event_file = pq.ParquetFile(first.output_dir / "events" / "part-00000.parquet")
    assert event_file.metadata.num_row_groups <= 2


def test_purchase_transactions_reconcile_to_operational_orders(tmp_path: Path) -> None:
    result = generate_dataset("fixture", output_dir=tmp_path / "fixture")
    events = pq.read_table(result.output_dir / "events").to_pylist()
    orders = pq.read_table(result.output_dir / "orders").to_pylist()
    transaction_ids = {
        parameter["value"]["string_value"]
        for event in events
        if event["event_name"] == "purchase"
        for parameter in event["event_params"]
        if parameter["key"] == "transaction_id"
    }

    assert transaction_ids == {order["order_id"] for order in orders}


def test_manifest_verification_rejects_tampered_parquet(tmp_path: Path) -> None:
    result = generate_dataset("fixture", output_dir=tmp_path / "fixture")
    counts = verify_manifest_files(result.output_dir)
    assert counts == result.counts

    product_path = result.output_dir / "products" / "part-00000.parquet"
    with product_path.open("r+b") as product_file:
        product_file.seek(-1, 2)
        original = product_file.read(1)
        product_file.seek(-1, 2)
        product_file.write(bytes([original[0] ^ 1]))

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_manifest_files(result.output_dir)
