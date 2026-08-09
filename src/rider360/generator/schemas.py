from __future__ import annotations

from collections.abc import Mapping

import pyarrow as pa

PARAM_VALUE = pa.struct(
    [
        pa.field("string_value", pa.string()),
        pa.field("int_value", pa.int64()),
        pa.field("double_value", pa.float64()),
    ]
)
PARAM = pa.struct([pa.field("key", pa.string(), nullable=False), pa.field("value", PARAM_VALUE)])
ITEM = pa.struct(
    [
        pa.field("item_id", pa.string()),
        pa.field("item_name", pa.string()),
        pa.field("item_category", pa.string()),
        pa.field("item_variant", pa.string()),
        pa.field("price", pa.int64()),
        pa.field("quantity", pa.int64()),
        pa.field("item_params", pa.list_(PARAM)),
    ]
)

SCHEMAS: Mapping[str, pa.Schema] = {
    "events": pa.schema(
        [
            pa.field("event_date", pa.date32(), nullable=False),
            pa.field("event_timestamp", pa.int64(), nullable=False),
            pa.field("event_name", pa.string(), nullable=False),
            pa.field("event_id", pa.string(), nullable=False),
            pa.field("event_bundle_sequence_id", pa.int64(), nullable=False),
            pa.field("user_pseudo_id", pa.string()),
            pa.field("user_id", pa.string()),
            pa.field("user_first_touch_timestamp", pa.int64()),
            pa.field("stream_id", pa.string(), nullable=False),
            pa.field("platform", pa.string(), nullable=False),
            pa.field("device_category", pa.string()),
            pa.field("browser", pa.string()),
            pa.field("geo_country", pa.string()),
            pa.field("privacy_analytics_storage", pa.string()),
            pa.field("traffic_source_source", pa.string()),
            pa.field("traffic_source_medium", pa.string()),
            pa.field("traffic_source_campaign", pa.string()),
            pa.field("collected_source", pa.string()),
            pa.field("collected_medium", pa.string()),
            pa.field("collected_campaign_id", pa.string()),
            pa.field("session_source", pa.string()),
            pa.field("session_medium", pa.string()),
            pa.field("session_campaign_id", pa.string()),
            pa.field("event_params", pa.list_(PARAM)),
            pa.field("items", pa.list_(ITEM)),
            pa.field("source_kind", pa.string()),
            pa.field("source_updated_at", pa.timestamp("us", tz="UTC")),
            pa.field("arrived_at", pa.timestamp("us", tz="UTC")),
        ]
    ),
    "orders": pa.schema(
        [
            pa.field("order_id", pa.string(), nullable=False),
            pa.field("customer_id", pa.string()),
            pa.field("session_key", pa.string()),
            pa.field("placed_at", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("paid_at", pa.timestamp("us", tz="UTC")),
            pa.field("cancelled_at", pa.timestamp("us", tz="UTC")),
            pa.field("source_updated_at", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("status", pa.string(), nullable=False),
            pa.field("site_market", pa.string(), nullable=False),
            pa.field("currency", pa.string(), nullable=False),
            pa.field("gross_item_sales", pa.int64(), nullable=False),
            pa.field("item_discount", pa.int64(), nullable=False),
            pa.field("tax_amount", pa.int64(), nullable=False),
            pa.field("shipping_charged", pa.int64(), nullable=False),
            pa.field("order_total", pa.int64(), nullable=False),
            pa.field("payment_cost", pa.int64(), nullable=False),
            pa.field("fulfillment_cost", pa.int64(), nullable=False),
            pa.field("is_test", pa.bool_(), nullable=False),
        ]
    ),
    "order_items": pa.schema(
        [
            pa.field("order_item_id", pa.string(), nullable=False),
            pa.field("order_id", pa.string(), nullable=False),
            pa.field("customer_id", pa.string()),
            pa.field("sku", pa.string(), nullable=False),
            pa.field("quantity", pa.int64(), nullable=False),
            pa.field("currency", pa.string(), nullable=False),
            pa.field("unit_list_price", pa.int64(), nullable=False),
            pa.field("discount_amount", pa.int64(), nullable=False),
            pa.field("tax_amount", pa.int64(), nullable=False),
            pa.field("unit_cogs", pa.int64(), nullable=False),
            pa.field("fulfilled_at", pa.timestamp("us", tz="UTC")),
            pa.field("delivered_at", pa.timestamp("us", tz="UTC")),
            pa.field("source_updated_at", pa.timestamp("us", tz="UTC"), nullable=False),
        ]
    ),
    "returns": pa.schema(
        [
            pa.field("return_id", pa.string(), nullable=False),
            pa.field("order_item_id", pa.string(), nullable=False),
            pa.field("requested_at", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("received_at", pa.timestamp("us", tz="UTC")),
            pa.field("refunded_at", pa.timestamp("us", tz="UTC")),
            pa.field("source_updated_at", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("quantity", pa.int64(), nullable=False),
            pa.field("reason", pa.string(), nullable=False),
            pa.field("currency", pa.string(), nullable=False),
            pa.field("refund_amount", pa.int64(), nullable=False),
            pa.field("processing_cost", pa.int64(), nullable=False),
        ]
    ),
    "products": pa.schema(
        [
            pa.field("product_version_id", pa.string(), nullable=False),
            pa.field("sku", pa.string(), nullable=False),
            pa.field("product_name", pa.string(), nullable=False),
            pa.field("category", pa.string(), nullable=False),
            pa.field("family", pa.string(), nullable=False),
            pa.field("wheel_size", pa.int64()),
            pa.field("age_band", pa.string()),
            pa.field("height_band", pa.string()),
            pa.field("valid_from", pa.date32(), nullable=False),
            pa.field("valid_to", pa.date32()),
            pa.field("status", pa.string(), nullable=False),
        ]
    ),
    "product_market_prices": pa.schema(
        [
            pa.field("price_version_id", pa.string(), nullable=False),
            pa.field("sku", pa.string(), nullable=False),
            pa.field("site_market", pa.string(), nullable=False),
            pa.field("currency", pa.string(), nullable=False),
            pa.field("list_price", pa.int64(), nullable=False),
            pa.field("promotional_price", pa.int64()),
            pa.field("valid_from", pa.date32(), nullable=False),
            pa.field("valid_to", pa.date32()),
        ]
    ),
    "product_accessory_compatibility": pa.schema(
        [
            pa.field("compatibility_id", pa.string(), nullable=False),
            pa.field("parent_sku", pa.string(), nullable=False),
            pa.field("accessory_sku", pa.string(), nullable=False),
            pa.field("compatibility_type", pa.string(), nullable=False),
            pa.field("valid_from", pa.date32(), nullable=False),
            pa.field("valid_to", pa.date32()),
        ]
    ),
    "inventory_daily": pa.schema(
        [
            pa.field("inventory_date", pa.date32(), nullable=False),
            pa.field("site_market", pa.string(), nullable=False),
            pa.field("sku", pa.string(), nullable=False),
            pa.field("beginning_ats", pa.int64(), nullable=False),
            pa.field("receipts", pa.int64(), nullable=False),
            pa.field("units_reserved", pa.int64(), nullable=False),
            pa.field("units_sold", pa.int64(), nullable=False),
            pa.field("ending_ats", pa.int64(), nullable=False),
            pa.field("stockout_minutes", pa.int64(), nullable=False),
            pa.field("stock_status", pa.string(), nullable=False),
            pa.field("source_updated_at", pa.timestamp("us", tz="UTC"), nullable=False),
        ]
    ),
    "marketing_spend": pa.schema(
        [
            pa.field("spend_date", pa.date32(), nullable=False),
            pa.field("site_market", pa.string(), nullable=False),
            pa.field("campaign_id", pa.string(), nullable=False),
            pa.field("channel", pa.string(), nullable=False),
            pa.field("source", pa.string(), nullable=False),
            pa.field("medium", pa.string(), nullable=False),
            pa.field("impressions", pa.int64(), nullable=False),
            pa.field("clicks", pa.int64(), nullable=False),
            pa.field("currency", pa.string(), nullable=False),
            pa.field("cost", pa.int64(), nullable=False),
            pa.field("source_updated_at", pa.timestamp("us", tz="UTC"), nullable=False),
        ]
    ),
    "exchange_rates": pa.schema(
        [
            pa.field("rate_date", pa.date32(), nullable=False),
            pa.field("source_currency", pa.string(), nullable=False),
            pa.field("reporting_currency", pa.string(), nullable=False),
            pa.field("rate", pa.decimal128(18, 8), nullable=False),
            pa.field("provider_date", pa.date32(), nullable=False),
            pa.field("loaded_at", pa.timestamp("us", tz="UTC"), nullable=False),
        ]
    ),
    "customers": pa.schema(
        [
            pa.field("customer_id", pa.string(), nullable=False),
            pa.field("first_order_at", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("first_order_date", pa.date32(), nullable=False),
            pa.field("acquisition_market", pa.string(), nullable=False),
            pa.field("acquisition_channel", pa.string(), nullable=False),
            pa.field("source_updated_at", pa.timestamp("us", tz="UTC"), nullable=False),
        ]
    ),
    "source_delivery_log": pa.schema(
        [
            pa.field("delivery_id", pa.string(), nullable=False),
            pa.field("source_name", pa.string(), nullable=False),
            pa.field("partition_date", pa.date32(), nullable=False),
            pa.field("expected_at", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("received_at", pa.timestamp("us", tz="UTC"), nullable=False),
            pa.field("loaded_at", pa.timestamp("us", tz="UTC")),
            pa.field("row_count", pa.int64(), nullable=False),
            pa.field("checksum", pa.string(), nullable=False),
            pa.field("delivery_version", pa.int64(), nullable=False),
        ]
    ),
}


def event_parameter(key: str, value: str | int | float | None) -> dict[str, object]:
    result: dict[str, object | None] = {
        "string_value": None,
        "int_value": None,
        "double_value": None,
    }
    if isinstance(value, bool):
        result["int_value"] = int(value)
    elif isinstance(value, int):
        result["int_value"] = value
    elif isinstance(value, float):
        result["double_value"] = value
    elif value is not None:
        result["string_value"] = str(value)
    return {"key": key, "value": result}
