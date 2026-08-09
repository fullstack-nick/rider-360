from rider360.config import ProjectConfig


def test_project_config_loads_and_cross_file_contracts_hold() -> None:
    config = ProjectConfig.load()

    assert config.generator.reporting_currency == "EUR"
    assert config.profile("full").target_sessions == 450_000
    assert {market.code for market in config.markets.markets} == {
        "AT",
        "DE",
        "FR",
        "NL",
        "GB",
        "US",
    }
    assert all(product.sku.startswith("R360-") for product in config.catalog.products)
