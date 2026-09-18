"""Pareto-фронт для UI «карта компромиссов» (этап 4.3).

API:

    pareto_front(df, criteria)              — индексы Парето-оптимальных кандидатов (ранг 1)
    pareto_front_2d(df, x_col, x_dir, y_col, y_dir)  — для 2D-плоскости (TCO vs price)
    non_dominated_ranks(df, criteria, max_layers=5)  — multi-layer non-dominated sorting
    compute_pareto_layers(df, criteria, max_layers=5)  — добавляет колонку 'pareto_layer'

`criteria` — список `CriterionSpec` (см. `ml/recommendation/criteria.py`).
Кандидат A **доминирует** B, если по каждому критерию A не хуже B и хотя бы по
одному строго лучше. Парето-фронт — множество недоминируемых кандидатов.

Сложность: O(n² · m) для простой реализации (m — число критериев). Для каталога
875 машин и 6 критериев это ~ 5 млн сравнений = ~ 100 мс на одном Python ядре.
"""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd

from .criteria import CriterionSpec, DEFAULT_CRITERIA


def _criteria_to_arrays(
    df: pd.DataFrame, criteria: Iterable[CriterionSpec],
) -> tuple[np.ndarray, np.ndarray]:
    """Return (X, sign) where:
        X[i, j]  = value of criterion j for candidate i;
        sign[j] = +1 for maximize (we'll compare bigger = better),
                  -1 for minimize (we'll flip sign so bigger = better).
    """
    cols = [c.name for c in criteria]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"DataFrame missing criteria columns: {missing}")
    X = df[cols].astype(float).values
    sign = np.array([1.0 if c.direction == "maximize" else -1.0 for c in criteria], dtype=float)
    Xn = X * sign[np.newaxis, :]  # bigger = better in all dims
    return Xn, sign


def _dominated_mask(Xn: np.ndarray) -> np.ndarray:
    """Return boolean mask of *dominated* rows (True = dominated by some other)."""
    n = Xn.shape[0]
    if n == 0:
        return np.zeros(0, dtype=bool)

    dominated = np.zeros(n, dtype=bool)
    for i in range(n):
        if dominated[i]:
            continue
        diff = Xn - Xn[i]
        not_worse = (diff >= 0).all(axis=1)
        strictly_better = (diff > 0).any(axis=1)
        is_dominator = not_worse & strictly_better
        is_dominator[i] = False
        if is_dominator.any():
            dominated[i] = True
    return dominated


def pareto_front(
    df: pd.DataFrame, criteria: Optional[list[CriterionSpec]] = None,
) -> np.ndarray:
    """Return positional indices (0-based) of Pareto-optimal rows.

    Args:
        df: candidates DataFrame (must contain criteria columns).
        criteria: list of CriterionSpec; default = DEFAULT_CRITERIA (6).
    """
    criteria = criteria or DEFAULT_CRITERIA
    if len(df) == 0:
        return np.array([], dtype=int)
    Xn, _ = _criteria_to_arrays(df, criteria)
    dominated = _dominated_mask(Xn)
    return np.where(~dominated)[0]


def pareto_front_2d(
    df: pd.DataFrame,
    x_col: str, x_direction: str,
    y_col: str, y_direction: str,
) -> np.ndarray:
    """2D Pareto-фронт по `(x_col, y_col)` — для UI карта-компромиссов.

    Returns positional indices.
    """
    criteria_2d = [
        CriterionSpec(x_col, x_direction, x_col, ""),
        CriterionSpec(y_col, y_direction, y_col, ""),
    ]
    return pareto_front(df, criteria_2d)


def non_dominated_ranks(
    df: pd.DataFrame,
    criteria: Optional[list[CriterionSpec]] = None,
    max_layers: int = 5,
) -> np.ndarray:
    """NSGA-style non-dominated sorting layers.

    Returns int array of length len(df) with values:
        1 = первый Парето-фронт (лучший);
        2 = второй фронт после удаления первого;
        ...
        0 = глубже max_layers (можно скрывать в UI).
    """
    criteria = criteria or DEFAULT_CRITERIA
    n = len(df)
    if n == 0:
        return np.array([], dtype=int)
    Xn, _ = _criteria_to_arrays(df, criteria)
    layers = np.zeros(n, dtype=int)
    remaining = np.arange(n)
    cur = 1
    while len(remaining) > 0 and cur <= max_layers:
        sub = Xn[remaining]
        dominated = _dominated_mask(sub)
        front_local = ~dominated
        layers[remaining[front_local]] = cur
        remaining = remaining[~front_local]
        cur += 1
    return layers


def compute_pareto_layers(
    df: pd.DataFrame,
    criteria: Optional[list[CriterionSpec]] = None,
    max_layers: int = 3,
) -> pd.DataFrame:
    """Return copy of df with extra column 'pareto_layer' (int in {0, 1, 2, ...})."""
    layers = non_dominated_ranks(df, criteria, max_layers=max_layers)
    out = df.copy()
    out["pareto_layer"] = layers
    return out
