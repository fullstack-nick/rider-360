"""Reusable estimators for the SizePath observational analysis."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from google.cloud import bigquery
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = PROJECT_ROOT / "analyses" / "sizepath_session_extract.sql"
CATEGORICAL_COVARIATES = (
    "site_market",
    "device_category",
    "channel",
    "viewed_sku",
    "day_of_week",
    "year_month",
    "prior_purchaser",
)
NUMERIC_COVARIATES = ("session_hour", "prior_session_count")


@dataclass(frozen=True)
class EffectEstimate:
    method: str
    risk_difference: float
    standard_error: float
    confidence_low: float
    confidence_high: float
    treated_conversion: float | None = None
    control_conversion: float | None = None


def load_sessions(
    *,
    project_id: str,
    cache_path: Path | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """Load the governed session extract, with an ignored local Parquet cache."""
    if cache_path and cache_path.exists() and not refresh:
        return pd.read_parquet(cache_path)
    query = QUERY_PATH.read_text(encoding="utf-8").format(project_id=project_id)
    frame = bigquery.Client(project=project_id).query(query).to_dataframe()
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(cache_path, index=False)
    return frame


def validate_sessions(frame: pd.DataFrame) -> None:
    required = {
        "session_key",
        "user_pseudo_id",
        "treatment",
        "outcome",
        *CATEGORICAL_COVARIATES,
        *NUMERIC_COVARIATES,
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"analysis extract is missing columns: {missing}")
    if frame["session_key"].duplicated().any():
        raise ValueError("analysis grain violation: session_key is not unique")
    for column in ("treatment", "outcome"):
        observed = set(frame[column].dropna().astype(int).unique())
        if not observed <= {0, 1}:
            raise ValueError(f"{column} must be binary, observed {sorted(observed)}")
    if frame[list(CATEGORICAL_COVARIATES) + list(NUMERIC_COVARIATES)].isna().any().any():
        raise ValueError("pre-treatment covariates contain nulls")


def _pipeline() -> Pipeline:
    transformer = ColumnTransformer(
        [
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", min_frequency=25),
                list(CATEGORICAL_COVARIATES),
            ),
            ("numeric", StandardScaler(), list(NUMERIC_COVARIATES)),
        ]
    )
    return Pipeline(
        [
            ("features", transformer),
            (
                "model",
                LogisticRegression(
                    C=1.0,
                    max_iter=500,
                    solver="lbfgs",
                ),
            ),
        ]
    )


def cross_fitted_predictions(
    frame: pd.DataFrame,
    *,
    folds: int = 3,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return out-of-fold propensity and potential-outcome probabilities."""
    validate_sessions(frame)
    covariates = frame[list(CATEGORICAL_COVARIATES) + list(NUMERIC_COVARIATES)]
    treatment = frame["treatment"].to_numpy(dtype=int)
    outcome = frame["outcome"].to_numpy(dtype=int)
    groups = frame["user_pseudo_id"].astype(str).to_numpy()
    propensity = np.empty(len(frame), dtype=float)
    outcome_treated = np.empty(len(frame), dtype=float)
    outcome_control = np.empty(len(frame), dtype=float)
    splitter = GroupKFold(n_splits=folds)
    for train, test in splitter.split(covariates, treatment, groups):
        propensity_model = _pipeline().fit(covariates.iloc[train], treatment[train])
        propensity[test] = propensity_model.predict_proba(covariates.iloc[test])[:, 1]
        for arm, destination in ((1, outcome_treated), (0, outcome_control)):
            arm_train = train[treatment[train] == arm]
            outcome_model = _pipeline().fit(covariates.iloc[arm_train], outcome[arm_train])
            destination[test] = outcome_model.predict_proba(covariates.iloc[test])[:, 1]
    return (
        np.clip(propensity, 0.01, 0.99),
        np.clip(outcome_treated, 0.0001, 0.9999),
        np.clip(outcome_control, 0.0001, 0.9999),
    )


def _clustered_estimate(
    *,
    method: str,
    estimate: float,
    influence: np.ndarray,
    groups: pd.Series,
    treated_conversion: float | None = None,
    control_conversion: float | None = None,
) -> EffectEstimate:
    group_frame = pd.DataFrame({"group": groups.astype(str), "influence": influence})
    cluster_sums = group_frame.groupby("group", sort=False)["influence"].sum().to_numpy()
    clusters = len(cluster_sums)
    correction = clusters / (clusters - 1) if clusters > 1 else 1.0
    standard_error = math.sqrt(correction * float(np.square(cluster_sums).sum())) / len(groups)
    return EffectEstimate(
        method=method,
        risk_difference=float(estimate),
        standard_error=standard_error,
        confidence_low=float(estimate - 1.96 * standard_error),
        confidence_high=float(estimate + 1.96 * standard_error),
        treated_conversion=treated_conversion,
        control_conversion=control_conversion,
    )


def estimate_effects(
    frame: pd.DataFrame,
    propensity: np.ndarray,
    outcome_treated: np.ndarray,
    outcome_control: np.ndarray,
) -> list[EffectEstimate]:
    """Estimate naive, stabilized-IPW, and doubly robust risk differences."""
    treatment = frame["treatment"].to_numpy(dtype=float)
    outcome = frame["outcome"].to_numpy(dtype=float)
    groups = frame["user_pseudo_id"]
    treatment_share = float(treatment.mean())

    naive_treated = float(outcome[treatment == 1].mean())
    naive_control = float(outcome[treatment == 0].mean())
    naive = naive_treated - naive_control
    naive_influence = treatment * (outcome - naive_treated) / treatment_share - (1 - treatment) * (
        outcome - naive_control
    ) / (1 - treatment_share)

    treated_weights = treatment_share / propensity
    control_weights = (1 - treatment_share) / (1 - propensity)
    weighted_treated = float(
        np.sum(treatment * treated_weights * outcome) / np.sum(treatment * treated_weights)
    )
    weighted_control = float(
        np.sum((1 - treatment) * control_weights * outcome)
        / np.sum((1 - treatment) * control_weights)
    )
    ipw = weighted_treated - weighted_control
    treated_scale = float(np.mean(treatment * treated_weights))
    control_scale = float(np.mean((1 - treatment) * control_weights))
    ipw_influence = (
        treatment * treated_weights * (outcome - weighted_treated) / treated_scale
        - (1 - treatment) * control_weights * (outcome - weighted_control) / control_scale
    )

    pseudo_outcome = (
        outcome_treated
        - outcome_control
        + treatment * (outcome - outcome_treated) / propensity
        - (1 - treatment) * (outcome - outcome_control) / (1 - propensity)
    )
    doubly_robust = float(pseudo_outcome.mean())
    return [
        _clustered_estimate(
            method="Naive observed",
            estimate=naive,
            influence=naive_influence,
            groups=groups,
            treated_conversion=naive_treated,
            control_conversion=naive_control,
        ),
        _clustered_estimate(
            method="Stabilized IPW",
            estimate=ipw,
            influence=ipw_influence,
            groups=groups,
            treated_conversion=weighted_treated,
            control_conversion=weighted_control,
        ),
        _clustered_estimate(
            method="Cross-fitted doubly robust",
            estimate=doubly_robust,
            influence=pseudo_outcome - doubly_robust,
            groups=groups,
        ),
    ]


def _weighted_mean_variance(
    values: np.ndarray,
    weights: np.ndarray,
) -> tuple[float, float]:
    mean = float(np.average(values, weights=weights))
    variance = float(np.average(np.square(values - mean), weights=weights))
    return mean, variance


def balance_table(frame: pd.DataFrame, propensity: np.ndarray) -> pd.DataFrame:
    """Report standardized mean differences before and after IP weighting."""
    treatment = frame["treatment"].to_numpy(dtype=int)
    encoded = pd.get_dummies(
        frame[list(CATEGORICAL_COVARIATES) + list(NUMERIC_COVARIATES)].astype(
            {column: "string" for column in CATEGORICAL_COVARIATES}
        ),
        columns=list(CATEGORICAL_COVARIATES),
        dtype=float,
    )
    treatment_share = float(treatment.mean())
    weights = np.where(
        treatment == 1,
        treatment_share / propensity,
        (1 - treatment_share) / (1 - propensity),
    )
    rows: list[dict[str, float | str]] = []
    for column in encoded.columns:
        values = encoded[column].to_numpy(dtype=float)
        treated_values = values[treatment == 1]
        control_values = values[treatment == 0]
        treated_mean = float(treated_values.mean())
        control_mean = float(control_values.mean())
        pooled = math.sqrt((float(treated_values.var()) + float(control_values.var())) / 2)
        before = 0.0 if pooled == 0 else (treated_mean - control_mean) / pooled
        weighted_treated_mean, weighted_treated_variance = _weighted_mean_variance(
            treated_values, weights[treatment == 1]
        )
        weighted_control_mean, weighted_control_variance = _weighted_mean_variance(
            control_values, weights[treatment == 0]
        )
        weighted_pooled = math.sqrt((weighted_treated_variance + weighted_control_variance) / 2)
        after = (
            0.0
            if weighted_pooled == 0
            else (weighted_treated_mean - weighted_control_mean) / weighted_pooled
        )
        rows.append(
            {
                "covariate": str(column),
                "smd_before": before,
                "smd_after": after,
            }
        )
    return pd.DataFrame(rows).sort_values(
        "smd_before", key=lambda values: values.abs(), ascending=False
    )


def synthetic_truth_reference(
    frame: pd.DataFrame, *, draws_seed: int = 3602026
) -> dict[str, float]:
    """Integrate the configured structural effect over the observed session mix.

    Latent intent is sampled only inside this validation helper and is never
    joined back to a session or written to a warehouse mart.
    """
    scenarios = yaml.safe_load(
        (PROJECT_ROOT / "config" / "scenarios.yml").read_text(encoding="utf-8")
    )["scenarios"]
    b3 = next(item for item in scenarios if item["id"] == "B3")
    effect = float(b3["mechanism"]["conversion_log_odds_effect"])
    rng = np.random.default_rng(draws_seed)
    intent = rng.beta(2.0, 2.8, size=len(frame))
    baseline_cart = 1 / (1 + np.exp(-(-2.25 + 1.2 * intent)))
    treated_cart = 1 / (1 + np.exp(-(-2.25 + 1.2 * intent + effect)))
    checkout = 0.46 + 0.24 * intent
    payment = np.full(len(frame), 0.78, dtype=float)
    regression = (
        (pd.to_datetime(frame["session_date"]).dt.date >= pd.Timestamp("2025-03-10").date())
        & (frame["site_market"].astype(str) == "FR")
        & (frame["device_category"].astype(str) == "mobile")
    )
    payment[regression.to_numpy()] *= 0.70
    downstream = checkout * 0.91 * 0.91 * payment
    risk_difference = float(np.mean((treated_cart - baseline_cart) * downstream))
    return {
        "conversion_log_odds_effect": effect,
        "conversion_odds_ratio": math.exp(effect),
        "average_purchase_risk_difference": risk_difference,
    }


def export_results(
    path: Path,
    *,
    frame: pd.DataFrame,
    propensity: np.ndarray,
    estimates: list[EffectEstimate],
    truth: dict[str, float],
    balance: pd.DataFrame,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "analysis_grain": "eligible product-view session",
        "sessions": len(frame),
        "users": int(frame["user_pseudo_id"].nunique()),
        "treatment_share": float(frame["treatment"].mean()),
        "outcome_share": float(frame["outcome"].mean()),
        "propensity": {
            "minimum": float(propensity.min()),
            "p01": float(np.quantile(propensity, 0.01)),
            "median": float(np.median(propensity)),
            "p99": float(np.quantile(propensity, 0.99)),
            "maximum": float(propensity.max()),
        },
        "effects": [asdict(item) for item in estimates],
        "synthetic_truth": truth,
        "maximum_absolute_smd_before": float(balance["smd_before"].abs().max()),
        "maximum_absolute_smd_after": float(balance["smd_after"].abs().max()),
        "interpretation": (
            "The estimand is an observational association among eligible product-view sessions. "
            "Any gap from the synthetic truth is residual bias, including unobserved latent intent."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
