import pytest

from rider360.warehouse.bigquery import dataset_name
from rider360.warehouse.publisher import PUBLISH_ALLOWLIST, publish_marts


def test_dataset_names_are_isolated() -> None:
    assert dataset_name("raw") == "r360_raw"
    with pytest.raises(ValueError):
        dataset_name("tracegate")


def test_publisher_allowlist_is_aggregate_only() -> None:
    assert PUBLISH_ALLOWLIST
    assert all(name.startswith("mart_") for name in PUBLISH_ALLOWLIST)
    with pytest.raises(ValueError, match="allowlist"):
        publish_marts(
            project_id="unused",
            pg_dsn="unused",
            allowlist=(*PUBLISH_ALLOWLIST, "stg_customers"),
        )
