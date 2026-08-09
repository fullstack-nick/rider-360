"""Execute the full SizePath analysis and export reviewable results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analyses.sizepath import (
    balance_table,
    cross_fitted_predictions,
    estimate_effects,
    export_results,
    load_sessions,
    synthetic_truth_reference,
    validate_sessions,
)


def _plot_effects(
    estimates: pd.DataFrame,
    truth: dict[str, float],
    output: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(9, 4.8))
    y = np.arange(len(estimates))
    points = estimates["risk_difference"].to_numpy() * 100
    lower = (estimates["risk_difference"] - estimates["confidence_low"]).to_numpy() * 100
    upper = (estimates["confidence_high"] - estimates["risk_difference"]).to_numpy() * 100
    axis.errorbar(points, y, xerr=np.vstack([lower, upper]), fmt="o", capsize=4, color="#3f37c9")
    axis.axvline(
        truth["average_purchase_risk_difference"] * 100,
        color="#e76f51",
        linestyle="--",
        label="Known synthetic truth",
    )
    axis.axvline(0, color="#7f8c8d", linewidth=0.8)
    axis.set_yticks(y, estimates["method"])
    axis.set_xlabel("Purchase conversion difference (percentage points)")
    axis.set_title("SizePath start: observational estimates vs synthetic truth")
    axis.legend(loc="lower right")
    axis.grid(axis="x", alpha=0.2)
    figure.tight_layout()
    figure.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(figure)


def _plot_overlap(frame: pd.DataFrame, propensity: np.ndarray, output: Path) -> None:
    figure, axis = plt.subplots(figsize=(9, 4.8))
    axis.hist(
        propensity[frame["treatment"].to_numpy() == 0],
        bins=40,
        density=True,
        alpha=0.6,
        label="Did not start",
        color="#6c757d",
    )
    axis.hist(
        propensity[frame["treatment"].to_numpy() == 1],
        bins=40,
        density=True,
        alpha=0.6,
        label="Started SizePath",
        color="#3f37c9",
    )
    axis.set_xlabel("Estimated propensity")
    axis.set_ylabel("Density")
    axis.set_title("Observable overlap is strong")
    axis.legend()
    axis.grid(axis="y", alpha=0.2)
    figure.tight_layout()
    figure.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(figure)


def _plot_balance(balance: pd.DataFrame, output: Path) -> None:
    selected = balance.assign(
        maximum=lambda data: data[["smd_before", "smd_after"]].abs().max(axis=1)
    )
    selected = selected.nlargest(15, "maximum").sort_values("maximum")
    figure, axis = plt.subplots(figsize=(9, 6.5))
    y = np.arange(len(selected))
    axis.scatter(selected["smd_before"], y, label="Before weighting", color="#e76f51")
    axis.scatter(selected["smd_after"], y, label="After weighting", color="#2a9d8f")
    axis.axvline(-0.1, color="#7f8c8d", linestyle="--", linewidth=0.8)
    axis.axvline(0.1, color="#7f8c8d", linestyle="--", linewidth=0.8)
    axis.axvline(0, color="#7f8c8d", linewidth=0.8)
    axis.set_yticks(y, selected["covariate"])
    axis.set_xlabel("Standardized mean difference")
    axis.set_title("Largest observable balance differences")
    axis.legend(loc="lower right")
    axis.grid(axis="x", alpha=0.2)
    figure.tight_layout()
    figure.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(figure)


def run(args: argparse.Namespace) -> dict:
    args.results_dir.mkdir(parents=True, exist_ok=True)
    frame = load_sessions(
        project_id=args.project_id,
        cache_path=args.cache,
        refresh=args.refresh,
    )
    validate_sessions(frame)
    propensity, outcome_treated, outcome_control = cross_fitted_predictions(
        frame,
        folds=args.folds,
    )
    estimates = estimate_effects(frame, propensity, outcome_treated, outcome_control)
    truth = synthetic_truth_reference(frame)
    balance = balance_table(frame, propensity)
    result = export_results(
        args.results_dir / "sizepath_effects.json",
        frame=frame,
        propensity=propensity,
        estimates=estimates,
        truth=truth,
        balance=balance,
    )
    estimate_frame = pd.DataFrame([item.__dict__ for item in estimates])
    estimate_frame.to_csv(args.results_dir / "sizepath_effects.csv", index=False)
    balance.to_csv(args.results_dir / "sizepath_balance.csv", index=False)
    segment = (
        frame.groupby(["site_market", "device_category", "treatment"], observed=True)["outcome"]
        .agg(["count", "mean"])
        .reset_index()
        .rename(columns={"count": "sessions", "mean": "conversion_rate"})
    )
    segment.to_csv(args.results_dir / "sizepath_segments.csv", index=False)
    _plot_effects(estimate_frame, truth, args.results_dir / "sizepath_effects.png")
    _plot_overlap(frame, propensity, args.results_dir / "sizepath_overlap.png")
    _plot_balance(balance, args.results_dir / "sizepath_balance.png")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", default="tracegate-r7m5o9ld")
    parser.add_argument("--cache", type=Path, default=Path("artifacts/analysis/sizepath.parquet"))
    parser.add_argument("--results-dir", type=Path, default=Path("analyses/results"))
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2))
