from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass(frozen=True)
class CardSpec:
    name: str
    description: str
    sql: str
    display: str
    visualization_settings: dict[str, Any]
    col: int
    row: int
    size_x: int
    size_y: int
    market_column: str = "site_market"
    date_column: str | None = "metric_date"


def _currency(column: str) -> dict[str, Any]:
    return {
        "column_settings": {
            json.dumps(["name", column], separators=(",", ":")): {
                "number_style": "currency",
                "currency": "EUR",
                "currency_style": "symbol",
                "decimals": 0,
            }
        }
    }


def _percent(*columns: str) -> dict[str, Any]:
    return {
        "column_settings": {
            json.dumps(["name", column], separators=(",", ":")): {
                "number_style": "percent",
                "decimals": 1,
            }
            for column in columns
        }
    }


CARD_SPECS: tuple[CardSpec, ...] = (
    CardSpec(
        "Net Revenue",
        "Net item revenue after discounts and refunds.",
        "select round(sum(net_item_revenue_eur)::numeric, 0) as net_revenue_eur "
        "from r360_bi.mart_executive_daily where 1=1 {filters}",
        "scalar",
        _currency("net_revenue_eur"),
        0,
        0,
        6,
        3,
    ),
    CardSpec(
        "Orders",
        "Operational orders reconciled to deduplicated purchase transactions.",
        "select sum(orders)::bigint as orders from r360_bi.mart_executive_daily "
        "where 1=1 {filters}",
        "scalar",
        {},
        6,
        0,
        6,
        3,
    ),
    CardSpec(
        "Session Conversion",
        "Orders divided by attribution-safe sessions.",
        "select sum(orders)::numeric / nullif(sum(sessions), 0) as session_conversion_rate "
        "from r360_bi.mart_executive_daily where 1=1 {filters}",
        "scalar",
        _percent("session_conversion_rate"),
        12,
        0,
        6,
        3,
    ),
    CardSpec(
        "Contribution After Marketing",
        "Net item revenue less variable costs and marketing spend.",
        "select round(sum(contribution_margin_eur - marketing_spend_eur)::numeric, 0) "
        "as contribution_after_marketing_eur from r360_bi.mart_executive_daily "
        "where 1=1 {filters}",
        "scalar",
        _currency("contribution_after_marketing_eur"),
        18,
        0,
        6,
        3,
    ),
    CardSpec(
        "Average Order Value",
        "Gross operational revenue divided by orders for the selected slice.",
        "select round(sum(revenue_eur)::numeric / nullif(sum(orders), 0), 2) "
        "as average_order_value_eur from r360_bi.mart_executive_daily "
        "where 1=1 {filters}",
        "scalar",
        _currency("average_order_value_eur"),
        0,
        3,
        6,
        3,
    ),
    CardSpec(
        "Marketing CAC Proxy",
        "Marketing spend divided by purchasing-customer observations; a directional proxy.",
        "select round(sum(marketing_spend_eur)::numeric / "
        "nullif(sum(purchasing_customers), 0), 2) as marketing_cac_proxy_eur "
        "from r360_bi.mart_executive_daily where 1=1 {filters}",
        "scalar",
        _currency("marketing_cac_proxy_eur"),
        6,
        3,
        6,
        3,
    ),
    CardSpec(
        "Mature Size Return Rate",
        "Size-related returns divided by purchased sessions with at least 60 days of observation.",
        "select sum(mature_size_return_sessions)::numeric / "
        "nullif(sum(mature_order_sessions), 0) as mature_size_return_rate "
        "from r360_bi.mart_sizepath_daily where 1=1 {filters}",
        "scalar",
        _percent("mature_size_return_rate"),
        12,
        3,
        6,
        3,
    ),
    CardSpec(
        "Compatible Attach Rate",
        "Bike orders containing at least one accessory valid for that bike.",
        "select sum(orders_with_compatible_accessory)::numeric / "
        "nullif(sum(bike_orders), 0) as compatible_attach_rate "
        "from r360_bi.mart_accessory_attach_daily where 1=1 {filters}",
        "scalar",
        _percent("compatible_attach_rate"),
        18,
        3,
        6,
        3,
    ),
    CardSpec(
        "Commercial Trend",
        "Daily net revenue and contribution margin.",
        "select metric_date, round(sum(net_item_revenue_eur)::numeric, 2) as net_revenue_eur, "
        "round(sum(contribution_margin_eur)::numeric, 2) as contribution_margin_eur "
        "from r360_bi.mart_executive_daily where 1=1 {filters} group by 1 order by 1",
        "line",
        {
            "graph.dimensions": ["metric_date"],
            "graph.metrics": ["net_revenue_eur", "contribution_margin_eur"],
            "graph.show_values": False,
        },
        0,
        3,
        16,
        6,
    ),
    CardSpec(
        "Conversion by Channel",
        "Governed session-source channel performance.",
        "select channel, sum(orders)::numeric / nullif(sum(sessions), 0) as conversion_rate "
        "from r360_bi.mart_executive_daily where 1=1 {filters} group by 1 "
        "having sum(sessions) > 0 order by 2 desc",
        "bar",
        {
            "graph.dimensions": ["channel"],
            "graph.metrics": ["conversion_rate"],
            **_percent("conversion_rate"),
        },
        16,
        3,
        8,
        6,
    ),
    CardSpec(
        "Journey Funnel",
        "Session progression through the canonical commerce funnel.",
        "with totals as (select sum(sessions) sessions, sum(product_view_sessions) product_views, "
        "sum(add_to_cart_sessions) carts, sum(checkout_sessions) checkouts, "
        "sum(payment_sessions) payments, sum(purchase_sessions) purchases "
        "from r360_bi.mart_funnel_daily where 1=1 {filters}) "
        "select * from (values ('Sessions', (select sessions from totals), 1), "
        "('Product view', (select product_views from totals), 2), "
        "('Cart', (select carts from totals), 3), ('Checkout', (select checkouts from totals), 4), "
        "('Payment', (select payments from totals), 5), ('Purchase', (select purchases from totals), 6)) "
        "as funnel(stage, sessions, sequence) order by sequence",
        "bar",
        {"graph.dimensions": ["stage"], "graph.metrics": ["sessions"]},
        0,
        9,
        12,
        6,
    ),
    CardSpec(
        "SizePath Outcomes",
        "Observed conversion and mature size-return rates; association is not causal proof.",
        "select case when used_size_path then 'Used SizePath' else 'Did not use' end as cohort, "
        "sum(purchasing_sessions)::numeric / nullif(sum(sessions), 0) as conversion_rate, "
        "sum(size_return_sessions)::numeric / nullif(sum(mature_order_sessions), 0) as mature_size_return_rate "
        "from r360_bi.mart_sizepath_daily where 1=1 {filters} group by 1 order by 1 desc",
        "bar",
        {
            "graph.dimensions": ["cohort"],
            "graph.metrics": ["conversion_rate", "mature_size_return_rate"],
            **_percent("conversion_rate", "mature_size_return_rate"),
        },
        12,
        9,
        12,
        6,
    ),
    CardSpec(
        "Stockout Exposure",
        "Stockout minutes by product, highlighting availability pressure.",
        "select product_name, round(sum(stockout_minutes)::numeric / 60, 1) as stockout_hours "
        "from r360_bi.mart_inventory_daily where category = 'bike' {filters} "
        "group by 1 order by 2 desc limit 10",
        "bar",
        {"graph.dimensions": ["product_name"], "graph.metrics": ["stockout_hours"]},
        0,
        15,
        12,
        6,
    ),
    CardSpec(
        "Compatible Accessory Attach",
        "Compatibility-aware attachment rate by bike model.",
        "select parent_product, sum(orders_with_compatible_accessory)::numeric / "
        "nullif(sum(bike_orders), 0) as compatible_attach_rate "
        "from r360_bi.mart_accessory_attach_daily where 1=1 {filters} "
        "group by 1 order by 2 desc",
        "bar",
        {
            "graph.dimensions": ["parent_product"],
            "graph.metrics": ["compatible_attach_rate"],
            **_percent("compatible_attach_rate"),
        },
        12,
        15,
        12,
        6,
    ),
    CardSpec(
        "Contribution LTV by Acquisition Channel",
        "Observed contribution per customer; 90- and 365-day horizons remain explicit.",
        "select acquisition_channel, customers, round(contribution_ltv_per_customer_eur::numeric, 2) "
        "as contribution_ltv_eur, round(orders_per_customer::numeric, 2) as orders_per_customer "
        "from r360_bi.mart_customer_ltv where 1=1 {filters} order by contribution_ltv_eur desc",
        "table",
        _currency("contribution_ltv_eur"),
        0,
        21,
        12,
        6,
        market_column="acquisition_market",
        date_column=None,
    ),
    CardSpec(
        "Data Through",
        "Latest successful metric date visible in the public serving snapshot.",
        "select max(metric_date)::text as data_through "
        "from r360_bi.mart_data_quality_daily where 1=1 {filters}",
        "scalar",
        {},
        0,
        21,
        12,
        3,
        date_column=None,
    ),
    CardSpec(
        "Critical Check Status",
        "Public-safe rollup of transaction-ID and FX completeness checks.",
        "select case when sum(purchases_missing_transaction_id + orders_missing_fx) = 0 "
        "then 'PASS' else 'REVIEW' end as critical_check_status "
        "from r360_bi.mart_data_quality_daily where 1=1 {filters}",
        "scalar",
        {},
        12,
        21,
        12,
        3,
    ),
    CardSpec(
        "Measurement Health",
        "Coverage, duplicate-safe purchase measurement, missing parameters, and FX readiness.",
        "select metric_date, site_market, event_rows, purchase_event_rows, "
        "orders_missing_fx, round(recommendation_parameter_missing_rate::numeric, 3) "
        "as recommendation_missing_rate, late_events "
        "from r360_bi.mart_data_quality_daily where 1=1 {filters} "
        "order by metric_date desc, site_market limit 100",
        "table",
        _percent("recommendation_missing_rate"),
        12,
        21,
        12,
        6,
    ),
)


TAB_NAMES: tuple[str, ...] = (
    "Executive",
    "Funnel & SizePath",
    "Product & Inventory",
    "Customers & Growth",
    "Trust",
)

CARD_TABS: dict[str, str] = {
    "Net Revenue": "Executive",
    "Orders": "Executive",
    "Session Conversion": "Executive",
    "Contribution After Marketing": "Executive",
    "Average Order Value": "Executive",
    "Marketing CAC Proxy": "Executive",
    "Mature Size Return Rate": "Executive",
    "Compatible Attach Rate": "Executive",
    "Commercial Trend": "Executive",
    "Conversion by Channel": "Funnel & SizePath",
    "Journey Funnel": "Funnel & SizePath",
    "SizePath Outcomes": "Funnel & SizePath",
    "Stockout Exposure": "Product & Inventory",
    "Compatible Accessory Attach": "Product & Inventory",
    "Contribution LTV by Acquisition Channel": "Customers & Growth",
    "Data Through": "Trust",
    "Critical Check Status": "Trust",
    "Measurement Health": "Trust",
}

# Rows are local to a dashboard tab. Keep each section compact instead of preserving
# the coordinates from the original single-page dashboard.
CARD_TAB_LAYOUT: dict[str, tuple[int, int, int, int]] = {
    "Net Revenue": (0, 0, 6, 3),
    "Orders": (6, 0, 6, 3),
    "Session Conversion": (12, 0, 6, 3),
    "Contribution After Marketing": (18, 0, 6, 3),
    "Average Order Value": (0, 3, 6, 3),
    "Marketing CAC Proxy": (6, 3, 6, 3),
    "Mature Size Return Rate": (12, 3, 6, 3),
    "Compatible Attach Rate": (18, 3, 6, 3),
    "Commercial Trend": (0, 6, 24, 6),
    "Conversion by Channel": (0, 0, 24, 6),
    "Journey Funnel": (0, 6, 12, 6),
    "SizePath Outcomes": (12, 6, 12, 6),
    "Stockout Exposure": (0, 0, 12, 6),
    "Compatible Accessory Attach": (12, 0, 12, 6),
    "Contribution LTV by Acquisition Channel": (0, 0, 24, 6),
    "Data Through": (0, 0, 12, 3),
    "Critical Check Status": (12, 0, 12, 3),
    "Measurement Health": (0, 3, 24, 6),
}


class MetabaseClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.session.request(method, f"{self.base_url}{path}", timeout=60, **kwargs)
        if not response.ok:
            raise RuntimeError(
                f"Metabase {method} {path} failed ({response.status_code}): {response.text[:1500]}"
            )
        if not response.content:
            return None
        try:
            return response.json()
        except requests.JSONDecodeError:
            return response.text

    def wait_until_healthy(self, timeout_seconds: int = 300) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                if self.request("GET", "/api/health").get("status") == "ok":
                    return
            except (requests.RequestException, RuntimeError):
                pass
            time.sleep(3)
        raise TimeoutError(f"Metabase did not become healthy within {timeout_seconds} seconds")

    def login(self, email: str, password: str) -> None:
        result = self.request(
            "POST", "/api/session", json={"username": email, "password": password}
        )
        self.session.headers["X-Metabase-Session"] = result["id"]


def _template_tags() -> dict[str, dict[str, Any]]:
    return {
        "market": {
            "name": "market",
            "display-name": "Market",
            "type": "text",
            "required": False,
        },
        "start_date": {
            "name": "start_date",
            "display-name": "Start date",
            "type": "date",
            "required": False,
        },
        "end_date": {
            "name": "end_date",
            "display-name": "End date",
            "type": "date",
            "required": False,
        },
    }


def _filters(spec: CardSpec) -> str:
    result = f"[[and {spec.market_column} = {{{{market}}}}]]"
    if spec.date_column:
        result += f" [[and {spec.date_column} >= {{{{start_date}}}}]]"
        result += f" [[and {spec.date_column} <= {{{{end_date}}}}]]"
    return result


def _find_database(client: MetabaseClient, name: str) -> dict[str, Any] | None:
    response = client.request("GET", "/api/database")
    databases = response.get("data", response) if isinstance(response, dict) else response
    return next((database for database in databases if database["name"] == name), None)


def _find_dashboard(client: MetabaseClient, name: str) -> dict[str, Any] | None:
    response = client.request("GET", "/api/dashboard")
    dashboards = response.get("data", response) if isinstance(response, dict) else response
    return next((dashboard for dashboard in dashboards if dashboard["name"] == name), None)


def bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    client = MetabaseClient(args.url)
    client.wait_until_healthy()
    properties = client.request("GET", "/api/session/properties")
    if not properties.get("has-user-setup"):
        client.request(
            "POST",
            "/api/setup",
            json={
                "token": properties["setup-token"],
                "user": {
                    "email": args.admin_email,
                    "first_name": "Rider",
                    "last_name": "Admin",
                    "password": args.admin_password,
                },
                "prefs": {"site_name": "Rider 360", "site_locale": "en"},
            },
        )
    client.login(args.admin_email, args.admin_password)
    for key, value in (
        ("site-name", "Rider 360"),
        ("enable-public-sharing", True),
        ("anon-tracking-enabled", False),
    ):
        client.request("PUT", f"/api/setting/{key}", json={"value": value})

    database = _find_database(client, "Rider 360 Analytics")
    if database is None:
        database = client.request(
            "POST",
            "/api/database",
            json={
                "name": "Rider 360 Analytics",
                "engine": "postgres",
                "details": {
                    "host": args.db_host,
                    "port": args.db_port,
                    "dbname": args.db_name,
                    "user": args.db_user,
                    "password": "" if args.db_iam_auth else args.db_password,
                    "ssl": args.db_ssl,
                    "tunnel-enabled": False,
                    "schema-filters-type": "inclusion",
                    "schema-filters-patterns": "r360_bi",
                },
                "is_full_sync": True,
                "is_on_demand": False,
                "connection_source": "admin",
            },
        )
    database_id = int(database["id"])
    client.request("POST", f"/api/database/{database_id}/sync_schema")

    dashboard_name = "Rider 360 | Executive Overview"
    dashboard = _find_dashboard(client, dashboard_name)
    parameters = [
        {"id": "market", "name": "Market", "slug": "market", "type": "string/="},
        {
            "id": "start_date",
            "name": "Start date",
            "slug": "start_date",
            "type": "date/single",
        },
        {"id": "end_date", "name": "End date", "slug": "end_date", "type": "date/single"},
    ]
    if dashboard is None:
        dashboard = client.request(
            "POST",
            "/api/dashboard",
            json={
                "name": dashboard_name,
                "description": (
                    "Fictional synthetic demonstration data. Commercial, journey, product, "
                    "and measurement signals; no real riders or companies are represented."
                ),
                "parameters": parameters,
            },
        )
    dashboard_id = int(dashboard["id"])
    dashboard = client.request("GET", f"/api/dashboard/{dashboard_id}")
    existing = {
        item["card"]["name"]: item for item in dashboard.get("dashcards", []) if item.get("card")
    }
    for spec in CARD_SPECS:
        payload = {
            "name": spec.name,
            "description": spec.description,
            "dataset_query": {
                "database": database_id,
                "type": "native",
                "native": {
                    "query": spec.sql.format(filters=_filters(spec)),
                    "template-tags": _template_tags(),
                },
            },
            "display": spec.display,
            "visualization_settings": spec.visualization_settings,
            "dashboard_id": dashboard_id,
        }
        if spec.name in existing:
            card_id = int(existing[spec.name]["card"]["id"])
            client.request("PUT", f"/api/card/{card_id}", json=payload)
        else:
            client.request("POST", "/api/card", json=payload)

    dashboard = client.request("GET", f"/api/dashboard/{dashboard_id}")
    dashcards = {item["card"]["name"]: item for item in dashboard["dashcards"] if item.get("card")}
    existing_tabs = {tab["name"]: int(tab["id"]) for tab in dashboard.get("tabs", [])}
    tab_ids = {
        name: existing_tabs.get(name, -(position + 1)) for position, name in enumerate(TAB_NAMES)
    }
    tabs = [
        {"id": tab_ids[name], "name": name, "position": position}
        for position, name in enumerate(TAB_NAMES)
    ]
    layout: list[dict[str, Any]] = []
    validation: dict[str, int] = {}
    for spec in CARD_SPECS:
        item = dashcards[spec.name]
        card_id = int(item["card"]["id"])
        col, row, size_x, size_y = CARD_TAB_LAYOUT[spec.name]
        mappings = [
            {
                "parameter_id": "market",
                "card_id": card_id,
                "target": ["variable", ["template-tag", "market"]],
            }
        ]
        if spec.date_column:
            mappings.extend(
                [
                    {
                        "parameter_id": name,
                        "card_id": card_id,
                        "target": ["variable", ["template-tag", name]],
                    }
                    for name in ("start_date", "end_date")
                ]
            )
        layout.append(
            {
                **item,
                "id": int(item["id"]),
                "size_x": size_x,
                "size_y": size_y,
                "row": row,
                "col": col,
                "dashboard_tab_id": tab_ids[CARD_TABS[spec.name]],
                "parameter_mappings": mappings,
            }
        )
        result = client.request("POST", f"/api/card/{card_id}/query", json={})
        validation[spec.name] = len(result.get("data", {}).get("rows", []))
    client.request(
        "PUT",
        f"/api/dashboard/{dashboard_id}",
        json={
            "name": dashboard_name,
            "description": dashboard["description"],
            "parameters": parameters,
            "width": "full",
            "dashcards": layout,
            "tabs": tabs,
        },
    )
    dashboard = client.request("GET", f"/api/dashboard/{dashboard_id}")
    actual_tabs = {tab["name"]: int(tab["id"]) for tab in dashboard.get("tabs", [])}
    if tuple(actual_tabs) != TAB_NAMES:
        raise RuntimeError(
            f"Dashboard tabs do not match expected order: {tuple(actual_tabs)} != {TAB_NAMES}"
        )
    for dashcard in dashboard.get("dashcards", []):
        card = dashcard.get("card")
        if card and dashcard.get("dashboard_tab_id") != actual_tabs[CARD_TABS[card["name"]]]:
            raise RuntimeError(f"Card {card['name']} was not assigned to its expected tab")
    public_link = client.request("POST", f"/api/dashboard/{dashboard_id}/public_link")
    public_uuid = public_link["uuid"]
    public_url = f"{args.url.rstrip('/')}/public/dashboard/{public_uuid}"
    public_response = requests.get(public_url, timeout=60)
    public_response.raise_for_status()
    return {
        "metabase_url": args.url.rstrip("/"),
        "database_id": database_id,
        "dashboard_id": dashboard_id,
        "public_uuid": public_uuid,
        "public_dashboard_url": public_url,
        "cards": validation,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Idempotently configure Rider 360 in Metabase.")
    parser.add_argument("--url", default=os.getenv("METABASE_URL", "http://localhost:3000"))
    parser.add_argument(
        "--admin-email", default=os.getenv("METABASE_ADMIN_EMAIL", "admin@rider360.example")
    )
    parser.add_argument("--admin-password", default=os.getenv("METABASE_ADMIN_PASSWORD"))
    parser.add_argument("--db-host", default=os.getenv("R360_METABASE_DB_HOST", "r360-postgres"))
    parser.add_argument(
        "--db-port", type=int, default=int(os.getenv("R360_METABASE_DB_PORT", "5432"))
    )
    parser.add_argument("--db-name", default=os.getenv("R360_METABASE_DB_NAME", "r360_bi"))
    parser.add_argument("--db-user", default=os.getenv("R360_METABASE_DB_USER", "r360_metabase"))
    parser.add_argument("--db-password", default=os.getenv("R360_METABASE_DB_PASSWORD"))
    parser.add_argument(
        "--db-iam-auth",
        action="store_true",
        default=os.getenv("R360_METABASE_DB_IAM_AUTH", "").lower() in {"1", "true", "yes"},
        help="Use the attached Cloud Run identity through an auto-IAM-auth proxy.",
    )
    parser.add_argument("--db-ssl", action="store_true", default=False)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.admin_password:
        parser.error("the admin password must be supplied through a flag or environment")
    if not args.db_password and not args.db_iam_auth:
        parser.error("supply a database password or explicitly enable --db-iam-auth")
    if args.db_password and args.db_iam_auth:
        parser.error("--db-password and --db-iam-auth are mutually exclusive")
    return args


def main() -> int:
    args = parse_args()
    result = bootstrap(args)
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    sys.stdout.write(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
