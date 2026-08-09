from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import pyarrow.parquet as pq
from sqlalchemy import create_engine, text

from rider360.warehouse.publisher import PUBLISH_ALLOWLIST

CHANNEL_LOOKUP = {
    ("search", "organic"): "Organic Search",
    ("search_ads", "cpc"): "Paid Search",
    ("social_ads", "paid_social"): "Paid Social",
    ("riderly_news", "email"): "Email",
    ("partner_path", "affiliate"): "Affiliate",
    ("(direct)", "(none)"): "Direct",
}
FX_TO_EUR = {"EUR": 1.0, "GBP": 1.16, "USD": 0.92}


def _read(dataset_dir: Path, table: str) -> pd.DataFrame:
    return pq.read_table(dataset_dir / table).to_pandas()


def _event_value(parameter: dict[str, Any]) -> Any:
    value = parameter["value"]
    return value.get("string_value") or value.get("int_value") or value.get("double_value")


def _sessions_and_quality(dataset_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    sessions: dict[str, dict[str, Any]] = {}
    quality: dict[tuple[Any, str], dict[str, int]] = defaultdict(
        lambda: {
            "event_rows": 0,
            "purchase_event_rows": 0,
            "purchases_missing_transaction_id": 0,
            "recommendation_events": 0,
            "recommendations_missing_product": 0,
            "late_events": 0,
        }
    )
    parquet = pq.ParquetFile(dataset_dir / "events" / "part-00000.parquet")
    for batch in parquet.iter_batches(batch_size=20_000):
        for event in batch.to_pylist():
            params = {
                parameter["key"]: _event_value(parameter) for parameter in event["event_params"]
            }
            session_key = params["session_key"]
            current = sessions.setdefault(
                session_key,
                {
                    "session_key": session_key,
                    "session_date": event["event_date"],
                    "site_market": event["geo_country"],
                    "device_category": event["device_category"],
                    "channel": CHANNEL_LOOKUP.get(
                        (event["session_source"], event["session_medium"]), "Other"
                    ),
                    "viewed_product": False,
                    "used_size_path": False,
                    "added_to_cart": False,
                    "began_checkout": False,
                    "added_shipping_info": False,
                    "added_payment_info": False,
                    "purchased": False,
                },
            )
            event_name = event["event_name"]
            flag = {
                "view_item": "viewed_product",
                "size_path_open": "used_size_path",
                "add_to_cart": "added_to_cart",
                "begin_checkout": "began_checkout",
                "add_shipping_info": "added_shipping_info",
                "add_payment_info": "added_payment_info",
                "purchase": "purchased",
            }.get(event_name)
            if flag:
                current[flag] = True
            q = quality[(event["event_date"], event["geo_country"])]
            q["event_rows"] += 1
            if event_name == "purchase":
                q["purchase_event_rows"] += 1
                q["purchases_missing_transaction_id"] += int(not params.get("transaction_id"))
            if event_name == "size_path_recommendation":
                q["recommendation_events"] += 1
                q["recommendations_missing_product"] += int(
                    not params.get("recommended_product_id")
                )
            q["late_events"] += int(
                (
                    event["arrived_at"]
                    - pd.Timestamp(event["event_timestamp"], unit="us", tz="UTC")
                ).total_seconds()
                > 86_400
            )
    session_frame = pd.DataFrame(sessions.values())
    quality_rows = [
        {"metric_date": key[0], "site_market": key[1], **metrics}
        for key, metrics in quality.items()
    ]
    quality_frame = pd.DataFrame(quality_rows)
    quality_frame["orders_missing_fx"] = 0
    quality_frame["recommendation_parameter_missing_rate"] = quality_frame[
        "recommendations_missing_product"
    ] / quality_frame["recommendation_events"].replace(0, pd.NA)
    return session_frame, quality_frame


def _executive(
    sessions: pd.DataFrame,
    orders: pd.DataFrame,
    returns: pd.DataFrame,
    order_items: pd.DataFrame,
    spend: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    session_metrics = (
        sessions.groupby(["session_date", "site_market", "channel"], as_index=False)
        .agg(
            sessions=("session_key", "size"),
            add_to_cart_sessions=("added_to_cart", "sum"),
            checkout_sessions=("began_checkout", "sum"),
            purchase_sessions=("purchased", "sum"),
        )
        .rename(columns={"session_date": "metric_date"})
    )
    line_returns = order_items[["order_item_id", "order_id"]].merge(
        returns[["order_item_id", "refund_amount", "processing_cost", "reason"]],
        how="left",
        on="order_item_id",
    )
    return_metrics = line_returns.groupby("order_id", as_index=False).agg(
        refund_amount=("refund_amount", "sum"),
        return_processing_cost=("processing_cost", "sum"),
        returned_line_count=("reason", "count"),
        size_return_line_count=("reason", lambda values: (values == "size_not_right").sum()),
    )
    enriched = orders.merge(
        sessions[["session_key", "channel", "used_size_path"]], on="session_key"
    )
    enriched = enriched.merge(return_metrics, how="left", on="order_id").fillna(
        {
            "refund_amount": 0,
            "return_processing_cost": 0,
            "returned_line_count": 0,
            "size_return_line_count": 0,
        }
    )
    enriched["metric_date"] = pd.to_datetime(enriched["placed_at"]).dt.date
    enriched["fx_to_eur"] = enriched["currency"].map(FX_TO_EUR)
    enriched["revenue_eur"] = enriched["order_total"] / 100 * enriched["fx_to_eur"]
    enriched["net_item_revenue_eur"] = (
        (enriched["gross_item_sales"] - enriched["item_discount"] - enriched["refund_amount"])
        / 100
        * enriched["fx_to_eur"]
    )
    enriched["variable_cost_eur"] = (
        (
            enriched["payment_cost"]
            + enriched["fulfillment_cost"]
            + enriched["return_processing_cost"]
        )
        / 100
        * enriched["fx_to_eur"]
    )
    order_metrics = enriched.groupby(["metric_date", "site_market", "channel"], as_index=False).agg(
        orders=("order_id", "size"),
        purchasing_customers=("customer_id", "nunique"),
        revenue_eur=("revenue_eur", "sum"),
        net_item_revenue_eur=("net_item_revenue_eur", "sum"),
        variable_cost_eur=("variable_cost_eur", "sum"),
        refunds_eur=("refund_amount", lambda value: (value / 100).sum()),
    )
    order_metrics["contribution_margin_eur"] = (
        order_metrics["net_item_revenue_eur"] - order_metrics["variable_cost_eur"]
    )
    spend = spend.copy()
    spend["metric_date"] = spend["spend_date"]
    spend["marketing_spend_eur"] = spend["cost"] / 100 * spend["currency"].map(FX_TO_EUR)
    spend_metrics = spend.groupby(["metric_date", "site_market", "channel"], as_index=False).agg(
        marketing_spend_eur=("marketing_spend_eur", "sum")
    )
    result = session_metrics.merge(
        order_metrics, how="outer", on=["metric_date", "site_market", "channel"]
    ).merge(spend_metrics, how="outer", on=["metric_date", "site_market", "channel"])
    numeric = result.select_dtypes(include="number").columns
    result[numeric] = result[numeric].fillna(0)
    result["session_conversion_rate"] = result["orders"] / result["sessions"].replace(0, pd.NA)
    result["average_order_value_eur"] = result["revenue_eur"] / result["orders"].replace(0, pd.NA)
    result["marketing_roi"] = (
        result["contribution_margin_eur"] - result["marketing_spend_eur"]
    ) / result["marketing_spend_eur"].replace(0, pd.NA)
    return result, enriched


def _funnel(sessions: pd.DataFrame) -> pd.DataFrame:
    grouped = sessions.groupby(
        ["session_date", "site_market", "device_category", "channel"], as_index=False
    ).agg(
        sessions=("session_key", "size"),
        product_view_sessions=("viewed_product", "sum"),
        add_to_cart_sessions=("added_to_cart", "sum"),
        checkout_sessions=("began_checkout", "sum"),
        shipping_sessions=("added_shipping_info", "sum"),
        payment_sessions=("added_payment_info", "sum"),
        purchase_sessions=("purchased", "sum"),
    )
    grouped = grouped.rename(columns={"session_date": "metric_date"})
    grouped["view_to_cart_rate"] = grouped["add_to_cart_sessions"] / grouped[
        "product_view_sessions"
    ].replace(0, pd.NA)
    grouped["cart_to_checkout_rate"] = grouped["checkout_sessions"] / grouped[
        "add_to_cart_sessions"
    ].replace(0, pd.NA)
    grouped["payment_to_purchase_rate"] = grouped["purchase_sessions"] / grouped[
        "payment_sessions"
    ].replace(0, pd.NA)
    grouped["session_conversion_rate"] = grouped["purchase_sessions"] / grouped["sessions"].replace(
        0, pd.NA
    )
    return grouped


def _sizepath(sessions: pd.DataFrame, enriched_orders: pd.DataFrame) -> pd.DataFrame:
    outcomes = sessions.merge(
        enriched_orders[["session_key", "order_id", "size_return_line_count"]].drop_duplicates(
            "session_key"
        ),
        how="left",
        on="session_key",
    )
    outcomes["had_size_return"] = outcomes["size_return_line_count"].fillna(0) > 0
    outcomes["has_mature_order"] = outcomes["order_id"].notna()
    grouped = outcomes.groupby(
        ["session_date", "site_market", "device_category", "used_size_path"], as_index=False
    ).agg(
        sessions=("session_key", "size"),
        purchasing_sessions=("purchased", "sum"),
        size_return_sessions=("had_size_return", "sum"),
        mature_order_sessions=("has_mature_order", "sum"),
    )
    grouped = grouped.rename(columns={"session_date": "metric_date"})
    grouped["conversion_rate"] = grouped["purchasing_sessions"] / grouped["sessions"]
    grouped["mature_size_return_rate"] = grouped["size_return_sessions"] / grouped[
        "mature_order_sessions"
    ].replace(0, pd.NA)
    return grouped


def _inventory(dataset_dir: Path) -> pd.DataFrame:
    inventory = _read(dataset_dir, "inventory_daily")
    products = _read(dataset_dir, "products")
    result = inventory.merge(
        products[["sku", "product_name", "category", "family", "wheel_size"]], on="sku"
    ).rename(columns={"inventory_date": "metric_date"})
    result["stockout_day_fraction"] = result["stockout_minutes"] / 1440
    return result[
        [
            "metric_date",
            "site_market",
            "sku",
            "product_name",
            "category",
            "family",
            "wheel_size",
            "beginning_ats",
            "receipts",
            "units_reserved",
            "units_sold",
            "ending_ats",
            "stockout_minutes",
            "stock_status",
            "stockout_day_fraction",
        ]
    ]


def _accessory_attach(dataset_dir: Path, orders: pd.DataFrame) -> pd.DataFrame:
    items = _read(dataset_dir, "order_items")
    products = _read(dataset_dir, "products")
    compatibility = _read(dataset_dir, "product_accessory_compatibility")
    enriched = items.merge(
        products[["sku", "product_name", "category", "family", "wheel_size"]], on="sku"
    ).merge(orders[["order_id", "placed_at", "site_market"]], on="order_id")
    rows: list[dict[str, Any]] = []
    compatible_pairs = set(zip(compatibility.parent_sku, compatibility.accessory_sku, strict=True))
    for order_id, lines in enriched.groupby("order_id"):
        bikes = lines[lines.category == "bike"]
        accessories = lines[lines.category == "accessory"]
        for _, bike in bikes.iterrows():
            rows.append(
                {
                    "metric_date": pd.Timestamp(bike.placed_at).date(),
                    "site_market": bike.site_market,
                    "parent_sku": bike.sku,
                    "parent_product": bike.product_name,
                    "parent_family": bike.family,
                    "wheel_size": bike.wheel_size,
                    "bike_order": order_id,
                    "any_accessory": not accessories.empty,
                    "compatible_accessory": any(
                        (bike.sku, accessory.sku) in compatible_pairs
                        for _, accessory in accessories.iterrows()
                    ),
                }
            )
    frame = pd.DataFrame(rows)
    grouped = frame.groupby(
        [
            "metric_date",
            "site_market",
            "parent_sku",
            "parent_product",
            "parent_family",
            "wheel_size",
        ],
        as_index=False,
    ).agg(
        bike_orders=("bike_order", "size"),
        orders_with_any_accessory=("any_accessory", "sum"),
        orders_with_compatible_accessory=("compatible_accessory", "sum"),
    )
    grouped["compatible_attach_rate"] = (
        grouped["orders_with_compatible_accessory"] / grouped["bike_orders"]
    )
    return grouped


def _ltv(dataset_dir: Path, enriched_orders: pd.DataFrame) -> pd.DataFrame:
    customers = _read(dataset_dir, "customers")
    frame = customers.merge(enriched_orders, on="customer_id")
    frame["cohort_month"] = (
        pd.to_datetime(frame["first_order_date"]).dt.to_period("M").dt.to_timestamp()
    )
    frame["contribution_margin_eur"] = frame["net_item_revenue_eur"] - frame["variable_cost_eur"]
    frame["days_since_first"] = (
        pd.to_datetime(frame["placed_at"]).dt.date - frame["first_order_date"]
    ).map(lambda value: value.days)
    grouped = frame.groupby(
        ["cohort_month", "acquisition_market", "acquisition_channel"], as_index=False
    ).agg(
        customers=("customer_id", "nunique"),
        lifetime_orders=("order_id", "nunique"),
        observed_contribution_margin_eur=("contribution_margin_eur", "sum"),
        contribution_margin_90d_eur=(
            "contribution_margin_eur",
            lambda values: values[frame.loc[values.index, "days_since_first"] <= 90].sum(),
        ),
        contribution_margin_365d_eur=(
            "contribution_margin_eur",
            lambda values: values[frame.loc[values.index, "days_since_first"] <= 365].sum(),
        ),
    )
    grouped["contribution_ltv_per_customer_eur"] = (
        grouped["observed_contribution_margin_eur"] / grouped["customers"]
    )
    grouped["orders_per_customer"] = grouped["lifetime_orders"] / grouped["customers"]
    return grouped


def build_local_marts(dataset_dir: Path) -> dict[str, pd.DataFrame]:
    sessions, quality = _sessions_and_quality(dataset_dir)
    orders = _read(dataset_dir, "orders")
    order_items = _read(dataset_dir, "order_items")
    returns = _read(dataset_dir, "returns")
    spend = _read(dataset_dir, "marketing_spend")
    executive, enriched_orders = _executive(sessions, orders, returns, order_items, spend)
    return {
        "mart_executive_daily": executive,
        "mart_funnel_daily": _funnel(sessions),
        "mart_sizepath_daily": _sizepath(sessions, enriched_orders),
        "mart_inventory_daily": _inventory(dataset_dir),
        "mart_accessory_attach_daily": _accessory_attach(dataset_dir, orders),
        "mart_customer_ltv": _ltv(dataset_dir, enriched_orders),
        "mart_data_quality_daily": quality,
    }


def publish_local_marts(
    dataset_dir: Path,
    pg_dsn: str,
    *,
    target_schema: str = "r360_bi",
    reader_role: str = "r360_metabase",
) -> dict[str, int]:
    marts = build_local_marts(dataset_dir)
    if tuple(marts) != PUBLISH_ALLOWLIST:
        raise RuntimeError(
            "local mart contract does not match the production publication allowlist"
        )
    suffix = uuid4().hex[:10]
    staging = f"r360_bi_next_{suffix}"
    previous = f"r360_bi_previous_{suffix}"
    engine = create_engine(pg_dsn)
    with engine.begin() as connection:
        connection.execute(text(f'create schema "{staging}"'))
        for table_name, frame in marts.items():
            frame.to_sql(table_name, connection, schema=staging, index=False, if_exists="fail")
            connection.execute(
                text(f'grant select on "{staging}"."{table_name}" to "{reader_role}"')
            )
        connection.execute(text(f'grant usage on schema "{staging}" to "{reader_role}"'))
        exists = connection.execute(
            text("select exists(select 1 from pg_namespace where nspname = :name)"),
            {"name": target_schema},
        ).scalar_one()
        if exists:
            connection.execute(text(f'alter schema "{target_schema}" rename to "{previous}"'))
        connection.execute(text(f'alter schema "{staging}" rename to "{target_schema}"'))
        if exists:
            connection.execute(text(f'drop schema "{previous}" cascade'))
    engine.dispose()
    return {name: len(frame) for name, frame in marts.items()}
