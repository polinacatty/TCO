from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CompactSarima:

    model: Any  # SARIMAXResults (без статической зависимости в типах)
    order: tuple[int, int, int]
    seasonal_order: tuple[int, int, int, int]
    metrics: dict[str, float]
    train_window: tuple[str, str]
    test_window: tuple[str, str]
    fitted_at: str


def load_compact(path: Path) -> CompactSarima:

    from statsmodels.tsa.statespace.sarimax import SARIMAX

    path = Path(path)
    with path.open("rb") as f:
        state: dict[str, Any] = pickle.load(f)

    if state.get("format_version") != "compact_v1":
        raise ValueError(
            f"unsupported SARIMA artifact format: {state.get('format_version')!r}; "
            "expected 'compact_v1'"
        )

    endog = np.asarray(state["endog"], dtype=float)
    idx = pd.date_range(state["train_index_start"], periods=len(endog), freq=state["freq"])
    endog_series = pd.Series(endog, index=idx)

    model = SARIMAX(
        endog_series,
        order=state["order"],
        seasonal_order=state["seasonal_order"],
        trend=state["trend"],
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fit = model.smooth(state["params"])

    return CompactSarima(
        model=fit,
        order=tuple(state["order"]),
        seasonal_order=tuple(state["seasonal_order"]),
        metrics=state["metrics"],
        train_window=tuple(state["train_window"]),
        test_window=tuple(state["test_window"]),
        fitted_at=state["fitted_at"],
    )


__all__ = ["CompactSarima", "load_compact"]
