"""Export governed decision tables and a compact executive finding set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
from google.cloud import bigquery

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUERY_FILES = (
    "funnel_investigation",
    "product_opportunity",
    "acquisition_quality",
    "cohort_clv",
    "sizepath_return_guardrail",
    "inventory_incident",
)


def _frame(client: bigquery.Client, project_id: str, name: str) -> pd.DataFrame:
    query = (PROJECT_ROOT / "analyses" / f"{name}.sql").read_text(encoding="utf-8")
    return client.query(query.format(project_id=project_id)).to_dataframe()


def _rate(frame: pd.DataFrame, segment: str, period: str) -> float:
    row = frame[(frame["segment"] == segment) & (frame["period"] == period)]
    if len(row) != 1:
        raise ValueError(f"expected one funnel row for {segment}/{period}, got {len(row)}")
    return float(row.iloc[0]["payment_to_purchase_rate"])


def _safe_number(value: Any) -> int | float | str | bool | None:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return float(value)
    if isinstance(value, int | str | bool):
        return value
    return str(value)


def run(project_id: str, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    client = bigquery.Client(project=project_id)
    frames = {name: _frame(client, project_id, name) for name in QUERY_FILES}
    for name, frame in frames.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)

    funnel = frames["funnel_investigation"]
    fr_change = _rate(funnel, "FR mobile", "post") - _rate(funnel, "FR mobile", "pre")
    control_change = _rate(funnel, "DE/NL mobile control", "post") - _rate(
        funnel, "DE/NL mobile control", "pre"
    )
    did = fr_change - control_change

    acquisition = frames["acquisition_quality"]
    total_after_marketing = float(acquisition["contribution_after_marketing_eur"].sum())
    worst_channel = acquisition.sort_values("contribution_after_marketing_eur").iloc[0]

    opportunity = frames["product_opportunity"]
    incremental_attach_orders = float(opportunity["incremental_attach_orders"].sum())
    accessory_contribution_midpoint = 22.0

    returns = frames["sizepath_return_guardrail"].set_index("used_size_path")
    return_rate_started = float(returns.loc[True, "mature_size_return_rate"])
    return_rate_not_started = float(returns.loc[False, "mature_size_return_rate"])

    inventory = frames["inventory_incident"]
    incident = inventory[inventory["period"] == "incident"]
    pre = inventory[inventory["period"] == "pre"]

    findings: dict[str, Any] = {
        "project_id": project_id,
        "french_mobile_payment": {
            "pre_rate": _rate(funnel, "FR mobile", "pre"),
            "post_rate": _rate(funnel, "FR mobile", "post"),
            "control_pre_rate": _rate(funnel, "DE/NL mobile control", "pre"),
            "control_post_rate": _rate(funnel, "DE/NL mobile control", "post"),
            "difference_in_differences": did,
        },
        "marketing": {
            "contribution_after_marketing_eur": total_after_marketing,
            "worst_channel": str(worst_channel["channel"]),
            "worst_channel_contribution_after_marketing_eur": float(
                worst_channel["contribution_after_marketing_eur"]
            ),
        },
        "accessory_attach": {
            "affected_products": len(opportunity),
            "incremental_attach_orders_at_peer_rate": incremental_attach_orders,
            "illustrative_incremental_contribution_eur": (
                incremental_attach_orders * accessory_contribution_midpoint
            ),
            "contribution_assumption_eur_per_order": accessory_contribution_midpoint,
        },
        "sizepath_return_guardrail": {
            "started_rate": return_rate_started,
            "not_started_rate": return_rate_not_started,
            "descriptive_difference": return_rate_started - return_rate_not_started,
        },
        "inventory_incident": {
            "pre_average_stockout_fraction": float(pre["average_stockout_day_fraction"].mean()),
            "incident_average_stockout_fraction": float(
                incident["average_stockout_day_fraction"].mean()
            ),
            "note": (
                "Inventory availability is operational evidence only; generator v1.0 does not "
                "causally suppress order generation when stock is unavailable."
            ),
        },
        "tables": {
            name: [
                {column: _safe_number(value) for column, value in record.items()}
                for record in frame.to_dict(orient="records")
            ]
            for name, frame in frames.items()
        },
    }
    (output_dir / "business_findings.json").write_text(
        json.dumps(findings, indent=2) + "\n",
        encoding="utf-8",
    )
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", default="tracegate-r7m5o9ld")
    parser.add_argument("--output-dir", type=Path, default=Path("analyses/results"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run(args.project_id, args.output_dir), indent=2))
