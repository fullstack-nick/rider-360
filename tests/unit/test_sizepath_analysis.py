from __future__ import annotations

import numpy as np
import pandas as pd

from analyses.sizepath import balance_table, estimate_effects, validate_sessions


def _frame() -> pd.DataFrame:
    rows = 240
    rng = np.random.default_rng(360)
    treatment = rng.binomial(1, 0.4, rows)
    outcome = rng.binomial(1, 0.04 + 0.05 * treatment, rows)
    return pd.DataFrame(
        {
            "session_key": [f"session-{index}" for index in range(rows)],
            "user_pseudo_id": [f"user-{index // 2}" for index in range(rows)],
            "site_market": np.where(np.arange(rows) % 2, "DE", "FR"),
            "device_category": np.where(np.arange(rows) % 3, "mobile", "desktop"),
            "channel": np.where(np.arange(rows) % 2, "Organic Search", "Direct"),
            "viewed_sku": np.where(np.arange(rows) % 2, "R360-B16-COMET", "R360-B20-DRIFT"),
            "session_hour": np.arange(rows) % 24,
            "day_of_week": (np.arange(rows) % 7) + 1,
            "year_month": "2025-01",
            "prior_session_count": np.arange(rows) % 5,
            "prior_purchaser": np.arange(rows) % 7 == 0,
            "treatment": treatment,
            "outcome": outcome,
        }
    )


def test_estimators_return_finite_clustered_intervals() -> None:
    frame = _frame()
    validate_sessions(frame)
    propensity = np.full(len(frame), frame["treatment"].mean())
    outcome_treated = np.full(len(frame), frame.loc[frame.treatment == 1, "outcome"].mean())
    outcome_control = np.full(len(frame), frame.loc[frame.treatment == 0, "outcome"].mean())

    estimates = estimate_effects(frame, propensity, outcome_treated, outcome_control)

    assert [estimate.method for estimate in estimates] == [
        "Naive observed",
        "Stabilized IPW",
        "Cross-fitted doubly robust",
    ]
    assert all(np.isfinite(estimate.risk_difference) for estimate in estimates)
    assert all(estimate.confidence_low < estimate.confidence_high for estimate in estimates)


def test_balance_table_has_pre_and_post_weighting_diagnostics() -> None:
    frame = _frame()
    propensity = np.full(len(frame), frame["treatment"].mean())

    balance = balance_table(frame, propensity)

    assert {"covariate", "smd_before", "smd_after"} == set(balance.columns)
    assert not balance.empty
    assert np.isfinite(balance[["smd_before", "smd_after"]].to_numpy()).all()


def test_validation_rejects_duplicate_session_grain() -> None:
    frame = _frame()
    frame.loc[1, "session_key"] = frame.loc[0, "session_key"]

    try:
        validate_sessions(frame)
    except ValueError as error:
        assert "session_key is not unique" in str(error)
    else:
        raise AssertionError("duplicate session grain was accepted")
