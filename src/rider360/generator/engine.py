from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from rider360.config import MarketConfig, ProductConfig, ProjectConfig, ScenarioConfig
from rider360.constants import DEFAULT_CONFIG_DIR, DEFAULT_DATA_DIR
from rider360.generator.ids import stable_hex, stable_id, stable_int_seed
from rider360.generator.schemas import event_parameter
from rider360.generator.writer import DatasetWriter, write_manifest

CHANNELS: tuple[dict[str, str], ...] = (
    {
        "channel": "Organic Search",
        "source": "search",
        "medium": "organic",
        "campaign": "evergreen_discovery",
    },
    {
        "channel": "Paid Search",
        "source": "search_ads",
        "medium": "cpc",
        "campaign": "rider_intent",
    },
    {
        "channel": "Paid Social",
        "source": "social_ads",
        "medium": "paid_social",
        "campaign": "family_adventures",
    },
    {
        "channel": "Email",
        "source": "riderly_news",
        "medium": "email",
        "campaign": "trail_notes",
    },
    {
        "channel": "Affiliate",
        "source": "partner_path",
        "medium": "affiliate",
        "campaign": "guide_referrals",
    },
    {
        "channel": "Direct",
        "source": "(direct)",
        "medium": "(none)",
        "campaign": "(not set)",
    },
)
CHANNEL_WEIGHTS = np.array([0.30, 0.20, 0.16, 0.10, 0.09, 0.15], dtype=float)
DEVICE_VALUES = np.array(["mobile", "desktop", "tablet"], dtype=object)
DEVICE_WEIGHTS = np.array([0.66, 0.29, 0.05], dtype=float)
BROWSERS = {
    "mobile": (
        np.array(["Chrome", "Safari", "Samsung Internet"], dtype=object),
        [0.52, 0.39, 0.09],
    ),
    "desktop": (
        np.array(["Chrome", "Safari", "Edge", "Firefox"], dtype=object),
        [0.53, 0.22, 0.17, 0.08],
    ),
    "tablet": (np.array(["Safari", "Chrome"], dtype=object), [0.67, 0.33]),
}
TAX_RATES = {"AT": 0.20, "DE": 0.19, "FR": 0.20, "NL": 0.21, "GB": 0.20, "US": 0.08}
FX_TO_EUR = {"EUR": 1.0, "GBP": 1.16, "USD": 0.92}
SOURCE_TABLES = (
    "events",
    "orders",
    "order_items",
    "returns",
    "inventory_daily",
    "marketing_spend",
    "exchange_rates",
)


@dataclass(frozen=True)
class GenerationResult:
    profile: str
    output_dir: Path
    counts: dict[str, int]
    manifest_path: Path


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _money(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _local_timestamp(day: date, minute: int, timezone: str) -> datetime:
    local = datetime.combine(day, time.min, tzinfo=ZoneInfo(timezone)) + timedelta(minutes=minute)
    return local.astimezone(UTC)


def _allocate_sessions(config: ProjectConfig, profile_name: str) -> dict[tuple[date, str], int]:
    profile = config.profile(profile_name)
    days = _date_range(profile.start_date, profile.end_date)
    market_map = {market.code: market for market in config.markets.markets}
    chosen = [market_map[code] for code in profile.markets]
    selected_weight = sum(market.traffic_weight for market in chosen)
    weights: list[float] = []
    keys: list[tuple[date, str]] = []
    for day in days:
        weekday_factor = 1.15 if day.weekday() >= 5 else 0.94
        seasonal_factor = 1.0 + 0.18 * math.sin((day.timetuple().tm_yday - 70) / 365 * 2 * math.pi)
        holiday_factor = 1.28 if day.month in {11, 12} else 1.0
        for market in chosen:
            keys.append((day, market.code))
            weights.append(
                (market.traffic_weight / selected_weight)
                * weekday_factor
                * seasonal_factor
                * holiday_factor
            )
    normalized = np.asarray(weights, dtype=float)
    normalized /= normalized.sum()
    raw = normalized * profile.target_sessions
    allocated = np.floor(raw).astype(int)
    remainder = profile.target_sessions - int(allocated.sum())
    if remainder:
        order = np.argsort(-(raw - allocated), kind="stable")
        allocated[order[:remainder]] += 1
    return {key: int(value) for key, value in zip(keys, allocated, strict=True)}


def _scenario_applies(
    scenario: ScenarioConfig,
    day: date,
    **dimensions: str,
) -> bool:
    if not scenario.active_on(day):
        return False
    for name, allowed in scenario.affected_dimensions.items():
        observed = dimensions.get(name)
        if observed is not None and allowed and observed not in {str(value) for value in allowed}:
            return False
    return True


def _price_for(product: ProductConfig, market: MarketConfig) -> int:
    local = product.base_price_eur / FX_TO_EUR[market.currency]
    market_factor = {"AT": 1.00, "DE": 0.99, "FR": 1.02, "NL": 1.01, "GB": 1.04, "US": 1.06}[
        market.code
    ]
    return _money(local * market_factor)


def _static_records(config: ProjectConfig, profile_name: str) -> dict[str, list[dict[str, Any]]]:
    profile = config.profile(profile_name)
    market_map = {market.code: market for market in config.markets.markets}
    products: list[dict[str, Any]] = []
    prices: list[dict[str, Any]] = []
    compatibilities: list[dict[str, Any]] = []
    for product in config.catalog.products:
        products.append(
            {
                "product_version_id": stable_id(
                    "pv", "product-version", product.sku, profile.start_date
                ),
                "sku": product.sku,
                "product_name": product.name,
                "category": product.category,
                "family": product.family,
                "wheel_size": product.wheel_size,
                "age_band": product.age_band,
                "height_band": product.height_band,
                "valid_from": profile.start_date,
                "valid_to": None,
                "status": "active",
            }
        )
        for market_code in profile.markets:
            market = market_map[market_code]
            prices.append(
                {
                    "price_version_id": stable_id(
                        "price", "market-price", product.sku, market.code, profile.start_date
                    ),
                    "sku": product.sku,
                    "site_market": market.code,
                    "currency": market.currency,
                    "list_price": _price_for(product, market),
                    "promotional_price": None,
                    "valid_from": profile.start_date,
                    "valid_to": None,
                }
            )
    bikes = [product for product in config.catalog.products if product.category == "bike"]
    for rule_index, rule in enumerate(config.catalog.compatibility):
        parents = [
            product
            for product in bikes
            if (rule.parent_family is not None and product.family == rule.parent_family)
            or (rule.parent_wheel_size is not None and product.wheel_size == rule.parent_wheel_size)
        ]
        for parent in parents:
            for accessory_sku in rule.accessory_skus:
                compatibilities.append(
                    {
                        "compatibility_id": stable_id(
                            "compat", "compatibility", rule_index, parent.sku, accessory_sku
                        ),
                        "parent_sku": parent.sku,
                        "accessory_sku": accessory_sku,
                        "compatibility_type": "recommended",
                        "valid_from": profile.start_date,
                        "valid_to": None,
                    }
                )
    return {
        "products": products,
        "product_market_prices": prices,
        "product_accessory_compatibility": compatibilities,
    }


class SyntheticGenerator:
    def __init__(self, config: ProjectConfig, profile_name: str) -> None:
        self.config = config
        self.profile_name = profile_name
        self.profile = config.profile(profile_name)
        self.market_map = {market.code: market for market in config.markets.markets}
        self.product_map = {product.sku: product for product in config.catalog.products}
        self.bikes = [product for product in config.catalog.products if product.category == "bike"]
        self.accessories = [
            product for product in config.catalog.products if product.category == "accessory"
        ]
        self.compatible: dict[str, list[ProductConfig]] = defaultdict(list)
        static = _static_records(config, profile_name)
        for row in static["product_accessory_compatibility"]:
            self.compatible[row["parent_sku"]].append(self.product_map[row["accessory_sku"]])
        self.first_orders: dict[str, dict[str, Any]] = {}
        self.order_sequence = 0
        self.event_sequence = 0

    def _event(
        self,
        *,
        name: str,
        timestamp: datetime,
        session_key: str,
        visitor_id: str,
        customer_id: str | None,
        market: MarketConfig,
        device: str,
        browser: str,
        channel: dict[str, str],
        params: dict[str, str | int | float | None] | None = None,
        items: list[dict[str, Any]] | None = None,
        suffix: object = "",
    ) -> dict[str, Any]:
        self.event_sequence += 1
        all_params: dict[str, str | int | float | None] = {
            "session_key": session_key,
            "ga_session_id": int(stable_hex("ga-session", session_key, length=12), 16),
            "engagement_time_msec": 1000,
            **(params or {}),
        }
        return {
            "event_date": timestamp.date(),
            "event_timestamp": int(timestamp.timestamp() * 1_000_000),
            "event_name": name,
            "event_id": stable_id(
                "evt", "event", session_key, name, self.event_sequence, suffix, length=24
            ),
            "event_bundle_sequence_id": self.event_sequence,
            "user_pseudo_id": visitor_id,
            "user_id": customer_id,
            "user_first_touch_timestamp": int(
                (
                    timestamp
                    - timedelta(days=int(stable_hex("age", visitor_id, length=4), 16) % 365)
                ).timestamp()
                * 1_000_000
            ),
            "stream_id": f"web-{market.code.lower()}",
            "platform": "WEB",
            "device_category": device,
            "browser": browser,
            "geo_country": market.code,
            "privacy_analytics_storage": "Yes",
            "traffic_source_source": channel["source"],
            "traffic_source_medium": channel["medium"],
            "traffic_source_campaign": channel["campaign"],
            "collected_source": channel["source"],
            "collected_medium": channel["medium"],
            "collected_campaign_id": channel["campaign"],
            "session_source": channel["source"],
            "session_medium": channel["medium"],
            "session_campaign_id": channel["campaign"],
            "event_params": [event_parameter(key, value) for key, value in all_params.items()],
            "items": items or [],
            "source_kind": "synthetic_web",
            "source_updated_at": timestamp + timedelta(hours=2),
            "arrived_at": timestamp + timedelta(hours=5),
        }

    @staticmethod
    def _item(product: ProductConfig, price: int, quantity: int = 1) -> dict[str, Any]:
        return {
            "item_id": product.sku,
            "item_name": product.name,
            "item_category": product.category,
            "item_variant": product.family,
            "price": price,
            "quantity": quantity,
            "item_params": [event_parameter("wheel_size", product.wheel_size)],
        }

    def _session(
        self,
        day: date,
        market: MarketConfig,
        index: int,
        rng: np.random.Generator,
    ) -> tuple[
        list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
    ]:
        session_key = stable_id("ses", "session", day, market.code, index)
        visitor_pool = max(3_000, int(self.profile.target_sessions * 0.38))
        visitor_index = int(rng.integers(0, visitor_pool))
        visitor_id = stable_id("usr", "visitor", market.code, visitor_index)
        minute = int(np.clip(rng.normal(18 * 60, 250), 0, 1438))
        started_at = _local_timestamp(day, minute, market.timezone)
        device = str(rng.choice(DEVICE_VALUES, p=DEVICE_WEIGHTS))
        browser_values, browser_weights = BROWSERS[device]
        browser = str(rng.choice(browser_values, p=browser_weights))
        channel_index = int(rng.choice(len(CHANNELS), p=CHANNEL_WEIGHTS))
        channel = CHANNELS[channel_index]
        intent = float(rng.beta(2.0, 2.8))
        is_repeat_visitor = visitor_id in self.first_orders
        product_weights = np.array(
            [1.35 if product.wheel_size in {16, 20, 24} else 0.75 for product in self.bikes]
        )
        product_weights /= product_weights.sum()
        product = self.bikes[int(rng.choice(len(self.bikes), p=product_weights))]
        price = _price_for(product, market)
        b3 = self.config.scenario("B3")
        size_path_probability = _sigmoid(
            -1.15 + float(b3.mechanism["intent_selection_strength"]) * intent
        )
        used_size_path = bool(rng.random() < size_path_probability)
        log_odds = -2.25 + 1.2 * intent + (0.24 if used_size_path else 0.0)
        add_to_cart = bool(rng.random() < _sigmoid(log_odds))
        began_checkout = add_to_cart and bool(rng.random() < (0.46 + 0.24 * intent))
        added_shipping = began_checkout and bool(rng.random() < 0.91)
        added_payment = added_shipping and bool(rng.random() < 0.91)
        payment_probability = 0.78
        b1 = self.config.scenario("B1")
        if _scenario_applies(b1, day, market=market.code, device_category=device):
            payment_probability *= float(b1.mechanism["payment_success_multiplier"])
        purchased = added_payment and bool(rng.random() < payment_probability)
        customer_id = stable_id("cus", "customer", visitor_id) if purchased else None
        events: list[dict[str, Any]] = []
        elapsed = 0

        def emit(
            name: str,
            *,
            params: dict[str, str | int | float | None] | None = None,
            items: list[dict[str, Any]] | None = None,
            step: int | None = None,
            suffix: object = "",
        ) -> None:
            nonlocal elapsed
            elapsed += step if step is not None else int(rng.integers(3, 38))
            events.append(
                self._event(
                    name=name,
                    timestamp=started_at + timedelta(seconds=elapsed),
                    session_key=session_key,
                    visitor_id=visitor_id,
                    customer_id=customer_id,
                    market=market,
                    device=device,
                    browser=browser,
                    channel=channel,
                    params=params,
                    items=items,
                    suffix=suffix,
                )
            )

        emit("session_start", step=0, params={"is_repeat_visitor": int(is_repeat_visitor)})
        emit("page_view", params={"page_type": "home"})
        emit("view_item_list", params={"item_list_name": "featured_rides"})
        if rng.random() < 0.72:
            emit("page_view", params={"page_type": "category"})
        emit("select_item", items=[self._item(product, price)])
        emit("view_item", items=[self._item(product, price)])
        emit("scroll", params={"percent_scrolled": int(rng.choice([50, 75, 90]))})
        if used_size_path:
            size_path_version = "2.1" if day >= date(2025, 1, 1) else "2.0"
            emit("size_path_open", params={"size_path_version": size_path_version})
            for answer_index, question in enumerate(("height", "age", "experience"), start=1):
                emit(
                    "size_path_answer",
                    params={
                        "size_path_version": size_path_version,
                        "question": question,
                        "answer_sequence": answer_index,
                    },
                    suffix=answer_index,
                )
            recommendation: str | None = product.sku
            q6 = self.config.scenario("Q6")
            if _scenario_applies(
                q6,
                day,
                market=market.code,
                device_category=device,
                size_path_version=size_path_version,
            ) and rng.random() < float(q6.mechanism["recommended_product_id_missing_rate"]):
                recommendation = None
            emit(
                "size_path_recommendation",
                params={
                    "size_path_version": size_path_version,
                    "recommended_product_id": recommendation,
                },
                items=[self._item(product, price)],
            )
        orders: list[dict[str, Any]] = []
        order_items: list[dict[str, Any]] = []
        returns: list[dict[str, Any]] = []
        if add_to_cart:
            emit("add_to_cart", items=[self._item(product, price)])
            emit("view_cart", items=[self._item(product, price)])
        if began_checkout:
            emit("begin_checkout", items=[self._item(product, price)])
        if added_shipping:
            emit("add_shipping_info", items=[self._item(product, price)])
        if added_payment:
            emit(
                "add_payment_info",
                params={"payment_type": "card"},
                items=[self._item(product, price)],
            )
        if purchased:
            self.order_sequence += 1
            order_id = stable_id("ord", "order", session_key, self.order_sequence)
            line_products = [product]
            compatible = self.compatible.get(product.sku, [])
            attach_probability = 0.24
            b4 = self.config.scenario("B4")
            if _scenario_applies(b4, day, sku=product.sku):
                attach_probability *= float(b4.mechanism["bundle_exposure_multiplier"])
            if compatible and rng.random() < attach_probability:
                line_products.append(compatible[int(rng.integers(0, len(compatible)))])
            line_rows: list[dict[str, Any]] = []
            event_items: list[dict[str, Any]] = []
            gross = 0
            item_discount = 0
            tax_amount = 0
            fulfilled_at = started_at + timedelta(days=int(rng.integers(1, 4)))
            delivered_at = fulfilled_at + timedelta(days=int(rng.integers(1, 5)))
            for line_index, line_product in enumerate(line_products, start=1):
                line_price = _price_for(line_product, market)
                discount_rate = 0.0
                if channel["channel"] == "Affiliate":
                    discount_rate = 0.07
                elif rng.random() < 0.08:
                    discount_rate = 0.05
                discount = _money(line_price * discount_rate)
                line_tax = _money(
                    (line_price - discount) * TAX_RATES[market.code] / (1 + TAX_RATES[market.code])
                )
                gross += line_price
                item_discount += discount
                tax_amount += line_tax
                order_item_id = stable_id("oli", "order-line", order_id, line_index)
                line_rows.append(
                    {
                        "order_item_id": order_item_id,
                        "order_id": order_id,
                        "customer_id": customer_id,
                        "sku": line_product.sku,
                        "quantity": 1,
                        "currency": market.currency,
                        "unit_list_price": line_price,
                        "discount_amount": discount,
                        "tax_amount": line_tax,
                        "unit_cogs": _money(
                            line_product.unit_cogs_eur / FX_TO_EUR[market.currency]
                        ),
                        "fulfilled_at": fulfilled_at,
                        "delivered_at": delivered_at,
                        "source_updated_at": delivered_at + timedelta(hours=1),
                    }
                )
                event_items.append(self._item(line_product, line_price))
                base_return_probability = 0.115 if line_product.category == "bike" else 0.055
                returned = bool(
                    rng.random() < base_return_probability * (0.78 if used_size_path else 1.0)
                )
                if returned:
                    is_size_reason = bool(rng.random() < (0.34 if used_size_path else 0.51))
                    requested = delivered_at + timedelta(days=int(rng.integers(3, 31)))
                    returns.append(
                        {
                            "return_id": stable_id("ret", "return", order_item_id),
                            "order_item_id": order_item_id,
                            "requested_at": requested,
                            "received_at": requested + timedelta(days=int(rng.integers(2, 7))),
                            "refunded_at": requested + timedelta(days=int(rng.integers(4, 9))),
                            "source_updated_at": requested + timedelta(days=9),
                            "quantity": 1,
                            "reason": "size_not_right"
                            if is_size_reason
                            else str(rng.choice(["changed_mind", "damaged_in_transit", "other"])),
                            "currency": market.currency,
                            "refund_amount": line_price - discount,
                            "processing_cost": _money(line_price * 0.035),
                        }
                    )
            shipping = (
                0
                if gross >= _money(30000 / FX_TO_EUR[market.currency])
                else _money(1200 / FX_TO_EUR[market.currency])
            )
            total = gross - item_discount + shipping
            placed_at = started_at + timedelta(seconds=elapsed + 1)
            orders.append(
                {
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "session_key": session_key,
                    "placed_at": placed_at,
                    "paid_at": placed_at,
                    "cancelled_at": None,
                    "source_updated_at": delivered_at + timedelta(hours=1),
                    "status": "fulfilled",
                    "site_market": market.code,
                    "currency": market.currency,
                    "gross_item_sales": gross,
                    "item_discount": item_discount,
                    "tax_amount": tax_amount,
                    "shipping_charged": shipping,
                    "order_total": total,
                    "payment_cost": _money(total * 0.023 + 30),
                    "fulfillment_cost": _money(1150 / FX_TO_EUR[market.currency]),
                    "is_test": False,
                }
            )
            order_items.extend(line_rows)
            emit(
                "purchase",
                params={
                    "transaction_id": order_id,
                    "currency": market.currency,
                    "value": total / 100,
                    "coupon": "PARTNER7" if channel["channel"] == "Affiliate" else None,
                },
                items=event_items,
            )
            q4 = self.config.scenario("Q4")
            if q4.active_on(day) and rng.random() < float(q4.mechanism["polluted_purchase_rate"]):
                events[-1]["collected_source"] = "pay-redirect"
                events[-1]["collected_medium"] = "referral"
            q1 = self.config.scenario("Q1")
            if q1.active_on(day) and rng.random() < float(q1.mechanism["duplicate_purchase_rate"]):
                emit(
                    "purchase",
                    params={
                        "transaction_id": order_id,
                        "currency": market.currency,
                        "value": total / 100,
                        "duplicate_reason": "client_retry",
                    },
                    items=event_items,
                    step=1,
                    suffix="duplicate",
                )
            if customer_id not in self.first_orders:
                self.first_orders[customer_id] = {
                    "customer_id": customer_id,
                    "first_order_at": placed_at,
                    "first_order_date": placed_at.date(),
                    "acquisition_market": market.code,
                    "acquisition_channel": channel["channel"],
                    "source_updated_at": placed_at + timedelta(hours=1),
                }
        emit("user_engagement", params={"session_engaged": int(add_to_cart)})
        return events, orders, order_items, returns

    def _inventory(
        self,
        day: date,
        market: MarketConfig,
        units_sold: Counter[str],
        rng: np.random.Generator,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        b2 = self.config.scenario("B2")
        updated = _local_timestamp(day, 23 * 60, market.timezone)
        for product in self.config.catalog.products:
            base = 65 if product.category == "bike" else 180
            beginning = max(0, int(base + rng.normal(0, base * 0.18)))
            receipts = int(rng.choice([0, 0, 0, 12, 24]))
            if _scenario_applies(b2, day, market=market.code, sku=product.sku):
                beginning = max(
                    0, _money(beginning * float(b2.mechanism["available_to_sell_multiplier"]))
                )
                receipts = 0
            sold = int(units_sold[product.sku])
            reserved = max(0, int(rng.poisson(1.5 if product.category == "bike" else 0.6)))
            ending = max(0, beginning + receipts - sold - reserved)
            stockout = 0 if ending > 3 else int(rng.integers(120, 1441))
            rows.append(
                {
                    "inventory_date": day,
                    "site_market": market.code,
                    "sku": product.sku,
                    "beginning_ats": beginning,
                    "receipts": receipts,
                    "units_reserved": reserved,
                    "units_sold": sold,
                    "ending_ats": ending,
                    "stockout_minutes": stockout,
                    "stock_status": "out_of_stock"
                    if ending == 0
                    else ("low_stock" if ending <= 3 else "in_stock"),
                    "source_updated_at": updated,
                }
            )
        return rows

    @staticmethod
    def _marketing(
        day: date, market: MarketConfig, rng: np.random.Generator
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for channel in CHANNELS[:5]:
            base_cost_eur = {
                "Organic Search": 650,
                "Paid Search": 2400,
                "Paid Social": 1800,
                "Email": 320,
                "Affiliate": 750,
            }[channel["channel"]]
            cost = _money(
                base_cost_eur * 100 / FX_TO_EUR[market.currency] * rng.uniform(0.72, 1.32)
            )
            clicks = max(1, int(cost / rng.uniform(90, 240)))
            rows.append(
                {
                    "spend_date": day,
                    "site_market": market.code,
                    "campaign_id": channel["campaign"],
                    "channel": channel["channel"],
                    "source": channel["source"],
                    "medium": channel["medium"],
                    "impressions": clicks * int(rng.integers(16, 45)),
                    "clicks": clicks,
                    "currency": market.currency,
                    "cost": cost,
                    "source_updated_at": _local_timestamp(day, 23 * 60, market.timezone),
                }
            )
        return rows

    def _fx(self, day: date, currencies: set[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        q3 = self.config.scenario("Q3")
        for currency in sorted(currencies):
            if currency != "EUR" and _scenario_applies(q3, day, currency=currency):
                continue
            day_wave = 1 + 0.025 * math.sin(day.toordinal() / 31)
            rate = Decimal(str(FX_TO_EUR[currency] * (1.0 if currency == "EUR" else day_wave)))
            rows.append(
                {
                    "rate_date": day,
                    "source_currency": currency,
                    "reporting_currency": self.config.generator.reporting_currency,
                    "rate": rate.quantize(Decimal("0.00000001")),
                    "provider_date": day,
                    "loaded_at": datetime.combine(day, time(23, 30), tzinfo=UTC),
                }
            )
        return rows

    def generate(self, output_dir: Path) -> GenerationResult:
        writer = DatasetWriter(output_dir)
        static = _static_records(self.config, self.profile_name)
        for table_name, rows in static.items():
            writer.write(table_name, rows)
        allocations = _allocate_sessions(self.config, self.profile_name)
        currencies = {self.market_map[code].currency for code in self.profile.markets}
        current_day: date | None = None
        try:
            for (day, market_code), session_count in allocations.items():
                market = self.market_map[market_code]
                rng = np.random.default_rng(
                    stable_int_seed(
                        self.config.generator.master_seed, "day-market", day, market_code
                    )
                )
                events: list[dict[str, Any]] = []
                orders: list[dict[str, Any]] = []
                order_items: list[dict[str, Any]] = []
                returns: list[dict[str, Any]] = []
                for session_index in range(session_count):
                    generated = self._session(day, market, session_index, rng)
                    events.extend(generated[0])
                    orders.extend(generated[1])
                    order_items.extend(generated[2])
                    returns.extend(generated[3])
                writer.write("events", events)
                writer.write("orders", orders)
                writer.write("order_items", order_items)
                writer.write("returns", returns)
                sold = Counter(
                    row["sku"] for row in order_items for _ in range(int(row["quantity"]))
                )
                writer.write("inventory_daily", self._inventory(day, market, sold, rng))
                writer.write("marketing_spend", self._marketing(day, market, rng))
                for table_name, row_count in (
                    ("events", len(events)),
                    ("orders", len(orders)),
                    ("order_items", len(order_items)),
                    ("returns", len(returns)),
                    ("inventory_daily", len(self.config.catalog.products)),
                    ("marketing_spend", 5),
                ):
                    received = _local_timestamp(day, 23 * 60 + 15, market.timezone)
                    writer.write(
                        "source_delivery_log",
                        [
                            {
                                "delivery_id": stable_id(
                                    "del", "delivery", table_name, day, market.code
                                ),
                                "source_name": table_name,
                                "partition_date": day,
                                "expected_at": received - timedelta(minutes=15),
                                "received_at": received,
                                "loaded_at": None,
                                "row_count": row_count,
                                "checksum": stable_hex(
                                    "delivery-checksum",
                                    table_name,
                                    day,
                                    market.code,
                                    row_count,
                                    length=32,
                                ),
                                "delivery_version": 1,
                            }
                        ],
                    )
                if current_day != day:
                    writer.write("exchange_rates", self._fx(day, currencies))
                    current_day = day
            writer.write("customers", self.first_orders.values())
        finally:
            writer.close()
        manifest = writer.manifest(
            {
                "project": "Rider 360",
                "profile": self.profile_name,
                "generator_version": self.config.generator.generator_version,
                "master_seed": self.config.generator.master_seed,
                "start_date": self.profile.start_date,
                "end_date": self.profile.end_date,
                "markets": self.profile.markets,
                "target_sessions": self.profile.target_sessions,
                "scenario_ids": [
                    scenario.id for scenario in self.config.scenarios.scenarios if scenario.enabled
                ],
            }
        )
        manifest_path = write_manifest(output_dir, manifest)
        return GenerationResult(
            profile=self.profile_name,
            output_dir=output_dir,
            counts=dict(writer.counts),
            manifest_path=manifest_path,
        )


def generate_dataset(
    profile_name: str,
    *,
    config_dir: Path = DEFAULT_CONFIG_DIR,
    output_dir: Path | None = None,
) -> GenerationResult:
    config = ProjectConfig.load(config_dir)
    profile = config.profile(profile_name)
    destination = output_dir or DEFAULT_DATA_DIR / profile.output_subdir
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(
            f"{destination} is not empty; remove it explicitly or choose a different --output directory"
        )
    destination.mkdir(parents=True, exist_ok=True)
    return SyntheticGenerator(config, profile_name).generate(destination)
