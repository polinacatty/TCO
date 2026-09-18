"""Compact serialization for SARIMA(X) models.

The default `pickle.dump(SARIMAXResults, ...)` includes the full Kalman
filter / smoother state and several covariance matrices, weighing ~15 MB
per 132-point series. We store only what is needed to reproduce the
fitted model and its forecasts:

    * train series (endog) — needed to start the Kalman filter at t=0
    * fitted parameters (a small numpy array, ~5–8 floats)
    * SARIMA orders (p,d,q,P,D,Q,s) and trend
    * metrics dict (mape/rmse/mae/coverage_95/aic/bic)
    * train/test window timestamps

`save_compact()` writes ~ 2–5 KB per model.
`load_compact()` reconstructs a `SARIMAXResults` object via
`SARIMAX(...).smooth(params)`, which runs the Kalman filter once
(deterministic, ~ 50 ms) and yields an object identical to the original
fit for `get_forecast()` / `get_prediction()` purposes.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def save_compact(
    fit,
    *,
    metrics: dict,
    train_window: tuple[str, str],
    test_window: tuple[str, str],
    fitted_at: str,
    output_path: Path,
) -> Path:
    """Persist a SARIMA fit in compact form (~2–5 KB)."""
    spec = fit.specification
    endog = np.asarray(fit.data.orig_endog, dtype=float)
    train_index_start = pd.Timestamp(train_window[0]).strftime("%Y-%m-%d")

    state: dict[str, Any] = {
        "format_version": "compact_v1",
        "endog": endog,
        "train_index_start": train_index_start,
        "freq": "MS",
        "params": np.asarray(fit.params, dtype=float),
        "order": tuple(spec.order),
        "seasonal_order": tuple(spec.seasonal_order),
        "trend": spec.trend,
        "metrics": metrics,
        "train_window": train_window,
        "test_window": test_window,
        "fitted_at": fitted_at,
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
    return output_path


def load_compact(path: Path) -> dict:
    """Reconstruct a SARIMA fit from compact pickle.

    Returns a dict with keys identical to what direct `pickle.dump(fit)` style
    artifacts had:

        {
          "model": SARIMAXResults,        # reconstructed via .smooth(params)
          "order": tuple,
          "seasonal_order": tuple,
          "metrics": dict,
          "train_window": (str, str),
          "test_window": (str, str),
          "fitted_at": str,
        }
    """
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    path = Path(path)
    with open(path, "rb") as f:
        state = pickle.load(f)

    if state.get("format_version") != "compact_v1":
        # Backward-compat: assume it's the old direct-pickle format
        # (just return as-is).
        return state

    n = len(state["endog"])
    idx = pd.date_range(state["train_index_start"], periods=n, freq=state["freq"])
    endog_series = pd.Series(state["endog"], index=idx)

    model = SARIMAX(
        endog_series,
        order=state["order"],
        seasonal_order=state["seasonal_order"],
        trend=state["trend"],
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fit = model.smooth(state["params"])

    return {
        "model": fit,
        "order": state["order"],
        "seasonal_order": state["seasonal_order"],
        "metrics": state["metrics"],
        "train_window": state["train_window"],
        "test_window": state["test_window"],
        "fitted_at": state["fitted_at"],
    }
