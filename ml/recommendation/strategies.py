"""Ranking strategies — `RankingStrategy` ABC + `TopsisStrategy`, `WeightedSumStrategy`.

Pattern: Strategy (GoF). Allows backend to swap algorithms via DI/config without
touching `RecommendationService`. Future: `LearningToRankStrategy` (LambdaMART).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from .criteria import CriterionSpec, DEFAULT_CRITERIA
from .topsis import topsis_rank, matrix_from_dataframe


class RankingStrategy(ABC):
    """Abstract ranking strategy.

    Implementations must add a 'rank_score' column (higher = better) and sort
    the DataFrame descending by it. They should not mutate the input.
    """

    name: str = "abstract"

    @abstractmethod
    def rank(
        self,
        candidates: pd.DataFrame,
        weights: dict[str, float],
        criteria: list[CriterionSpec] = None,  # type: ignore[assignment]
    ) -> pd.DataFrame: ...


class TopsisStrategy(RankingStrategy):
    """TOPSIS ranking strategy."""

    name = "topsis"

    def rank(
        self,
        candidates: pd.DataFrame,
        weights: dict[str, float],
        criteria: list[CriterionSpec] = None,  # type: ignore[assignment]
    ) -> pd.DataFrame:
        criteria = criteria or DEFAULT_CRITERIA
        if len(candidates) == 0:
            return candidates.assign(rank_score=[]).copy()

        X, directions = matrix_from_dataframe(candidates, criteria)
        weight_vec = np.array([weights[c.name] for c in criteria], dtype=float)

        out = topsis_rank(X, weight_vec, directions)

        result = candidates.copy()
        result["rank_score"] = out.closeness
        result["_topsis_s_plus"] = out.s_plus
        result["_topsis_s_minus"] = out.s_minus
        for j, c in enumerate(criteria):
            result[f"_topsis_v_{c.name}"] = out.weighted_matrix[:, j]
            result[f"_topsis_aplus_{c.name}"] = out.ideal[j]
            result[f"_topsis_aminus_{c.name}"] = out.anti_ideal[j]

        return result.sort_values("rank_score", ascending=False).reset_index(drop=True)


class WeightedSumStrategy(RankingStrategy):
    """Weighted Sum Method (baseline).

    Linear normalization (column / max for maximize, min / column for minimize),
    then weighted sum.
    """

    name = "wsm"

    def rank(
        self,
        candidates: pd.DataFrame,
        weights: dict[str, float],
        criteria: list[CriterionSpec] = None,  # type: ignore[assignment]
    ) -> pd.DataFrame:
        criteria = criteria or DEFAULT_CRITERIA
        if len(candidates) == 0:
            return candidates.assign(rank_score=[]).copy()

        result = candidates.copy()
        score = np.zeros(len(candidates))
        for c in criteria:
            x = result[c.name].astype(float).values
            if c.direction == "maximize":
                m = np.nanmax(x) if np.nanmax(x) != 0 else 1.0
                norm = x / m
            else:  # minimize
                m = np.nanmin(x[x > 0]) if (x > 0).any() else 1.0
                norm = m / np.where(x == 0, 1.0, x)
            score += weights[c.name] * norm

        result["rank_score"] = score
        return result.sort_values("rank_score", ascending=False).reset_index(drop=True)
