from dagster import AssetKey

from rider360.orchestration.definitions import defs


def test_dagster_definitions_load_and_expose_governed_assets() -> None:
    repository = defs.get_repository_def()
    asset_keys = repository.asset_graph.get_all_asset_keys()

    assert AssetKey("synthetic_sources") in asset_keys
    assert AssetKey("raw_bigquery") in asset_keys
    assert AssetKey("mart_executive_daily") in asset_keys
    assert AssetKey("postgres_bi_serving") in asset_keys
    assert repository.has_job("rider360_full_pipeline")
    assert repository.has_job("rider360_publish_serving")
    assert repository.has_schedule_def("rider360_daily_refresh")
    assert repository.has_sensor_def("rider360_marketing_arrival")
