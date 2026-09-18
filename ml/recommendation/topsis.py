"""Pure-numpy TOPSIS implementation.

Reference: Hwang & Yoon (1981).

Steps:
    1. Decision matrix X (n_candidates × m_criteria)
    2. Vector normalization R[i,j] = X[i,j] / sqrt(sum_k X[k,j]^2)
    3. Weighted matrix V[i,j] = w[j] * R[i,j]
    4. Ideal A+ and anti-ideal A- per direction (max/min)
    5. Distances S+, S- (Euclidean)
    6. Closeness coefficient C[i] = S-/(S+ + S-)
    7. Sort by C descending
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .criteria import CriterionSpec


@dataclass
class TopsisOutput:
    closeness: np.ndarray         # shape (n,) — C[i] in [0, 1]
    weighted_matrix: np.ndarray   # shape (n, m) — V
    ideal: np.ndarray             # shape (m,) — A+
    anti_ideal: np.ndarray        # shape (m,) — A-
    s_plus: np.ndarray            # shape (n,) — distance to ideal
    s_minus: np.ndarray           # shape (n,) — distance to anti-ideal
    rank: np.ndarray              # shape (n,) — 0-based rank by closeness desc


def topsis_rank(
    X: np.ndarray,
    weights: np.ndarray,
    directions: list[str],
) -> TopsisOutput:
    """Run full TOPSIS pipeline.

    Args:
        X: decision matrix shape (n, m), float
        weights: weights shape (m,), should sum to 1
        directions: list of 'maximize' or 'minimize' per column

    Returns:
        TopsisOutput
    """
    X = np.asarray(X, dtype=float)
    n, m = X.shape
    weights = np.asarray(weights, dtype=float)
    if len(weights) != m:
        raise ValueError(f"weights length {len(weights)} != n_criteria {m}")
    if len(directions) != m:
        raise ValueError(f"directions length {len(directions)} != n_criteria {m}")

    if n == 0:
        return TopsisOutput(
            closeness=np.array([]),
            weighted_matrix=np.zeros((0, m)),
            ideal=np.zeros(m),
            anti_ideal=np.zeros(m),
            s_plus=np.array([]),
            s_minus=np.array([]),
            rank=np.array([], dtype=int),
        )

    norms = np.sqrt((X ** 2).sum(axis=0))
    norms = np.where(norms == 0, 1.0, norms)
    R = X / norms

    V = R * weights[np.newaxis, :]

    A_plus = np.zeros(m)
    A_minus = np.zeros(m)
    for j, direction in enumerate(directions):
        col = V[:, j]
        if direction == "maximize":
            A_plus[j] = col.max()
            A_minus[j] = col.min()
        elif direction == "minimize":
            A_plus[j] = col.min()
            A_minus[j] = col.max()
        else:
            raise ValueError(f"unknown direction {direction!r} at index {j}")

    s_plus = np.sqrt(((V - A_plus[np.newaxis, :]) ** 2).sum(axis=1))
    s_minus = np.sqrt(((V - A_minus[np.newaxis, :]) ** 2).sum(axis=1))

    denom = s_plus + s_minus
    C = np.where(denom == 0, 0.5, s_minus / np.where(denom == 0, 1.0, denom))

    rank_order = np.argsort(-C)
    rank = np.empty(n, dtype=int)
    rank[rank_order] = np.arange(n)

    return TopsisOutput(
        closeness=C,
        weighted_matrix=V,
        ideal=A_plus,
        anti_ideal=A_minus,
        s_plus=s_plus,
        s_minus=s_minus,
        rank=rank,
    )


def matrix_from_dataframe(
    df,
    criteria: list[CriterionSpec],
) -> tuple[np.ndarray, list[str]]:
    """Extract X matrix and directions list from a DataFrame using CriterionSpec list."""
    cols = [c.name for c in criteria]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"DataFrame missing columns: {missing}")
    X = df[cols].astype(float).values
    directions = [c.direction for c in criteria]
    return X, directions
