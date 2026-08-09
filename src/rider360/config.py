from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rider360.constants import DEFAULT_CONFIG_DIR


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerationProfile(StrictModel):
    start_date: date
    end_date: date
    markets: list[str]
    target_sessions: int = Field(gt=0)
    output_subdir: str

    @model_validator(mode="after")
    def dates_are_ordered(self) -> GenerationProfile:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class GeneratorConfig(StrictModel):
    version: int
    master_seed: int
    generator_version: str
    property_timezone: str
    reporting_currency: str
    return_maturity_days: int = Field(gt=0)
    profiles: dict[str, GenerationProfile]


class MarketConfig(StrictModel):
    code: str = Field(pattern=r"^[A-Z]{2}$")
    name: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    timezone: str
    locale: str
    traffic_weight: float = Field(gt=0)

    @model_validator(mode="after")
    def timezone_exists(self) -> MarketConfig:
        ZoneInfo(self.timezone)
        return self


class MarketsConfig(StrictModel):
    version: int
    markets: list[MarketConfig]

    @model_validator(mode="after")
    def codes_are_unique(self) -> MarketsConfig:
        codes = [market.code for market in self.markets]
        if len(codes) != len(set(codes)):
            raise ValueError("market codes must be unique")
        total = sum(market.traffic_weight for market in self.markets)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"market traffic weights must sum to 1.0, got {total}")
        return self


class ProductConfig(StrictModel):
    sku: str = Field(pattern=r"^R360-[A-Z0-9-]+$")
    name: str
    category: str
    family: str
    wheel_size: int | None
    age_band: str | None
    height_band: str | None
    base_price_eur: int = Field(gt=0)
    unit_cogs_eur: int = Field(gt=0)


class CompatibilityRule(StrictModel):
    parent_family: str | None = None
    parent_wheel_size: int | None = None
    accessory_skus: list[str]

    @model_validator(mode="after")
    def exactly_one_parent_selector(self) -> CompatibilityRule:
        if (self.parent_family is None) == (self.parent_wheel_size is None):
            raise ValueError("compatibility rule requires exactly one parent selector")
        return self


class CatalogConfig(StrictModel):
    version: int
    products: list[ProductConfig]
    compatibility: list[CompatibilityRule]

    @model_validator(mode="after")
    def catalog_is_consistent(self) -> CatalogConfig:
        skus = [product.sku for product in self.products]
        if len(skus) != len(set(skus)):
            raise ValueError("catalog SKUs must be unique")
        products = {product.sku: product for product in self.products}
        for rule in self.compatibility:
            for sku in rule.accessory_skus:
                if sku not in products or products[sku].category != "accessory":
                    raise ValueError(f"unknown or non-accessory compatible SKU: {sku}")
        return self


class ScenarioConfig(StrictModel):
    id: str
    name: str
    enabled: bool
    start_date: date
    end_date: date | None = None
    affected_dimensions: dict[str, list[Any]] = Field(default_factory=dict)
    mechanism: dict[str, Any] = Field(default_factory=dict)
    expected_direction: dict[str, Any] = Field(default_factory=dict)
    validation_tolerance: float | None = None

    def active_on(self, value: date) -> bool:
        return (
            self.enabled
            and self.start_date <= value
            and (self.end_date is None or value <= self.end_date)
        )


class ScenariosConfig(StrictModel):
    version: int
    scenarios: list[ScenarioConfig]

    @model_validator(mode="after")
    def ids_are_unique(self) -> ScenariosConfig:
        ids = [scenario.id for scenario in self.scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError("scenario IDs must be unique")
        return self


class ProjectConfig(StrictModel):
    generator: GeneratorConfig
    markets: MarketsConfig
    catalog: CatalogConfig
    scenarios: ScenariosConfig

    @classmethod
    def load(cls, config_dir: Path = DEFAULT_CONFIG_DIR) -> ProjectConfig:
        def read_yaml(name: str) -> dict[str, Any]:
            path = config_dir / name
            with path.open("r", encoding="utf-8") as handle:
                value = yaml.safe_load(handle)
            if not isinstance(value, dict):
                raise ValueError(f"{path} must contain a YAML object")
            return value

        result = cls(
            generator=GeneratorConfig.model_validate(read_yaml("generator.yml")),
            markets=MarketsConfig.model_validate(read_yaml("markets.yml")),
            catalog=CatalogConfig.model_validate(read_yaml("catalog.yml")),
            scenarios=ScenariosConfig.model_validate(read_yaml("scenarios.yml")),
        )
        result.validate_cross_file_contracts()
        return result

    def validate_cross_file_contracts(self) -> None:
        market_codes = {market.code for market in self.markets.markets}
        for name, profile in self.generator.profiles.items():
            unknown = set(profile.markets) - market_codes
            if unknown:
                raise ValueError(f"profile {name!r} contains unknown markets: {sorted(unknown)}")

    def profile(self, name: str) -> GenerationProfile:
        try:
            return self.generator.profiles[name]
        except KeyError as error:
            choices = ", ".join(sorted(self.generator.profiles))
            raise ValueError(f"unknown profile {name!r}; choose one of: {choices}") from error

    def scenario(self, scenario_id: str) -> ScenarioConfig:
        for scenario in self.scenarios.scenarios:
            if scenario.id == scenario_id:
                return scenario
        raise KeyError(scenario_id)
