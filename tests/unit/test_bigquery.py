from datetime import date

import pytest

from rider360.warehouse.bigquery import (
    _load_job_config,
    _partition_replace_sql,
    _validate_partition_range,
)


def test_parquet_load_enables_standard_list_inference() -> None:
    config = _load_job_config("events")

    assert config.parquet_options is not None
    assert config.parquet_options.enable_list_inference is True


def test_partition_range_must_be_complete_and_ordered() -> None:
    with pytest.raises(ValueError, match="supplied together"):
        _validate_partition_range(date(2025, 1, 1), None)
    with pytest.raises(ValueError, match="on or before"):
        _validate_partition_range(date(2025, 1, 2), date(2025, 1, 1))


def test_partition_replacement_is_transactional_and_scoped() -> None:
    sql = _partition_replace_sql(
        destination="tracegate-r7m5o9ld.r360_raw.events",
        temporary="tracegate-r7m5o9ld.r360_raw._r360_load_events_deadbeef",
        table_name="events",
    )

    assert "begin transaction" in sql
    assert "event_date between @partition_start and @partition_end" in sql
    assert "assert (" in sql
    assert "commit transaction" in sql
